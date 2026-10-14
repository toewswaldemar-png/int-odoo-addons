import contextlib
import errno
import importlib.metadata
import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time

import psutil
import psycopg2.errors

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.addons.base.models.ir_cron import MIN_TIME_PER_JOB
from odoo.service.server import SLEEP_INTERVAL
from odoo.tools import SQL, config

from ..tools import ocr_plan
from .int_filemanager_document import BLOB_FOLDER, _remove_file

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
# Starts ``ocrmypdf`` with the limits and the environment that suit it (see the script).
START_OCR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "start_ocr.py")
# Says how many pictures an image file has and how wide it is (Pillow knows few formats here).
IMAGE_INFO = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "image_info.py")
# The folder of the sections of the files that are being recognized, next to the blobs.
OCR_FOLDER = ".ocr"
# What a run of the recognition says: it did a step, it has nothing to do, it has no time left.
OCR_PROGRESS, OCR_IDLE, OCR_NO_TIME = "progress", "idle", "no_time"
# A page with less text than this (letters, without white space) counts as a scan; only the
# start of the page is looked at.
SCAN_PAGE_CHARS = 20
SCAN_PAGE_LOOK = 2000
# The setup (a missing language, a full disk) keeps the recognition from starting for this long.
OCR_BLOCK_PARAMETER = "int_filemanager.ocr_blocked"
OCR_BLOCK_SECONDS = 3600
# What the programs are asked for their version and languages: kept for this long.
TOOLS_CACHE_SECONDS = 300
PROBE_SECONDS = 10
# The last bytes of what the recognition wrote as errors, kept for the decision and the message.
STDERR_BYTES = 4000
# A process that was told to stop gets this long before it is killed.
KILL_GRACE_SECONDS = 5
# A section stopped after less than this teaches nothing: it had no time to speak of.
MIN_TEACH_SECONDS = 5
# The reading of a finished section gets at least this long, whatever is left of the run.
MIN_READ_SECONDS = 10
# Files in a job folder younger than this are left to the cleaner (a section may be writing).
JOB_MIN_AGE_SECONDS = 600
OCR_LANGUAGES = re.compile(r"[A-Za-z0-9_]+(\+[A-Za-z0-9_]+)*")
DEFAULT_LANGUAGES = "deu+eng"
OCR_OUTPUT_TYPES = ("pdf", "pdfa")
_tools_cache = {}

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
    "ocr_jobs": (1, 1),  # cores of one text recognition (-j)
    "ocr_nice": (19, 0),  # priority of the text recognition (19: the lowest)
}


def _probe(command):
    """What a program writes when asked for its version or languages (empty if it fails)."""
    try:
        done = subprocess.run(  # noqa: S603 (a program found on the path, fixed arguments)
            command, capture_output=True, check=False, timeout=PROBE_SECONDS, text=True, errors="replace"
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout + done.stderr


def _kill_tree(process):
    """Stop a process and all it started (Tesseract, Ghostscript ...): asked first, then killed."""
    try:
        parent = psutil.Process(process.pid)
        family = [*parent.children(recursive=True), parent]
    except psutil.NoSuchProcess:
        family = []
    for member in family:
        with contextlib.suppress(psutil.NoSuchProcess):
            member.terminate()
    _gone, alive = psutil.wait_procs(family, timeout=KILL_GRACE_SECONDS)
    for member in alive:
        with contextlib.suppress(psutil.NoSuchProcess):
            member.kill()
    psutil.wait_procs(alive, timeout=KILL_GRACE_SECONDS)
    with contextlib.suppress(ProcessLookupError):
        process.kill()
    process.wait()


def _image_info(path):
    """``(number of pictures, width in pixels)`` of an image file, from its header; ``None`` if it is none.

    A child process answers (``tools/image_info.py``): the Odoo process loads only some of the
    formats of Pillow, and TIFF and WebP are not among them.
    """
    try:
        done = subprocess.run(  # noqa: S603 (own script, own interpreter, no shell)
            [sys.executable, "-I", IMAGE_INFO, path],
            capture_output=True,
            check=False,
            timeout=PROBE_SECONDS,
        )
        answer = json.loads(done.stdout.decode().splitlines()[-1])
        return int(answer["frames"]), int(answer["width"])
    except (OSError, subprocess.TimeoutExpired, IndexError, ValueError, KeyError):
        return None


def _remove_path(path):
    """Remove a file or a folder with all in it (what a stopped program left)."""
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, ignore_errors=True)
    else:
        _remove_file(path)


def _last_line(text):
    """The last line of a text that has something in it, short (for a message)."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1][:200] if lines else ""


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
    # Pages that had no text after reading: a scan. The text recognition is needed if there are some.
    # -1: not counted yet (rows made before the recognition existed).
    scan_pages = fields.Integer(string="Pages without text", default=-1, readonly=True)
    # The text recognition (OCR) has a state of its own, apart from the reading above. Empty:
    # not needed (or not judged yet). The reading goes on first, the recognition comes after it.
    ocr_state = fields.Selection(
        [
            ("wait", "Waiting"),
            ("running", "Running"),
            ("done", "Done"),
            ("skipped", "Skipped"),
            ("failed", "Failed"),
        ],
        string="Recognition",
        readonly=True,
    )
    ocr_message = fields.Char(string="Recognition message", readonly=True)
    # The page the recognition goes on with, and the file it goes on with: the last section it
    # finished (a name in the job folder of the module, with its size to see if it is whole).
    ocr_next_page = fields.Integer(string="Next page to recognize", default=1, readonly=True)
    ocr_file = fields.Char(string="Section file", readonly=True)
    ocr_file_size = fields.Integer(string="Section file size", readonly=True)
    ocr_attempts = fields.Integer(string="Recognition tries", readonly=True)
    # Pages that got text from the recognition: without any, its PDF is not worth a second copy.
    ocr_found_pages = fields.Integer(string="Pages with recognized text", readonly=True)
    # Smoothed time one page takes, to size the next section.
    ocr_seconds_per_page = fields.Float(string="Seconds per page", readonly=True)
    # The PDF the recognition made (a blob of the storage, no document has it): its checksum
    # keeps it from the cleaner of the blobs, and its size is for the status in the settings.
    ocr_checksum = fields.Char(string="Recognized PDF (checksum)", readonly=True, index="btree_not_null")
    ocr_size = fields.Float(string="Recognized PDF (size)", readonly=True)
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
    _ocr_checksum_is_sha256 = models.Constraint(
        "CHECK (ocr_checksum IS NULL OR ocr_checksum ~ '^[0-9a-f]{64}$')",
        "The checksum of the recognized PDF must be a SHA-256 in lowercase hexadecimal.",
    )
    _work_index = models.Index("(id) WHERE state IN ('pending', 'running')")
    _ocr_work_index = models.Index("(id) WHERE ocr_state IN ('wait', 'running')")
    _uncounted_index = models.Index("(id) WHERE scan_pages < 0")
    _unqueued_index = models.Index("(id) WHERE ocr_state IS NULL AND scan_pages > 0")

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
        # A picture whose pages are not counted yet counts as one page.
        [[pages_left, seconds_left]] = self.env.execute_query(
            SQL(
                """
                SELECT coalesce(sum(left_pages), 0),
                       coalesce(sum(left_pages * CASE WHEN ocr_seconds_per_page > 0
                                                      THEN ocr_seconds_per_page ELSE %s END), 0)
                  FROM (SELECT ocr_seconds_per_page,
                               CASE WHEN page_count > 0 THEN greatest(page_count - ocr_next_page + 1, 0)
                                    ELSE 1 END AS left_pages
                          FROM int_filemanager_text
                         WHERE ocr_state IN ('wait', 'running')) waiting
                """,
                ocr_plan.DEFAULT_SECONDS_PER_PAGE,
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
        """Make the rows for new files, read their text, recognize the text of scans, in the time.

        One step is one file (or one section of the pages of a scan), committed
        (``_commit_progress``). The reading and the new rows come first, the recognition
        after them. When the time is up with work left it reports the rows that wait, so Odoo
        calls it again at once and the next run goes on. Called again with the budget used up
        it returns at once.
        """
        assert self.env.context.get("cron_id") == self.env.ref(CRON_XMLID).id, (
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
    def _missing_where(self):
        """Documents that are not archived, of a type with text, and have no row yet.

        Pictures count only if the recognition is on and the document lies in a folder where
        the recognition of images is on (``ocr_images_active``): a row for each photo would
        have them all recognized.
        """
        return SQL(
            """
            document.active
            AND (document.mimetype IN %(types)s OR document.mimetype LIKE %(text)s
                 OR (%(images_on)s AND document.mimetype IN %(images)s AND EXISTS (
                         SELECT 1 FROM int_filemanager_folder folder
                          WHERE folder.id = document.folder_id AND folder.ocr_images_active)))
            AND NOT EXISTS (
                SELECT 1 FROM int_filemanager_text text WHERE text.checksum = document.checksum)
            """,
            types=self._supported_types(),
            text=TEXT_PREFIX,
            images_on=self._ocr_options()["enabled"],
            images=IMAGE_TYPES,
        )

    @api.model
    def _flush_for_missing(self):
        # Raw SQL: what is not written yet (a document just archived) must be, first.
        self.env["int.filemanager.document"].flush_model(["checksum", "mimetype", "active", "folder_id"])
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

        A picture is read by the recognition: it starts again from there.
        """
        self.env["int.filemanager.text.page"].search([("text_id", "in", self.ids)]).unlink()
        pictures = self.filtered(lambda row: row.mimetype in IMAGE_TYPES)
        for row in pictures:
            row._ocr_drop_job()
        pictures.write(
            {
                **self._ocr_restart_values(),
                "state": "empty",
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
        again would lose it, and have the scans recognized a second time).
        """
        self.ensure_one()
        section = self._ocr_section_path()
        if section:
            return section
        Document = self.env["int.filemanager.document"]
        if self.ocr_checksum and os.path.isfile(Document._blob_path(self.ocr_checksum)):
            return Document._blob_path(self.ocr_checksum)
        return Document._blob_path(self.checksum)

    @api.model
    def _reader_command(self, path, mimetype, first_page, last_page=0):
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
            str(last_page),
        ]

    @api.model
    def _run_reader(self, path, mimetype, first_page, seconds, last_page=0):
        """Run the reader for at most ``seconds`` and collect what it says.

        :return: ``{"pages": [(n, text, cut)], "count", "done", "error", "message", "timeout",
            "exit"}``; a reader that was stopped at the limit has given the pages it finished
        """
        command = self._reader_command(path, mimetype, first_page, last_page)
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

    # ---- Scans and the text recognition -------------------------------------------------

    @api.model
    def _scan_page_counts(self, ids):
        """``{row id: number of pages with (almost) no text}``; rows without such a page are left out.

        Only the start of a page is looked at (a page of 500 KB would cost a lot to measure).
        """
        self.env["int.filemanager.text.page"].flush_model()
        return dict(
            self.env.execute_query(
                SQL(
                    """
                    SELECT text_id, count(*) FROM int_filemanager_text_page
                     WHERE text_id IN %s
                       AND length(regexp_replace(
                               left(coalesce(content, ''), %s), '[[:space:]]', '', 'g')) < %s
                     GROUP BY text_id
                    """,
                    tuple(ids),
                    SCAN_PAGE_LOOK,
                    SCAN_PAGE_CHARS,
                )
            )
        )

    def _count_scan_pages(self):
        """The pages of this PDF that have (almost) no text: scans. Other files have none."""
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

    @api.model
    def _flag(self, name, default):
        """A yes or no from the system parameters, ``int_filemanager.<name>`` (else ``default``)."""
        value = self.env["ir.config_parameter"].sudo().get_param(f"int_filemanager.{name}")
        if not value:
            return default
        return value.strip().lower() not in ("0", "false", "no", "off")

    @api.model
    def _ocr_options(self):
        """What the settings say about the recognition."""
        params = self.env["ir.config_parameter"].sudo()
        languages = params.get_param("int_filemanager.ocr_languages") or DEFAULT_LANGUAGES
        output_type = params.get_param("int_filemanager.ocr_output_type")
        return {
            "enabled": self._flag("ocr_enabled", False),
            "languages": languages if OCR_LANGUAGES.fullmatch(languages) else DEFAULT_LANGUAGES,
            "jobs": self._setting("ocr_jobs"),
            "nice": min(self._setting("ocr_nice"), 19),
            "deskew": self._flag("ocr_deskew", True),
            "output_type": output_type if output_type in OCR_OUTPUT_TYPES else "pdf",
        }

    @api.model
    def _ocr_tools(self):
        """The programs of the recognition: ``{"program", "version", "tesseract", "languages"}``.

        ``program`` and ``tesseract`` are the paths, or ``False`` where the program is missing.
        Kept for a few minutes: asking costs two starts of a process.
        """
        cached = _tools_cache.get("tools")
        if cached and time.monotonic() - cached[0] < TOOLS_CACHE_SECONDS:
            return cached[1]
        program, tesseract = shutil.which("ocrmypdf"), shutil.which("tesseract")
        version = _probe([program, "--version"]).strip() if program else ""
        languages = {
            line.strip()
            for line in (_probe([tesseract, "--list-langs"]).splitlines()[1:] if tesseract else [])
            if line.strip()
        }
        tools = {
            "program": program or False,
            "version": version or False,
            "tesseract": tesseract or False,
            "languages": languages,
        }
        _tools_cache["tools"] = (time.monotonic(), tools)
        return tools

    @api.model
    def _ocr_blocked(self):
        """``(code, detail)`` while a fault of the setup keeps the recognition from starting."""
        value = self.env["ir.config_parameter"].sudo().get_param(OCR_BLOCK_PARAMETER)
        if not value:
            return None
        stamp, _sep, rest = value.partition("|")
        code, _sep, detail = rest.partition("|")
        try:
            young = time.time() - float(stamp) < OCR_BLOCK_SECONDS
        except ValueError:
            return None
        return (code, detail) if young else None

    @api.model
    def _ocr_block(self, code, detail=""):
        """Keep the recognition from starting for a while (a full disk, a wrong setup)."""
        self.env["ir.config_parameter"].sudo().set_param(
            OCR_BLOCK_PARAMETER, f"{time.time()}|{code}|{detail[:200].replace('|', '/')}"
        )

    @api.model
    def _ocr_ready(self):
        """Whether the recognition can run: ``(yes, reason)``; the reason is a short code."""
        options = self._ocr_options()
        if not options["enabled"]:
            return False, "off"
        blocked = self._ocr_blocked()
        if blocked:
            return False, blocked[0]
        tools = self._ocr_tools()
        if not tools["program"] or not tools["tesseract"]:
            return False, "missing_dependency"
        if any(language not in tools["languages"] for language in options["languages"].split("+")):
            return False, "missing_language"
        return True, None

    @api.model
    def _ocr_step(self, deadline):
        """Recognize a section of the next scan that waits: ``OCR_PROGRESS``, ``OCR_IDLE`` or ``OCR_NO_TIME``."""
        if not self._ocr_ready()[0]:
            return OCR_IDLE
        row = self.search([("ocr_state", "=", "wait")], order="id", limit=1)
        if not row:
            return OCR_IDLE
        if not row.try_lock_for_update():
            # Somebody holds it (the cleaner); the next run tries again.
            return OCR_NO_TIME
        return row._ocr_section(deadline)

    @api.model
    def _ocr_dir(self):
        return os.path.join(self.env["ir.attachment"]._filestore(), BLOB_FOLDER, OCR_FOLDER)

    def _job_dir(self):
        """The folder of the sections of this file."""
        self.ensure_one()
        return os.path.join(self._ocr_dir(), str(self.id))

    def _ocr_section_path(self):
        """The last finished section if it is there and whole, else ``False``."""
        self.ensure_one()
        if not self.ocr_file:
            return False
        path = os.path.join(self._job_dir(), self.ocr_file)
        try:
            whole = os.path.getsize(path) == self.ocr_file_size
        except OSError:
            whole = False
        return path if whole else False

    def _ocr_section(self, deadline):
        """Recognize the next section of the pages of this file, within the time.

        The row says ``running`` (committed) while the program runs, so a crash is counted at
        the next run. Sections build on each other: each reads the file the last one made, and
        the row points to the new file in the same commit that saves the text of its pages.

        :return: ``OCR_PROGRESS`` (a step was done and is to be committed) or ``OCR_NO_TIME``
        """
        self.ensure_one()
        options, tools = self._ocr_options(), self._ocr_tools()
        source = self._ocr_section_path()
        if self.ocr_file and not source:
            # The file the row points to is gone (or not whole): start again from the original.
            # It is the fault of a crash or the cleaner, not of the file: no try is used up.
            self.write({"ocr_file": False, "ocr_file_size": 0, "ocr_next_page": 1})
        if not source:
            source = self.env["int.filemanager.document"]._blob_path(self.checksum)
            if not os.path.isfile(source):
                self._ocr_fail("missing")
                return OCR_PROGRESS
        if self.mimetype in IMAGE_TYPES and not self.page_count:
            info = _image_info(source)
            if not info:
                self._ocr_fail("bad_file")
                return OCR_PROGRESS
            self.write({"page_count": info[0]})
        first = self.ocr_next_page
        left = self.page_count - first + 1
        if left < 1:
            self._ocr_finish()
            return OCR_PROGRESS
        # The program gets the run up to the time that the reading of the new pages needs.
        run_until = deadline - MIN_READ_SECONDS
        fair = min(ocr_plan.MIN_COUNTING_SECONDS, self._budget()[2] * 0.8)
        pages = ocr_plan.section_pages(run_until - time.monotonic(), self.ocr_seconds_per_page, left, fair)
        if not pages:
            return OCR_NO_TIME
        last = first + pages - 1
        row_id, max_attempts = self.id, self._setting("max_attempts")
        self.write({"ocr_state": "running"})
        self.env["ir.cron"]._commit_progress()
        job = self._job_dir()
        name = f"upto-{last}.pdf"
        target = os.path.join(job, name + ".tmp")
        try:
            os.makedirs(job, exist_ok=True)
            tried, dpi = set(), None
            while True:
                _remove_file(target)
                if ocr_plan.DPI in tried and not dpi:
                    # A picture without a resolution: take its width for the width of an A4 page.
                    width = (_image_info(source) or (0, 0))[1]
                    dpi = ocr_plan.estimate_dpi(width) if width else None
                command = ocr_plan.section_command(
                    tools["program"],
                    source,
                    target,
                    first,
                    last,
                    languages=options["languages"],
                    jobs=options["jobs"],
                    output_type=options["output_type"],
                    deskew_and_rotate=options["deskew"],
                    add=tried,
                    image_dpi=dpi,
                )
                started = time.monotonic()
                code, stderr, timed_out = self._ocr_run(command, options["nice"], job, run_until - started)
                used = time.monotonic() - started
                if timed_out:
                    break
                empty = code == 0 and not (os.path.isfile(target) and os.path.getsize(target))
                outcome = ocr_plan.classify(
                    code,
                    stderr,
                    tried=tried,
                    attempts=self.ocr_attempts,
                    max_attempts=max_attempts,
                    empty_result=empty,
                )
                if outcome.action == ocr_plan.AGAIN and outcome.add:
                    tried.add(outcome.add)
                    continue
                break
            # The cleaner may have deleted the row while the program ran; it is then not needed.
            row = self.browse(row_id).exists().try_lock_for_update()
            if not row:
                shutil.rmtree(job, ignore_errors=True)
            elif timed_out:
                row._ocr_timed_out(pages, used, fair)
            else:
                # In a savepoint: a fault of the disk half way leaves nothing half done in the database.
                with self.env.cr.savepoint():
                    row._ocr_conclude(outcome, stderr, (first, last, target, name, pages, used, deadline), dpi)
        except OSError as error:
            self._ocr_io_failed(row_id, error)
        return OCR_PROGRESS

    def _ocr_io_failed(self, row_id, error):
        """The disk or its folder failed after the row was set to ``running``.

        A full disk (or a quota) is the setup, not the file: the recognition pauses for a while
        and the file waits as it was. Any other fault counts as a failed try. Told here because
        nothing else would: the exception would roll the step back and leave the row
        ``running``, to be counted as a crash at the next run.
        """
        row = self.browse(row_id).exists().try_lock_for_update()
        if not row:
            return
        with contextlib.suppress(OSError):
            row._ocr_clean_job(keep=row.ocr_file)
        if error.errno in (errno.ENOSPC, errno.EDQUOT):
            self._ocr_block("disk_full", str(error))
            row.write({"ocr_state": "wait"})
        else:
            row._ocr_after_failure(str(error))

    @api.model
    def _ocr_run(self, command, nice, job, seconds):
        """Run the recognition for at most ``seconds``; its whole process tree is stopped after that.

        :return: ``(exit code, what it wrote as errors, was stopped)``
        """
        if seconds <= 0:
            return None, "", True
        errors_path = os.path.join(job, "stderr.txt")
        with open(errors_path, "wb") as errors:
            process = subprocess.Popen(  # noqa: S603 (own script, own interpreter, no shell)
                [sys.executable, "-I", START_OCR, str(nice), job, *command],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=errors,
            )
            try:
                process.wait(timeout=seconds)
                timed_out = False
            except subprocess.TimeoutExpired:
                _kill_tree(process)
                timed_out = True
        with open(errors_path, "rb") as errors:
            errors.seek(0, os.SEEK_END)
            errors.seek(max(errors.tell() - STDERR_BYTES, 0))
            text = errors.read().decode(errors="replace")
        return process.returncode, text, timed_out

    def _ocr_timed_out(self, pages, used, fair):
        """A section was stopped by the time: the next one is smaller; a lone page may count."""
        self.ensure_one()
        self._ocr_clean_job(keep=self.ocr_file)
        if used < MIN_TEACH_SECONDS:
            # It got no time worth the name: no lesson for the file.
            self.write({"ocr_state": "wait"})
            return
        lesson = ocr_plan.after_timeout(pages, self.ocr_seconds_per_page, used, fair)
        attempts = self.ocr_attempts + (1 if lesson.counts else 0)
        if attempts >= self._setting("max_attempts"):
            self._ocr_fail("too_slow")
        else:
            self.write(
                {
                    "ocr_state": "wait",
                    "ocr_attempts": attempts,
                    "ocr_seconds_per_page": lesson.seconds_per_page,
                }
            )

    def _ocr_conclude(self, outcome, stderr, section, dpi=None):
        """Do what the rules say about the end of the program (see ``ocr_plan.classify``)."""
        self.ensure_one()
        first, last, target, name, pages, used, deadline = section
        if outcome.action == ocr_plan.DONE:
            self._ocr_accept(first, last, target, name, pages, used, deadline)
            if dpi and dpi < ocr_plan.LOW_DPI and self.ocr_state != "failed":
                self.ocr_message = self.env._(
                    "The picture has no resolution; %(dpi)s dpi was assumed, the text may not be recognized.",
                    dpi=dpi,
                )
            return
        _remove_file(target)
        self._ocr_clean_job(keep=self.ocr_file)
        if outcome.action == ocr_plan.FAIL:
            self.write({"ocr_attempts": outcome.attempts})
            self._ocr_fail(outcome.reason, stderr)
        elif outcome.action == ocr_plan.AGAIN:
            self.write({"ocr_state": "wait", "ocr_attempts": outcome.attempts})
        else:
            # Block (a wrong setup) or pause (disk full): not the fault of the file. Nothing
            # more is started for a while, and the file waits as it was.
            self._ocr_block(outcome.reason, _last_line(stderr))
            self.write({"ocr_state": "wait"})

    def _ocr_accept(self, first, last, target, name, pages, used, deadline):
        """Take over a finished section: its file, and the text of its pages, in one commit."""
        self.ensure_one()
        final = os.path.join(self._job_dir(), name)
        with open(target, "r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(target, final)
        result = self._run_reader(final, PDF, first, max(deadline - time.monotonic(), MIN_READ_SECONDS), last)
        numbers = {number for number, _text, _cut in result["pages"]}
        if result["error"] or not result["done"] or numbers != set(range(first, last + 1)):
            _remove_file(final)
            self._ocr_after_failure(self.env._("The text of the recognized pages could not be read."))
            return
        old = self.ocr_file
        old_pages = self.env["int.filemanager.text.page"].search(
            [("text_id", "=", self.id), ("page", "in", sorted(numbers))]
        )
        before = {page.page: len("".join((page.content or "").split())) for page in old_pages}
        found = sum(
            1 for number, text, _cut in result["pages"] if len("".join(text.split())) > before.get(number, 0)
        )
        old_pages.unlink()
        self._store_pages(result["pages"])
        seconds_per_page = ocr_plan.smoothed(
            self.ocr_seconds_per_page, ocr_plan.measured_seconds_per_page(pages, used)
        )
        self.write(
            {
                "ocr_state": "wait",
                "ocr_next_page": last + 1,
                "ocr_file": name,
                "ocr_file_size": os.path.getsize(final),
                "ocr_attempts": 0,
                "ocr_found_pages": self.ocr_found_pages + found,
                "ocr_seconds_per_page": seconds_per_page,
            }
        )
        if last >= self.page_count:
            self._ocr_finish()
        # Last: this is done once the transaction is committed, whatever happens until then.
        if old and old != name:
            self._ocr_forget(os.path.join(self._job_dir(), old))

    def _ocr_finish(self):
        """All pages are done: keep the recognized PDF if it gave text, and say so.

        The PDF goes to the storage like an upload (``_store_stream``, ``_publish_blob``). It is
        kept only if the recognition gave text to some page (``ocr_found_pages``): otherwise it
        is a second copy of the file for nothing. The row is saved first, then the file is placed: the cleaner of the blobs waits
        for this transaction and then sees the checksum (it is on its checklist before).
        """
        self.ensure_one()
        Document = self.env["int.filemanager.document"]
        scan_pages = self._count_scan_pages()
        gained = self.ocr_found_pages > 0
        # A picture keeps no PDF: the viewer shows the picture.
        keep = gained and self.mimetype == PDF
        final = self._ocr_section_path()
        values = {
            "ocr_state": "done",
            "ocr_file": False,
            "ocr_file_size": 0,
            "ocr_attempts": 0,
            "scan_pages": scan_pages,
            "ocr_message": self.ocr_message if gained else self.env._("The text recognition found no text."),
        }
        stored = None
        if keep and final:
            with open(final, "rb") as stream:
                stored = Document._store_stream(stream, "recognized.pdf", PDF)
            values.update(ocr_checksum=stored["checksum"], ocr_size=stored["size"])
        try:
            self.write(values)
            if self.state == "empty" and self._has_text():
                self.state = "done"
            if stored:
                self.flush_recordset()
                Document._publish_blob(stored["tmp_path"], stored["checksum"])
        finally:
            if stored:
                _remove_file(stored["tmp_path"])
        self._ocr_drop_job()

    def _ocr_after_failure(self, reason):
        """The recognition did not finish: try again, or give up after the tries are used up."""
        self.ensure_one()
        attempts = self.ocr_attempts + 1
        if attempts >= self._setting("max_attempts"):
            self.write({"ocr_attempts": attempts})
            self._ocr_fail("gave_up", reason)
        else:
            self.write({"ocr_state": "wait", "ocr_attempts": attempts})

    def _ocr_fail(self, reason, detail=""):
        """Give the file up: the text read so far stays, the original is never touched."""
        self.ensure_one()
        messages = {
            "bad_file": self.env._("The file cannot be read by the text recognition."),
            "encrypted": self.env._("The file needs a password."),
            "no_resolution": self.env._("The image has no usable resolution."),
            "empty_result": self.env._("The text recognition gave no file."),
            "already_text": self.env._("The text recognition refused pages that have text."),
            "image_too_large": self.env._("The image is too large for the text recognition."),
            "gave_up": self.env._("The text recognition stopped with an error several times."),
            "too_slow": self.env._("A page takes longer than the time of one run."),
            "missing": self.env._("The file is missing."),
        }
        text = messages.get(reason, reason)
        self.write(
            {
                "ocr_state": "failed",
                "ocr_message": f"{text} {_last_line(detail)}".strip()[:MESSAGE_LENGTH],
                "ocr_file": False,
                "ocr_file_size": 0,
            }
        )
        self._ocr_drop_job()

    def _ocr_clean_job(self, keep=None):
        """Remove what a stopped program left in the job folder (the file ``keep`` stays)."""
        self.ensure_one()
        job = self._job_dir()
        if not os.path.isdir(job):
            return
        for entry in os.scandir(job):
            if entry.name != keep:
                _remove_path(entry.path)

    def _ocr_drop_job(self):
        """Remove the job folder once this transaction is committed (it may be used until then)."""
        path = self._job_dir()
        self.env.cr.postcommit.add(lambda: shutil.rmtree(path, ignore_errors=True))

    @api.model
    def _ocr_forget(self, path):
        self.env.cr.postcommit.add(lambda: _remove_file(path))

    @api.model
    def _ocr_restart_values(self):
        """The recognition of a file put back to the start (its state is left to the caller)."""
        return {
            "ocr_message": False,
            "ocr_next_page": 1,
            "ocr_file": False,
            "ocr_file_size": 0,
            "ocr_attempts": 0,
            "ocr_found_pages": 0,
            "ocr_seconds_per_page": 0,
            "ocr_checksum": False,
            "ocr_size": 0,
        }

    def action_recognize_again(self):
        """Throw away the recognition and the text, and begin again with the original.

        Public (the button calls it): it checks the right itself.
        """
        if not self.env.user.has_group("int_filemanager.int_filemanager_group_admin"):
            raise AccessError(self.env._("Only a Filemanager administrator can do that."))
        rows = self.sudo().filtered(lambda row: row.state not in ("pending", "running") and row.ocr_state != "running")
        for row in rows:
            row._ocr_drop_job()
        rows.write({**self._ocr_restart_values(), "ocr_state": False})
        rows._reset()
        cron = self.env.ref(CRON_XMLID, raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()

    # ---- Cleaning up the job folders ----------------------------------------------------

    @api.autovacuum
    def _gc_ocr_jobs(self):
        """Delete what is left in the job folders: files of rows that are gone or have finished.

        A row that is ``running`` is left alone, and so is everything younger than a few
        minutes (a section may just be writing). A row that waits keeps the file it points to.
        """
        base = self._ocr_dir()
        if not os.path.isdir(base):
            return
        jobs = [entry for entry in os.scandir(base) if entry.is_dir() and entry.name.isdigit()]
        rows = self.browse([int(entry.name) for entry in jobs]).exists()
        oldest_kept = time.time() - JOB_MIN_AGE_SECONDS
        for entry in jobs:
            row = rows.filtered(lambda row, entry=entry: row.id == int(entry.name))
            if row.ocr_state == "running":
                continue
            keep = row.ocr_file if row.ocr_state == "wait" else None
            for child in os.scandir(entry.path):
                if child.name != keep and child.stat().st_mtime < oldest_kept:
                    _remove_path(child.path)
            with contextlib.suppress(OSError):
                os.rmdir(entry.path)  # only when it is empty

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
