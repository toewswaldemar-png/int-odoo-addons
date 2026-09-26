"""Prototyp WebDAV als eigener Odoo-Befehl `odoo fmdav` (int_filemanager 2, Konzept 19.10).

WsgiDAV laeuft in einem eigenen Prozess mit werkzeugs Thread-Server (wie Odoo im Thread-Modus), nutzt aber Odoos
Registry und ORM direkt (Muster von ir_cron / odoo shell: Registry(db).check_signaling(), registry.cursor(),
api.Environment, signal_changes/reset_changes). Kein Odoo-HTTP beteiligt:
- roher Strom direkt aus dem WSGI-environ (kein internes Attribut),
- Transaktionen nur um die kurzen DB-Schritte (PUT: Pruefen -> commit -> Strom ohne Transaktion -> Abschluss),
- keine Prefork-Worker, kein limit_time_real; ein Upload belegt einen Thread,
- Wiederholung bei DB-Konflikten mit Odoos retrying(): ganze Anfrage fuer alles ausser PUT (kleiner Body gepuffert),
  beim PUT nur der Abschluss.
Rechte: jede Anfrage laeuft mit env des angemeldeten Nutzers (I7). Odoo bleibt alleiniger Schreiber (I1).
"""
import base64
import functools
import hashlib
import io
import logging
import os
import threading
import time
from urllib.parse import quote, unquote

import werkzeug.wsgi

from odoo import SUPERUSER_ID, api
from odoo.modules.registry import Registry
from odoo.service.model import retrying

from wsgidav import util as dav_util
from wsgidav.dav_error import DAVError
from wsgidav.dav_provider import DAVCollection, DAVNonCollection, DAVProvider
from wsgidav.dir_browser import WsgiDavDirBrowser
from wsgidav.lock_man.lock_manager import generate_lock_token, normalize_lock_root, validate_lock
from wsgidav.request_resolver import RequestResolver
from wsgidav.wsgidav_app import WsgiDAVApp

from . import blobstore
from .dav import DavError
from .dav_inproc import _MaterializeAndMapErrors

_logger = logging.getLogger("odoo.fmdav")

MOUNT = "/dav"
REALM = "Odoo Dateien"
LOCK_ADVISORY_KEY = 0x464D4441
SMALL_BODY_LIMIT = 16 * 1024 * 1024       # Nicht-PUT-Bodies (XML) werden fuer Wiederholungen gepuffert
AUTH_CACHE_TTL = 60

_ctx = threading.local()                  # je Thread: env, Sperren-Cache
_auth_cache = {}
_auth_lock = threading.Lock()


def _env():
    return _ctx.env


def _parts(path):
    return [p for p in path.strip("/").split("/") if p]


def _dav_call(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except DavError as e:
        raise DAVError(e.status, str(e)) from None


# ---------------------------------------------------------------------------------------------------------------
# Sperren und tote Eigenschaften (fm.dav.lock / fm.dav.prop aus dav_inproc.py)
# ---------------------------------------------------------------------------------------------------------------

class DbLockStorage:
    LOCK_TIME_OUT_DEFAULT = 604800
    LOCK_TIME_OUT_MAX = 4 * 604800

    def __repr__(self):
        return "DbLockStorage(fm.dav.lock)"

    def open(self):
        pass

    def close(self):
        pass

    def cleanup(self):
        pass

    def clear(self):
        self._m().search([]).unlink()
        self._drop()

    @staticmethod
    def _m():
        return _env()["fm.dav.lock"].sudo()

    def _all(self):
        if getattr(_ctx, "locks", None) is None:
            _ctx.locks = self._m().search([])
        return _ctx.locks

    @staticmethod
    def _drop():
        _ctx.locks = None

    @staticmethod
    def _to_db(lock):
        data = dict(lock)
        if isinstance(data.get("owner"), bytes):
            data["owner"] = data["owner"].decode("utf-8")
        return data

    @staticmethod
    def _from_db(rec):
        lock = dict(rec.data)
        if isinstance(lock.get("owner"), str):
            lock["owner"] = lock["owner"].encode("utf-8")
        return lock

    def _valid(self, rec):
        if rec.expire >= 0 and rec.expire < time.time():
            rec.unlink()
            self._drop()
            return False
        return True

    def get(self, token):
        rec = self._all().exists().filtered(lambda r: r.token == token)[:1]
        return self._from_db(rec) if rec and self._valid(rec) else None

    def create(self, path, lock):
        path = normalize_lock_root(path)
        lock["root"] = path
        timeout = float(lock.get("timeout") or self.LOCK_TIME_OUT_DEFAULT)
        if timeout < 0 or timeout > self.LOCK_TIME_OUT_MAX:
            timeout = self.LOCK_TIME_OUT_MAX
        lock["timeout"] = timeout
        lock["expire"] = time.time() + timeout
        validate_lock(lock)
        lock["token"] = generate_lock_token()
        self._m().create({"token": lock["token"], "root": path, "data": self._to_db(lock), "expire": lock["expire"]})
        self._drop()
        return lock

    def refresh(self, token, *, timeout):
        rec = self._m().search([("token", "=", token)], limit=1)
        if not rec:
            raise ValueError("Lock must exist")
        if timeout < 0 or timeout > self.LOCK_TIME_OUT_MAX:
            timeout = self.LOCK_TIME_OUT_MAX
        lock = self._from_db(rec)
        lock["timeout"] = timeout
        lock["expire"] = time.time() + timeout
        rec.write({"data": self._to_db(lock), "expire": lock["expire"]})
        self._drop()
        return lock

    def delete(self, token):
        rec = self._m().search([("token", "=", token)], limit=1)
        if not rec:
            return False
        rec.unlink()
        self._drop()
        return True

    def get_lock_list(self, path, *, include_root, include_children, token_only):
        path = normalize_lock_root(path)
        prefix = path.rstrip("/") + "/"

        def match(root):
            return include_root if root == path else include_children and root.startswith(prefix)
        result = []
        for rec in self._all().exists().filtered(lambda r: match(r.root)):
            if self._valid(rec):
                result.append(rec.token if token_only else self._from_db(rec))
        return result


class DbPropertyManager:
    def __init__(self, root_id):
        self.root_id = root_id

    def __repr__(self):
        return "DbPropertyManager(fm.dav.prop)"

    def _node(self, norm_url):
        return _env()["fm.node"]._dav_resolve(self.root_id, _parts(unquote(norm_url)))

    @staticmethod
    def _m():
        return _env()["fm.dav.prop"].sudo()

    def get_properties(self, norm_url, environ=None):
        node = self._node(norm_url)
        return self._m().search([("node_id", "=", node.id)]).mapped("name") if node else []

    def get_property(self, norm_url, name, environ=None):
        node = self._node(norm_url)
        rec = self._m().search([("node_id", "=", node.id), ("name", "=", name)], limit=1) if node else None
        return rec.value.encode() if rec else None

    def write_property(self, norm_url, name, property_value, dry_run=False, environ=None):
        node = None if dry_run else self._node(norm_url)
        if not node:
            return
        value = property_value.decode() if isinstance(property_value, bytes) else property_value
        rec = self._m().search([("node_id", "=", node.id), ("name", "=", name)], limit=1)
        if rec:
            rec.value = value
        else:
            self._m().create({"node_id": node.id, "name": name, "value": value})

    def remove_property(self, norm_url, name, dry_run=False, environ=None):
        node = None if dry_run else self._node(norm_url)
        if node:
            self._m().search([("node_id", "=", node.id), ("name", "=", name)]).unlink()

    def remove_properties(self, norm_url, environ=None):
        node = self._node(norm_url)
        if node:
            self._m().search([("node_id", "=", node.id)]).unlink()

    def copy_properties(self, src_url, dest_url, environ=None):
        src, dst = self._node(src_url), self._node(dest_url)
        if src and dst:
            for rec in self._m().search([("node_id", "=", src.id)]):
                self._m().create({"node_id": dst.id, "name": rec.name, "value": rec.value})

    def move_properties(self, src_url, dest_url, with_children, environ=None):
        pass      # an der Knoten-ID (I8)


# ---------------------------------------------------------------------------------------------------------------
# Provider (ORM, env des Nutzers)
# ---------------------------------------------------------------------------------------------------------------

class _Common:
    def _init_node(self, node):
        self.node = node
        self.info = node._dav_info() if node else {}

    def get_creation_date(self):
        return self.info.get("ctime")

    def get_last_modified(self):
        return self.info.get("mtime")

    def set_last_modified(self, dest_path, time_stamp, *, dry_run):
        return True

    def _root(self):
        return self.provider.root_id

    def _cache_clear(self):
        self.environ.pop("fm.cache", None)

    def handle_delete(self):
        self.provider.lock_manager.check_write_permission(
            url=self.get_ref_url(), depth="infinity", token_list=self.environ.get("wsgidav.ifLockTokenList", []),
            principal=self.environ.get("wsgidav.user_name"))
        self._cache_clear()
        self.node.lock_for_update()
        self.node._dav_discard()
        self.remove_all_locks(recursive=True)
        return True

    def handle_move(self, dest_path):
        self._cache_clear()
        res = _dav_call(_env()["fm.node"]._dav_move, self._root(), _parts(self.path), _parts(dest_path),
                        self.environ.get("HTTP_OVERWRITE", "T") == "T")
        _logger.info("MOVE %s -> %s: %s", self.path, dest_path, res.get("result"))
        self.remove_all_locks(recursive=True)
        return True

    def handle_copy(self, dest_path, *, depth_infinity):
        self._cache_clear()
        _dav_call(_env()["fm.node"]._dav_copy, self._root(), _parts(self.path), _parts(dest_path),
                  self.environ.get("HTTP_OVERWRITE", "T") == "T", depth_infinity)
        self.provider.prop_manager.copy_properties(self.get_ref_url(),
                                                   self.provider.ref_url_for(dest_path, self.is_collection))
        return True

    def support_recursive_delete(self):
        return True

    def support_recursive_move(self, dest_path):
        return True


class FmCollection(_Common, DAVCollection):
    def __init__(self, path, environ, node):
        DAVCollection.__init__(self, path, environ)
        self._init_node(node)
        self._children = None

    def get_etag(self):
        return None

    def _child_nodes(self):
        if self._children is None:
            self._children = _env()["fm.node"].search([("parent_id", "=", self.node.id)], order="name")
        return self._children

    def get_member_names(self):
        return self._child_nodes().mapped("name")

    def get_member(self, name):
        child = self._child_nodes().filtered(lambda n: n.name == name)[:1]
        return _make(dav_util.join_uri(self.path, name), self.environ, child) if child else None

    def get_member_list(self):
        return [_make(dav_util.join_uri(self.path, c.name), self.environ, c) for c in self._child_nodes()]

    def create_empty_resource(self, name):
        path = dav_util.join_uri(self.path, name)
        self._cache_clear()
        if self.environ["REQUEST_METHOD"] == "PUT":
            return FmFile(path, self.environ, _env()["fm.node"].browse())
        parent, name = _dav_call(_env()["fm.node"]._dav_resolve_parent, self._root(), _parts(path))
        node = parent._dav_child(name) or _env()["fm.node"].create({"name": name, "parent_id": parent.id})
        return FmFile(path, self.environ, node)

    def create_collection(self, name):
        path = dav_util.join_uri(self.path, name)
        self._cache_clear()
        parent, name = _dav_call(_env()["fm.node"]._dav_resolve_parent, self._root(), _parts(path))
        if parent._dav_child(name):
            raise DAVError(405)
        _env()["fm.node"].create({"name": name, "parent_id": parent.id, "is_dir": True})


class _Writer:
    """Strom -> Temp-Datei im Blob-Speicher, SHA-256 unterwegs; Temp-Datei erst beim ersten Byte."""

    def __init__(self, res):
        self.res = res
        self.tmp = os.path.join(blobstore.tmp_dir(_env()), "fmdav_%d_%d" % (os.getpid(), threading.get_ident()))
        self.out = None
        self.h = hashlib.sha256()
        self.size = 0
        self.done = None

    def write(self, data):
        if data:
            if self.out is None:
                self.out = open(self.tmp, "wb")
            self.h.update(data)
            self.out.write(data)
            self.size += len(data)

    def close(self):
        if self.out is not None:
            self.out.flush()
            os.fsync(self.out.fileno())
            self.out.close()
        expected = self.res.environ.get("CONTENT_LENGTH")
        if expected not in (None, "") and int(expected) != self.size:
            if self.out is not None:
                os.unlink(self.tmp)
            raise DAVError(400, "Body unvollstaendig: %s von %s Bytes" % (self.size, expected))
        self.done = (self.tmp, self.h.hexdigest(), self.size)


class FmFile(_Common, DAVNonCollection):
    def __init__(self, path, environ, node):
        DAVNonCollection.__init__(self, path, environ)
        self._init_node(node)
        self.writer = None

    def get_content_length(self):
        return self.info.get("size", 0)

    def get_content_type(self):
        return dav_util.guess_mime_type(self.name)

    def get_etag(self):
        return self.info.get("sha256") or "empty-%s" % self.info.get("id", 0)

    def support_etag(self):
        return True

    def support_ranges(self):
        return True

    def get_content(self):
        sha = self.info.get("sha256")
        if not sha or not self.info.get("size"):
            return io.BytesIO(b"")
        return open(blobstore.blob_path(_env(), sha), "rb")

    def begin_write(self, *, content_type=None):
        # Wie Cloudreve PrepareUpload -> Upload -> CompleteUpload: bis hier nur gelesen; waehrend des Datenstroms
        # keine offene Transaktion (eigener Cursor, eigene Entscheidung - kein Eingriff in Odoo-HTTP).
        env = _env()
        env.flush_all()
        env.cr.commit()
        env.invalidate_all()
        DbLockStorage._drop()
        self._cache_clear()
        self.writer = _Writer(self)
        return self.writer

    def end_write(self, *, with_errors):
        if with_errors or self.writer is None or self.writer.done is None:
            return
        env = _env()
        tmp, sha, size = self.writer.done
        if size:
            blobstore.adopt_hashed(env, tmp, sha, size)                 # idempotent, vor dem Commit (I3)
        # Nur der Abschluss wird bei DB-Konflikten wiederholt (der Strom ist gelesen).
        retrying(functools.partial(self._complete, sha, size), env)
        if os.path.exists(tmp):
            env.cr.postcommit.add(lambda: os.path.exists(tmp) and os.unlink(tmp))

    def _complete(self, sha, size):
        env = _env()
        DbLockStorage._drop()
        self._cache_clear()
        # Sperre und Ziel neu pruefen (Cloudreve: CompleteUpload -> ConfirmLock)
        self.provider.lock_manager.check_write_permission(
            url=self.get_ref_url(), depth="0", token_list=self.environ.get("wsgidav.ifLockTokenList", []),
            principal=self.environ.get("wsgidav.user_name"))
        blob = env["fm.blob"]._get_or_create(sha, size) if size else env["fm.blob"]
        parent, name = _dav_call(env["fm.node"]._dav_resolve_parent, self._root(), _parts(self.path))
        node = parent._dav_child(name)
        if node and node.is_dir:
            raise DAVError(405, "Ziel ist inzwischen ein Ordner")
        if not node:
            node = env["fm.node"].create({"name": name, "parent_id": parent.id})
        node.lock_for_update()
        node._dav_set_content(blob, "webdav")
        self._init_node(node)


def _make(path, environ, node):
    if node.is_dir or node.id == environ["wsgidav.provider"].root_id:
        return FmCollection(path, environ, node)
    return FmFile(path, environ, node)


class OdooProvider(DAVProvider):
    def __init__(self, root_id):
        super().__init__()
        self.root_id = root_id

    def ref_url_for(self, path, is_collection):
        return quote(self.share_path + path.rstrip("/") + ("/" if is_collection else ""))

    def get_resource_inst(self, path, environ):
        cache = environ.setdefault("fm.cache", {})
        key = path.rstrip("/") or "/"
        if key not in cache:
            cache[key] = _env()["fm.node"]._dav_resolve(self.root_id, _parts(path))
        node = cache[key]
        return _make(path, environ, node) if node else None


# ---------------------------------------------------------------------------------------------------------------
# Rahmen: Anmeldung, Transaktion, Wiederholung, Auslieferung
# ---------------------------------------------------------------------------------------------------------------

class FmDavApplication:
    def __init__(self, dbname, root_id, accel_prefix="", anon_ips=(), anon_login="", proxy_mode=False):
        self.db = dbname
        self.root_id = root_id
        self.accel_prefix = accel_prefix.rstrip("/")
        self.anon_ips = set(anon_ips)
        self.anon_login = anon_login
        self.proxy_mode = proxy_mode
        self.dav = WsgiDAVApp({
            "provider_mapping": {"/": OdooProvider(root_id)},
            "mount_path": MOUNT,
            "lock_storage": DbLockStorage(),
            "property_manager": DbPropertyManager(root_id),
            "middleware_stack": [_MaterializeAndMapErrors, WsgiDavDirBrowser, RequestResolver],
            "http_authenticator": {"domain_controller": None},
            "simple_dc": {"user_mapping": {"*": True}},
            "block_size": 1024 * 1024,
            "verbose": 1,
            "logging": {"enable": False},
            "dir_browser": {"enable": True, "response_trailer": ""},
            "hotfixes": {"emulate_win32_lastmod": True},
        })

    # --- Anmeldung ------------------------------------------------------------------------------------------------

    def _remote_addr(self, environ):
        if self.proxy_mode and environ.get("HTTP_X_FORWARDED_FOR"):
            return environ["HTTP_X_FORWARDED_FOR"].split(",")[0].strip()
        return environ.get("REMOTE_ADDR")

    def _authenticate(self, registry, environ):
        if self.anon_login and self._remote_addr(environ) in self.anon_ips:       # nur Testinstanz
            key = ("anon", self.anon_login)
        else:
            auth = environ.get("HTTP_AUTHORIZATION", "")
            if not auth.lower().startswith("basic "):
                return None, None
            try:
                login, password = base64.b64decode(auth[6:]).decode("utf-8").split(":", 1)
            except Exception:
                return None, None
            key = hashlib.sha256(("%s:%s" % (login, password)).encode()).hexdigest()
        hit = _auth_cache.get(key)
        if hit and hit[0] > time.time():
            return hit[1], hit[2]
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            if key[0] == "anon":
                user = env["res.users"].search([("login", "=", self.anon_login)], limit=1)
            else:
                # dieselbe Pruefung wie auth='bearer' (ir_http.py:235-240)
                uid = env["res.users.apikeys"]._check_credentials(scope="rpc", key=password)
                user = env["res.users"].browse(uid) if uid else env["res.users"]
                if user and user.login != login:
                    user = env["res.users"]
            if not user:
                return None, None
            result = (user.id, user.login)
        with _auth_lock:
            _auth_cache[key] = (time.time() + AUTH_CACHE_TTL, *result)
        return result

    # --- WSGI -----------------------------------------------------------------------------------------------------

    def __call__(self, environ, start_response):
        method = environ["REQUEST_METHOD"]
        path = environ.get("PATH_INFO", "")
        if not (path == MOUNT or path.startswith(MOUNT + "/")):
            start_response("404 Not Found", [("Content-Length", "0")])
            return [b""]
        if method == "OPTIONS":        # Windows-WebClient fragt ohne Anmeldung (Cloudreve-Vergleich 19.5)
            start_response("200 OK", [("DAV", "1, 2"), ("MS-Author-Via", "DAV"), ("Content-Length", "0"),
                                      ("Allow", "OPTIONS, GET, HEAD, PUT, DELETE, MKCOL, COPY, MOVE, LOCK, UNLOCK, "
                                                "PROPFIND, PROPPATCH")])
            return [b""]
        t0 = time.time()
        registry = Registry(self.db).check_signaling()
        uid, login = self._authenticate(registry, environ)
        if not uid:
            start_response("401 Unauthorized", [("WWW-Authenticate", 'Basic realm="%s", charset="UTF-8"' % REALM),
                                                ("Content-Length", "0")])
            return [b""]
        thread = threading.current_thread()
        thread.dbname, thread.uid = self.db, uid

        environ = dict(environ)
        # werkzeugs Server liefert wsgi.input als rohen Socket; ohne Begrenzung liest WsgiDAV bis zum Verbindungsende
        # (haengt bei Keep-Alive). get_input_stream begrenzt auf Content-Length bzw. das Ende bei chunked.
        environ["wsgi.input"] = werkzeug.wsgi.get_input_stream(environ)
        environ["SCRIPT_NAME"] = MOUNT
        environ["PATH_INFO"] = path[len(MOUNT):] or "/"
        environ["wsgidav.auth.user_name"] = environ["wsgidav.user_name"] = login
        environ["wsgidav.auth.realm"] = REALM
        body = None
        if method != "PUT":
            length = int(environ.get("CONTENT_LENGTH") or 0)
            if length > SMALL_BODY_LIMIT:
                start_response("413 Request Entity Too Large", [("Content-Length", "0")])
                return [b""]
            body = environ["wsgi.input"].read(length) if length else b""

        try:
            with registry.cursor() as cr:
                env = api.Environment(cr, uid, {})
                _ctx.env, _ctx.locks = env, None
                if method == "GET":
                    direct = self._get_file(env, environ, start_response)
                    if direct is not None:
                        return direct
                if method in ("LOCK", "UNLOCK"):
                    cr.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_ADVISORY_KEY])
                if method == "PUT":
                    status, headers, out = self._call_dav(environ, None)
                else:
                    status, headers, out = retrying(functools.partial(self._call_dav, environ, body), env)
                if int(status.split()[0]) >= 400:
                    cr.rollback()
            registry.signal_changes()
        except Exception:
            registry.reset_changes()
            _logger.exception("fmdav: %s %s fehlgeschlagen", method, path)
            start_response("500 Internal Server Error", [("Content-Length", "0")])
            return [b""]
        finally:
            _ctx.env = _ctx.locks = None
        _logger.info("%s %s -> %s (%.0f ms)", method, path, status.split()[0], (time.time() - t0) * 1000)
        start_response(status, headers)
        return [out]

    def _call_dav(self, environ, body):
        env = dict(environ)            # WsgiDAV veraendert environ; bei Wiederholung frische Kopie
        if body is not None:
            env["wsgi.input"] = io.BytesIO(body)
            env["CONTENT_LENGTH"] = str(len(body))
        env.pop("fm.cache", None)
        _ctx.locks = None
        result = {}

        def start_response(status, headers, exc_info=None):
            result["status"], result["headers"] = status, headers
        out = b"".join(self.dav(env, start_response))
        return result["status"], result["headers"], out

    def _get_file(self, env, environ, start_response):
        """GET auf Dateien: nginx liefert per X-Accel-Redirect (Range, sendfile); der Thread ist sofort frei."""
        node = env["fm.node"]._dav_resolve(self.root_id, _parts(environ["PATH_INFO"]))
        if not node or node.is_dir or node.id == self.root_id or not node.current_revision_id:
            return None
        sha = node.current_revision_id.blob_id.sha256
        size = int(node.current_revision_id.blob_id.size or 0)
        headers = [("Content-Type", dav_util.guess_mime_type(node.name)), ("ETag", '"%s"' % sha),
                   ("Last-Modified", dav_util.get_rfc1123_time(node.current_revision_id.create_date.timestamp())),
                   ("Accept-Ranges", "bytes")]
        if environ.get("HTTP_IF_NONE_MATCH", "").strip('" ') == sha:
            start_response("304 Not Modified", headers)
            return [b""]
        if self.accel_prefix:
            rel = os.path.relpath(blobstore.blob_path(env, sha), os.path.dirname(os.path.dirname(
                blobstore.root(env))))        # <data_dir>/filestore/<db>/fm/... -> <db>/fm/...
            start_response("200 OK", headers + [("X-Accel-Redirect", "%s/%s" % (self.accel_prefix, rel))])
            return [b""]
        f = open(blobstore.blob_path(env, sha), "rb")      # ohne nginx: ganze Datei, ohne Range
        start_response("200 OK", headers + [("Content-Length", str(size))])
        return environ.get("wsgi.file_wrapper", lambda fh, bs: iter(lambda: fh.read(bs), b""))(f, 1024 * 1024)


def serve(dbname, host, port, **kw):
    import werkzeug.serving
    app = FmDavApplication(dbname, **kw)
    Registry(dbname)          # Module laden, bevor Anfragen kommen
    srv = werkzeug.serving.make_server(host, port, app, threaded=True)
    _logger.info("fmdav: WebDAV fuer DB %s auf %s:%s%s (Wurzel %s, X-Accel %s)", dbname, host, port, MOUNT,
                 kw.get("root_id"), kw.get("accel_prefix") or "-")
    srv.serve_forever()
