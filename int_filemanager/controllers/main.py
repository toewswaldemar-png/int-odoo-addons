import base64
import json
import logging
import mimetypes
import os
import shutil

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request
from odoo.tools.sql import escape_psql

from .. import authz, write_service
from ..index_utils import index_move_tree, index_remove_tree, index_upsert
from ..path_utils import get_root, make_shareable, resolve_path, safe_name, to_relative

_logger = logging.getLogger(__name__)


class IntFilemanagerController(http.Controller):

    # ---------------------------------------------------------------------
    # helpers
    # ---------------------------------------------------------------------

    def _check_access(self):
        """Grober Basis-Gate: überhaupt Mitglied im Filemanager. Die
        feingranulare, pfadbezogene Prüfung übernimmt authz.require() pro
        Route - dieser Check allein reicht seit Phase 2 nicht mehr aus."""
        if not request.env.user.has_group("int_filemanager.group_filemanager_user"):
            raise AccessError(_("Kein Zugriff auf den Dateimanager."))

    def _breadcrumbs(self, rel_path):
        parts = [p for p in rel_path.split("/") if p]
        crumbs = [{"name": "Start", "path": ""}]
        acc = []
        for part in parts:
            acc.append(part)
            crumbs.append({"name": part, "path": "/".join(acc)})
        return crumbs

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data),
            headers=[("Content-Type", "application/json")],
            status=status,
        )

    # ---------------------------------------------------------------------
    # browsing
    # ---------------------------------------------------------------------

    LIST_PAGE_SIZE = 200

    @http.route("/int_filemanager/list", type="jsonrpc", auth="user", methods=["POST"])
    def list_dir(self, path="", recursive=False, domain=None, offset=0):
        """Lists entries from the search index (int_filemanager.file), not directly
        from disk - this is what makes the native Odoo search bar/facets possible.
        The index is kept in sync by every mutation below plus a periodic ir.cron scan.
        Paginated: rendering (and each row's own tags read) doesn't scale to the
        thousands of rows a large folder or a recursive/unfiltered search can return."""
        self._check_access()
        abs_path = resolve_path(request.env, path)
        if not os.path.isdir(abs_path):
            raise UserError(_("Ordner nicht gefunden."))
        rel = to_relative(request.env, abs_path)
        authz.require(request.env, rel, "read")

        if recursive:
            scope_domain = [("path", "=like", escape_psql(rel) + "/%")] if rel else []
        else:
            scope_domain = [("folder_path", "=", rel or False)]

        # Nicht-sudo: die generierten Record Rules aus acl_rules.py filtern
        # geschützten Inhalt automatisch mit heraus.
        Model = request.env["int_filemanager.file"]
        full_domain = scope_domain + (domain or [])
        total = Model.search_count(full_domain)
        records = Model.search(full_domain, order="is_dir desc, name", limit=self.LIST_PAGE_SIZE, offset=offset)

        entries = []
        for r in records:
            entry = {
                "name": r.name,
                "is_dir": r.is_dir,
                "size": r.size,
                "mtime": fields.Datetime.to_string(r.mtime)[:16] if r.mtime else "",
                "meta_id": r.id,
                "path": r.path,
                "media_state": r.meta_state or False,
            }
            if r.meta_state == "error":
                entry["media_error"] = r.meta_error
            elif r.meta_state == "done":
                if r.media_width:
                    entry["media_width"] = r.media_width
                    entry["media_height"] = r.media_height
                if r.page_count:
                    entry["page_count"] = r.page_count
                if r.audio_duration:
                    entry["audio_duration"] = r.audio_duration
                    entry["audio_title"] = r.audio_title
                    entry["audio_artist"] = r.audio_artist
            entries.append(entry)

        return {
            "path": rel,
            "breadcrumbs": self._breadcrumbs(rel),
            "entries": entries,
            "total": total,
            "offset": offset,
            "limit": self.LIST_PAGE_SIZE,
        }

    @http.route("/int_filemanager/tree", type="jsonrpc", auth="user", methods=["POST"])
    def tree_dir(self, path=""):
        """Baut den Ordnerbaum für die Sidebar über die ORM statt über
        os.scandir - ein direkter Dateisystem-Scan würde die Namen
        geschützter Unterordner sichtbar machen, obwohl die generierten
        Record Rules sie eigentlich verbergen sollen (Ordner ohne eigenen,
        sichtbaren Indexeintrag - z.B. gerade erst angelegt, Watcher noch
        nicht durchgelaufen - erscheinen dadurch bewusst konservativ NICHT
        im Baum, statt sie ungeprüft direkt von der Platte zu lesen)."""
        self._check_access()
        abs_path = resolve_path(request.env, path)
        if not os.path.isdir(abs_path):
            raise UserError(_("Ordner nicht gefunden."))
        rel = to_relative(request.env, abs_path)
        authz.require(request.env, rel, "read")

        Model = request.env["int_filemanager.file"]
        records = Model.search(
            [("folder_path", "=", rel or False), ("is_dir", "=", True)],
            order="name",
        )
        return {
            "children": [{"name": r.name, "path": r.path} for r in records],
        }

    @http.route("/int_filemanager/download", type="http", auth="user")
    def download(self, path="", disposition="attachment"):
        self._check_access()
        abs_path = resolve_path(request.env, path)
        rel = to_relative(request.env, abs_path)
        authz.require(request.env, rel, "read")
        if not os.path.isfile(abs_path):
            raise UserError(_("Datei nicht gefunden."))
        disposition = "inline" if disposition == "inline" else "attachment"
        filename = os.path.basename(abs_path)
        mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        with open(abs_path, "rb") as f:
            data = f.read()
        headers = [
            ("Content-Type", mimetype),
            ("Content-Length", str(len(data))),
            ("Content-Disposition", http.content_disposition(filename, disposition)),
        ]
        return request.make_response(data, headers=headers)

    @http.route("/int_filemanager/thumbnail", type="http", auth="user")
    def thumbnail(self, path=""):
        self._check_access()
        abs_path = resolve_path(request.env, path)
        rel = to_relative(request.env, abs_path)
        authz.require(request.env, rel, "read")
        # Nicht-sudo: dieselbe generierte Leserechte-Regel wie auf
        # int_filemanager.file filtert eine geschuetzte Datei automatisch
        # heraus, statt nur ueber authz.require() hier gesondert zu pruefen.
        record = request.env["int_filemanager.file"].search([("path", "=", rel)], limit=1)
        if not record or record.meta_state != "done" or not record.sudo().thumbnail:
            raise UserError(_("Keine Vorschau verfügbar."))
        data = base64.b64decode(record.sudo().thumbnail)
        headers = [
            ("Content-Type", "image/jpeg"),
            ("Content-Length", str(len(data))),
            ("Cache-Control", "private, max-age=3600"),
        ]
        return request.make_response(data, headers=headers)

    # ---------------------------------------------------------------------
    # mutations
    # ---------------------------------------------------------------------

    @http.route("/int_filemanager/mkdir", type="jsonrpc", auth="user", methods=["POST"])
    def mkdir(self, path="", name=""):
        self._check_access()
        name = safe_name(name)
        abs_parent = resolve_path(request.env, path)
        parent_rel = to_relative(request.env, abs_parent)
        authz.require(request.env, parent_rel, "write")
        new_path = os.path.join(abs_parent, name)
        if os.path.exists(new_path):
            raise UserError(_("Es existiert bereits ein Eintrag mit diesem Namen."))
        os.makedirs(new_path)
        make_shareable(new_path, is_dir=True)
        index_upsert(request.env, new_path)
        return {"ok": True}

    @http.route("/int_filemanager/rename", type="jsonrpc", auth="user", methods=["POST"])
    def rename(self, path="", new_name=""):
        self._check_access()
        new_name = safe_name(new_name)
        abs_path = resolve_path(request.env, path)
        old_rel = to_relative(request.env, abs_path)
        authz.require(request.env, old_rel, "write")
        parent_rel = os.path.dirname(old_rel)
        authz.require_rename_or_move_allowed(request.env, old_rel, parent_rel)
        if not os.path.exists(abs_path):
            raise UserError(_("Eintrag nicht gefunden."))
        new_abs = os.path.join(os.path.dirname(abs_path), new_name)
        new_rel = to_relative(request.env, new_abs)
        if os.path.exists(new_abs):
            raise UserError(_("Es existiert bereits ein Eintrag mit diesem Namen."))
        os.rename(abs_path, new_abs)
        index_move_tree(request.env, old_rel, new_rel)
        return {"ok": True}

    @http.route("/int_filemanager/move", type="jsonrpc", auth="user", methods=["POST"])
    def move(self, path="", dest_path=""):
        self._check_access()
        abs_src = resolve_path(request.env, path)
        abs_dest_dir = resolve_path(request.env, dest_path)
        old_rel = to_relative(request.env, abs_src)
        dest_dir_rel = to_relative(request.env, abs_dest_dir)
        authz.require(request.env, old_rel, "write")
        authz.require(request.env, dest_dir_rel, "write")
        authz.require_rename_or_move_allowed(request.env, old_rel, dest_dir_rel)
        if not os.path.isdir(abs_dest_dir):
            raise UserError(_("Zielordner nicht gefunden."))
        new_abs = os.path.join(abs_dest_dir, os.path.basename(abs_src))
        new_rel = to_relative(request.env, new_abs)
        if os.path.exists(new_abs):
            raise UserError(_("Es existiert bereits ein Eintrag mit diesem Namen im Zielordner."))
        shutil.move(abs_src, new_abs)
        index_move_tree(request.env, old_rel, new_rel)
        return {"ok": True}

    @http.route("/int_filemanager/delete", type="jsonrpc", auth="user", methods=["POST"])
    def delete(self, path=""):
        self._check_access()
        abs_path = resolve_path(request.env, path)
        if abs_path == get_root(request.env):
            raise UserError(_("Das Stammverzeichnis kann nicht gelöscht werden."))
        rel = to_relative(request.env, abs_path)
        authz.require(request.env, rel, "unlink")
        authz.require_subtree_deletable(request.env, rel)
        if not os.path.exists(abs_path):
            raise UserError(_("Eintrag nicht gefunden."))
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
        else:
            os.remove(abs_path)
        index_remove_tree(request.env, rel)
        return {"ok": True}

    @http.route("/int_filemanager/upload", type="http", auth="user", methods=["POST"], csrf=False)
    def upload(self, path="", **kwargs):
        self._check_access()
        abs_dir = resolve_path(request.env, path)
        dir_rel = to_relative(request.env, abs_dir)
        authz.require(request.env, dir_rel, "write")
        if not os.path.isdir(abs_dir):
            raise UserError(_("Zielordner nicht gefunden."))

        saved = []
        for f in request.httprequest.files.getlist("ufile"):
            name = safe_name(f.filename)
            target = os.path.join(abs_dir, name)
            target_rel = to_relative(request.env, target)
            existing = None
            if os.path.exists(target):
                existing = request.env["int_filemanager.file"].sudo().search([("path", "=", target_rel)], limit=1)
            if existing:
                # Überschreibt eine bereits indexierte Datei - über den
                # zentralen Dienst (Version sichern, atomar schreiben) statt
                # kommentarlos zu überschreiben.
                write_service.snapshot_and_write(request.env, existing, f.read(), operation="upload_overwrite")
            else:
                # Neue Datei (auch: existiert auf Platte, aber noch nicht
                # indexiert) - kein Versionierungsziel vorhanden.
                f.save(target)
                make_shareable(target, is_dir=False)
                index_upsert(request.env, target)
            saved.append(name)
        return self._json_response({"ok": True, "saved": saved})

    # ---------------------------------------------------------------------
    # versioning
    # ---------------------------------------------------------------------

    @http.route("/int_filemanager/versions", type="jsonrpc", auth="user", methods=["POST"])
    def list_versions(self, path=""):
        self._check_access()
        abs_path = resolve_path(request.env, path)
        rel = to_relative(request.env, abs_path)
        authz.require(request.env, rel, "read")
        file_record = request.env["int_filemanager.file"].sudo().search([("path", "=", rel)], limit=1)
        if not file_record:
            return {"versions": []}
        # Nicht-sudo: dieselbe generierte Regel wie auf int_filemanager.file
        # filtert Versionen geschützter Dateien automatisch mit heraus.
        versions = request.env["int_filemanager.version"].search(
            [("file_id", "=", file_record.id)], order="version_no desc"
        )
        return {
            "versions": [
                {
                    "id": v.id,
                    "version_no": v.version_no,
                    "size": v.size,
                    "create_uid": v.create_uid.name,
                    "create_date": fields.Datetime.to_string(v.create_date)[:16] if v.create_date else "",
                }
                for v in versions
            ]
        }

    @http.route("/int_filemanager/version_restore", type="jsonrpc", auth="user", methods=["POST"])
    def version_restore(self, version_id=None):
        """Nimmt ausschließlich eine version_id entgegen, nie einen
        zusätzlichen frei wählbaren Zielpfad - geschrieben wird immer auf
        version.file_id's eigenen, aktuellen Pfad."""
        self._check_access()
        Version = request.env["int_filemanager.version"]
        # Bewusst search() statt browse().exists(): exists() baut nur eine
        # rohe "id IN (...)"-Abfrage ohne jede ir.rule-Einschraenkung (am
        # Odoo-19-Code verifiziert) - eine version_id ohne Leserecht waere
        # darueber also faelschlich "gefunden" gewesen. search() wendet die
        # generierte Leserechte-Regel auf int_filemanager.version korrekt an.
        version = Version.search([("id", "=", int(version_id))], limit=1) if version_id else Version.browse()
        if not version:
            raise UserError(_("Version nicht gefunden."))
        file_record = version.file_id
        authz.require(request.env, file_record.path, "write")
        raw = base64.b64decode(version.sudo().content or b"")
        write_service.snapshot_and_write(request.env, file_record, raw, operation="restore")
        return {"ok": True}

    # ---------------------------------------------------------------------
    # onlyoffice bridge
    # ---------------------------------------------------------------------

    @http.route("/int_filemanager/open_editor", type="jsonrpc", auth="user", methods=["POST"])
    def open_editor(self, path=""):
        self._check_access()
        abs_path = resolve_path(request.env, path)
        rel = to_relative(request.env, abs_path)
        # Öffnen zum Bearbeiten impliziert die Absicht, zurückzuschreiben -
        # "write" statt nur "read" prüfen.
        authz.require(request.env, rel, "write")
        if not os.path.isfile(abs_path):
            raise UserError(_("Datei nicht gefunden."))

        with open(abs_path, "rb") as f:
            raw = f.read()

        Attachment = request.env["ir.attachment"].sudo()
        attachment = Attachment.search([("int_filemanager_path", "=", abs_path)], limit=1)
        vals = {
            "name": os.path.basename(abs_path),
            "raw": raw,
            "int_filemanager_path": abs_path,
            "mimetype": mimetypes.guess_type(abs_path)[0] or "application/octet-stream",
        }
        if attachment:
            attachment.write(vals)
        else:
            attachment = Attachment.create(vals)

        return {"attachment_id": attachment.id}
