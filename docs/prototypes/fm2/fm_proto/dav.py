"""Prototyp WebDAV-Anbindung (int_filemanager 2, Konzept Abschnitt 11 A).

Der WebDAV-Dienst (docs/prototypes/fm2/fmdav) spricht das Protokoll mit dem Client und ruft diese Routen im Namen
des Nutzers auf (auth='bearer', API-Schluessel des Nutzers). Odoo bleibt alleiniger Schreiber (I1): der Dienst
schreibt nichts auf die Platte, grosse PUTs kommen in 4-MB-Stuecken hier an.

Pfade sind Listen von Namen unterhalb eines Wurzelknotens (root). Alle Verweise intern ueber IDs (I8).

Identitaetsregel ("Ersetzen durch Umbenennen behaelt die Identitaet"):
- MOVE auf einen belegten Namen (Overwrite): das Ziel bekommt den Inhalt der Quelle als neue Revision, die Quelle
  verschwindet. Das Ziel behaelt ID, Versionen, Tags.
- Word/Excel speichern als: neue Fassung in Temp-Datei T schreiben, Original X wegbenennen (oder loeschen), T auf
  den alten Namen von X umbenennen, weggebenanntes X loeschen. Jeder MOVE/DELETE einer Datei merkt sich den
  geraeumten Platz (vacated_*). Wird eine *frische* Datei T desselben Nutzers auf einen kuerzlich von X
  geraeumten Platz gezogen, tauschen X und T: X bekommt den neuen Inhalt und seinen Namen zurueck, T uebernimmt
  X' Zwischenname mit dem alten Inhalt und ist "Schatten" von X (shadow_of_id). Loeschen eines Schattens, dessen
  Inhalte alle in X' Versionen liegen, loescht endgueltig (nichts geht verloren, I6); sonst Papierkorb.
"""
import datetime
import logging
import mimetypes
import os
import unicodedata

from odoo import api, fields, http, models
from odoo.exceptions import AccessError
from odoo.http import request

from . import blobstore

_logger = logging.getLogger(__name__)
SWAP_WINDOW = int(os.environ.get("FM_DAV_SWAP_WINDOW", "600"))  # Sekunden
CHUNK_LIMIT = 8 * 1024 * 1024


class DavError(Exception):
    def __init__(self, status, msg=""):
        super().__init__(msg)
        self.status = status


class FmNodeDav(models.Model):
    _inherit = "fm.node"

    vacated_parent_id = fields.Many2one("fm.node", ondelete="set null")
    vacated_name = fields.Char()
    vacated_at = fields.Datetime(index=True)
    vacated_uid = fields.Many2one("res.users", ondelete="set null")
    shadow_of_id = fields.Many2one("fm.node", ondelete="set null")
    removal_reason = fields.Selection([("trash", "Papierkorb")])

    # ---------- Hilfen ----------

    def _dav_info(self):
        self.ensure_one()
        rev = self.current_revision_id
        mdate = rev.create_date or self.write_date
        return {
            "id": self.id,
            "name": self.name,
            "is_dir": self.is_dir,
            "size": int(rev.blob_id.size or 0) if rev else 0,
            "sha256": rev.blob_id.sha256 if rev else None,
            "rev": rev.revision_no if rev else 0,
            "mtime": mdate.timestamp() if mdate else None,
            "ctime": self.create_date.timestamp() if self.create_date else None,
        }

    def _dav_child(self, name):
        self.ensure_one()
        return self.search([("parent_id", "=", self.id), ("name", "=", name)], limit=1)

    def _dav_subtree(self):
        """Knoten selbst plus alle aktiven Nachfahren (parent_path-Praefix, indiziert)."""
        self.ensure_one()
        return self.search([("parent_path", "=like", self.parent_path + "%")])

    def _dav_vacate(self):
        """Den aktuellen Platz (Ordner, Name) als geraeumt merken."""
        for node in self.filtered(lambda n: not n.is_dir):
            node.write({
                "vacated_parent_id": node.parent_id.id,
                "vacated_name": node.name,
                "vacated_at": fields.Datetime.now(),
                "vacated_uid": self.env.uid,
            })

    def _dav_trash(self):
        self.ensure_one()
        self._dav_vacate()
        subtree = self._dav_subtree()
        subtree.write({"active": False, "removal_reason": "trash"})
        # Der eindeutige Name-Index kennt das ORM nicht: sofort schreiben, sonst laeuft ein folgendes
        # INSERT/UPDATE mit demselben Namen vor diesem UPDATE (litmus copymove).
        subtree.flush_recordset()

    def _dav_blob_ids(self):
        """Inhalte aller Revisionen (ohne den leeren Inhalt)."""
        blobs = self.env["fm.revision"].search([("node_id", "=", self.id)]).blob_id
        return set(blobs.filtered(lambda b: b.sha256 != blobstore.EMPTY_SHA).ids)

    def _dav_discard(self):
        """Entfernen eines Knotens aus dem Namensraum. Endgueltig nur fuer Schatten, deren Inhalte alle in den
        Versionen ihres Originals liegen (I6), sonst Papierkorb."""
        self.ensure_one()
        orig = self.shadow_of_id
        if not self.is_dir and orig and self._dav_blob_ids() <= orig._dav_blob_ids():
            self.unlink()
            return "purged"
        self._dav_trash()
        return "trashed"

    def _dav_set_content(self, blob, origin):
        """Neue Fassung setzen. Gleicher Inhalt wie bisher -> keine neue Revision. Leerer Inhalt auf einer Datei
        ohne Revision -> bleibt ohne Revision (Explorer legt Dateien erst leer an, dann mit Inhalt)."""
        self.ensure_one()
        current = self.current_revision_id.blob_id
        if blob == current:
            return self.current_revision_id
        if not blob:
            if not current:
                return self.current_revision_id
            blobstore.ensure_empty_blob(self.env)
            blob = self.env["fm.blob"]._get_or_create(blobstore.EMPTY_SHA, 0)
        return self._add_revision(blob, origin)

    # ---------- Operationen ----------

    @api.model
    def _dav_resolve(self, root_id, path):
        """Pfad (Liste von Namen) unter root_id -> Knoten, in **einer** Abfrage (19.7: Ebene fuer Ebene kostete je
        Request 3-4 Abfragen, mehrfach je Request). Rechte bleiben beim ORM: der gefundene Knoten wird mit
        check_access('read') geprueft, sonst gilt er als nicht vorhanden (I7)."""
        if not path:
            node = self.browse(root_id).exists()
            if not node:
                raise DavError(404, "root")
            return node
        self.flush_model(["name", "parent_id", "active", "is_dir"])
        self.env.cr.execute("""
            WITH RECURSIVE r(id, depth, is_dir) AS (
                SELECT id, 0, TRUE FROM fm_node WHERE id = %(root)s
                UNION ALL
                SELECT n.id, r.depth + 1, COALESCE(n.is_dir, FALSE)
                  FROM r JOIN fm_node n ON n.parent_id = r.id
                 WHERE r.depth < %(depth)s AND r.is_dir AND n.active IS TRUE
                   AND n.name = (%(names)s::varchar[])[r.depth + 1]
            ) SELECT id FROM r WHERE depth = %(depth)s""", {"root": root_id, "depth": len(path), "names": list(path)})
        row = self.env.cr.fetchone()
        if not row:
            return self.browse()
        node = self.browse(row[0])
        try:
            node.check_access("read")
        except AccessError:
            return self.browse()
        return node

    @api.model
    def _dav_resolve_parent(self, root_id, path):
        if not path:
            raise DavError(403, "root")
        parent = self._dav_resolve(root_id, path[:-1])
        if not parent or not (parent.is_dir or parent.id == root_id):
            raise DavError(409, "parent missing")
        return parent, _norm(path[-1])

    @api.model
    def _dav_move(self, root_id, src, dst, overwrite):
        s = self._dav_resolve(root_id, src)
        if not s or s.id == root_id:
            raise DavError(404 if not s else 403, "source")
        parent, name = self._dav_resolve_parent(root_id, dst)
        if s.is_dir and (parent == s or parent.parent_path.startswith(s.parent_path)):
            raise DavError(403, "move below itself")
        s.lock_for_update()
        d = parent._dav_child(name)
        if d == s:
            return {"result": "noop"}
        if d:
            if not overwrite:
                raise DavError(412, "destination exists")
            d.lock_for_update()
            if not s.is_dir and not d.is_dir:
                # Ersetzen: Ziel behaelt die Identitaet
                d._dav_set_content(s.current_revision_id.blob_id, "webdav")
                s.shadow_of_id = d
                how = s._dav_discard()
                return {"result": "replaced", "node": d.id, "source": how}
            d._dav_trash()
        elif not s.is_dir:
            x = self._dav_vacated_candidate(parent, name, s)
            if x:
                return self._dav_swap(x, s, parent, name)
        if not s.is_dir:
            s._dav_vacate()
        s.write({"parent_id": parent.id, "name": name})
        return {"result": "moved", "node": s.id}

    @api.model
    def _dav_vacated_candidate(self, parent, name, s):
        now = fields.Datetime.now()
        window = now - datetime.timedelta(seconds=SWAP_WINDOW)
        fresh = s.create_uid.id == self.env.uid and s.create_date >= window
        if not fresh:
            return self.browse()
        return self.with_context(active_test=False).search([
            ("vacated_parent_id", "=", parent.id), ("vacated_name", "=", name),
            ("vacated_at", ">=", window), ("vacated_uid", "=", self.env.uid),
            ("is_dir", "=", False), ("id", "!=", s.id),
            "|", ("active", "=", True), ("removal_reason", "=", "trash"),
        ], order="vacated_at desc", limit=1)

    @api.model
    def _dav_swap(self, x, s, parent, name):
        """x (Original, weggebenannt oder geloescht) bekommt Namen und neuen Inhalt von s; s wird Schatten."""
        x.lock_for_update()
        old_blob = x.current_revision_id.blob_id
        new_blob = s.current_revision_id.blob_id
        vacate_off = {"vacated_parent_id": False, "vacated_name": False, "vacated_at": False, "vacated_uid": False}
        if x.active:
            x_parent, x_name = x.parent_id, x.name
            x.write({"parent_id": parent.id, "name": name, **vacate_off})
            x.flush_recordset()     # Platz von x erst freigeben, dann s hineinsetzen (Name-Index)
            s.write({"parent_id": x_parent.id, "name": x_name, "shadow_of_id": x.id})
            x._dav_set_content(new_blob, "webdav")
            s._dav_set_content(old_blob, "webdav")
            result = "swapped"
        else:
            x.write({"active": True, "removal_reason": False, "parent_id": parent.id, "name": name, **vacate_off})
            x._dav_set_content(new_blob, "webdav")
            s.shadow_of_id = x
            s._dav_discard()
            result = "restored"
        _logger.info("fm dav: %s node %s <- %s (%s)", result, x.id, s.id, name)
        return {"result": result, "node": x.id, "shadow": s.id}

    @api.model
    def _dav_copy(self, root_id, src, dst, overwrite, depth_infinity=True):
        s = self._dav_resolve(root_id, src)
        if not s:
            raise DavError(404, "source")
        parent, name = self._dav_resolve_parent(root_id, dst)
        if s.is_dir and (parent == s or parent.parent_path.startswith(s.parent_path)):
            raise DavError(403, "copy below itself")
        d = parent._dav_child(name)
        if d:
            if not overwrite:
                raise DavError(412, "destination exists")
            if not s.is_dir and not d.is_dir:
                d._dav_set_content(s.current_revision_id.blob_id, "webdav")
                return {"result": "replaced", "node": d.id}
            d._dav_trash()
        new = self._dav_copy_node(s, parent, name, depth_infinity)
        return {"result": "copied", "node": new.id}

    @api.model
    def _dav_copy_node(self, s, parent, name, recursive):
        new = self.create({"name": name, "parent_id": parent.id, "is_dir": s.is_dir})
        if not s.is_dir:
            if s.current_revision_id:
                new._add_revision(s.current_revision_id.blob_id, "webdav")   # keine Bytes kopiert
        elif recursive:
            for child in self.search([("parent_id", "=", s.id)]):
                self._dav_copy_node(child, new, child.name, True)
        return new


def _norm(name):
    name = unicodedata.normalize("NFC", name)
    if not name or name in (".", "..") or "/" in name:
        raise DavError(400, "bad name")
    return name


class FmDav(http.Controller):
    """Alle Routen im Namen des Nutzers (Bearer-API-Schluessel). Kein sudo auf Nutzereingaben (I7)."""

    def _run(self, fn):
        try:
            return {"ok": True, **(fn() or {})}
        except DavError as e:
            request.env.cr.rollback()
            return {"ok": False, "status": e.status, "msg": str(e)}

    @http.route("/fmp/dav/whoami", type="jsonrpc", auth="bearer")
    def whoami(self):
        return {"uid": request.env.uid, "login": request.env.user.login}

    @http.route("/fmp/dav/stat", type="jsonrpc", auth="bearer", readonly=True)
    def stat(self, root, path, children=False):
        def fn():
            Node = request.env["fm.node"]
            node = Node._dav_resolve(root, path)
            if not node:
                return {"node": None}
            res = {"node": node._dav_info()}
            if children and (node.is_dir or node.id == root):
                res["children"] = [c._dav_info() for c in Node.search([("parent_id", "=", node.id)], order="name")]
            return res
        return self._run(fn)

    @http.route("/fmp/dav/mkcol", type="jsonrpc", auth="bearer")
    def mkcol(self, root, path):
        def fn():
            Node = request.env["fm.node"]
            parent, name = Node._dav_resolve_parent(root, path)
            if parent._dav_child(name):
                raise DavError(405, "exists")
            return {"node": Node.create({"name": name, "parent_id": parent.id, "is_dir": True})._dav_info()}
        return self._run(fn)

    @http.route("/fmp/dav/touch", type="jsonrpc", auth="bearer")
    def touch(self, root, path):
        """Leere Datei anlegen (LOCK auf unbelegten Namen, leerer PUT). Leere Datei = Knoten ohne Revision."""
        def fn():
            Node = request.env["fm.node"]
            parent, name = Node._dav_resolve_parent(root, path)
            node = parent._dav_child(name)
            if node and node.is_dir:
                raise DavError(405, "is collection")
            if not node:
                node = Node.create({"name": name, "parent_id": parent.id})
            return {"node": node._dav_info()}
        return self._run(fn)

    @http.route("/fmp/dav/delete", type="jsonrpc", auth="bearer")
    def delete(self, root, path):
        def fn():
            node = request.env["fm.node"]._dav_resolve(root, path)
            if not node:
                raise DavError(404, "missing")
            if node.id == root:
                raise DavError(403, "root")
            node.lock_for_update()
            return {"result": node._dav_discard()}
        return self._run(fn)

    @http.route("/fmp/dav/move", type="jsonrpc", auth="bearer")
    def move(self, root, src, dst, overwrite=True):
        return self._run(lambda: request.env["fm.node"]._dav_move(root, src, dst, overwrite))

    @http.route("/fmp/dav/copy", type="jsonrpc", auth="bearer")
    def copy(self, root, src, dst, overwrite=True, depth_infinity=True):
        return self._run(lambda: request.env["fm.node"]._dav_copy(root, src, dst, overwrite, depth_infinity))

    # ---------- PUT in Stuecken ----------

    @http.route("/fmp/dav/put/init", type="jsonrpc", auth="bearer")
    def put_init(self, root, path, operation_key, size=None):
        def fn():
            Node = request.env["fm.node"]
            parent, name = Node._dav_resolve_parent(root, path)
            node = parent._dav_child(name)
            if node and node.is_dir:
                raise DavError(405, "is collection")
            Up = request.env["fm.upload"]
            up = Up.search([("operation_key", "=", operation_key)], limit=1)
            if not up:
                up = Up.create({"operation_key": operation_key, "name": name, "parent_id": parent.id,
                                "size_expected": size if size is not None else -1})
            return {"received": up._received(), "state": up.state}
        return self._run(fn)

    @http.route("/fmp/dav/put/chunk", type="http", auth="bearer", methods=["PUT"], csrf=False,
                max_content_length=CHUNK_LIMIT)
    def put_chunk(self, operation_key, offset, **kw):
        up = request.env["fm.upload"].search([("operation_key", "=", operation_key)], limit=1)
        if not up or up.state != "open":
            return request.make_json_response({"error": "unknown or finished upload"}, status=409)
        offset = int(offset)
        have = up._received()
        length = int(request.httprequest.headers.get("Content-Length", 0))
        if offset + length <= have:
            return request.make_json_response({"received": have, "skipped": True})
        if offset != have:
            return request.make_json_response({"error": "offset mismatch", "received": have}, status=409)
        data = request.httprequest.get_data()      # ein Stueck, begrenzt durch max_content_length (19.2)
        with open(up._tmp_path(), "ab") as out:
            out.write(data)
        return request.make_json_response({"received": have + len(data)})

    @http.route("/fmp/dav/put/finish", type="jsonrpc", auth="bearer")
    def put_finish(self, operation_key, size):
        def fn():
            env = request.env
            up = env["fm.upload"].search([("operation_key", "=", operation_key)], limit=1)
            if not up:
                raise DavError(409, "unknown upload")
            up.lock_for_update()
            if up.state == "done":
                return {"node": up.node_id._dav_info(), "repeated": True}
            received = up._received()
            if received != size or (up.size_expected >= 0 and int(up.size_expected) != size):
                raise DavError(400, "size mismatch: %s/%s/%s" % (received, size, up.size_expected))
            Node = env["fm.node"]
            node = up.parent_id._dav_child(up.name)
            if not node:
                node = Node.create({"name": up.name, "parent_id": up.parent_id.id})
            node.lock_for_update()
            blob = env["fm.blob"]
            if size:
                tmp = up._tmp_path()
                sha, bsize, _dedup = blobstore.adopt_temp(env, tmp, keep_tmp=True)   # vor dem Commit (I3)
                env.cr.postcommit.add(lambda: os.path.exists(tmp) and os.unlink(tmp))
                blob = env["fm.blob"]._get_or_create(sha, bsize)
            rev = node._dav_set_content(blob, "webdav")
            up.write({"state": "done", "node_id": node.id, "revision_id": rev.id})
            return {"node": node._dav_info(), "repeated": False}
        return self._run(fn)

    @http.route("/fmp/dav/put/small", type="http", auth="bearer", methods=["PUT"], csrf=False,
                max_content_length=CHUNK_LIMIT)
    def put_small(self, root, path, **kw):
        """Kleine Datei in einem Aufruf (ein Commit). Wiederholung durch retrying() ist harmlos: gleicher Hash ->
        derselbe Blob, gleicher Inhalt -> keine neue Revision."""
        def fn():
            env = request.env
            parts = [p for p in path.split("/") if p]
            parent, name = env["fm.node"]._dav_resolve_parent(int(root), parts)
            node = parent._dav_child(name)
            if node and node.is_dir:
                raise DavError(405, "is collection")
            data = request.httprequest.get_data()
            blob = env["fm.blob"]
            if data:
                tmp = os.path.join(blobstore.tmp_dir(env), "small_%s_%d" % (os.getpid(), id(data)))
                with open(tmp, "wb") as out:
                    out.write(data)
                sha, bsize, _dedup = blobstore.adopt_temp(env, tmp)
                blob = env["fm.blob"]._get_or_create(sha, bsize)
            if not node:
                node = env["fm.node"].create({"name": name, "parent_id": parent.id})
            node.lock_for_update()
            node._dav_set_content(blob, "webdav")
            return {"node": node._dav_info()}
        return request.make_json_response(self._run(fn))

    # ---------- GET ----------

    @http.route("/fmp/dav/get/<int:node_id>", type="http", auth="bearer", readonly=True)
    def get(self, node_id, **kw):
        node = request.env["fm.node"].browse(node_id).exists()
        if not node or not node.current_revision_id:
            raise request.not_found()
        sha = node.current_revision_id.blob_id.sha256
        path = blobstore.blob_path(request.env, sha)
        stream = http.Stream(
            type="path", path=path, mimetype=mimetypes.guess_type(node.name)[0] or "application/octet-stream",
            download_name=node.name, etag=sha, size=os.path.getsize(path),
            last_modified=os.path.getmtime(path), immutable=False,
        )
        return stream.get_response(as_attachment=False)


class FmStreamDiag(http.Controller):
    """Diagnose (Konzept 19.6): Kann eine Odoo-Route einen grossen Body streamen, ohne ihn in den RAM zu laden?
    Odoo filtert wsgi.input aus request.httprequest.environ und reicht .stream nicht durch (HTTPREQUEST_ATTRIBUTES),
    das originale werkzeug.Request liegt aber im Wrapper (_HTTPRequest__wrapped, so greift auch Odoo selbst zu)."""

    @http.route("/fmp/diag/stream", type="http", auth="bearer", methods=["PUT"], csrf=False,
                max_content_length=64 * 1024 ** 3)
    def diag_stream(self, **kw):
        import hashlib
        import time
        from .controllers import _rss
        raw = request.httprequest._HTTPRequest__wrapped.stream
        before = _rss()
        t = time.time()
        h = hashlib.sha256()
        n = 0
        tmp = os.path.join(blobstore.tmp_dir(request.env), "diag_stream_%d" % os.getpid())
        with open(tmp, "wb") as out:
            while chunk := raw.read(1024 * 1024):
                h.update(chunk)
                out.write(chunk)
                n += len(chunk)
        os.unlink(tmp)
        return request.make_json_response({"bytes": n, "sha256": h.hexdigest(), "seconds": round(time.time() - t, 1),
                                           "rss_before": before, "rss_after": _rss(), "pid": os.getpid()})
