import logging
import math
import time
from urllib.parse import urlparse

import requests
from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PARAM_URL = "int_ui_showcase.icecast_url"
FETCH_TIMEOUT = 3
TITLE_SECONDS = 45

# mount, name, base listeners, bitrate, type, titles in rotation
DEMO_MOUNTS = (
    (
        "/gottesdienst",
        "Gottesdienst live",
        18,
        128,
        "audio/mpeg",
        ("Befiehl du deine Wege", "Großer Gott, wir loben dich", "Nun danket alle Gott"),
    ),
    (
        "/gottesdienst-low",
        "Gottesdienst (mobil)",
        9,
        48,
        "audio/mpeg",
        ("Befiehl du deine Wege", "Großer Gott, wir loben dich", "Nun danket alle Gott"),
    ),
    (
        "/jugend",
        "Jugendstunde",
        6,
        96,
        "application/ogg",
        ("Lobe den Herren", "Chorstück Eins"),
    ),
)


# === PAYLOAD === #


def _to_int(value):
    """Return ``value`` as an integer, or 0 if it is not a number."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def normalize_icestats(payload):
    """Return the mounts and totals of an Icecast ``status-json.xsl`` payload.

    Icecast writes ``source`` as an object for one mount, as a list for several and leaves it
    out when no source is connected.
    """
    stats = (payload or {}).get("icestats") or {}
    sources = stats.get("source") or []
    if isinstance(sources, dict):
        sources = [sources]
    mounts = []
    for source in sources:
        title = source.get("title") or ""
        artist = source.get("artist") or ""
        if artist and artist not in title:
            title = f"{artist} - {title}" if title else artist
        mounts.append(
            {
                "mount": urlparse(source.get("listenurl") or "").path or "/",
                "name": source.get("server_name") or "",
                "title": title,
                "listeners": _to_int(source.get("listeners")),
                "peak": _to_int(source.get("listener_peak")),
                "bitrate": _to_int(source.get("bitrate")),
                "type": source.get("server_type") or "",
            }
        )
    mounts.sort(key=lambda mount: mount["mount"])
    return {
        "server": stats.get("server_id") or "",
        "mounts": mounts,
        "listeners": sum(mount["listeners"] for mount in mounts),
        "peak": sum(mount["peak"] for mount in mounts),
    }


def demo_icestats(now):
    """Return a payload in the shape of ``status-json.xsl``, with listeners and titles that move."""
    sources = []
    for index, (mount, name, base, bitrate, kind, titles) in enumerate(DEMO_MOUNTS):
        wave = round(3 * math.sin(now / 25 + index * 2))
        sources.append(
            {
                "listenurl": f"http://icecast.example:8000{mount}",
                "server_name": name,
                "listeners": base + wave,
                "listener_peak": base + 4,
                "title": titles[int(now // TITLE_SECONDS) % len(titles)],
                "bitrate": bitrate,
                "server_type": kind,
            }
        )
    return {"icestats": {"server_id": "Icecast 2.4.4 (demo)", "source": sources}}


# === CONTROLLER === #


class IntUiShowcaseIcecast(http.Controller):
    @http.route("/int_ui_showcase/icecast/status", type="jsonrpc", auth="user", methods=["POST"], readonly=True)
    def icecast_status(self):
        """Return the Icecast overview: live from the configured server, otherwise demo data.

        The browser never talks to Icecast: the server may need credentials, and a browser
        request to another host fails on CORS.
        """
        if not request.env.user._is_internal():
            raise Forbidden()
        # sudo: ir.config_parameter: an internal user may not read system parameters; the
        # Icecast URL is the only value read.
        url = request.env["ir.config_parameter"].sudo().get_param(PARAM_URL)
        result = {"demo": not url, "error": None, "checked_at": time.time()}
        if not url:
            return {**result, **normalize_icestats(demo_icestats(result["checked_at"]))}
        try:
            response = requests.get(url.rstrip("/") + "/status-json.xsl", timeout=FETCH_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            _logger.warning("Icecast status at %s is not readable", url, exc_info=True)
            result["error"] = request.env._("Icecast is not reachable.")
            payload = None
        return {**result, **normalize_icestats(payload)}
