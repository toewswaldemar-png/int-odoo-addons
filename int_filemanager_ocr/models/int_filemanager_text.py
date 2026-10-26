import importlib.metadata
import importlib.util
import json
import logging
import os
import subprocess
import sys
import threading
import time

import psycopg2.errors

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import SQL

from odoo.addons.int_filemanager.models.int_filemanager_document import PDF, PREVIEW_EXTENSIONS

from ..tools import ocr_plan

TEXT_CRON_XMLID = "int_filemanager_ocr.int_filemanager_text_cron"

_logger = logging.getLogger(__name__)

# Whoever changes how the text is read raises this: the texts are read again.
ENGINE_VERSION = 2

OFFICE_TYPES = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
)
# Pictures that the text recognition reads (what ``ocrmypdf`` takes as an image). A picture has no
# text to read: its row exists only in a folder that has the recognition of images switched on,
# and the recognition is its reading. No PDF is kept of it, the viewer shows the picture.
IMAGE_TYPES = (
    "image/bmp",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
)
# Every text type is read as text, too (``text/%``). Other types get no row: a row for an MP3
# would stay "a document without a row" for ever.
TEXT_PREFIX = "text/%"
READER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "extract_text.py")
# What a run of the recognition says: it did a step, it has nothing to do, it has no time left.
OCR_PROGRESS, OCR_IDLE, OCR_NO_TIME = "progress", "idle", "no_time"
# A page with a picture and less text than this (letters, without white space) counts as a scan;
# only the start of the page is looked at.
SCAN_PAGE_CHARS = 20
SCAN_PAGE_LOOK = 2000

# Rows made and requeued per step; rows deleted per run of the cleaner.
BATCH = 500
GC_BATCH = 1000
# The reader gets no less time than this to count as having had a try.
MIN_ATTEMPT_SECONDS = 20
# Time left below which no new file is started.
MIN_START_SECONDS = 2
# The longest message kept on a row.
MESSAGE_LENGTH = 1000

SETTINGS = {
    # name: (default, least); the numbers of the previews and the time reserve are in the core
    "memory_mib": (1024, 64),  # what the reader may grow by
    "text_block_kib": (64, 1),  # block of text of a file without pages
    "text_cut_bytes": (650000, 1000),  # the most bytes of a page of a PDF
    "work_mem_mib": (128, 4),  # for the full text search
    "max_attempts": (3, 1),  # tries of a file that crashes or is too slow
    "ocr_jobs": (1, 1),  # cores of one text recognition (-j)
    "ocr_nice": (19, 0),  # priority of the text recognition (19: the lowest)
}


def _is_scan_text(text):
    """Whether this is (almost) no text: the start of the page, without white space, is short."""
    return len("".join(text[:SCAN_PAGE_LOOK].split())) < SCAN_PAGE_CHARS


class IntFilemanagerText(models.Model):
    """The text of a file: one row per blob (checksum), shared by all documents with it.

    Made and filled by the scheduled action (``_cron_ocr``); the pages are in
    ``int.filemanager.text.page``. Not readable by the users, see the search of the document.
    """

    _name = "int.filemanager.text"
    _inherit = ["int.filemanager.cron"]
    _description = "Filemanager text of a file"
    _order = "id"

    checksum = fields.Char(required=True, readonly=True)
    mimetype = fields.Char(readonly=True)
    state = fields.Selection(
        [
            ("pending", "Waiting"),
            ("running", "Running"),
            ("done", "Done"),
            ("empty", "No text"),
            ("skipped", "Skipped"),
            ("failed", "Failed"),
        ],
        default="pending",
        required=True,
    )
    message = fields.Char(readonly=True)
    page_count = fields.Integer(readonly=True)
    # Where the reading goes on if it was stopped.
    next_page = fields.Integer(default=1, readonly=True)
    attempts = fields.Integer(readonly=True)
    engine_version = fields.Integer(readonly=True)
    # The memory budget (MiB) a file was too big for: with a higher budget it is read again.
    memory_limit_mib = fields.Integer(readonly=True)
    # Pages that had no text after reading: a scan. The text recognition is needed if there are some.
    # -1: not counted yet (rows made before the recognition existed).
    scan_pages = fields.Integer(string="Pages without text", default=-1, readonly=True)
    # For the list of the administrator: a file that has this text, and how many have it.
    document_id = fields.Many2one(
        "int.filemanager.document", string="File", compute="_compute_documents"
    )
    document_count = fields.Integer(string="Documents", compute="_compute_documents")

    _checksum_unique = models.UniqueIndex("(checksum)", "A file has one text.")
    _checksum_is_sha256 = models.Constraint(
        "CHECK (checksum ~ '^[0-9a-f]{64}$')",
        "The checksum must be a SHA-256 in lowercase hexadecimal.",
    )
    _work_index = models.Index("(id) WHERE state IN ('pending', 'running')")
    _uncounted_index = models.Index("(id) WHERE scan_pages < 0")

    @api.depends("checksum")
    def _compute_documents(self):
        documents = self.env["int.filemanager.document"].sudo().with_context(active_test=False)
        found = {
            checksum: (first, count)
            for checksum, first, count in documents._read_group(
                [("checksum", "in", self.mapped("checksum"))],
                ["checksum"],
                ["id:min", "__count"],
            )
        }
        for row in self:
            first, count = found.get(row.checksum, (False, 0))
            row.document_id = first
            row.document_count = count

    def write(self, vals):
        # A recognized PDF that the row lets go of may be free: the cleaner of the blobs looks.
        old_checksums = set(self.mapped("ocr_checksum")) if "ocr_checksum" in vals else set()
        result = super().write(vals)
        self._mark_ocr_blobs(old_checksums - {vals.get("ocr_checksum")})
        return result

    def unlink(self):
        # First delete the rows, then mark the blobs, like the documents do.
        checksums = set(self.mapped("ocr_checksum"))
        result = super().unlink()
        self._mark_ocr_blobs(checksums)
        return result

    @api.model
    def _mark_ocr_blobs(self, checksums):
        Document = self.env["int.filemanager.document"]
        for checksum in filter(None, checksums):
            Document._mark_blob_for_gc(checksum)

    @api.model
    def _used_ocr_checksums(self, checksums):
        """Of these checksums those that a row keeps as its recognized PDF.

        The cleaner of the blobs asks (see ``int.filemanager.document._gc_blobs``).
        """
        return {
            checksum
            for [checksum] in self.sudo()._read_group([("ocr_checksum", "in", list(checksums))], ["ocr_checksum"])
        }

    # ---- For the administrator ----------------------------------------------------------

    def action_read_again(self):
        """Throw the text away and read the file again (failed, skipped, empty or done rows).

        Public (the button calls it), so it checks the right itself: the administrators of the
        filemanager have no right to write the rows, the reset runs as superuser.
        """
        if not self.env.user.has_group("int_filemanager.int_filemanager_group_admin"):
            raise AccessError(self.env._("Only a Filemanager administrator can do that."))
        self.sudo().filtered(lambda row: row.state not in ("pending", "running"))._reset()
        # Wake the scheduled action; if it is running already, it finds the rows by itself.
        cron = self.env.ref(TEXT_CRON_XMLID, raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()

    @api.model
    def _status(self):
        """The numbers for the status in the settings: rows per state, and files without a row.

        :return: ``{"pending": n, ..., "missing": n}``
        """
        counts = dict.fromkeys(("pending", "running", "done", "empty", "skipped", "failed"), 0)
        counts.update(self.sudo()._read_group([], ["state"], ["__count"]))
        counts["missing"] = self._count_missing()
        return counts

    @api.model
    def _ocr_status(self):
        """The numbers for the status of the text recognition in the settings.

        :return: ``{"counts": {state: n}, "pages_left", "seconds_left", "pdf_size", "ready",
            "reason", "detail", "tools", "lc_ctype"}``; ``reason`` is why it cannot run (the
            codes of ``_ocr_ready``), ``detail`` what the fault said (a stopped recognition)
        """
        Text = self.sudo()
        Text.flush_model()
        counts = dict.fromkeys(("wait", "running", "done", "skipped", "failed"), 0)
        counts.update(Text._read_group([("ocr_state", "!=", False)], ["ocr_state"], ["__count"]))
        # A picture whose pages are not counted yet counts as one page; a PDF has its scans left.
        self.env["int.filemanager.text.page"].flush_model()
        [[pages_left, seconds_left]] = self.env.execute_query(
            SQL(
                """
                SELECT coalesce(sum(left_pages), 0),
                       coalesce(sum(left_pages * CASE WHEN ocr_seconds_per_page > 0
                                                      THEN ocr_seconds_per_page ELSE %s END), 0)
                  FROM (SELECT item.ocr_seconds_per_page,
                               CASE WHEN coalesce(item.page_count, 0) <= 0 THEN 1
                                    WHEN item.mimetype IN %s
                                    THEN greatest(item.page_count - item.ocr_next_page + 1, 0)
                                    ELSE (SELECT count(*) FROM int_filemanager_text_page page
                                           WHERE page.text_id = item.id AND page.scan
                                             AND page.page >= item.ocr_next_page)
                               END AS left_pages
                          FROM int_filemanager_text item
                         WHERE item.ocr_state IN ('wait', 'running')) waiting
                """,
                ocr_plan.DEFAULT_SECONDS_PER_PAGE,
                IMAGE_TYPES,
            )
        )
        [[pdf_size]] = Text._read_group([], [], ["ocr_size:sum"])
        [[lc_ctype]] = self.env.execute_query(
            SQL("SELECT datctype FROM pg_database WHERE datname = current_database()")
        )
        ready, reason = self._ocr_ready()
        blocked = self._ocr_blocked()
        return {
            "counts": counts,
            "pages_left": int(pages_left),
            "seconds_left": float(seconds_left),
            "pdf_size": pdf_size or 0,
            "ready": ready,
            "reason": reason,
            "detail": blocked[1] if blocked else "",
            "tools": self._ocr_tools(),
            "lc_ctype": lc_ctype,
        }

    @api.model
    def _tools(self):
        """The version of the PDF reader, or ``False`` if it is not installed."""
        try:
            return importlib.metadata.version("pdfminer.six")
        except importlib.metadata.PackageNotFoundError:
            return False

    # ---- Settings and time --------------------------------------------------------------

    @api.model
    def _setting_defaults(self):
        return {**super()._setting_defaults(), **SETTINGS}

    @api.model
    def _use_search_memory(self):
        """More memory for the full text search, in this transaction only.

        A word that is on most pages makes the list of hits so long that PostgreSQL, with the
        small standard memory, works it out again and again (minutes instead of seconds). No
        parallel workers either (each would take that much again).
        """
        self.env.cr.execute(
            SQL(
                "SELECT set_config('work_mem', %s, true),"
                " set_config('max_parallel_workers_per_gather', '0', true)",
                f"{self._setting('work_mem_mib')}MB",
            )
        )

    # ---- The scheduled action -----------------------------------------------------------

    @api.model
    def _cron_ocr(self):
        """Make the rows for new files, read their text, recognize the text of scans, in the time.

        One step is one file (or one section of the pages of a scan), committed
        (``_commit_progress``). The reading and the new rows come first, the recognition
        after them. When the time is up with work left it reports the rows that wait, so Odoo
        calls it again at once and the next run goes on. Called again with the budget used up
        it returns at once.
        """
        assert self.env.context.get("cron_id") == self.env.ref(TEXT_CRON_XMLID).id, (
            "Meant for cron usage only"
        )
        cron = self.env["ir.cron"]
        deadline = self._pass_deadline()
        self._requeue_stale()
        while True:
            if deadline - time.monotonic() < MIN_START_SECONDS:
                cron._commit_progress(0, remaining=self._work_left() or 1)
                return
            row = self.search([("state", "=", "pending")], order="id", limit=1)
            if row:
                if not row.try_lock_for_update():
                    # Somebody holds it (the cleaner); the next run tries again.
                    cron._commit_progress(0, remaining=1)
                    return
                row._read_text(deadline)
                cron._commit_progress(1)
                continue
            if self._requeue(BATCH) or self._create_rows(BATCH) or self._ocr_queue(BATCH):
                cron._commit_progress(1)
                continue
            step = self._ocr_step(deadline)
            if step == OCR_PROGRESS:
                cron._commit_progress(1)
                continue
            # No time for a section: more is waiting, so Odoo calls the action again at once.
            cron._commit_progress(0, remaining=(self._work_left() or 1) if step == OCR_NO_TIME else 0)
            return

    @api.model
    def _work_left(self):
        """The rows that wait for the reading, and for the recognition if it can run."""
        waiting = self.search_count([("state", "=", "pending")])
        # Cheap on purpose: this is asked when the time is up, so no program is started to look
        # at the tools (``_ocr_ready`` would).
        if self._ocr_options()["enabled"] and not self._ocr_blocked():
            waiting += self.search_count([("ocr_state", "=", "wait")])
        return waiting

    @api.model
    def _supported_types(self):
        """The types that get a row: PDF if the reader can read it, office files, text."""
        types = list(OFFICE_TYPES)
        if importlib.util.find_spec("pdfminer"):
            types.append(PDF)
        return tuple(types)

    @api.model
    def _preview_read_types(self):
        """The types that the reader cannot open (Word, Excel, PowerPoint of before 2007, RTF).

        Their text is read from the PDF that LibreOffice made for the preview, once it is there.
        """
        if not importlib.util.find_spec("pdfminer"):
            return ()
        return tuple(mimetype for mimetype in PREVIEW_EXTENSIONS if mimetype not in OFFICE_TYPES)

    @api.model
    def _missing_where(self):
        """Documents that are not archived, of a type with text, and have no row yet.

        The files of the old formats count when their preview is made.

        Pictures count only if the recognition is on and the document lies in a folder where
        the recognition of images is on (``ocr_images_active``): a row for each photo would
        have them all recognized.
        """
        preview_types = self._preview_read_types()
        return SQL(
            """
            document.active
            AND (document.mimetype IN %(types)s OR document.mimetype LIKE %(text)s
                 OR %(preview)s
                 OR (%(images_on)s AND document.mimetype IN %(images)s AND EXISTS (
                         SELECT 1 FROM int_filemanager_folder folder
                          WHERE folder.id = document.folder_id AND folder.ocr_images_active)))
            AND NOT EXISTS (
                SELECT 1 FROM int_filemanager_text text WHERE text.checksum = document.checksum)
            """,
            types=self._supported_types(),
            text=TEXT_PREFIX,
            preview=(
                SQL("(document.mimetype IN %s AND document.preview_checksum IS NOT NULL)", preview_types)
                if preview_types
                else SQL("FALSE")
            ),
            images_on=self._ocr_options()["enabled"],
            images=IMAGE_TYPES,
        )

    @api.model
    def _flush_for_missing(self):
        # Raw SQL: what is not written yet (a document just archived) must be, first.
        self.env["int.filemanager.document"].flush_model(
            ["checksum", "mimetype", "active", "folder_id", "preview_checksum"]
        )
        self.env["int.filemanager.folder"].flush_model(["ocr_images_active"])
        self.flush_model(["checksum"])

    @api.model
    def _count_missing(self):
        """How many different files have no row yet."""
        self._flush_for_missing()
        [[count]] = self.env.execute_query(
            SQL(
                "SELECT count(DISTINCT document.checksum) FROM int_filemanager_document document"
                " WHERE %s",
                self._missing_where(),
            )
        )
        return count

    @api.model
    def _create_rows(self, limit):
        """Make a row for the checksums of files of a supported type that have none.

        Archived documents get none (they come back as soon as one is restored).
        :return: how many were made
        """
        self._flush_for_missing()
        found = self.env.execute_query(
            SQL(
                """
                SELECT DISTINCT ON (document.checksum) document.checksum, document.mimetype
                  FROM int_filemanager_document document
                 WHERE %s
                 ORDER BY document.checksum
                 LIMIT %s
                """,
                self._missing_where(),
                limit,
            )
        )
        self.create([self._new_row_values(checksum, mimetype) for checksum, mimetype in found])
        return len(found)

    @api.model
    def _new_row_values(self, checksum, mimetype):
        """The values of a new row. A picture has nothing to read: the recognition is its reading."""
        values = {"checksum": checksum, "mimetype": mimetype}
        if mimetype in IMAGE_TYPES:
            values.update(
                state="empty",
                engine_version=ENGINE_VERSION,
                scan_pages=1,
                ocr_state="wait",
            )
        return values

    @api.model
    def _requeue_stale(self):
        """A row that is ``running`` at the start of a run was cut off by a crash or a kill.

        Odoo never runs two of the same action at the same time. It counts as a try.
        """
        for row in self.search([("state", "=", "running")]):
            row._after_failure(self.env._("The reader did not come back, the server was stopped."))
        for row in self.search([("ocr_state", "=", "running")]):
            row._ocr_after_failure(
                self.env._("The text recognition did not come back, the server was stopped.")
            )

    @api.model
    def _requeue(self, limit):
        """Read again what an older reader or a lower memory budget left out.

        :return: how many rows were put back
        """
        memory = self._setting("memory_mib")
        rows = self.search(
            [
                "|",
                "&",
                ("state", "in", ("done", "empty")),
                ("engine_version", "<", ENGINE_VERSION),
                "&",
                ("state", "=", "skipped"),
                ("memory_limit_mib", "<", memory),
            ],
            limit=limit,
        )
        rows._reset()
        return len(rows)

    def _reset(self):
        """Throw the text away and put the row back to the start.

        A picture is read by the recognition: it starts again from there. Its state stays
        ``empty``, so it gets the engine version here, like a new row, or ``_requeue`` would take
        it again at every step.
        """
        self.env["int.filemanager.text.page"].search([("text_id", "in", self.ids)]).unlink()
        pictures = self.filtered(lambda row: row.mimetype in IMAGE_TYPES)
        for row in pictures:
            row._ocr_drop_job()
        pictures.write(
            {
                **self._ocr_restart_values(),
                "state": "empty",
                "engine_version": ENGINE_VERSION,
                "message": False,
                "page_count": 0,
                "next_page": 1,
                "attempts": 0,
                "memory_limit_mib": 0,
                "scan_pages": 1,
                "ocr_state": "wait",
            }
        )
        (self - pictures).write(
            {
                "state": "pending",
                "message": False,
                "page_count": 0,
                "next_page": 1,
                "attempts": 0,
                "memory_limit_mib": 0,
                "scan_pages": -1,
            }
        )

    # ---- Reading one file ---------------------------------------------------------------

    def _read_text(self, deadline):
        """Read the text of this file until it is done or the deadline comes.

        The reader is a child process with a time limit. The row is marked ``running`` and
        committed first, so a crash of the server (or a file that kills the reader for good) is
        counted at the next run. The caller commits the result.
        """
        self.ensure_one()
        row_id, mimetype, first_page = self.id, self.mimetype, self.next_page
        if mimetype in self._preview_read_types():
            mimetype = PDF
        path = self._text_source()
        if not os.path.isfile(path):
            self.write({"state": "failed", "message": self.env._("The file is missing.")})
            return
        self.write({"state": "running"})
        self.env["ir.cron"]._commit_progress()
        seconds = deadline - time.monotonic()
        result = self._run_reader(path, mimetype, first_page, seconds)
        # The cleaner may have deleted the row while the reader ran; it is then not needed.
        row = self.browse(row_id).exists().try_lock_for_update()
        if row:
            row._apply_result(result, seconds)

    def _text_source(self):
        """The file the text is read from.

        The last finished section of a recognition that is under way, else the recognized PDF,
        else the original: the text of the scans is only in the first two (reading the original
        again would lose it, and have the scans recognized a second time). A file of an old
        format is read from its preview; ``""`` if that is gone.
        """
        self.ensure_one()
        section = self._ocr_section_path()
        if section:
            return section
        Document = self.env["int.filemanager.document"]
        if self.mimetype in self._preview_read_types():
            return Document._blob_path(preview) if (preview := self._preview_checksum()) else ""
        if self.ocr_checksum and os.path.isfile(Document._blob_path(self.ocr_checksum)):
            return Document._blob_path(self.ocr_checksum)
        return Document._blob_path(self.checksum)

    def _preview_checksum(self):
        """The preview PDF of a file of an old format, from a document that has the file."""
        self.ensure_one()
        document = (
            self.env["int.filemanager.document"]
            .sudo()
            .with_context(active_test=False)
            .search_fetch(
                [("checksum", "=", self.checksum), ("preview_checksum", "!=", False)],
                ["preview_checksum"],
                limit=1,
            )
        )
        return document.preview_checksum

    @api.model
    def _reader_command(self, path, mimetype, first_page, pages=()):
        return [
            sys.executable,
            "-I",
            READER,
            path,
            mimetype,
            str(first_page),
            str(self._setting("text_block_kib") * 1024),
            str(self._setting("text_cut_bytes")),
            str(self._setting("memory_mib")),
            ",".join(str(number) for number in pages),
        ]

    @api.model
    def _run_reader(self, path, mimetype, first_page, seconds, pages=()):
        """Run the reader for at most ``seconds`` and collect what it says.

        :param pages: the page numbers to read (a PDF); none: from ``first_page`` to the end
        :return: ``{"pages": [(n, text, cut, image)], "count", "done", "error", "message",
            "timeout", "exit"}``; a reader that was stopped at the limit has given the pages it
            finished; ``image`` is whether the page has a picture (``None``: not a PDF page)
        """
        command = self._reader_command(path, mimetype, first_page, pages)
        process = subprocess.Popen(  # noqa: S603 (own script, own interpreter, no shell)
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        lines = []
        reader = threading.Thread(target=lambda: lines.extend(process.stdout), daemon=True)
        reader.start()
        timeout = False
        try:
            process.wait(timeout=max(seconds, 0))
        except subprocess.TimeoutExpired:
            timeout = True
            process.kill()
            process.wait()
        reader.join(timeout=10)
        process.stdout.close()
        result = {
            "pages": [],
            "count": None,
            "done": False,
            "error": None,
            "message": None,
            "timeout": timeout,
            "exit": process.returncode,
        }
        for line in lines:
            try:
                data = json.loads(line)
            except ValueError:
                continue  # the last line of a reader that was killed
            if "page" in data:
                result["pages"].append((data["page"], data["text"], bool(data.get("cut")), data.get("image")))
            elif "pages" in data:
                result["count"] = data["pages"]
            elif data.get("done"):
                result["done"] = True
            elif "error" in data:
                result["error"], result["message"] = data["error"], data.get("message")
        return result

    def _apply_result(self, result, seconds):
        """Save what the reader gave and set the state of the row."""
        self.ensure_one()
        notes = self._store_pages(result["pages"])
        if result["count"] is not None:
            self.page_count = result["count"]
        if result["pages"]:
            self.write({"next_page": result["pages"][-1][0] + 1, "attempts": 0})
        if result["error"] == "memory":
            self.write(
                {
                    "state": "skipped",
                    "memory_limit_mib": self._setting("memory_mib"),
                    "message": self.env._("The file needs more memory than the budget allows."),
                }
            )
        elif result["error"]:
            self.write({"state": "failed", "message": (result["message"] or "")[:MESSAGE_LENGTH]})
        elif result["done"]:
            self.write(
                {
                    "state": "done" if self._has_text() else "empty",
                    "scan_pages": self._count_scan_pages(),
                    "engine_version": ENGINE_VERSION,
                    "message": " ".join(notes)[:MESSAGE_LENGTH] or False,
                }
            )
        elif result["timeout"]:
            # A short time left is no fair try for a slow page.
            self._after_failure(
                self.env._("A page takes longer than the time of one run."),
                counts=not result["pages"] and seconds >= MIN_ATTEMPT_SECONDS,
            )
        else:
            self._after_failure(
                self.env._("The reader stopped (exit code %(code)s).", code=result["exit"]),
                counts=not result["pages"],
            )

    def _after_failure(self, reason, counts=True):
        """The reader did not finish: try again, or give up after the tries are used up."""
        self.ensure_one()
        attempts = self.attempts + (1 if counts else 0)
        if attempts >= self._setting("max_attempts"):
            self.write({"state": "failed", "attempts": attempts, "message": reason})
        else:
            self.write({"state": "pending", "attempts": attempts})

    def _has_text(self):
        self.ensure_one()
        self.env["int.filemanager.text.page"].flush_model()
        rows = self.env.execute_query(
            SQL(
                "SELECT 1 FROM int_filemanager_text_page"
                " WHERE text_id = %s AND content ~ '[^[:space:]]' LIMIT 1",
                self.id,
            )
        )
        return bool(rows)

    def _store_pages(self, pages):
        """Write the pages. One that PostgreSQL cannot index is cut until it fits.

        An entry for the search is limited to 1 MB; it is not the size of the text that decides
        but the number of different words, so the limit in bytes cannot rule it out. The
        pages are written together, and one by one only if that failed.
        :param pages: ``[(number, text, was_cut, has_picture)]``
        :return: notes for the row, for pages that were cut
        """
        Page = self.env["int.filemanager.text.page"]
        notes = [
            self.env._("Page %(page)s was cut at the size limit.", page=number)
            for number, _text, was_cut, _picture in pages
            if was_cut
        ]
        values = [
            {
                "text_id": self.id,
                "page": number,
                "content": text,
                "scan": bool(picture) and _is_scan_text(text),
            }
            for number, text, _cut, picture in pages
        ]
        try:
            with self.env.cr.savepoint():
                Page.create(values)
            return notes
        except psycopg2.errors.ProgramLimitExceeded:
            pass
        for value in values:
            text = value["content"]
            while True:
                try:
                    with self.env.cr.savepoint():
                        Page.create({**value, "content": text})
                    break
                except psycopg2.errors.ProgramLimitExceeded:
                    text = text[: len(text) // 2]
            if text != value["content"]:
                notes.append(
                    self.env._(
                        "Page %(page)s was cut: too many different words.", page=value["page"]
                    )
                )
        return notes

    # ---- Scans and the text recognition -------------------------------------------------

    @api.model
    def _scan_page_counts(self, ids):
        """``{row id: number of scans (pages with a picture and (almost) no text)}``; rows without one are left out."""
        self.env["int.filemanager.text.page"].flush_model()
        return dict(
            self.env.execute_query(
                SQL(
                    """
                    SELECT text_id, count(*) FROM int_filemanager_text_page
                     WHERE text_id IN %s AND scan
                     GROUP BY text_id
                    """,
                    tuple(ids),
                )
            )
        )

    def _count_scan_pages(self):
        """The pages of this PDF that are scans. Other files have none."""
        self.ensure_one()
        if self.mimetype != PDF:
            return 0
        return self._scan_page_counts(self.ids).get(self.id, 0)

    @api.model
    def _ocr_queue(self, limit):
        """Count the scans of rows read before the recognition existed, and queue rows that need it.

        :return: how many rows were changed
        """
        counted = self.search([("state", "in", ("done", "empty")), ("scan_pages", "<", 0)], limit=limit)
        if counted:
            counts = self._scan_page_counts(counted.filtered(lambda row: row.mimetype == PDF).ids or [0])
            by_count = {}
            for row in counted:
                by_count.setdefault(counts.get(row.id, 0), []).append(row.id)
            for count, ids in by_count.items():
                self.browse(ids).write({"scan_pages": count})
        queued = self.browse()
        if self._ocr_options()["enabled"]:
            queued = self.search(
                [
                    ("ocr_state", "=", False),
                    ("scan_pages", ">", 0),
                    ("state", "in", ("done", "empty")),
                ],
                limit=limit,
            )
            queued.write({"ocr_state": "wait"})
        return len(counted) + len(queued)

    # ---- Cleaning up --------------------------------------------------------------------

    @api.autovacuum
    def _gc_texts(self):
        """Delete the texts of files that no document has any more (archived ones count).

        The pages go with their text (``ondelete="cascade"``). In batches: Odoo calls it again
        for as long as it says that rows are left.
        """
        self.env["int.filemanager.document"].flush_model(["checksum"])
        self.flush_model(["checksum"])
        found = [
            row_id
            for [row_id] in self.env.execute_query(
                SQL(
                    """
                    SELECT text.id FROM int_filemanager_text text
                     WHERE NOT EXISTS (
                           SELECT 1 FROM int_filemanager_document document
                            WHERE document.checksum = text.checksum)
                     ORDER BY text.id LIMIT %s
                    """,
                    GC_BATCH + 1,
                )
            )
        ]
        self.browse(found[:GC_BATCH]).unlink()
        return len(found[:GC_BATCH]), int(len(found) > GC_BATCH)
