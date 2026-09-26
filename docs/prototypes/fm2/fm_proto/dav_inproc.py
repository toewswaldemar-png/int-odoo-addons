"""Prototyp WebDAV **im Odoo-Prozess** (int_filemanager 2, Konzept 19.7).

Statt eines eigenen Dienstes (fmdav, 19.4) laeuft WsgiDAV hinter einer Odoo-Route unter /dav/. Der Provider arbeitet
direkt mit dem ORM (dieselben Methoden wie die JSON-Routen in dav.py). Voraussetzungen aus 19.6:
- Der Body wird ueber das mitgefuehrte werkzeug.Request gestreamt (request.httprequest._HTTPRequest__wrapped.stream),
  SHA-256 beim Empfang berechnet; kein Upload in Stuecken, kein erneutes Lesen.
- Downloads von Dateien beantwortet die Route selbst mit Odoos Stream + x_sendfile (nginx liefert).
- Prefork: Worker teilen keinen Speicher -> Sperren (fm.dav.lock) und tote Eigenschaften (fm.dav.prop, an der
  Knoten-ID, I8) in der DB.
- Anmeldung: eigene Auth-Methode auth='fmdav' (ir.http._auth_method_fmdav, dokumentierter Erweiterungspunkt):
  Basic mit Odoo-Login und API-Schluessel; nur Testinstanz: anonymer Zugang fuer einzelne IPs.
- Jede Antwort >= 400 rollt die Transaktion zurueck; DB-Konkurrenzfehler laufen bis zu Odoo durch (retrying).
"""
import hashlib
import logging
import os
import time
from urllib.parse import unquote

import werkzeug.exceptions
from werkzeug.datastructures import WWWAuthenticate

from odoo import fields, http, models
from odoo.http import request

from . import blobstore
from .dav import DavError

_logger = logging.getLogger(__name__)

try:
    from wsgidav import util as dav_util
    from wsgidav.dav_error import DAVError, HTTP_NO_CONTENT, HTTP_NOT_MODIFIED, get_http_status_string
    from wsgidav.dav_provider import DAVCollection, DAVNonCollection, DAVProvider
    from wsgidav.dir_browser import WsgiDavDirBrowser
    from wsgidav.lock_man.lock_manager import generate_lock_token, normalize_lock_root, validate_lock
    from wsgidav.mw.base_mw import BaseMiddleware
    from wsgidav.request_resolver import RequestResolver
    from wsgidav.wsgidav_app import WsgiDAVApp
except ImportError:          # wsgidav nicht installiert -> Route liefert 501
    WsgiDAVApp = None
    BaseMiddleware = DAVCollection = DAVNonCollection = DAVProvider = object

MOUNT = "/dav"
ROOT_ID = int(os.environ.get("FM_DAV_ROOT_ID", "0"))
ANON_IPS = {ip for ip in os.environ.get("FM_DAV_ANON_IPS", "").split(",") if ip}
ANON_LOGIN = os.environ.get("FM_DAV_ANON_LOGIN", "")
AUTH_CACHE_TTL = float(os.environ.get("FM_DAV_AUTH_CACHE", "60"))
REALM = "Odoo Dateien"
DAV_METHODS = ["OPTIONS", "GET", "HEAD", "PUT", "DELETE", "MKCOL", "COPY", "MOVE", "LOCK", "UNLOCK", "PROPFIND",
               "PROPPATCH"]
LOCK_ADVISORY_KEY = 0x464D4441   # 'FMDA': serialisiert LOCK/UNLOCK ueber alle Worker

_auth_cache = {}   # sha256(login:key) -> (expires, uid); je Worker


# ---------------------------------------------------------------------------------------------------------------
# Anmeldung
# ---------------------------------------------------------------------------------------------------------------

class IrHttpFmDav(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _auth_method_fmdav(cls):
        hr = request.httprequest
        if hr.method == "OPTIONS":
            # Windows-WebClient fragt OPTIONS ohne Anmeldung (Cloudreve-Vergleich 19.5); Route antwortet ohne Daten
            cls._auth_method_public()
            return
        users = request.env["res.users"].sudo()
        if ANON_LOGIN and hr.remote_addr in ANON_IPS:          # nur Testinstanz
            uid = users.search([("login", "=", ANON_LOGIN)], limit=1).id
        else:
            auth = hr.authorization
            if not auth or auth.type != "basic" or not auth.password:
                raise werkzeug.exceptions.Unauthorized(www_authenticate=WWWAuthenticate("basic", {"realm": REALM}))
            ck = hashlib.sha256(("%s:%s" % (auth.username, auth.password)).encode()).hexdigest()
            hit = _auth_cache.get(ck)
            if hit and hit[0] > time.time():
                uid = hit[1]
            else:
                # dieselbe Pruefung wie auth='bearer' (ir_http.py:235-240)
                uid = request.env["res.users.apikeys"]._check_credentials(scope="rpc", key=auth.password)
                if not uid or users.browse(uid).login != auth.username:
                    raise werkzeug.exceptions.Unauthorized(
                        www_authenticate=WWWAuthenticate("basic", {"realm": REALM}))
                _auth_cache[ck] = (time.time() + AUTH_CACHE_TTL, uid)
        request.update_env(user=uid)
        request.session.can_save = False      # zustandslos


# ---------------------------------------------------------------------------------------------------------------
# Sperren und tote Eigenschaften in der DB
# ---------------------------------------------------------------------------------------------------------------

class FmDavLock(models.Model):
    _name = "fm.dav.lock"
    _description = "Prototyp WebDAV-Sperre"

    token = fields.Char(required=True)
    root = fields.Char(required=True, index=True)
    data = fields.Json()
    expire = fields.Float()

    _token_uniq = models.UniqueIndex("(token)")


class FmDavProp(models.Model):
    _name = "fm.dav.prop"
    _description = "Prototyp WebDAV-Eigenschaft"

    node_id = fields.Many2one("fm.node", required=True, index=True, ondelete="cascade")
    name = fields.Char(required=True)
    value = fields.Text()

    _node_name_uniq = models.UniqueIndex("(node_id, name)")


class DbLockStorage:
    """Schnittstelle wie wsgidav.lock_man.lock_storage.LockStorageDict, Ablage in fm.dav.lock (alle Worker)."""
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

    @staticmethod
    def _m():
        return request.env["fm.dav.lock"].sudo()

    @staticmethod
    def _all():
        """Alle Sperren einmal je Request laden (die Tabelle enthaelt nur aktive Sperren, wenige Zeilen);
        WsgiDAV fragt je Pruefung jede Elternebene einzeln ab."""
        wr = request.httprequest._HTTPRequest__wrapped
        cached = getattr(wr, "_fm_dav_locks", None)
        if cached is None:
            cached = wr._fm_dav_locks = request.env["fm.dav.lock"].sudo().search([])
        return cached

    @staticmethod
    def _drop_cache():
        request.httprequest._HTTPRequest__wrapped._fm_dav_locks = None

    @staticmethod
    def _to_db(lock):
        """WsgiDAV haelt 'owner' als XML-Bytes (etree.tostring); JSON kennt keine Bytes."""
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

    @staticmethod
    def _valid(rec):
        if rec.expire >= 0 and rec.expire < time.time():
            rec.unlink()
            DbLockStorage._drop_cache()
            return False
        return True

    def get(self, token):
        rec = self._all().filtered(lambda r: r.exists() and r.token == token)[:1]
        return self._from_db(rec) if rec and self._valid(rec) else None

    def create(self, path, lock):
        assert lock.get("token") is None and lock.get("expire") is None
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
        self._drop_cache()
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
        self._drop_cache()
        return lock

    def delete(self, token):
        rec = self._m().search([("token", "=", token)], limit=1)
        if not rec:
            return False
        rec.unlink()
        self._drop_cache()
        return True

    def get_lock_list(self, path, *, include_root, include_children, token_only):
        path = normalize_lock_root(path)
        prefix = path.rstrip("/") + "/"

        def match(root):
            if root == path:
                return include_root
            return include_children and root.startswith(prefix)
        result = []
        for rec in self._all().filtered(lambda r: r.exists() and match(r.root)):
            if self._valid(rec):
                result.append(rec.token if token_only else self._from_db(rec))
        return result


class DbPropertyManager:
    """Tote Eigenschaften an der Knoten-ID (fm.dav.prop). Verschieben braucht nichts zu tun (I8)."""

    def __repr__(self):
        return "DbPropertyManager(fm.dav.prop)"

    @staticmethod
    def _node(norm_url):
        parts = [p for p in unquote(norm_url).split("/") if p]
        return request.env["fm.node"]._dav_resolve(ROOT_ID, parts)

    @staticmethod
    def _m():
        return request.env["fm.dav.prop"].sudo()

    def get_properties(self, norm_url, environ=None):
        node = self._node(norm_url)
        return self._m().search([("node_id", "=", node.id)]).mapped("name") if node else []

    def get_property(self, norm_url, name, environ=None):
        node = self._node(norm_url)
        if not node:
            return None
        rec = self._m().search([("node_id", "=", node.id), ("name", "=", name)], limit=1)
        return rec.value.encode() if rec else None

    def write_property(self, norm_url, name, property_value, dry_run=False, environ=None):
        if dry_run:
            return
        node = self._node(norm_url)
        if not node:
            return
        value = property_value.decode() if isinstance(property_value, bytes) else property_value
        rec = self._m().search([("node_id", "=", node.id), ("name", "=", name)], limit=1)
        if rec:
            rec.value = value
        else:
            self._m().create({"node_id": node.id, "name": name, "value": value})

    def remove_property(self, norm_url, name, dry_run=False, environ=None):
        if dry_run:
            return
        node = self._node(norm_url)
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
        pass   # an der Knoten-ID, die sich beim Verschieben nicht aendert


# ---------------------------------------------------------------------------------------------------------------
# Provider (direkt auf dem ORM)
# ---------------------------------------------------------------------------------------------------------------

def _parts(path):
    return [p for p in path.strip("/").split("/") if p]


def _dav_call(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except DavError as e:
        raise DAVError(e.status, str(e)) from None


class _Common:
    def _init_node(self, node):
        self.node = node
        self.info = node._dav_info() if node else {}

    def get_creation_date(self):
        return self.info.get("ctime")

    def get_last_modified(self):
        return self.info.get("mtime")

    def set_last_modified(self, dest_path, time_stamp, *, dry_run):
        return True     # Aenderungsdatum ist das der Revision (Win32LastModifiedTime wird ignoriert)

    def _nodes(self):
        return request.env["fm.node"]

    def _cache_clear(self):
        self.environ.pop("fm.cache", None)     # Request-Cache der Pfadaufloesung nach jedem Schreiben verwerfen

    def handle_delete(self):
        # WsgiDAV prueft vor handle_delete() nur die Sperre des Elternordners (request_server.py:585-599)
        lm = self.provider.lock_manager
        lm.check_write_permission(url=self.get_ref_url(), depth="infinity",
                                  token_list=self.environ.get("wsgidav.ifLockTokenList", []),
                                  principal=self.environ.get("wsgidav.user_name"))
        self._cache_clear()
        node = self.node
        node.lock_for_update()
        node._dav_discard()
        self.remove_all_locks(recursive=True)
        return True

    def handle_move(self, dest_path):
        self._cache_clear()
        res = _dav_call(self._nodes()._dav_move, ROOT_ID, _parts(self.path), _parts(dest_path),
                        self.environ.get("HTTP_OVERWRITE", "T") == "T")
        _logger.info("fm dav: MOVE %s -> %s: %s", self.path, dest_path, res.get("result"))
        self.remove_all_locks(recursive=True)
        return True

    def handle_copy(self, dest_path, *, depth_infinity):
        self._cache_clear()
        _dav_call(self._nodes()._dav_copy, ROOT_ID, _parts(self.path), _parts(dest_path),
                  self.environ.get("HTTP_OVERWRITE", "T") == "T", depth_infinity)
        pm = self.provider.prop_manager
        pm.copy_properties(self.get_ref_url(), self.provider.ref_url_for(dest_path, self.is_collection))
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
            self._children = self._nodes().search([("parent_id", "=", self.node.id)], order="name")
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
            return FmFile(path, self.environ, self._nodes().browse())   # Knoten entsteht in end_write
        parent, name = _dav_call(self._nodes()._dav_resolve_parent, ROOT_ID, _parts(path))
        node = parent._dav_child(name) or self._nodes().create({"name": name, "parent_id": parent.id})
        return FmFile(path, self.environ, node)

    def create_collection(self, name):
        path = dav_util.join_uri(self.path, name)
        self._cache_clear()
        parent, name = _dav_call(self._nodes()._dav_resolve_parent, ROOT_ID, _parts(path))
        if parent._dav_child(name):
            raise DAVError(405)
        self._nodes().create({"name": name, "parent_id": parent.id, "is_dir": True})


class _Writer:
    """Nimmt den PUT-Strom entgegen: Temp-Datei im Blob-Speicher, SHA-256 unterwegs. Wiederholt Odoo den Request
    (retrying), ist der Strom schon gelesen: dann wird das Ergebnis des ersten Durchlaufs wiederverwendet."""

    def __init__(self, res):
        self.res = res
        self.wr = request.httprequest._HTTPRequest__wrapped
        self.done = getattr(self.wr, "_fm_dav_put", None)
        if self.done is None:
            self.tmp = os.path.join(blobstore.tmp_dir(request.env), "dav_%d_%d" % (os.getpid(), id(self.wr)))
            self.out = None          # erst beim ersten Byte: der Explorer schickt vor jeder Datei einen leeren PUT,
            self.h = hashlib.sha256()  # und fsync kostet auf dem Unraid-Array ~28 ms (19.7)
            self.size = 0

    def write(self, data):
        if self.done is None and data:
            if self.out is None:
                self.out = open(self.tmp, "wb")
            self.h.update(data)
            self.out.write(data)
            self.size += len(data)

    def close(self):
        if self.done is None:
            if self.out is not None:
                self.out.flush()
                os.fsync(self.out.fileno())
                self.out.close()
            expected = self.res.environ.get("CONTENT_LENGTH")
            if expected not in (None, "") and int(expected) != self.size:
                if self.out is not None:
                    os.unlink(self.tmp)
                raise DAVError(400, "Body unvollstaendig: %s von %s Bytes" % (self.size, expected))
            self.done = self.wr._fm_dav_put = (self.tmp, self.h.hexdigest(), self.size)


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
            import io
            return io.BytesIO(b"")
        return open(blobstore.blob_path(request.env, sha), "rb")

    def begin_write(self, *, content_type=None):
        # Wie Cloudreve (dbfs/upload.go: PrepareUpload / Upload / CompleteUpload): waehrend des Datenstroms keine
        # offene Transaktion. Bis hierher wurde nur gelesen (Aufloesung, Sperrpruefung; hoechstens abgelaufene
        # Sperren geloescht). Ohne diesen Commit stand die Verbindung den ganzen Upload lang "idle in transaction"
        # (19.8) - haelt den Snapshot, bremst VACUUM, macht Konflikte beim Abschluss wahrscheinlich.
        request.env.flush_all()
        request.env.cr.commit()
        request.env.invalidate_all()        # Abschluss liest mit neuem Snapshot, nicht aus dem ORM-Cache
        DbLockStorage._drop_cache()
        self.environ.pop("fm.cache", None)
        self.writer = _Writer(self)
        return self.writer

    def end_write(self, *, with_errors):
        if with_errors or self.writer is None or self.writer.done is None:
            return
        env = request.env
        self._cache_clear()
        tmp, sha, size = self.writer.done
        blob = env["fm.blob"]
        if size:
            blobstore.adopt_hashed(env, tmp, sha, size)            # vor dem Commit (I3)
            env.cr.postcommit.add(lambda: os.path.exists(tmp) and os.unlink(tmp))
            blob = env["fm.blob"]._get_or_create(sha, size)
        elif os.path.exists(tmp):
            env.cr.postcommit.add(lambda: os.path.exists(tmp) and os.unlink(tmp))
        # Neue Transaktion: Sperre und Ziel erneut pruefen, beides kann sich waehrend des Uploads geaendert haben
        # (Cloudreve: CompleteUpload -> ConfirmLock).
        self.provider.lock_manager.check_write_permission(
            url=self.get_ref_url(), depth="0", token_list=self.environ.get("wsgidav.ifLockTokenList", []),
            principal=self.environ.get("wsgidav.user_name"))
        parent, name = _dav_call(env["fm.node"]._dav_resolve_parent, ROOT_ID, _parts(self.path))
        node = parent._dav_child(name)
        if node and node.is_dir:
            raise DAVError(405, "Ziel ist inzwischen ein Ordner")
        if not node:
            node = env["fm.node"].create({"name": name, "parent_id": parent.id})
        node.lock_for_update()
        node._dav_set_content(blob, "webdav")
        self._init_node(node)


def _make(path, environ, node):
    if node.is_dir or node.id == ROOT_ID:
        return FmCollection(path, environ, node)
    return FmFile(path, environ, node)


class OdooInprocProvider(DAVProvider):
    def ref_url_for(self, path, is_collection):
        from urllib.parse import quote
        return quote(self.share_path + path.rstrip("/") + ("/" if is_collection else ""))

    def get_resource_inst(self, path, environ):
        cache = environ.setdefault("fm.cache", {})
        key = path.rstrip("/") or "/"
        if key not in cache:
            cache[key] = request.env["fm.node"]._dav_resolve(ROOT_ID, _parts(path))
        node = cache[key]
        if not node:
            return None
        return _make(path, environ, node)


class _MaterializeAndMapErrors(BaseMiddleware):
    """Statt WsgiDAVs ErrorPrinter: DAVError -> Antwort; alle anderen Ausnahmen (auch DB-Konkurrenzfehler) laufen
    bis zu Odoo durch (Rollback, retrying). Die Antwort wird hier vollstaendig erzeugt, weil WsgiDAV Handler als
    Generatoren schreibt, die sonst erst nach dem Ende der Odoo-Transaktion liefen."""

    def __call__(self, environ, start_response):
        sub = dav_util.SubAppStartResponse()
        try:
            it = self.next_app(environ, sub)
            try:
                body = b"".join(it)
            finally:
                if hasattr(it, "close"):
                    it.close()
        except DAVError as e:
            status = get_http_status_string(e)
            if e.value in (HTTP_NOT_MODIFIED, HTTP_NO_CONTENT):
                start_response(status, [("Content-Length", "0")])
                return [b""]
            content_type, body = e.get_response_page()
            start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(body)))]
                           + (e.add_headers or []))
            return [body]
        headers = [(k, "application/xml; charset=utf-8" if k.lower() == "content-type" and v.startswith("application;")
                    else v) for k, v in sub.response_headers]      # WsgiDAV 4.3.5, request_server.py:1283
        start_response(sub.status, headers, sub.exc_info)
        return [body]


_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = WsgiDAVApp({
            "provider_mapping": {"/": OdooInprocProvider()},
            "mount_path": MOUNT,
            "lock_storage": DbLockStorage(),
            "property_manager": DbPropertyManager(),
            "middleware_stack": [_MaterializeAndMapErrors, WsgiDavDirBrowser, RequestResolver],
            "http_authenticator": {"domain_controller": None},
            "simple_dc": {"user_mapping": {"*": True}},
            "block_size": 1024 * 1024,
            "verbose": 1,
            "logging": {"enable": False},
            "dir_browser": {"enable": True, "response_trailer": ""},
            "hotfixes": {"emulate_win32_lastmod": True},
        })
    return _APP


# ---------------------------------------------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------------------------------------------

class FmDavInproc(http.Controller):

    @http.route([MOUNT, MOUNT + "/", MOUNT + "/<path:subpath>"], type="http", auth="fmdav", methods=DAV_METHODS,
                csrf=False, save_session=False, max_content_length=64 * 1024 ** 3)
    def dav(self, subpath="", **kw):
        if WsgiDAVApp is None:
            return request.make_response("wsgidav fehlt", status=501)
        hr = request.httprequest
        wr = hr._HTTPRequest__wrapped
        method = hr.method
        if method == "OPTIONS":
            return request.make_response(b"", headers=[
                ("DAV", "1, 2"), ("MS-Author-Via", "DAV"), ("Allow", ", ".join(DAV_METHODS)), ("Content-Length", "0")])
        if method in ("LOCK", "UNLOCK"):
            request.env.cr.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_ADVISORY_KEY])
        if method == "GET":
            node = request.env["fm.node"]._dav_resolve(ROOT_ID, _parts(subpath))
            if node and not node.is_dir and node.id != ROOT_ID and node.current_revision_id:
                return self._send_file(node)

        environ = dict(wr.environ)
        environ["wsgi.input"] = wr.stream                 # Streaming, 19.6
        environ["SCRIPT_NAME"] = MOUNT
        environ["PATH_INFO"] = wr.environ["PATH_INFO"][len(MOUNT):] or "/"
        environ["REMOTE_ADDR"] = hr.remote_addr
        environ["wsgidav.auth.user_name"] = environ["wsgidav.user_name"] = request.env.user.login
        environ["wsgidav.auth.realm"] = REALM
        result = {}

        def start_response(status, headers, exc_info=None):
            result["status"], result["headers"] = status, headers

        body = b"".join(_app()(environ, start_response))
        code = int(result["status"].split()[0])
        if code >= 400:
            request.env.cr.rollback()
        headers = [(k, v) for k, v in result["headers"] if k.lower() != "content-length"]
        return request.make_response(body, headers=headers, status=code)

    def _send_file(self, node):
        sha = node.current_revision_id.blob_id.sha256
        path = blobstore.blob_path(request.env, sha)
        stream = http.Stream(
            type="path", path=path, mimetype=dav_util.guess_mime_type(node.name), download_name=node.name,
            etag=sha, size=os.path.getsize(path), last_modified=node.current_revision_id.create_date,
            immutable=False,
        )
        return stream.get_response(as_attachment=False)
