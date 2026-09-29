"""Client of the converter service.

The converter is a separate container with read-only access to the blob store
(the only place that opens foreign file bytes). Odoo sends it the hash of a
blob and gets the result back as a byte stream, which is stored without ever
being decoded here.
"""

import contextlib
import dataclasses
import logging

import requests
import urllib3

_logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_S = 5
# What the converter may declare as the type of a result; anything else is refused
# so that a result is never served with a type of the converter's choosing.
ALLOWED_MIMES = {"image/jpeg", "application/pdf", "text/plain", "application/json"}


class ConverterUnavailable(Exception):
    """The converter could not be reached or answered with a server error.

    Not the file's fault: the job stays open for a later run.
    """


class _GuardedStream:
    """Read the result body; a broken connection counts as "converter unavailable"."""

    def __init__(self, raw):
        self._raw = raw

    def read(self, size=-1):  # pylint: disable=unknown-option-value,method-required-super
        try:
            return self._raw.read(size)
        except (OSError, urllib3.exceptions.HTTPError) as exc:
            raise ConverterUnavailable(str(exc)) from exc


@dataclasses.dataclass
class ConversionResult:
    # "done", "not_applicable", "failed" or "running" (still working: poll ``job_id``)
    state: str
    stream: object = None
    mime: str = ""
    tool: str = ""
    tool_version: str = ""
    error: str = ""
    job_id: str = ""


def _interpret(response):
    """A finished (200/422) or still-running (202) answer as a ConversionResult."""
    if response.status_code == 200:
        mime = response.headers.get("Content-Type", "").split(";")[0].strip()
        if mime not in ALLOWED_MIMES:
            return ConversionResult(
                "failed", error=f"converter returned an unexpected type {mime!r}"
            )
        return ConversionResult(
            "done",
            stream=_GuardedStream(response.raw),
            mime=mime,
            tool=response.headers.get("X-Converter-Tool", ""),
            tool_version=response.headers.get("X-Converter-Tool-Version", ""),
        )
    if response.status_code == 422:
        try:
            body = response.json()
        except ValueError:
            body = {}
        state = body.get("state")
        return ConversionResult(
            state if state in ("not_applicable", "failed") else "failed",
            error=str(body.get("error", ""))[:500],
            tool=str(body.get("tool", "")),
            tool_version=str(body.get("tool_version", "")),
        )
    if response.status_code == 202:
        try:
            body = response.json()
        except ValueError:
            body = {}
        job_id = str(body.get("job_id", ""))
        return ConversionResult("running", job_id=job_id) if job_id else None
    return None


@contextlib.contextmanager
def convert(url, sha256, kind, spec, ext, timeout):
    """Ask the converter for ``kind``/``spec`` of the blob ``sha256``.

    ``ext`` is the file name extension the caller knows: a hint for the converter.

    Yields a ConversionResult; for state "done" its ``stream`` is a file-like
    object that is only valid inside the ``with`` block. State "running" means the
    conversion is taking a while (OCR on a scan): the caller polls ``job_id`` with
    ``poll()`` on a later run instead of waiting for it here.
    """
    try:
        response = requests.post(
            f"{url.rstrip('/')}/convert",
            json={"sha256": sha256, "kind": kind, "spec": spec, "ext": ext},
            stream=True,
            timeout=(CONNECT_TIMEOUT_S, timeout),
        )
    except requests.RequestException as exc:
        raise ConverterUnavailable(str(exc)) from exc
    try:
        result = _interpret(response)
        if result is None:
            raise ConverterUnavailable(f"converter answered {response.status_code}")
        yield result
    finally:
        response.close()


@contextlib.contextmanager
def poll(url, job_id, timeout):
    """Ask whether an earlier "running" job finished; same result shape as convert()."""
    try:
        response = requests.get(
            f"{url.rstrip('/')}/convert/{job_id}",
            stream=True,
            timeout=(CONNECT_TIMEOUT_S, timeout),
        )
    except requests.RequestException as exc:
        raise ConverterUnavailable(str(exc)) from exc
    try:
        if response.status_code == 404:
            # The converter no longer knows this job (restarted, or already
            # collected): not the file's fault, but there is nothing to resume -
            # the caller's own lease will time out and the job is resubmitted fresh.
            raise ConverterUnavailable(f"converter has no job {job_id!r} any more")
        result = _interpret(response)
        if result is None:
            raise ConverterUnavailable(f"converter answered {response.status_code}")
        yield result
    finally:
        response.close()
