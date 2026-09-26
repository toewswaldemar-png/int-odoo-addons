"""Prototyp WebDAV-Dienst neben Odoo (int_filemanager 2, Konzept 11 A).

WsgiDAV spricht das Protokoll (PROPFIND, LOCK, Windows-/Office-Eigenheiten). Dieser Provider uebersetzt nur:
jede Operation wird im Namen des Nutzers an Odoo weitergereicht (Bearer-API-Schluessel), Odoo prueft Rechte und
schreibt (I1). Grosse PUTs werden gestreamt und in 4-MB-Stuecken an Odoo gegeben (Odoo liest Bodies ganz in den
RAM, Konzept 19.2). GET wird von Odoo per x_sendfile ueber nginx geliefert und hier nur durchgereicht.

Anmeldung: Basic mit Odoo-Login und API-Schluessel als Passwort (nur ueber HTTPS sinnvoll). Nur fuer Tests auf der
Testinstanz: anonymer Zugriff fuer einzelne IPs (FM_DAV_ANON_IPS) mit festem Test-Schluessel, weil der
Windows-WebClient Basic ueber HTTP ablehnt (BasicAuthLevel=1) und hier kein vertrautes Zertifikat vorliegt.
"""
import hashlib
import io
import logging
import mimetypes
import os
import threading
import time
import uuid
from urllib.parse import quote

import requests
from wsgidav import util
from wsgidav.dav_error import (
    HTTP_BAD_REQUEST, HTTP_CONFLICT, HTTP_FORBIDDEN, HTTP_INTERNAL_ERROR, HTTP_METHOD_NOT_ALLOWED,
    HTTP_NOT_FOUND, HTTP_PRECONDITION_FAILED, DAVError,
)
from wsgidav.dav_provider import DAVCollection, DAVNonCollection, DAVProvider
from wsgidav.dc.base_dc import BaseDomainController
from wsgidav.wsgidav_app import WsgiDAVApp

_logger = logging.getLogger("fmdav")

ODOO = os.environ.get("FM_ODOO_URL", "http://fmv2_nginx:8081").rstrip("/")
ROOT = int(os.environ["FM_DAV_ROOT_ID"])
ANON_IPS = {ip for ip in os.environ.get("FM_DAV_ANON_IPS", "").split(",") if ip}
ANON_KEY = os.environ.get("FM_DAV_ANON_KEY", "")
CHUNK = int(os.environ.get("FM_DAV_CHUNK", str(4 * 1024 * 1024)))
AUTH_CACHE_SECONDS = 60

STAT_TTL = float(os.environ.get("FM_DAV_STAT_TTL", "3"))

_local = threading.local()
_auth_cache = {}   # sha256(login:key) -> (expires, uid)


class _StatCache:
    """Kurzlebiger Zustands-Cache je Nutzer und Pfad. Jeder Odoo-Aufruf kostet 25-35 ms Grundlast; der
    Windows-WebClient schickt je Datei 8 Requests. Eigene Schreibvorgaenge verwerfen die betroffenen Eintraege
    sofort (fuer alle Nutzer); Aenderungen aus der Odoo-Oberflaeche werden spaetestens nach STAT_TTL sichtbar."""

    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}

    def get(self, key, kind, path):
        e = self.data.get((key, kind, path))
        if e and e[0] > time.time():
            return True, e[1]
        return False, None

    def put(self, key, kind, path, value):
        if STAT_TTL > 0:
            with self.lock:
                self.data[(key, kind, path)] = (time.time() + STAT_TTL, value)

    def invalidate(self, *paths):
        with self.lock:
            for k in list(self.data):
                p = k[2]
                for q in paths:
                    q = q.rstrip("/") or "/"
                    parent = q.rsplit("/", 1)[0] or "/"
                    if p == q or p == parent or p.startswith(q + "/"):
                        self.data.pop(k, None)
                        break


_cache = _StatCache()


def _session():
    s = getattr(_local, "session", None)
    if s is None:
        s = _local.session = requests.Session()
    return s


class Odoo:
    """JSON-RPC an die fm_proto-Routen im Namen eines Nutzers."""

    def __init__(self, key):
        self.headers = {"Authorization": "Bearer " + key}

    def call(self, route, **params):
        for attempt in range(3):
            try:
                r = _session().post(ODOO + route, headers=self.headers, timeout=1800,
                                    json={"jsonrpc": "2.0", "method": "call", "params": params})
                break
            except requests.ConnectionError:
                if attempt == 2:
                    raise DAVError(HTTP_INTERNAL_ERROR, "Odoo nicht erreichbar")
                time.sleep(1)
        if r.status_code == 401:
            raise DAVError(403, "API-Schluessel ungueltig")
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            _logger.error("Odoo-Fehler %s: %s", route, body["error"].get("data", {}).get("message"))
            raise DAVError(HTTP_INTERNAL_ERROR, body["error"].get("message"))
        res = body["result"]
        if isinstance(res, dict) and res.get("ok") is False:
            raise DAVError(res["status"], res.get("msg"))
        return res

    def put_small(self, path, data):
        for attempt in range(3):
            try:
                r = _session().put(ODOO + "/fmp/dav/put/small", params={"root": ROOT, "path": path}, data=data,
                                   headers=self.headers, timeout=600)
                break
            except requests.ConnectionError:
                if attempt == 2:
                    raise
                time.sleep(1)
        r.raise_for_status()
        res = r.json()
        if not res.get("ok"):
            raise DAVError(res.get("status", HTTP_INTERNAL_ERROR), res.get("msg"))
        return res

    def put_chunk(self, op, offset, data):
        for attempt in range(3):
            try:
                r = _session().put(ODOO + "/fmp/dav/put/chunk", params={"operation_key": op, "offset": offset},
                                   data=data, headers=self.headers, timeout=600)
            except requests.ConnectionError:
                if attempt == 2:
                    raise
                time.sleep(1)
                continue
            if r.status_code == 200:
                return r.json()["received"]
            if attempt == 2:
                raise DAVError(HTTP_INTERNAL_ERROR, "Stueck abgelehnt: %s %s" % (r.status_code, r.text[:200]))
            time.sleep(1)


def _client(environ):
    return Odoo(environ["fm.key"])


def _parts(path):
    return [p for p in path.strip("/").split("/") if p]


# ---------------------------------------------------------------------------------------------------------------
# Anmeldung
# ---------------------------------------------------------------------------------------------------------------

class OdooDomainController(BaseDomainController):
    def __init__(self, wsgidav_app, config):
        super().__init__(wsgidav_app, config)

    def get_domain_realm(self, path_info, environ):
        return "Odoo Dateien"

    def require_authentication(self, realm, environ):
        if environ is None:
            return True
        if ANON_KEY and environ.get("REMOTE_ADDR") in ANON_IPS:
            environ["fm.key"] = ANON_KEY
            environ["wsgidav.auth.user_name"] = "anon-test"
            return False
        return True

    def basic_auth_user(self, realm, user_name, password, environ):
        ck = hashlib.sha256(("%s:%s" % (user_name, password)).encode()).hexdigest()
        hit = _auth_cache.get(ck)
        if not hit or hit[0] < time.time():
            try:
                who = Odoo(password).call("/fmp/dav/whoami")
            except DAVError:
                return False
            if who["login"] != user_name:
                return False
            _auth_cache[ck] = (time.time() + AUTH_CACHE_SECONDS, who["uid"])
        environ["fm.key"] = password
        return True

    def supports_http_digest_auth(self):
        return False


# ---------------------------------------------------------------------------------------------------------------
# Lesen / Schreiben
# ---------------------------------------------------------------------------------------------------------------

class OdooReader(io.RawIOBase):
    """Lazy-HTTP-Leser mit seek() fuer Range-Anfragen; Odoo liefert per x_sendfile ueber nginx."""

    def __init__(self, client, node_id):
        self.client, self.node_id, self.pos, self.resp = client, node_id, 0, None

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        assert whence == 0
        self._close_resp()
        self.pos = offset
        return offset

    def read(self, n=-1):
        if self.resp is None:
            headers = dict(self.client.headers)
            if self.pos:
                headers["Range"] = "bytes=%d-" % self.pos
            self.resp = _session().get(ODOO + "/fmp/dav/get/%d" % self.node_id, headers=headers, stream=True,
                                       timeout=600)
            if self.resp.status_code not in (200, 206):
                raise DAVError(HTTP_INTERNAL_ERROR, "GET %s" % self.resp.status_code)
        data = self.resp.raw.read(n if n and n > 0 else None)
        self.pos += len(data)
        return data

    def _close_resp(self):
        if self.resp is not None:
            self.resp.close()
            self.resp = None

    def close(self):
        self._close_resp()
        super().close()


class OdooWriter:
    """Nimmt den PUT-Strom entgegen und gibt ihn in Stuecken an Odoo (fm.upload). Commit in end_write."""

    def __init__(self, res):
        self.res = res
        self.client = _client(res.environ)
        self.op = uuid.uuid4().hex
        self.buf = bytearray()
        self.offset = 0
        cl = res.environ.get("CONTENT_LENGTH")
        self.size = int(cl) if cl not in (None, "") else None
        self.chunked = False
        self.result = None

    def write(self, data):
        self.buf += data
        while len(self.buf) >= CHUNK:
            self._flush(CHUNK)

    def _flush(self, n):
        if not self.chunked:
            self.client.call("/fmp/dav/put/init", root=ROOT, path=_parts(self.res.path), operation_key=self.op,
                             size=self.size)
            self.chunked = True
        part = bytes(self.buf[:n])
        self.client.put_chunk(self.op, self.offset, part)
        self.offset += len(part)
        del self.buf[:n]

    def close(self):
        if not self.chunked:
            # kleine Datei: ein Aufruf, ein Commit
            data = bytes(self.buf)
            self.buf.clear()
            self.offset = len(data)
            self.result = self.client.put_small("/".join(_parts(self.res.path)), data)
        elif self.buf:
            self._flush(len(self.buf))

    def finish(self):
        if self.result is not None:
            return self.result
        return self.client.call("/fmp/dav/put/finish", operation_key=self.op, size=self.offset)


# ---------------------------------------------------------------------------------------------------------------
# Ressourcen
# ---------------------------------------------------------------------------------------------------------------

class _Common:
    def _init_info(self, info):
        self.info = info or {}

    def get_creation_date(self):
        return self.info.get("ctime")

    def get_last_modified(self):
        return self.info.get("mtime")

    def get_display_name(self):
        return self.name

    def _cache_clear(self, *extra):
        self.environ.pop("fm.cache", None)
        _cache.invalidate(self.path, *extra)

    def _dest_parts(self, dest_path):
        return _parts(dest_path)

    def _after_move(self, dest_path, is_move):
        """Wie WsgiDAVs eigener Ablauf: tote Eigenschaften mitnehmen, Sperren der Quelle aufheben."""
        pm = self.provider.prop_manager
        if pm:
            src_ref = self.get_ref_url()
            dest_ref = self.provider.ref_url_for(dest_path, self.is_collection)
            if is_move:
                pm.move_properties(src_ref, dest_ref, with_children=True, environ=self.environ)
            else:
                pm.copy_properties(src_ref, dest_ref, environ=self.environ)
        if is_move and self.provider.lock_manager:
            self.remove_all_locks(recursive=True)

    def handle_delete(self):
        # WsgiDAV prueft vor handle_delete() nur die Sperre des Elternordners (request_server.py:585-599),
        # die Sperren der Ressource selbst und ihrer Nachfahren nur im nicht selbst behandelten Pfad.
        lm = self.provider.lock_manager
        if lm:
            lm.check_write_permission(url=self.get_ref_url(), depth="infinity",
                                      token_list=self.environ.get("wsgidav.ifLockTokenList", []),
                                      principal=self.environ.get("wsgidav.user_name"))
        self._cache_clear()
        _client(self.environ).call("/fmp/dav/delete", root=ROOT, path=_parts(self.path))
        if self.provider.lock_manager:
            self.remove_all_locks(recursive=True)
        if self.provider.prop_manager:
            self.remove_all_properties(recursive=True)
        return True

    def handle_move(self, dest_path):
        self._cache_clear(dest_path)
        res = _client(self.environ).call("/fmp/dav/move", root=ROOT, src=_parts(self.path),
                                         dst=self._dest_parts(dest_path),
                                         overwrite=self.environ.get("HTTP_OVERWRITE", "T") == "T")
        _logger.info("MOVE %s -> %s: %s", self.path, dest_path, res.get("result"))
        self._after_move(dest_path, True)
        return True

    def handle_copy(self, dest_path, *, depth_infinity):
        self._cache_clear(dest_path)
        _client(self.environ).call("/fmp/dav/copy", root=ROOT, src=_parts(self.path),
                                   dst=self._dest_parts(dest_path), depth_infinity=depth_infinity,
                                   overwrite=self.environ.get("HTTP_OVERWRITE", "T") == "T")
        self._after_move(dest_path, False)
        return True

    def support_recursive_delete(self):
        return True

    def support_recursive_move(self, dest_path):
        return True


class FmCollection(_Common, DAVCollection):
    def __init__(self, path, environ, info):
        DAVCollection.__init__(self, path, environ)
        self._init_info(info)

    def get_etag(self):
        return None

    def _children(self):
        cache = self.environ.setdefault("fm.cache", {})
        key = ("children", self.path)
        if key not in cache:
            ukey = self.environ["fm.key"]
            p = self.path.rstrip("/") or "/"
            hit, children = _cache.get(ukey, "children", p)
            if not hit:
                res = _client(self.environ).call("/fmp/dav/stat", root=ROOT, path=_parts(self.path), children=True)
                children = res.get("children") or []
                _cache.put(ukey, "children", p, children)
            cache[key] = children
            base = self.path.rstrip("/")
            for c in children:
                cache[("stat", base + "/" + c["name"])] = c
                _cache.put(ukey, "stat", base + "/" + c["name"], c)
        return cache[key]

    def get_member_names(self):
        return [c["name"] for c in self._children()]

    def get_member(self, name):
        for c in self._children():
            if c["name"] == name:
                return _make(util.join_uri(self.path, name), self.environ, c)
        return None

    def get_member_list(self):
        return [_make(util.join_uri(self.path, c["name"]), self.environ, c) for c in self._children()]

    def create_empty_resource(self, name):
        path = util.join_uri(self.path, name)
        if self.environ["REQUEST_METHOD"] == "PUT":
            # Datei entsteht erst in end_write (ein Commit fuer Knoten und Inhalt)
            return FmFile(path, self.environ, None)
        self._cache_clear()
        res = _client(self.environ).call("/fmp/dav/touch", root=ROOT, path=_parts(path))
        _cache.invalidate(path)
        return FmFile(path, self.environ, res["node"])

    def create_collection(self, name):
        path = util.join_uri(self.path, name)
        _client(self.environ).call("/fmp/dav/mkcol", root=ROOT, path=_parts(path))
        self._cache_clear(path)


class FmFile(_Common, DAVNonCollection):
    def __init__(self, path, environ, info):
        DAVNonCollection.__init__(self, path, environ)
        self._init_info(info)
        self.writer = None

    def get_content_length(self):
        return self.info.get("size", 0)

    def get_content_type(self):
        return mimetypes.guess_type(self.name)[0] or "application/octet-stream"

    def get_etag(self):
        return self.info.get("sha256") or "empty-%s" % self.info.get("id", 0)

    def support_etag(self):
        return True

    def support_ranges(self):
        return True

    def get_content(self):
        if not self.info.get("sha256") or not self.info.get("size"):
            return io.BytesIO(b"")
        return OdooReader(_client(self.environ), self.info["id"])

    def begin_write(self, *, content_type=None):
        self._cache_clear()
        self.writer = OdooWriter(self)
        return self.writer

    def end_write(self, *, with_errors):
        if with_errors or self.writer is None:
            return
        t = time.time()
        res = self.writer.finish()
        self._init_info(res["node"])
        self._cache_clear()
        _cache.put(self.environ["fm.key"], "stat", self.path.rstrip("/"), res["node"])
        _logger.info("PUT %s: %d Bytes, finish %.1fs, rev %s", self.path, self.writer.offset, time.time() - t,
                     self.info.get("rev"))


def _make(path, environ, info):
    if info["is_dir"] or info["id"] == ROOT:
        return FmCollection(path, environ, info)
    return FmFile(path, environ, info)


class OdooProvider(DAVProvider):
    def ref_url_for(self, path, is_collection):
        return quote(self.share_path + path.rstrip("/") + ("/" if is_collection else ""))

    def get_resource_inst(self, path, environ):
        self._count_get_resource_inst += 1
        cache = environ.setdefault("fm.cache", {})
        key = ("stat", path.rstrip("/") or "/")
        if key not in cache:
            hit, info = _cache.get(environ["fm.key"], "stat", key[1])
            if not hit:
                info = _client(environ).call("/fmp/dav/stat", root=ROOT, path=_parts(path))["node"]
                _cache.put(environ["fm.key"], "stat", key[1], info)
            cache[key] = info
        info = cache[key]
        if info is None:
            return None
        return _make(path, environ, info)


def make_app():
    config = {
        "host": "0.0.0.0",
        "port": int(os.environ.get("FM_DAV_PORT", "8080")),
        "provider_mapping": {"/": OdooProvider()},
        "http_authenticator": {
            "domain_controller": OdooDomainController,
            "accept_basic": True,
            "accept_digest": False,
            "default_to_digest": False,
        },
        "lock_storage": True,          # Prototyp: Sperren im Speicher des Dienstes
        "property_manager": True,      # Prototyp: tote Eigenschaften (Win32-Zeiten) im Speicher
        "block_size": 1024 * 1024,
        "verbose": int(os.environ.get("FM_DAV_VERBOSE", "3")),
        "logging": {"enable": True, "enable_loggers": []},
        "dir_browser": {"enable": True, "response_trailer": ""},
        "hotfixes": {"emulate_win32_lastmod": True},
    }
    return _fix_lock_content_type(WsgiDAVApp(config))


def _fix_lock_content_type(app):
    """WsgiDAV 4.3.5 schickt bei LOCK 'Content-Type: application; charset=utf-8' (request_server.py:1283),
    litmus (und strenge Clients) erkennen die Antwort dann nicht als XML."""
    def wrapped(environ, start_response):
        def sr(status, headers, exc_info=None):
            headers = [(k, "application/xml; charset=utf-8" if k.lower() == "content-type"
                        and v.startswith("application;") else v) for k, v in headers]
            return start_response(status, headers, exc_info)
        return app(environ, sr)
    return wrapped


if __name__ == "__main__":
    from cheroot import wsgi

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    app = make_app()
    server = wsgi.Server(("0.0.0.0", int(os.environ.get("FM_DAV_PORT", "8080"))), app,
                         numthreads=int(os.environ.get("FM_DAV_THREADS", "16")))
    _logger.info("fmdav: Odoo %s, Wurzel %s, anonyme Test-IPs %s", ODOO, ROOT, sorted(ANON_IPS) or "-")
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
