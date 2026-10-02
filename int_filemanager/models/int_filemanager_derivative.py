import contextlib
import json
import logging
import time
import uuid
from datetime import timedelta

import psycopg2

from odoo import api, fields, models

from .. import blobstore, converter_client, derivative_plan, fault

_logger = logging.getLogger(__name__)

CONVERTER_URL_PARAM = "int_filemanager.converter_url"
CONVERTER_TIMEOUT_PARAM = "int_filemanager.converter_timeout_s"
# How long Odoo waits for one HTTP call to answer: comfortably above the converter's
# own inline wait budget (15s) for the fast kinds, and short for a poll of a slow one -
# the whole point of the async protocol is that this never has to be a long timeout.
DEFAULT_CONVERTER_TIMEOUT_S = 60
# One cron run stops starting new jobs after this long.
RUN_BUDGET_S = 45
CLAIM_BATCH = 5
# A job whose worker died is released this long after it was taken; also how long a
# job that answered "still running" is trusted before the next poll must renew it.
LEASE_MINUTES = 10
# A job polled for longer than this without ever finishing is given up on (counts as
# a failure, so the usual retry applies): a bit above the converter's own OCR ceiling
# (1800s), which is itself close to Odoo's documented cron real-time limit.
MAX_JOB_AGE_MINUTES = 40
MAX_ATTEMPTS = 3
MAX_CLAIM_CONFLICTS = 5
ENQUEUE_BATCH = 500
# What the explorer shows first: the rows of the folder the user is looking at.
VISIBLE_PRIORITY = 100
MAX_REQUESTED_NODES = 200
EXTENSION_SQL = r"substring(lower(n.name) from '\.([a-z0-9]{1,8})$')"
# The converter caps text at 2 million characters (up to 4 bytes each is more than
# it sends); its metadata is a few hundred bytes.
MAX_TEXT_BYTES = 8 * 1024 * 1024
MAX_META_BYTES = 256 * 1024
# A word list is 2 million characters of text plus at most 500,000 words of about
# 50 bytes each.
MAX_WORDS_BYTES = 40 * 1024 * 1024
INT4_MAX = 2**31 - 1
META_STRING_MAX = 200
META_KEYS_MAX = 40


class IntFilemanagerDerivative(models.Model):
    """Something derived from a blob: a picture, a PDF, the text or the facts of a file.

    Users have no access rights: the result is only served by the preview
    route, after the rights on the revision were checked. Odoo only stores and
    serves the converter's result; the converter is the only one that opens the
    bytes of the file.
    """

    _name = "int_filemanager.derivative"
    _description = "Filemanager v2 derived file"
    _order = "priority desc, id"

    source_blob_id = fields.Many2one(
        "int_filemanager.blob", required=True, index=True, ondelete="restrict"
    )
    kind = fields.Selection(
        [
            ("tile", "Thumbnail"),
            ("preview", "Preview image"),
            ("preview_pdf", "Preview PDF"),
            ("text", "Text"),
            ("words", "Text and word positions"),
            ("meta", "Metadata"),
        ],
        required=True,
    )
    spec = fields.Char(required=True)
    # The job whose result this one is made from (an office file's PDF).
    depends_on_id = fields.Many2one(
        "int_filemanager.derivative", index=True, ondelete="cascade"
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("not_applicable", "Not applicable"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    # May be the source blob itself (a browser shows a JPEG as its own large preview).
    # Empty for text and metadata: those are stored in this row.
    derived_blob_id = fields.Many2one(
        "int_filemanager.blob", index=True, ondelete="restrict"
    )
    mime = fields.Char()
    # The extension the queuing file name had: a hint for the converter.
    hint_ext = fields.Char()
    # Set while the converter is still working on this job (OCR on a scan): Odoo polls
    # instead of blocking. Cleared once a final answer (done or not) is stored.
    converter_job_id = fields.Char()
    priority = fields.Integer(default=0)
    attempts = fields.Integer()
    next_try_at = fields.Datetime()
    lease_until = fields.Datetime()
    started_at = fields.Datetime()
    finished_at = fields.Datetime()
    tool = fields.Char()
    tool_version = fields.Char()
    # Technical text, for administrators only (no user has access to this model).
    error = fields.Char()
    # The text of a document (kinds "text" and "words"; for "words" the same text the
    # word positions in the result blob point into). Empty text means "none found".
    text = fields.Text(index="trigram")
    # The facts of a file (kind "meta"): everything the converter found, and the
    # ones worth filtering and sorting by as columns.
    meta = fields.Json()
    taken_at = fields.Datetime()
    camera = fields.Char()
    width = fields.Integer()
    height = fields.Integer()
    duration = fields.Float()
    gps_lat = fields.Float(digits=(9, 6))
    gps_lon = fields.Float(digits=(9, 6))
    pages = fields.Integer()

    _source_kind_spec_uniq = models.Constraint(
        "UNIQUE(source_blob_id, kind, spec)",
        "This blob already has this derived file.",
    )

    # ------------------------------------------------------------------
    # queue
    # ------------------------------------------------------------------

    @api.model
    def _cron_run(self):
        """Queue the missing jobs, check on slow ones, and work through the rest."""
        params = self.env["ir.config_parameter"].sudo()
        url = params.get_param(CONVERTER_URL_PARAM)
        if not url:
            return
        self._drop_outdated_jobs()
        self._enqueue_missing()
        self._drop_jobs_without_input()
        timeout = int(
            params.get_param(CONVERTER_TIMEOUT_PARAM, DEFAULT_CONVERTER_TIMEOUT_S)
        )
        done_any = self._poll_running_jobs(url, timeout)
        deadline = time.monotonic() + RUN_BUDGET_S
        claim_conflicts = 0
        while time.monotonic() < deadline:
            # A fresh transaction, so the claim below sees what other runs committed
            # (Odoo's REPEATABLE READ would otherwise fail on a row they just took).
            self.env.flush_all()
            self.env["ir.cron"]._commit_progress()
            try:
                jobs = self._claim_jobs()
            except psycopg2.errors.SerializationFailure:
                # Another run took rows of this batch between our snapshot and our
                # lock (SKIP LOCKED does not skip rows changed since the snapshot).
                # Genuine and harmless: start over in a new transaction.
                self.env.cr.rollback()
                self.env.invalidate_all()
                claim_conflicts += 1
                if claim_conflicts > MAX_CLAIM_CONFLICTS:
                    break
                continue
            if not jobs:
                break
            # Everything the calls need is read before the commit: no statement, and so
            # no open transaction, while the converter works.
            plan = [job._call_args() for job in jobs]
            self.env["ir.cron"]._commit_progress()
            fault.fault_point("derivative_after_claim")
            for position, (job, sha256, kind, spec, ext) in enumerate(plan):
                try:
                    done_any |= job._run(url, timeout, sha256, kind, spec, ext)
                except converter_client.ConverterUnavailable as exc:
                    _logger.warning("converter not available: %s", exc)
                    # The rest of this batch was taken but not started: free it now
                    # instead of after its lease.
                    jobs[position + 1 :].write(
                        {"state": "pending", "lease_until": False}
                    )
                    self.env["ir.cron"]._commit_progress()
                    self._notify_ready(done_any)
                    return
                self.env["ir.cron"]._commit_progress(processed=1)
        self._notify_ready(done_any)

    @api.model
    def _enqueue_missing(self):
        """Create the jobs of current revisions that do not have all of theirs yet.

        Done here, not in the write paths, so those stay untouched. Only current
        revisions: an old revision had its results when it was current. A new kind of
        job for a kind of file, or a new spec of one, is caught up the same way: "fewer
        current rows than planned" - rows of an older spec do not count.
        """
        self.env.flush_all()
        cr = self.env.cr
        extensions = derivative_plan.ALL_EXTENSIONS
        planned = [len(derivative_plan.job_plan(f"x.{ext}")) for ext in extensions]
        # What is planned per extension, not for all kinds of file together: a row of a
        # kind that another kind of file plans (the text of a PDF read the old way) must
        # not count as a planned job of this one.
        plan_ext, plan_kind, plan_spec = [], [], []
        for ext in extensions:
            for item in derivative_plan.job_plan(f"x.{ext}"):
                plan_ext.append(ext)
                plan_kind.append(item.kind)
                plan_spec.append(item.spec)
        cr.execute(
            f"""
            SELECT DISTINCT ON (b.id) b.id, n.name
            FROM int_filemanager_node n
            JOIN int_filemanager_revision r ON r.id = n.current_revision_id
            JOIN int_filemanager_blob b ON b.id = r.blob_id
            JOIN unnest(%s::text[], %s::int[]) AS want(ext, n)
                 ON want.ext = {EXTENSION_SQL}
            WHERE n.active AND b.size > 0
              AND (SELECT count(*) FROM int_filemanager_derivative d
                   JOIN unnest(%s::text[], %s::text[], %s::text[])
                        AS plan(ext, kind, spec)
                        ON plan.ext = want.ext
                           AND plan.kind = d.kind AND plan.spec = d.spec
                   WHERE d.source_blob_id = b.id) < want.n
            ORDER BY b.id, n.id
            LIMIT %s
            """,  # noqa: S608 - EXTENSION_SQL is a constant
            [extensions, planned, plan_ext, plan_kind, plan_spec, ENQUEUE_BATCH],
        )
        for blob_id, name in cr.fetchall():
            self._queue_jobs(blob_id, name)

    @api.model
    def _queue_jobs(self, blob_id, name):
        """Create the missing job rows of one blob, by what its file name says it is."""
        ext = derivative_plan.file_extension(name)
        rows = {
            (job.kind, job.spec): job
            for job in self.search_fetch(
                [("source_blob_id", "=", blob_id)], ["kind", "spec"]
            )
        }
        by_kind = {}
        for item in derivative_plan.job_plan(name):
            job = rows.get((item.kind, item.spec))
            if not job:
                values = {
                    "source_blob_id": blob_id,
                    "kind": item.kind,
                    "spec": item.spec,
                    "hint_ext": ext,
                    "priority": item.priority,
                }
                if item.after:
                    values["depends_on_id"] = by_kind[item.after].id
                if item.original_mime:
                    # The original is the result; nothing to convert.
                    values.update(
                        state="done",
                        derived_blob_id=blob_id,
                        mime=item.original_mime,
                        finished_at=fields.Datetime.now(),
                    )
                try:
                    with self.env.cr.savepoint():
                        job = self.create(values)
                except psycopg2.errors.UniqueViolation:
                    # Another run queued it at the same time: use its row.
                    job = self.search(
                        [
                            ("source_blob_id", "=", blob_id),
                            ("kind", "=", item.kind),
                            ("spec", "=", item.spec),
                        ]
                    )
            by_kind[item.kind] = job

    @api.model
    def _request_words(self, blob_id, name):
        """Queue the reading of a picture's text, in front of the rest; return the job.

        A picture is never read without being asked, so this is not part of the plan of
        its file name. A job that gave up is started again.
        """
        domain = [
            ("source_blob_id", "=", blob_id),
            ("kind", "=", "words"),
            ("spec", "=", derivative_plan.WORDS_SPEC),
        ]
        job = self.search(domain)
        if not job:
            try:
                with self.env.cr.savepoint():
                    return self.create(
                        {
                            "source_blob_id": blob_id,
                            "kind": "words",
                            "spec": derivative_plan.WORDS_SPEC,
                            "hint_ext": derivative_plan.file_extension(name),
                            "priority": VISIBLE_PRIORITY,
                        }
                    )
            except psycopg2.errors.UniqueViolation:
                # Another request asked at the same time: use its row.
                job = self.search(domain)
        if job.state in ("failed", "not_applicable"):
            job.write(
                {
                    "state": "pending",
                    "attempts": 0,
                    "next_try_at": False,
                    "lease_until": False,
                    "finished_at": False,
                    "error": False,
                    "priority": VISIBLE_PRIORITY,
                }
            )
        return job

    @api.model
    def _drop_outdated_jobs(self):
        """Delete rows of a (kind, spec) the plan no longer makes.

        Their replacement is queued by ``_enqueue_missing``; a result blob that was only
        theirs is left without a reference and goes with the blob cleanup. Rows still
        running are left until the converter answered. A finished row stays until the
        current row of its kind is finished too, so the text search keeps finding the
        file while it is read again.
        """
        self.env.flush_all()
        kinds, specs = zip(*derivative_plan.CURRENT_JOBS, strict=True)
        self.env.cr.execute(
            """
            DELETE FROM int_filemanager_derivative
            WHERE id IN (
                SELECT old.id FROM int_filemanager_derivative old
                WHERE old.state != 'running'
                  AND (old.kind, old.spec) NOT IN (
                      SELECT * FROM unnest(%s::text[], %s::text[]))
                  AND (old.state != 'done' OR EXISTS (
                      SELECT 1 FROM int_filemanager_derivative new
                      WHERE new.source_blob_id = old.source_blob_id
                        AND new.kind = old.kind
                        AND (new.kind, new.spec) IN (
                            SELECT * FROM unnest(%s::text[], %s::text[]))
                        AND new.state IN ('done', 'not_applicable')))
                LIMIT %s)
            """,
            [list(kinds), list(specs), list(kinds), list(specs), ENQUEUE_BATCH],
        )
        self.env.invalidate_all()

    @api.model
    def _drop_jobs_without_input(self):
        """A job made from another job's result cannot run if that one gave none."""
        self.env.flush_all()
        self.env.cr.execute(
            """
            UPDATE int_filemanager_derivative d
            SET state = 'not_applicable', error = 'the PDF it is made from is missing',
                finished_at = (now() at time zone 'utc')
            FROM int_filemanager_derivative dependency
            WHERE dependency.id = d.depends_on_id
              AND d.state = 'pending'
              AND dependency.state IN ('failed', 'not_applicable')
            """
        )
        self.env.invalidate_all()

    @api.model
    def _claim_jobs(self):
        """Mark open jobs as taken; the caller commits before calling the converter."""
        self.env.flush_all()
        self.env.cr.execute(
            """
            SELECT id FROM int_filemanager_derivative d
            WHERE ((state = 'pending' AND (
                        next_try_at IS NULL
                        OR next_try_at <= (now() at time zone 'utc')))
                   OR (state = 'running'
                       AND lease_until < (now() at time zone 'utc')))
              AND (depends_on_id IS NULL OR EXISTS (
                       SELECT 1 FROM int_filemanager_derivative dependency
                       WHERE dependency.id = d.depends_on_id
                         AND dependency.state = 'done'))
            ORDER BY priority DESC, id
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            [CLAIM_BATCH],
        )
        jobs = self.browse([row[0] for row in self.env.cr.fetchall()])
        if jobs:
            now = fields.Datetime.now()
            jobs.write(
                {
                    "state": "running",
                    "started_at": now,
                    "lease_until": now + timedelta(minutes=LEASE_MINUTES),
                }
            )
        return jobs

    def _call_args(self):
        """What to ask the converter: (job, blob hash, kind, spec, extension hint)."""
        self.ensure_one()
        if self.depends_on_id:
            # Made from the result of another job (an office file's PDF).
            return (
                self,
                self.depends_on_id.derived_blob_id.sha256,
                self.kind,
                self.spec,
                "pdf",
            )
        return (
            self,
            self.source_blob_id.sha256,
            self.kind,
            self.spec,
            self.hint_ext or "",
        )

    def _run(self, url, timeout, sha256, kind, spec, ext):
        """Convert one blob; return True if a result was stored.

        The arguments are read by the caller before its commit, so that no query
        runs (and no transaction is open) while the converter works.
        """
        self.ensure_one()
        try:
            with converter_client.convert(
                url, sha256, kind, spec, ext, timeout
            ) as result:
                if result.state == "done":
                    if kind in ("text", "meta"):
                        return self._store_value(kind, result)
                    return self._store_result(result, kind)
                if result.state == "running":
                    self._mark_running(result.job_id)
                    return False
                self._finish(result)
        except converter_client.ConverterUnavailable:
            # Not the file's fault: hand the job back without counting an attempt.
            self.write({"state": "pending", "lease_until": False})
            raise
        return False

    def _mark_running(self, job_id):
        """Remember the converter's job id; the lease covers it until the next poll."""
        if self.exists():
            self.write(
                {
                    "converter_job_id": job_id,
                    "lease_until": fields.Datetime.now()
                    + timedelta(minutes=LEASE_MINUTES),
                }
            )

    @api.model
    def _poll_running_jobs(self, url, timeout):
        """Check on jobs the converter is still working on; return True if any finished.

        Each row is its own request and its own commit, so one gone missing (its
        source purged, say) or one answer that takes a moment does not hold up the
        others - and a crash here leaves the rest to the next run, not half-done.
        """
        done_any = False
        for job in self.search(
            [("converter_job_id", "!=", False), ("state", "=", "running")]
        ):
            if fields.Datetime.now() - job.started_at > timedelta(
                minutes=MAX_JOB_AGE_MINUTES
            ):
                job.write({"converter_job_id": False})
                job._finish(
                    converter_client.ConversionResult(
                        "failed", error="gave up waiting for the converter"
                    )
                )
                self.env["ir.cron"]._commit_progress()
                continue
            try:
                with converter_client.poll(
                    url, job.converter_job_id, timeout
                ) as result:
                    if result.state == "running":
                        job._mark_running(job.converter_job_id)
                    else:
                        job.write({"converter_job_id": False})
                        if result.state == "done":
                            done_any |= (
                                job._store_value(job.kind, result)
                                if job.kind in ("text", "meta")
                                else job._store_result(result, job.kind)
                            )
                        else:
                            job._finish(result)
            except converter_client.ConverterUnavailable as exc:
                _logger.warning("converter not available while polling: %s", exc)
            self.env["ir.cron"]._commit_progress()
        return done_any

    def _finish(self, result):
        """Record a failure or "not applicable"; retry a failure a few times."""
        if not self.exists():
            return
        values = {
            "tool": result.tool,
            "tool_version": result.tool_version,
            "error": result.error,
            "lease_until": False,
            "finished_at": fields.Datetime.now(),
        }
        if result.state == "failed" and self.attempts + 1 < MAX_ATTEMPTS:
            wait = timedelta(minutes=2 ** (self.attempts + 1))
            values.update(
                state="pending",
                attempts=self.attempts + 1,
                next_try_at=fields.Datetime.now() + wait,
            )
        else:
            values.update(state=result.state, attempts=self.attempts + 1)
        self.write(values)

    def _store_result(self, result, kind):
        """Store the converter's bytes as a blob and link them to this job.

        Same order as a user upload: the file is linked under its hash first,
        the database row follows in a short transaction, the temp file is kept
        until after the commit so the cleanup job cannot take the blob away.
        """
        tmp_path = blobstore.write_stream_to_temp(
            self.env, result.stream, f"derivative_{self.id}_{uuid.uuid4().hex}"
        )
        try:
            sha256, size = blobstore.hash_file(tmp_path)
            text = self._words_text(tmp_path, size) if kind == "words" else False
            blobstore.adopt_hashed(self.env, tmp_path, sha256, keep_tmp=True)
            fault.fault_point("derivative_after_link")
            blob = self.env["int_filemanager.blob"]._get_or_create(sha256, size)
            blobstore.ensure_on_disk(self.env, sha256, tmp_path)
            stored = bool(self.exists())
            if stored:
                # The job may be gone (its source was purged meanwhile); then the
                # blob stays unreferenced and the cleanup job removes it.
                self.write(
                    {
                        "state": "done",
                        "derived_blob_id": blob.id,
                        "mime": result.mime,
                        "tool": result.tool,
                        "tool_version": result.tool_version,
                        "error": False,
                        "lease_until": False,
                        "finished_at": fields.Datetime.now(),
                        "text": text,
                    }
                )
            self.env["ir.cron"]._commit_progress()
            return stored
        finally:
            blobstore.remove_if_exists(tmp_path)

    @staticmethod
    def _words_text(path, size):
        """The text part of the converter's word list, for search and value recognition.

        The word list is the converter's own JSON, not a foreign file. False if it is
        larger than any answer of the converter can be, or not what it sends; the word
        list itself is still kept.
        """
        if size > MAX_WORDS_BYTES:
            _logger.warning("word list of %d bytes not read for its text", size)
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except ValueError:
            return False
        text = data.get("text") if isinstance(data, dict) else None
        # A NUL cannot go into the database; the converter already replaces it, so
        # this keeps every position the same even for a list that slipped through.
        return text.replace("\x00", "�") if isinstance(text, str) else False

    @staticmethod
    def _read_limited(stream, limit):
        """Read the converter's answer, refusing an unreasonably long one."""
        chunks, total = [], 0
        while chunk := stream.read(64 * 1024):
            total += len(chunk)
            if total > limit:
                raise converter_client.ConverterUnavailable(
                    "the converter's answer is longer than allowed"
                )
            chunks.append(chunk)
        return b"".join(chunks)

    def _store_value(self, kind, result):
        """Keep the text or the facts the converter found in this row.

        Its own protocol, not a foreign file: plain UTF-8 text and a small JSON object.
        """
        if kind == "text":
            data = self._read_limited(result.stream, MAX_TEXT_BYTES)
            values = {
                "text": data.decode("utf-8", errors="replace").replace("\x00", "")
            }
        else:
            data = self._read_limited(result.stream, MAX_META_BYTES)
            values = self._meta_values(data)
        if not self.exists():
            return False
        self.write(
            {
                **values,
                "state": "done",
                "mime": result.mime,
                "tool": result.tool,
                "tool_version": result.tool_version,
                "error": False,
                "lease_until": False,
                "finished_at": fields.Datetime.now(),
            }
        )
        return True

    @staticmethod
    def _meta_values(data):
        """The values of the meta columns from the converter's JSON; junk is dropped."""
        try:
            found = json.loads(data.decode("utf-8", errors="replace"))
        except ValueError:
            found = {}
        if not isinstance(found, dict):
            found = {}
        clean = {}
        for key, value in list(found.items())[:META_KEYS_MAX]:
            if isinstance(value, bool) or not isinstance(value, str | int | float):
                continue
            if isinstance(value, str):
                value = value[:META_STRING_MAX]
            clean[str(key)[:40]] = value

        def integer(key):
            value = clean.get(key)
            ok = isinstance(value, int) and 0 <= value <= INT4_MAX
            return value if ok else False

        def number(key):
            value = clean.get(key)
            return float(value) if isinstance(value, int | float) else False

        taken = clean.get("taken_at")
        values = {
            "meta": clean,
            "camera": clean.get("camera")
            if isinstance(clean.get("camera"), str)
            else False,
            "width": integer("width"),
            "height": integer("height"),
            "pages": integer("pages"),
            "duration": number("duration"),
            "gps_lat": number("gps_lat"),
            "gps_lon": number("gps_lon"),
            "taken_at": False,
        }
        if isinstance(taken, str):
            with contextlib.suppress(ValueError):
                values["taken_at"] = fields.Datetime.to_datetime(taken)
        return values

    @api.model
    def _notify_ready(self, done_any):
        """Tell open explorers to look again; carries no data of its own."""
        if done_any:
            self.env["bus.bus"]._sendone(
                self.env.ref("int_filemanager.group_filemanager_user"),
                "int_filemanager_preview_ready",
                {},
            )

    # ------------------------------------------------------------------
    # what the explorer asks for
    # ------------------------------------------------------------------

    @api.model
    def _result_for_blob(self, blob, kind):
        """Return the finished job of ``blob`` for ``kind``, or an empty recordset."""
        return self.sudo().search(
            [
                ("source_blob_id", "=", blob.id),
                ("kind", "=", kind),
                ("state", "=", "done"),
                ("derived_blob_id", "!=", False),
            ],
            limit=1,
        )
