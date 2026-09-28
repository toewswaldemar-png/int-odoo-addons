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
ALLOWED_MIMES = {"image/jpeg", "image/png", "application/pdf", "text/plain"}


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
    # "done", "not_applicable" or "failed"
    state: str
    stream: object = None
    mime: str = ""
    tool: str = ""
    tool_version: str = ""
    error: str = ""


@contextlib.contextmanager
def convert(url, sha256, kind, spec, timeout):
    """Ask the converter for ``kind``/``spec`` of the blob ``sha256``.

    Yields a ConversionResult; for state "done" its ``stream`` is a file-like
    object that is only valid inside the ``with`` block.
    """
    try:
        response = requests.post(
            f"{url.rstrip('/')}/convert",
            json={"sha256": sha256, "kind": kind, "spec": spec},
            stream=True,
            timeout=(CONNECT_TIMEOUT_S, timeout),
        )
    except requests.RequestException as exc:
        raise ConverterUnavailable(str(exc)) from exc
    try:
        if response.status_code == 200:
            mime = response.headers.get("Content-Type", "").split(";")[0].strip()
            if mime not in ALLOWED_MIMES:
                yield ConversionResult(
                    "failed", error=f"converter returned an unexpected type {mime!r}"
                )
                return
            yield ConversionResult(
                "done",
                stream=_GuardedStream(response.raw),
                mime=mime,
                tool=response.headers.get("X-Converter-Tool", ""),
                tool_version=response.headers.get("X-Converter-Tool-Version", ""),
            )
        elif response.status_code == 422:
            try:
                body = response.json()
            except ValueError:
                body = {}
            state = body.get("state")
            yield ConversionResult(
                state if state in ("not_applicable", "failed") else "failed",
                error=str(body.get("error", ""))[:500],
                tool=str(body.get("tool", "")),
                tool_version=str(body.get("tool_version", "")),
            )
        else:
            raise ConverterUnavailable(f"converter answered {response.status_code}")
    finally:
        response.close()
