"""Converter service: turns a blob of the blob store into a derived file.

Small HTTP service without any network access of its own. It mounts the blob
store read-only, reads the blob by its hash, runs the conversion in a
separate, resource-limited process and answers with the result bytes. It
writes nothing outside its private work directory.

POST /convert  {"sha256": ..., "kind": "tile", "spec": "400x300", "ext": "cr2"}
  200 <type of kind>  the result: image/jpeg (tile, preview), application/pdf
                      (preview_pdf), text/plain (text), application/json
                      (meta, words)
  202 {"job_id": ...} the conversion is taking a while (OCR on a scan): poll
                      GET /convert/<job_id> for the outcome instead of waiting
  422 {"state": "not_applicable" | "failed", "error": ...}
  503                 too many jobs at once (try again later)
GET  /convert/<job_id>
  200 / 422           same as above, once the job is done
  202 {"state": "running"}
  404                 unknown job id (already collected, expired, or the
                      service restarted and forgot it - the caller should
                      treat this like a job it never heard back from)
GET  /health         200 "ok"
"""

import http.server
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

BLOB_ROOT = os.environ.get("CONVERTER_BLOB_ROOT", "/blobs")
JOB_TIMEOUT_S = int(os.environ.get("CONVERTER_JOB_TIMEOUT_S", "60"))
OFFICE_TIMEOUT_S = int(os.environ.get("CONVERTER_OFFICE_TIMEOUT_S", "150"))
# Generous: covers OCR of a long, scanned document (measured ~15 min for 2000 pages),
# and matches Odoo's own recommended cron real-time limit (1800s).
WORDS_TIMEOUT_S = int(os.environ.get("CONVERTER_WORDS_TIMEOUT_S", "1800"))
# A request waits inline this long before it is handed off to the background and
# answered with a job id instead - comfortably above every kind's normal duration
# except OCR, so nothing else ever actually experiences the async path.
WAIT_BUDGET_S = int(os.environ.get("CONVERTER_WAIT_BUDGET_S", "15"))
# How long a finished-but-uncollected job, or a job id nobody ever asks about
# again, is kept before it is swept away.
JOB_TTL_S = int(os.environ.get("CONVERTER_JOB_TTL_S", "3600"))
MAX_JOBS = int(os.environ.get("CONVERTER_MAX_JOBS", "2"))
# LibreOffice starts badly when several run at once.
MAX_OFFICE_JOBS = int(os.environ.get("CONVERTER_MAX_OFFICE_JOBS", "1"))
# OCRmyPDF already parallelises internally across every core it is given; running
# more than one at a time would oversubscribe the machine for no benefit.
MAX_WORDS_JOBS = int(os.environ.get("CONVERTER_MAX_WORDS_JOBS", "1"))
MEMORY_LIMIT = int(os.environ.get("CONVERTER_MEMORY_LIMIT_MB", "2048")) * 1024 * 1024
OFFICE_MEMORY_LIMIT = int(os.environ.get("CONVERTER_OFFICE_MEMORY_LIMIT_MB", "8192")) * 1024 * 1024
WORDS_MEMORY_LIMIT = int(os.environ.get("CONVERTER_WORDS_MEMORY_LIMIT_MB", "4096")) * 1024 * 1024
MAX_RESULT_BYTES = 50 * 1024 * 1024
# OCRmyPDF can write a large repaired/linearised copy of the source next to the small
# JSON it finally answers with (Odoo bounds the JSON itself, separately, on its side);
# a scan can be sizeable, so this ceiling is generous, not tied to the answer size.
WORDS_MAX_FILE_BYTES = (
    int(os.environ.get("CONVERTER_WORDS_MAX_FILE_MB", "2048")) * 1024 * 1024
)
MAX_EDGE = 4096
TOOL = "pillow"

SHA256_RE = re.compile(r"[0-9a-f]{64}")
SPEC_RE = re.compile(r"([0-9]{2,4})x([0-9]{2,4})")
EXT_RE = re.compile(r"[a-z0-9]{0,8}")
LABEL_RE = re.compile(r"[a-z0-9_]{1,16}")
JOB_ID_RE = re.compile(r"[0-9a-f]{32}")
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker.py")
EXIT_STATES = {0: "done", 10: "not_applicable", 11: "failed"}
CONTENT_TYPES = {
    "tile": "image/jpeg",
    "preview": "image/jpeg",
    "preview_pdf": "application/pdf",
    "text": "text/plain; charset=utf-8",
    "words": "application/json",
    "meta": "application/json",
}

slots = threading.BoundedSemaphore(MAX_JOBS)
office_slots = threading.BoundedSemaphore(MAX_OFFICE_JOBS)
words_slots = threading.BoundedSemaphore(MAX_WORDS_JOBS)

# job_id -> dict with the running/finished conversion; guarded by jobs_lock. A job is
# only ever touched by its own collector thread and by request handlers, never by two
# collector threads at once.
jobs = {}
jobs_lock = threading.Lock()


def blob_path(sha256):
    return os.path.join(BLOB_ROOT, sha256[0:2], sha256[2:4], sha256)


def _limiter(memory, seconds, max_file_bytes):
    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (seconds + 5, seconds + 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (max_file_bytes, max_file_bytes))

    return limits


def _tier(kind):
    """(timeout, memory limit, max file size, semaphore) for this kind of job."""
    if kind == "preview_pdf":
        return OFFICE_TIMEOUT_S, OFFICE_MEMORY_LIMIT, MAX_RESULT_BYTES, office_slots
    if kind == "words":
        # OCRmyPDF can write a large repaired copy of the source before it ever gets
        # to the small JSON answer; the other kinds never legitimately need more than
        # the normal result-size ceiling.
        return WORDS_TIMEOUT_S, WORDS_MEMORY_LIMIT, WORDS_MAX_FILE_BYTES, words_slots
    return JOB_TIMEOUT_S, MEMORY_LIMIT, MAX_RESULT_BYTES, slots


def _start_worker(source, kind, spec, ext, timeout, memory, max_file_bytes):
    """Start the conversion as a subprocess; return (Popen, workdir, output path)."""
    workdir = tempfile.mkdtemp(prefix="conv_")
    output = os.path.join(workdir, "result.out")
    if kind == "words":
        tool_timeout = timeout - 30
    elif kind == "preview_pdf":
        tool_timeout = timeout - 10
    else:
        tool_timeout = timeout // 2
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": workdir,
        # Quick helper tools (pdfinfo, ffprobe, ...) inside the worker get a share of
        # the whole budget; the one slow tool a kind may run (OCRmyPDF, LibreOffice)
        # gets almost all of it.
        "CONVERTER_TOOL_TIMEOUT_S": str(tool_timeout),
        "CONVERTER_OCR_TOOL_TIMEOUT_S": str(max(timeout - 60, 30)),
    }
    for name, value in os.environ.items():
        if name.startswith("CONVERTER_MAX_") or name.startswith("CONVERTER_OCR_"):
            env[name] = value
    proc = subprocess.Popen(  # noqa: S603 - argument list, no shell
        [sys.executable, WORKER, source, kind, spec, ext, output],
        cwd=workdir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=_limiter(memory, timeout, max_file_bytes),  # noqa: PLW1509
    )
    return proc, workdir, output


def _collect(proc, workdir, output, timeout):
    """Wait for the subprocess (killing it if it overruns) and read its outcome."""
    try:
        stdout, _stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return "failed", "timeout", "", None, workdir
    state = EXIT_STATES.get(proc.returncode)
    info = {}
    try:
        info = json.loads(stdout.decode().strip().splitlines()[-1])
    except (ValueError, IndexError):
        pass
    if state is None:
        # Killed by a signal or a limit (memory, CPU, file size).
        return "failed", f"worker exited with {proc.returncode}", "", None, workdir
    return (
        state,
        info.get("error", ""),
        info.get("tool_version", ""),
        info.get("tool") or None,
        output if state == "done" else None,
        workdir,
    )


def _sweep_expired():
    """Forget jobs nobody ever asked about again; a delivered job is already gone
    (do_GET removes it on its one and only successful poll)."""
    now = time.monotonic()
    for job_id, job in list(jobs.items()):
        if now - job["started_at"] > JOB_TTL_S:
            result = job.get("result")
            if result and result[4]:
                # A finished result nobody ever collected: its workdir outlived it.
                shutil.rmtree(result[5], ignore_errors=True)
            del jobs[job_id]


def _run_job(job_id, kind, slot, proc, workdir, output, timeout):
    """Collector: waits for the process, stores the outcome, frees the slot."""
    result = _collect(proc, workdir, output, timeout)
    slot.release()
    with jobs_lock:
        job = jobs.get(job_id)
        if job is not None:
            job["result"] = result
            job["done_at"] = time.monotonic()
    if result[4]:
        # The result stays on disk until a GET has streamed it out (or it expires).
        return
    shutil.rmtree(workdir, ignore_errors=True)


def submit(sha256, kind, spec, ext):
    """Start a conversion; return ("result", <outcome tuple>) or ("job", job_id)."""
    source = blob_path(sha256)
    if not os.path.isfile(source):
        return "result", ("failed", "source blob not found", "", None, None, None)
    timeout, memory, max_file_bytes, slot = _tier(kind)
    if not slot.acquire(blocking=False):
        return "busy", None
    proc, workdir, output = _start_worker(
        source, kind, spec, ext, timeout, memory, max_file_bytes
    )
    # Never wait inline longer than the job's own timeout: a kind whose whole budget
    # is short (tile/preview, or a test with a patched-down timeout) still fails
    # synchronously exactly at that timeout, instead of being handed to a collector
    # thread with nothing left to give it.
    wait = min(WAIT_BUDGET_S, timeout)
    try:
        stdout, _stderr = proc.communicate(timeout=wait)
    except subprocess.TimeoutExpired:
        remaining = timeout - wait
        if remaining <= 0:
            proc.kill()
            proc.communicate()
            slot.release()
            shutil.rmtree(workdir, ignore_errors=True)
            return "result", ("failed", "timeout", "", None, None, None)
        # Still running, and there is time left to give it: hand it to a collector
        # thread and answer with a job id instead of blocking the caller further.
        job_id = uuid.uuid4().hex
        with jobs_lock:
            _sweep_expired()
            jobs[job_id] = {"started_at": time.monotonic(), "result": None}
        threading.Thread(
            target=_run_job,
            args=(job_id, kind, slot, proc, workdir, output, remaining),
            daemon=True,
        ).start()
        return "job", job_id
    state = EXIT_STATES.get(proc.returncode)
    info = {}
    try:
        info = json.loads(stdout.decode().strip().splitlines()[-1])
    except (ValueError, IndexError):
        pass
    slot.release()
    if state is None:
        result = ("failed", f"worker exited with {proc.returncode}", "", None, None, workdir)
    else:
        result = (
            state,
            info.get("error", ""),
            info.get("tool_version", ""),
            info.get("tool") or None,
            output if state == "done" else None,
            workdir,
        )
    if not result[4]:
        shutil.rmtree(workdir, ignore_errors=True)
    return "result", result


def run_worker(source, kind, spec, ext):
    """Run one conversion to completion, ignoring the async job protocol.

    For tests and tools/fmconverter/run_formats.py: waits out the kind's own full
    timeout inline instead of ever answering with a job id.
    Returns (state, error, tool_version, tool, result path or None, workdir).
    """
    timeout, memory, max_file_bytes, _slot = _tier(kind)
    proc, workdir, output = _start_worker(
        source, kind, spec, ext, timeout, memory, max_file_bytes
    )
    return _collect(proc, workdir, output, timeout)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "fmconverter"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.address_string()} {fmt % args}\n")

    def _json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_result(self, kind, result):
        """Answer a finished ("state", error, version, tool, result_path, workdir)."""
        state, error, version, tool, path, workdir = result
        try:
            if state != "done":
                return self._json(
                    422,
                    {
                        "state": state,
                        "error": error,
                        "tool": tool or TOOL,
                        "tool_version": version,
                    },
                )
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPES.get(kind, "application/octet-stream"))
            self.send_header("Content-Length", str(os.path.getsize(path)))
            self.send_header("X-Converter-Tool", tool or TOOL)
            self.send_header("X-Converter-Tool-Version", version)
            self.end_headers()
            with open(path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
        finally:
            if workdir:
                shutil.rmtree(workdir, ignore_errors=True)

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if self.path.startswith("/convert/"):
            job_id = self.path[len("/convert/") :]
            if not JOB_ID_RE.fullmatch(job_id):
                return self._json(404, {"error": "not found"})
            with jobs_lock:
                job = jobs.get(job_id)
                if job is None:
                    return self._json(404, {"error": "not found"})
                result = job["result"]
                kind = job.get("kind")
                if result is not None:
                    # Delivered exactly once; a second poll for the same id is 404.
                    del jobs[job_id]
            if result is None:
                return self._json(202, {"state": "running"})
            return self._send_result(kind, result)
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/convert":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(min(length, 4096)))
            sha256, kind, spec = request["sha256"], request["kind"], request["spec"]
            ext = str(request.get("ext", "")).lower()
            if (
                not SHA256_RE.fullmatch(sha256)
                or not EXT_RE.fullmatch(ext)
                or kind not in CONTENT_TYPES
            ):
                raise ValueError("bad request")
            if kind in ("tile", "preview"):
                # A picture spec is the box to fit into.
                match = SPEC_RE.fullmatch(spec)
                if not match or max(int(match[1]), int(match[2])) > MAX_EDGE:
                    raise ValueError("bad size")
            elif not LABEL_RE.fullmatch(spec):
                raise ValueError("bad spec")
        except (ValueError, KeyError, TypeError):
            return self._json(400, {"error": "bad request"})
        outcome, payload = submit(sha256, kind, spec, ext)
        if outcome == "busy":
            return self._json(503, {"error": "busy"})
        if outcome == "job":
            with jobs_lock:
                jobs[payload]["kind"] = kind
            return self._json(202, {"job_id": payload})
        return self._send_result(kind, payload)


def main():
    port = int(os.environ.get("CONVERTER_PORT", "8090"))
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
