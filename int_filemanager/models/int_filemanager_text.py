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
from odoo.addons.base.models.ir_cron import MIN_TIME_PER_JOB
from odoo.service.server import SLEEP_INTERVAL
from odoo.tools import SQL, config

_logger = logging.getLogger(__name__)

CRON_XMLID = "int_filemanager.int_filemanager_text_cron"
# Whoever changes how the text is read raises this: the texts are read again.
ENGINE_VERSION = 1

PDF = "application/pdf"
OFFICE_TYPES = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
)
# Every text type is read as text, too (``text/%``). Other types get no row: a row for an MP3
# would stay "a document without a row" for ever.
TEXT_PREFIX = "text/%"
READER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "extract_text.py")

# Rows made and requeued per step; rows deleted per run of the cleaner.
BATCH = 500
GC_BATCH = 1000
# The reader gets no less time than this to count as having had a try.
MIN_ATTEMPT_SECONDS = 20
# Time left below which no new file is started.
MIN_START_SECONDS = 2
# What a run may take if Odoo has no limit for it.
NO_LIMIT_SECONDS = 300
# The longest message kept on a row.
MESSAGE_LENGTH = 1000

SETTINGS = {
    # name: (default, least)
    "time_reserve": (15, 0),  # seconds kept free below the limit of Odoo
    "memory_mib": (1024, 64),  # what the reader may grow by
    "text_block_kib": (64, 1),  # block of text of a file without pages
    "text_cut_bytes": (650000, 1000),  # the most bytes of a page of a PDF
    "work_mem_mib": (128, 4),  # for the full text search
    "max_attempts": (3, 1),  # tries of a file that crashes or is too slow
}


class IntFilemanagerText(models.Model):
    """The text of a file: one row per blob (checksum), shared by all documents with it.

    Made and filled by the scheduled action (``_cron_ocr``); the pages are in
    ``int.filemanager.text.page``. Not readable by the users, see the search of the document.
    """

    _name = "int.filemanager.text"
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
        cron = self.env.ref(CRON_XMLID, raise_if_not_found=False)
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
    def _budget(self):
        """How long one run lasts: ``(mode, limit, seconds, bounded)``; see ``_pass_deadline``."""
        limit, bounded = self._limit_seconds()
        reserve = self._setting("time_reserve")
        prefork = bool(config["workers"])
        sleep = SLEEP_INTERVAL + 10 if prefork and bounded else 0
        return ("prefork" if prefork else "threaded", limit, max(limit - sleep - reserve, 0), bounded)

    @api.model
    def _tools(self):
        """The version of the PDF reader, or ``False`` if it is not installed."""
        try:
            return importlib.metadata.version("pdfminer.six")
        except importlib.metadata.PackageNotFoundError:
            return False

    # ---- Settings and time --------------------------------------------------------------

    @api.model
    def _setting(self, name):
        """A number from the system parameters, ``int_filemanager.<name>`` (else its default)."""
        default, least = SETTINGS[name]
        value = self.env["ir.config_parameter"].sudo().get_param(f"int_filemanager.{name}")
        try:
            return max(int(value), least) if value else default
        except ValueError:
            return default

    @api.model
    def _limit_seconds(self):
        """How long one run of a scheduled action may take at most, from its start.

        Prefork: ``limit_time_real_cron`` is ``-1`` for ``limit_time_real``, ``0`` for no limit.
        Threaded: ``0`` and ``-1`` both mean ``limit_time_real`` (``server.py``).
        :return: ``(seconds, bounded)``; ``bounded`` is false if Odoo has no limit
        """
        real, cron = config["limit_time_real"], config["limit_time_real_cron"]
        if config["workers"]:
            limit = real if cron == -1 else cron
        else:
            limit = cron if cron and cron > 0 else real
        if not limit or limit < 0:
            return NO_LIMIT_SECONDS, False
        return limit, True

    @api.model
    def _pass_deadline(self):
        """The time (``time.monotonic``) at which this run of the action must end.

        The Odoo limit minus a reserve minus what has been used up. The watchdog of a prefork
        worker counts from its last sign of life, before it sleeps 60 to 69 seconds, so that
        time is taken off too. Every call within one run gets the same deadline: the core calls
        the method up to ten times in a row, and a later call must find the budget used up.
        """
        limit, bounded = self._limit_seconds()
        reserve = self._setting("time_reserve")
        now = time.monotonic()
        end_time = self.env.context.get("cron_end_time")
        job_start = end_time - MIN_TIME_PER_JOB if end_time else now
        if config["workers"]:
            sleep = SLEEP_INTERVAL + 10 if bounded else 0
            return job_start + limit - sleep - reserve
        started = getattr(threading.current_thread(), "start_time", None)
        elapsed = time.time() - started if started else now - job_start
        return now + limit - reserve - elapsed

    # ---- The scheduled action -----------------------------------------------------------

    @api.model
    def _cron_ocr(self):
        """Make the rows for new files and read the text of the files that wait, within the time.

        One step is one file, committed (``_commit_progress``). When the time is up with work
        left it reports the rows that wait, so Odoo calls it again at once and the next run
        goes on. Called again with the budget used up it returns at once.
        """
        assert self.env.context.get("cron_id") == self.env.ref(CRON_XMLID).id, (
            "Meant for cron usage only"
        )
        cron = self.env["ir.cron"]
        deadline = self._pass_deadline()
        self._requeue_stale()
        while True:
            if deadline - time.monotonic() < MIN_START_SECONDS:
                cron._commit_progress(0, remaining=self.search_count([("state", "=", "pending")]) or 1)
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
            if self._requeue(BATCH) or self._create_rows(BATCH):
                cron._commit_progress(1)
                continue
            cron._commit_progress(0, remaining=0)
            return

    @api.model
    def _supported_types(self):
        """The types that get a row: PDF if the reader can read it, office files, text."""
        types = list(OFFICE_TYPES)
        if importlib.util.find_spec("pdfminer"):
            types.append(PDF)
        return tuple(types)

    @api.model
    def _missing_where(self):
        """Documents that are not archived, of a type with text, and have no row yet."""
        return SQL(
            """
            document.active
            AND (document.mimetype IN %s OR document.mimetype LIKE %s)
            AND NOT EXISTS (
                SELECT 1 FROM int_filemanager_text text WHERE text.checksum = document.checksum)
            """,
            self._supported_types(),
            TEXT_PREFIX,
        )

    @api.model
    def _flush_for_missing(self):
        # Raw SQL: what is not written yet (a document just archived) must be, first.
        self.env["int.filemanager.document"].flush_model(["checksum", "mimetype", "active"])
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
        self.create([{"checksum": checksum, "mimetype": mimetype} for checksum, mimetype in found])
        return len(found)

    @api.model
    def _requeue_stale(self):
        """A row that is ``running`` at the start of a run was cut off by a crash or a kill.

        Odoo never runs two of the same action at the same time. It counts as a try.
        """
        for row in self.search([("state", "=", "running")]):
            row._after_failure(self.env._("The reader did not come back, the server was stopped."))

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
        """Throw the text away and put the row back to the start."""
        self.env["int.filemanager.text.page"].search([("text_id", "in", self.ids)]).unlink()
        self.write(
            {
                "state": "pending",
                "message": False,
                "page_count": 0,
                "next_page": 1,
                "attempts": 0,
                "memory_limit_mib": 0,
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
        path = self.env["int.filemanager.document"]._blob_path(self.checksum)
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

    @api.model
    def _reader_command(self, path, mimetype, first_page):
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
        ]

    @api.model
    def _run_reader(self, path, mimetype, first_page, seconds):
        """Run the reader for at most ``seconds`` and collect what it says.

        :return: ``{"pages": [(n, text, cut)], "count", "done", "error", "message", "timeout",
            "exit"}``; a reader that was stopped at the limit has given the pages it finished
        """
        command = self._reader_command(path, mimetype, first_page)
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
                result["pages"].append((data["page"], data["text"], bool(data.get("cut"))))
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
        :param pages: ``[(number, text, was_cut)]``
        :return: notes for the row, for pages that were cut
        """
        Page = self.env["int.filemanager.text.page"]
        notes = [
            self.env._("Page %(page)s was cut at the size limit.", page=number)
            for number, _text, was_cut in pages
            if was_cut
        ]
        values = [{"text_id": self.id, "page": number, "content": text} for number, text, _cut in pages]
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
