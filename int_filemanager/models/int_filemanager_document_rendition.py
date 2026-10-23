"""The pictures of the documents: the first page of a PDF and the PDF preview of an office file."""

import base64
import importlib.util
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from odoo import api, fields, models
from odoo.fields import Domain

from ..tools.files import remove_file
from ..tools.programs import limited
from .int_filemanager_document import (
    PDF,
    PREVIEW_CRON_XMLID,
    PREVIEW_EXTENSIONS,
    TEXT_CRON_XMLID,
    THUMBNAIL_CRON_XMLID,
)

_logger = logging.getLogger(__name__)


# The picture of the first page of a PDF (``_cron_thumbnails``): the longer side in pixels, the
# files drawn per run, the time and the memory one page may take. A child process draws it
# (``tools/pdf_thumbnail.py``): a broken file may crash the PDF library.
THUMBNAIL_SIZE = 256
THUMBNAIL_BATCH = 100
THUMBNAIL_SECONDS = 60
THUMBNAIL_MEMORY_MIB = 1024
PDF_THUMBNAIL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "pdf_thumbnail.py")
PREVIEW_BATCH = 20
PREVIEW_NICE = 19
# A process that was told to stop gets this long before it is killed.
PREVIEW_KILL_SECONDS = 5


class IntFilemanagerDocument(models.Model):
    _inherit = "int.filemanager.document"

    # The first page of a PDF as a small picture for the list and the kanban. Made by the
    # scheduled action ``_cron_thumbnails`` on the server: the core's ``thumbnail`` of the
    # attachments of a message is made by the browser and only when somebody looks at the file.
    thumbnail = fields.Image(
        max_width=THUMBNAIL_SIZE,
        max_height=THUMBNAIL_SIZE,
        readonly=True,
        copy=False,
        exportable=False,
    )

    # Empty while a PDF waits for its picture, and for every other type. A PDF that cannot be
    # drawn is "failed" and is not tried again.
    thumbnail_state = fields.Selection(
        [("done", "Done"), ("failed", "Failed")],
        string="Picture state",
        readonly=True,
        copy=False,
    )

    # The PDF that LibreOffice made of an office file for the viewer (a blob of the storage that
    # no other record has): ``_cron_previews`` sets it, ``ocr_checksum`` hands it on. Empty while
    # the file waits for it, and for every other type; a file that cannot be turned is "failed"
    # and is not tried again.
    preview_checksum = fields.Char(
        string="Preview PDF",
        readonly=True,
        copy=False,
        exportable=False,
        index="btree_not_null",
    )

    preview_state = fields.Selection(
        [("done", "Done"), ("failed", "Failed")],
        string="Preview state",
        readonly=True,
        copy=False,
    )

    # The PDFs that wait for their picture: the scheduled action looks only at these.
    _thumbnail_work_index = models.Index(
        "(id) WHERE thumbnail_state IS NULL AND mimetype = 'application/pdf'"
    )

    # The same for the office files that wait for their preview.
    _preview_work_index = models.Index(
        "(id) WHERE preview_state IS NULL AND mimetype IN ("
        + ", ".join(f"'{mimetype}'" for mimetype in PREVIEW_EXTENSIONS)
        + ")"
    )

    _preview_thumbnail_work_index = models.Index(
        "(id) WHERE thumbnail_state IS NULL AND preview_checksum IS NOT NULL"
    )

    _preview_checksum_is_sha256 = models.Constraint(
        "CHECK (preview_checksum IS NULL OR preview_checksum ~ '^[0-9a-f]{64}$')",
        "The checksum of the preview must be a SHA-256 in lowercase hexadecimal.",
    )

    @api.model
    def _thumbnail_domain(self):
        """The PDFs, and the office files with a preview, that wait for their picture (one that failed is not tried again)."""
        return Domain("thumbnail_state", "=", False) & (
            Domain("mimetype", "=", PDF) | Domain("preview_checksum", "!=", False)
        )

    @api.model
    def _cron_thumbnails(self, limit=THUMBNAIL_BATCH):
        """Draw the first page of the PDFs that have no picture yet, one blob at a time.

        An office file is drawn from its preview. Documents with the same PDF share one drawing. Every blob is committed
        (``_commit_progress``), so a stop loses no more than the file that was being drawn; when
        the time is up with PDFs left, the report of what remains makes Odoo call it again.

        :param limit: the documents looked at in one call
        """
        assert self.env.context.get("cron_id") == self.env.ref(THUMBNAIL_CRON_XMLID).id, (
            "Meant for cron usage only"
        )
        if not importlib.util.find_spec("pypdfium2"):
            _logger.warning("pypdfium2 is not installed: the pictures of PDFs are not made.")
            return
        cron = self.env["ir.cron"]
        domain = self._thumbnail_domain()
        documents = self.with_context(active_test=False).search(domain, limit=limit)
        for checksum, same in documents.grouped(lambda document: document.preview_checksum or document.checksum).items():
            # Another transaction holds a row (the cleaner, a rename): the next call gets it.
            same = same.try_lock_for_update(allow_referencing=True).filtered_domain(domain)
            if same:
                same._make_thumbnail(checksum)
            if not cron._commit_progress(len(same)):
                break
        cron._commit_progress(0, remaining=self.with_context(active_test=False).search_count(domain))

    def _make_thumbnail(self, checksum):
        """Draw the blob ``checksum`` and give the picture to these documents, or mark them failed."""
        picture = self._draw_first_page(checksum)
        values = {"thumbnail_state": "failed"}
        if picture:
            values = {"thumbnail": base64.b64encode(picture), "thumbnail_state": "done"}
        # The users cannot write these fields (see ``write``); the job runs as superuser anyway.
        self.sudo().with_context(tracking_disable=True).write(values)

    @api.model
    def _draw_first_page(self, checksum):
        """The first page of the PDF blob as a JPEG, or ``None`` if it cannot be drawn.

        The program that cannot be started is no fault of the file: that error goes up (Odoo stops
        a scheduled action that fails again and again and tells the administrator).
        """
        command = [
            sys.executable,
            "-I",
            PDF_THUMBNAIL,
            self._blob_path(checksum),
            str(THUMBNAIL_SIZE),
            str(THUMBNAIL_MEMORY_MIB),
        ]
        try:
            done = subprocess.run(  # noqa: S603 (own script, own interpreter, no shell)
                command, capture_output=True, check=False, timeout=THUMBNAIL_SECONDS
            )
        except subprocess.TimeoutExpired:
            _logger.warning("No picture of %s: the first page took more than %s s.", checksum, THUMBNAIL_SECONDS)
            return None
        if done.returncode or not done.stdout:
            reason = done.stderr.decode(errors="replace").strip().splitlines()[-1:] or ["no answer"]
            _logger.warning("No picture of %s: %s", checksum, reason[0][:200])
            return None
        return done.stdout

    @api.model
    def _preview_domain(self):
        """The office files that wait for their preview (one that failed is not tried again)."""
        return Domain([("mimetype", "in", list(PREVIEW_EXTENSIONS)), ("preview_state", "=", False)])

    @api.model
    def _preview_counts(self):
        """How many office files wait for their preview, have it, or failed (for the settings)."""
        counts = dict.fromkeys((False, "done", "failed"), 0)
        counts.update(
            self.sudo()
            .with_context(active_test=False)
            ._read_group([("mimetype", "in", list(PREVIEW_EXTENSIONS))], ["preview_state"], ["__count"])
        )
        return counts

    @api.model
    def _cron_previews(self, limit=PREVIEW_BATCH):
        """Turn the office files that have no preview yet into PDFs, one blob at a time.

        Documents with the same checksum share one preview. Every blob is committed
        (``_commit_progress``), and a file gets the time of its setting at most, or the whole
        run if that is shorter: it is started only if that time is left. With files left the
        report of what remains makes Odoo call it again.

        :param limit: the documents looked at in one call
        """
        assert self.env.context.get("cron_id") == self.env.ref(PREVIEW_CRON_XMLID).id, (
            "Meant for cron usage only"
        )
        Text = self.env["int.filemanager.text"]
        if not Text._flag("preview_enabled", True):
            return
        if not shutil.which("soffice"):
            _logger.warning("LibreOffice is not installed: the previews of office files are not made.")
            return
        cron = self.env["ir.cron"]
        deadline = Text._pass_deadline()
        seconds = max(min(Text._setting("preview_seconds"), Text._budget()[2]), 1)
        domain = self._preview_domain()
        documents = self.with_context(active_test=False).search(domain, limit=limit)
        for index, (checksum, same) in enumerate(documents.grouped("checksum").items()):
            # The first file has the whole run: its time is at most that.
            if index and deadline - time.monotonic() < seconds:
                break
            # Another transaction holds a row (the cleaner, a rename): the next call gets it.
            same = same.try_lock_for_update(allow_referencing=True).filtered_domain(domain)
            if same:
                same._make_preview(checksum, seconds)
            if not cron._commit_progress(len(same)):
                break
        cron._commit_progress(0, remaining=self.with_context(active_test=False).search_count(domain))

    def _make_preview(self, checksum, seconds):
        """Give the blob ``checksum`` its preview PDF, or mark the documents failed.

        A document with the same file that has its outcome already hands it on (also a failure:
        the same bytes fail again).
        """
        done = self.search([("checksum", "=", checksum), ("preview_state", "!=", False)], limit=1)
        stored = None
        if done:
            values = {"preview_checksum": done.preview_checksum, "preview_state": done.preview_state}
        else:
            stored = self._convert_to_pdf(checksum, PREVIEW_EXTENSIONS[self[0].mimetype], seconds)
            values = {"preview_state": "failed"}
            if stored:
                values = {"preview_checksum": stored["checksum"], "preview_state": "done"}
        try:
            # The users cannot write these fields (see ``write``); the job runs as superuser anyway.
            self.sudo().with_context(tracking_disable=True).write(values)
            if stored:
                # The row first, then the file: the cleaner of the blobs looks at the rows.
                self.sudo().flush_recordset(["preview_checksum"])
                self._publish_blob(stored["tmp_path"], stored["checksum"])
            if values["preview_state"] == "done":
                # The picture of the first page, and the text of the old formats (read from it).
                for xmlid in (THUMBNAIL_CRON_XMLID, TEXT_CRON_XMLID):
                    self.env.ref(xmlid).sudo()._trigger()
        finally:
            if stored:
                remove_file(stored["tmp_path"])

    @api.model
    def _convert_to_pdf(self, checksum, extension, seconds):
        """The PDF that LibreOffice makes of the blob ``checksum`` as stored, or ``None``.

        The result of ``_store_stream``: the caller publishes the file or removes it. The blob has
        no ending, so LibreOffice gets a link to it that has one. The program that cannot be
        started is no fault of the file; the other faults are, and are told in the log.

        :param extension: the ending that tells LibreOffice the format (see ``PREVIEW_EXTENSIONS``)
        :param seconds: how long the program may take
        """
        path = self._blob_path(checksum)
        try:
            size = os.stat(path).st_size
        except FileNotFoundError:
            _logger.warning("No preview of %s: the file is missing.", checksum)
            return None
        limit = self.env["int.filemanager.text"]._setting("preview_max_size_mib")
        if size > limit * 1024**2:
            _logger.warning("No preview of %s: the file is bigger than %s MiB.", checksum, limit)
            return None
        with tempfile.TemporaryDirectory(prefix="int_filemanager_preview_", ignore_cleanup_errors=True) as job:
            source = os.path.join(job, f"file.{extension}")
            os.symlink(path, source)
            target = os.path.join(job, "file.pdf")
            code, errors = self._preview_run(job, source, seconds)
            if code or not (os.path.isfile(target) and os.path.getsize(target)):
                reason = f"it took more than {seconds:.0f} s" if code == 124 else errors or f"exit code {code}"
                _logger.warning("No preview of %s: %s", checksum, reason)
                return None
            with open(target, "rb") as stream:
                # A name without an ending: the head of the file tells what it is.
                stored = self._store_stream(stream, "preview")
        if stored["mimetype"] != PDF:
            remove_file(stored["tmp_path"])
            _logger.warning("No preview of %s: LibreOffice made no PDF.", checksum)
            return None
        return stored

    @api.model
    def _preview_run(self, job, source, seconds):
        """Run LibreOffice on ``source`` for at most ``seconds``; ``timeout`` stops all it started after that.

        Each run has a profile of its own in ``job``: LibreOffice runs only once for one profile.
        The priority is the lowest, the web pages come first.

        :return: ``(exit code, the last line it wrote as errors)``; 124: the time was up
        """
        done = subprocess.run(  # noqa: S603 (fixed program names, list arguments, no shell)
            limited(
                [
                    "soffice",
                    f"-env:UserInstallation={Path(job, 'profile').as_uri()}",
                    "--headless",
                    "--nologo",
                    "--nofirststartwizard",
                    "--invisible",
                    "--norestore",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    job,
                    source,
                ],
                seconds,
                PREVIEW_NICE,
                PREVIEW_KILL_SECONDS,
            ),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env={**os.environ, "HOME": job, "TMPDIR": job},
            check=False,
        )
        lines = done.stderr.decode(errors="replace").strip().splitlines()
        return done.returncode, lines[-1][:200] if lines else ""
