"""Converter service: turns a blob of the blob store into a derived file.

Small HTTP service without any network access of its own. It mounts the blob
store read-only, reads the blob by its hash, runs the conversion in a
separate, resource-limited process and answers with the result bytes. It
writes nothing outside its private work directory.

POST /convert  {"sha256": ..., "kind": "tile", "spec": "400x300", "ext": "cr2"}
  200 <type of kind>  the result: image/jpeg (tile, preview), application/pdf
                      (preview_pdf), text/plain (text), application/json (meta)
  422 {"state": "not_applicable" | "failed", "error": ...}
  503                 too many jobs at once (try again later)
GET  /health        200 "ok"
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

BLOB_ROOT = os.environ.get("CONVERTER_BLOB_ROOT", "/blobs")
JOB_TIMEOUT_S = int(os.environ.get("CONVERTER_JOB_TIMEOUT_S", "60"))
OFFICE_TIMEOUT_S = int(os.environ.get("CONVERTER_OFFICE_TIMEOUT_S", "150"))
MAX_JOBS = int(os.environ.get("CONVERTER_MAX_JOBS", "2"))
# LibreOffice starts badly when several run at once.
MAX_OFFICE_JOBS = int(os.environ.get("CONVERTER_MAX_OFFICE_JOBS", "1"))
MEMORY_LIMIT = int(os.environ.get("CONVERTER_MEMORY_LIMIT_MB", "2048")) * 1024 * 1024
OFFICE_MEMORY_LIMIT = int(os.environ.get("CONVERTER_OFFICE_MEMORY_LIMIT_MB", "8192")) * 1024 * 1024
MAX_RESULT_BYTES = 50 * 1024 * 1024
MAX_EDGE = 4096
TOOL = "pillow"

SHA256_RE = re.compile(r"[0-9a-f]{64}")
SPEC_RE = re.compile(r"([0-9]{2,4})x([0-9]{2,4})")
EXT_RE = re.compile(r"[a-z0-9]{0,8}")
LABEL_RE = re.compile(r"[a-z0-9_]{1,16}")
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker.py")
EXIT_STATES = {0: "done", 10: "not_applicable", 11: "failed"}
CONTENT_TYPES = {
    "tile": "image/jpeg",
    "preview": "image/jpeg",
    "preview_pdf": "application/pdf",
    "text": "text/plain; charset=utf-8",
    "meta": "application/json",
}

slots = threading.BoundedSemaphore(MAX_JOBS)
office_slots = threading.BoundedSemaphore(MAX_OFFICE_JOBS)


def blob_path(sha256):
    return os.path.join(BLOB_ROOT, sha256[0:2], sha256[2:4], sha256)


def _limiter(memory, seconds):
    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (seconds + 5, seconds + 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_RESULT_BYTES, MAX_RESULT_BYTES))

    return limits


def run_worker(source, kind, spec, ext):
    """Return (state, error, tool_version, result path or None, workdir)."""
    office = kind == "preview_pdf"
    timeout = OFFICE_TIMEOUT_S if office else JOB_TIMEOUT_S
    memory = OFFICE_MEMORY_LIMIT if office else MEMORY_LIMIT
    workdir = tempfile.mkdtemp(prefix="conv_")
    output = os.path.join(workdir, "result.out")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": workdir,
        # each tool inside the worker gets a share of the whole limit
        "CONVERTER_TOOL_TIMEOUT_S": str(timeout - 10 if office else timeout // 2),
    }
    for name, value in os.environ.items():
        if name.startswith("CONVERTER_MAX_"):
            env[name] = value
    try:
        proc = subprocess.run(
            [sys.executable, WORKER, source, kind, spec, ext, output],
            cwd=workdir,
            env=env,
            capture_output=True,
            timeout=timeout,
            preexec_fn=_limiter(memory, timeout),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "failed", "timeout", "", None, workdir
    state = EXIT_STATES.get(proc.returncode)
    info = {}
    try:
        info = json.loads(proc.stdout.decode().strip().splitlines()[-1])
    except (ValueError, IndexError):
        pass
    if state is None:
        # Killed by a signal or a limit (memory, CPU, file size).
        return "failed", f"worker exited with {proc.returncode}", "", None, workdir
    return (
        state,
        info.get("error", ""),
        info.get("tool_version", ""),
        output if state == "done" else None,
        workdir,
    )


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

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self._json(404, {"error": "not found"})

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
        source = blob_path(sha256)
        if not os.path.isfile(source):
            return self._json(
                422, {"state": "failed", "error": "source blob not found", "tool": TOOL}
            )
        slot = office_slots if kind == "preview_pdf" else slots
        if not slot.acquire(blocking=False):
            return self._json(503, {"error": "busy"})
        workdir = None
        try:
            state, error, version, result, workdir = run_worker(source, kind, spec, ext)
            if state != "done":
                return self._json(
                    422,
                    {
                        "state": state,
                        "error": error,
                        "tool": TOOL,
                        "tool_version": version,
                    },
                )
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPES[kind])
            self.send_header("Content-Length", str(os.path.getsize(result)))
            self.send_header("X-Converter-Tool", TOOL)
            self.send_header("X-Converter-Tool-Version", version)
            self.end_headers()
            with open(result, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
        finally:
            slot.release()
            if workdir:
                shutil.rmtree(workdir, ignore_errors=True)


def main():
    port = int(os.environ.get("CONVERTER_PORT", "8090"))
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
