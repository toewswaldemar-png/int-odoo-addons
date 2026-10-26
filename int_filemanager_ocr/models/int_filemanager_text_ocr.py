"""The text recognition (OCR) of the files: the sections of a scan are recognized one by one."""

import contextlib
import errno
import logging
import os
import re
import shutil
import signal
import subprocess
import time

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import SQL

from odoo.addons.int_filemanager.models.int_filemanager_document import BLOB_FOLDER, PDF
from odoo.addons.int_filemanager.tools.files import remove_file, remove_path
from odoo.addons.int_filemanager.tools.programs import last_line, limited, probe

from ..tools import ocr_plan
from ..tools.programs import image_info
from .int_filemanager_text import IMAGE_TYPES, MESSAGE_LENGTH, OCR_IDLE, OCR_NO_TIME, OCR_PROGRESS, TEXT_CRON_XMLID

_logger = logging.getLogger(__name__)

# The folder of the sections of the files that are being recognized, next to the blobs.
OCR_FOLDER = ".ocr"
# The setup (a missing language, a full disk) keeps the recognition from starting for this long.
OCR_BLOCK_PARAMETER = "int_filemanager.ocr_blocked"
OCR_BLOCK_SECONDS = 3600
# What the programs are asked for their version and languages: kept for this long.
TOOLS_CACHE_SECONDS = 300
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


class IntFilemanagerText(models.Model):
    _inherit = "int.filemanager.text"

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

    _ocr_checksum_is_sha256 = models.Constraint(
        "CHECK (ocr_checksum IS NULL OR ocr_checksum ~ '^[0-9a-f]{64}$')",
        "The checksum of the recognized PDF must be a SHA-256 in lowercase hexadecimal.",
    )

    _ocr_work_index = models.Index("(id) WHERE ocr_state IN ('wait', 'running')")

    _unqueued_index = models.Index("(id) WHERE ocr_state IS NULL AND scan_pages > 0")

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
        version = probe([program, "--version"]).strip() if program else ""
        languages = {
            line.strip()
            for line in (probe([tesseract, "--list-langs"]).splitlines()[1:] if tesseract else [])
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

    def _ocr_pages_left(self):
        """How many pages the recognition has still to do: the scans from ``ocr_next_page`` on.

        A picture has its frames (no rows of pages); a PDF has the pages that are scans.
        """
        self.ensure_one()
        if self.mimetype in IMAGE_TYPES:
            return max(self.page_count - self.ocr_next_page + 1, 0)
        return len(self._ocr_pages(None))

    def _ocr_pages(self, limit):
        """The numbers of the next ``limit`` pages to recognize, in order (``None``: all)."""
        self.ensure_one()
        if self.mimetype in IMAGE_TYPES:
            last = self.page_count if limit is None else min(self.page_count, self.ocr_next_page + limit - 1)
            return list(range(self.ocr_next_page, last + 1))
        self.env["int.filemanager.text.page"].flush_model()
        rows = self.env.execute_query(
            SQL(
                """
                SELECT page FROM int_filemanager_text_page
                 WHERE text_id = %s AND scan AND page >= %s
                 ORDER BY page LIMIT %s
                """,
                self.id,
                self.ocr_next_page,
                limit,
            )
        )
        return [number for [number] in rows]

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
            info = image_info(source)
            if not info:
                self._ocr_fail("bad_file")
                return OCR_PROGRESS
            self.write({"page_count": info[0]})
        left = self._ocr_pages_left()
        if left < 1:
            self._ocr_finish()
            return OCR_PROGRESS
        # The program gets the run up to the time that the reading of the new pages needs.
        run_until = deadline - MIN_READ_SECONDS
        fair = ocr_plan.fair_seconds(self._budget()[2] - MIN_READ_SECONDS)
        pages = ocr_plan.section_pages(run_until - time.monotonic(), self.ocr_seconds_per_page, left, fair)
        if not pages:
            return OCR_NO_TIME
        numbers = self._ocr_pages(pages)
        last = numbers[-1]
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
                remove_file(target)
                if ocr_plan.DPI in tried and not dpi:
                    # A picture without a resolution: take its width for the width of an A4 page.
                    width = (image_info(source) or (0, 0))[1]
                    dpi = ocr_plan.estimate_dpi(width) if width else None
                command = ocr_plan.section_command(
                    tools["program"],
                    source,
                    target,
                    numbers,
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
                    row._ocr_conclude(outcome, stderr, (numbers, target, name, used, deadline), dpi)
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
        """Run the recognition for at most ``seconds``; ``timeout`` stops everything it started after that.

        ``nice`` is the absolute priority of the settings; a lower number than the one of this
        process needs a right we do not have, so the priority stays as it is then.

        :return: ``(exit code, what it wrote as errors, was stopped)``
        """
        if seconds <= 0:
            return None, "", True
        errors_path = os.path.join(job, "stderr.txt")
        environment = {**os.environ, "OMP_THREAD_LIMIT": "1", "TMPDIR": job}
        started = time.monotonic()
        try:
            with open(errors_path, "wb") as errors:
                done = subprocess.run(  # noqa: S603 (fixed program names, list arguments, no shell)
                    limited(command, seconds, nice, KILL_GRACE_SECONDS),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=errors,
                    env=environment,
                    check=False,
                )
        except FileNotFoundError:
            return ocr_plan.NOT_FOUND, "", False
        with open(errors_path, "rb") as errors:
            errors.seek(0, os.SEEK_END)
            errors.seek(max(errors.tell() - STDERR_BYTES, 0))
            text = errors.read().decode(errors="replace")
        # 124: the time was up. -9: ``timeout`` had to kill it, or the machine did (its memory):
        # only the time tells.
        code = done.returncode
        return code, text, code == 124 or (code == -signal.SIGKILL and time.monotonic() - started >= seconds)

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
        numbers, target, name, used, deadline = section
        if outcome.action == ocr_plan.DONE:
            self._ocr_accept(numbers, target, name, used, deadline)
            if dpi and dpi < ocr_plan.LOW_DPI and self.ocr_state != "failed":
                self.ocr_message = self.env._(
                    "The picture has no resolution; %(dpi)s dpi was assumed, the text may not be recognized.",
                    dpi=dpi,
                )
            return
        remove_file(target)
        self._ocr_clean_job(keep=self.ocr_file)
        if outcome.action == ocr_plan.FAIL:
            self.write({"ocr_attempts": outcome.attempts})
            self._ocr_fail(outcome.reason, stderr)
        elif outcome.action == ocr_plan.AGAIN:
            self.write({"ocr_state": "wait", "ocr_attempts": outcome.attempts})
        else:
            # Block (a wrong setup) or pause (disk full): not the fault of the file. Nothing
            # more is started for a while, and the file waits as it was.
            self._ocr_block(outcome.reason, last_line(stderr))
            self.write({"ocr_state": "wait"})

    def _ocr_accept(self, numbers, target, name, used, deadline):
        """Take over a finished section: its file, and the text of its pages, in one commit.

        :param numbers: the page numbers of the section; the pages up to the last one are done
        """
        self.ensure_one()
        last = numbers[-1]
        final = os.path.join(self._job_dir(), name)
        with open(target, "r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(target, final)
        result = self._run_reader(final, PDF, 1, max(deadline - time.monotonic(), MIN_READ_SECONDS), numbers)
        if result["error"] or not result["done"] or {page[0] for page in result["pages"]} != set(numbers):
            remove_file(final)
            self._ocr_after_failure(self.env._("The text of the recognized pages could not be read."))
            return
        old = self.ocr_file
        old_pages = self.env["int.filemanager.text.page"].search(
            [("text_id", "=", self.id), ("page", "in", numbers)]
        )
        before = {page.page: len("".join((page.content or "").split())) for page in old_pages}
        found = sum(
            1 for number, text, _cut, _picture in result["pages"] if len("".join(text.split())) > before.get(number, 0)
        )
        old_pages.unlink()
        self._store_pages(result["pages"])
        seconds_per_page = ocr_plan.smoothed(
            self.ocr_seconds_per_page, ocr_plan.measured_seconds_per_page(len(numbers), used)
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
        if not self._ocr_pages_left():
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
                remove_file(stored["tmp_path"])
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
                "ocr_message": f"{text} {last_line(detail)}".strip()[:MESSAGE_LENGTH],
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
                remove_path(entry.path)

    def _ocr_drop_job(self):
        """Remove the job folder once this transaction is committed (it may be used until then)."""
        path = self._job_dir()
        self.env.cr.postcommit.add(lambda: shutil.rmtree(path, ignore_errors=True))

    @api.model
    def _ocr_forget(self, path):
        self.env.cr.postcommit.add(lambda: remove_file(path))

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
        cron = self.env.ref(TEXT_CRON_XMLID, raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()

    # ---- Cleaning up the job folders -------------------------------------------

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
                    remove_path(child.path)
            with contextlib.suppress(OSError):
                os.rmdir(entry.path)  # only when it is empty
