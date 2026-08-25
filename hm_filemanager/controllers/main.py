import json
import logging
import mimetypes
import os
import shutil

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from ..index_utils import index_move_tree, index_remove_tree, index_upsert
from ..path_utils import get_root, resolve_path, safe_name, to_relative

_logger = logging.getLogger(__name__)


class HmFilemanagerController(http.Controller):

    # ---------------------------------------------------------------------
    # helpers
    # ---------------------------------------------------------------------

    def _check_access(self):
        if not request.env.user.has_group("hm_filemanager.group_filemanager_user"):
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

    @http.route("/hm_filemanager/list", type="jsonrpc", auth="user", methods=["POST"])
    def list_dir(self, path="", recursive=False, domain=None):
        """Lists entries from the search index (hm_filemanager.file), not directly
        from disk - this is what makes the native Odoo search bar/facets possible.
        The index is kept in sync by every mutation below plus a periodic ir.cron scan."""
        self._check_access()
        abs_path = resolve_path(request.env, path)
        if not os.path.isdir(abs_path):
            raise UserError(_("Ordner nicht gefunden."))
        rel = to_relative(request.env, abs_path)

        if recursive:
            scope_domain = [("path", "like", f"{rel}/%")] if rel else []
        else:
            scope_domain = [("parent_path", "=", rel or False)]

        Model = request.env["hm_filemanager.file"]
        records = Model.search(scope_domain + (domain or []))

        entries = [
            {
                "name": r.name,
                "is_dir": r.is_dir,
                "size": r.size,
                "mtime": fields.Datetime.to_string(r.mtime)[:16] if r.mtime else "",
                "meta_id": r.id,
                "path": r.path,
            }
            for r in records
        ]

        return {
            "path": rel,
            "breadcrumbs": self._breadcrumbs(rel),
            "entries": entries,
        }

    @http.route("/hm_filemanager/tree", type="jsonrpc", auth="user", methods=["POST"])
    def tree_dir(self, path=""):
        self._check_access()
        abs_path = resolve_path(request.env, path)
        if not os.path.isdir(abs_path):
            raise UserError(_("Ordner nicht gefunden."))

        names = []
        with os.scandir(abs_path) as it:
            for entry in it:
                if entry.name.startswith("."):
                    continue
                try:
                    if not entry.is_dir():
                        continue
                except OSError:
                    continue
                names.append(entry.name)
        names.sort(key=str.lower)

        rel = to_relative(request.env, abs_path)
        return {
            "children": [
                {"name": name, "path": f"{rel}/{name}" if rel else name}
                for name in names
            ],
        }

    @http.route("/hm_filemanager/download", type="http", auth="user")
    def download(self, path="", disposition="attachment"):
        self._check_access()
        abs_path = resolve_path(request.env, path)
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

    # ---------------------------------------------------------------------
    # mutations
    # ---------------------------------------------------------------------

    @http.route("/hm_filemanager/mkdir", type="jsonrpc", auth="user", methods=["POST"])
    def mkdir(self, path="", name=""):
        self._check_access()
        name = safe_name(name)
        abs_parent = resolve_path(request.env, path)
        new_path = os.path.join(abs_parent, name)
        if os.path.exists(new_path):
            raise UserError(_("Es existiert bereits ein Eintrag mit diesem Namen."))
        os.makedirs(new_path)
        index_upsert(request.env, new_path)
        return {"ok": True}

    @http.route("/hm_filemanager/rename", type="jsonrpc", auth="user", methods=["POST"])
    def rename(self, path="", new_name=""):
        self._check_access()
        new_name = safe_name(new_name)
        abs_path = resolve_path(request.env, path)
        if not os.path.exists(abs_path):
            raise UserError(_("Eintrag nicht gefunden."))
        old_rel = to_relative(request.env, abs_path)
        new_abs = os.path.join(os.path.dirname(abs_path), new_name)
        new_rel = to_relative(request.env, new_abs)
        if os.path.exists(new_abs):
            raise UserError(_("Es existiert bereits ein Eintrag mit diesem Namen."))
        os.rename(abs_path, new_abs)
        index_move_tree(request.env, old_rel, new_rel)
        return {"ok": True}

    @http.route("/hm_filemanager/move", type="jsonrpc", auth="user", methods=["POST"])
    def move(self, path="", dest_path=""):
        self._check_access()
        abs_src = resolve_path(request.env, path)
        abs_dest_dir = resolve_path(request.env, dest_path)
        if not os.path.isdir(abs_dest_dir):
            raise UserError(_("Zielordner nicht gefunden."))
        old_rel = to_relative(request.env, abs_src)
        new_abs = os.path.join(abs_dest_dir, os.path.basename(abs_src))
        new_rel = to_relative(request.env, new_abs)
        if os.path.exists(new_abs):
            raise UserError(_("Es existiert bereits ein Eintrag mit diesem Namen im Zielordner."))
        shutil.move(abs_src, new_abs)
        index_move_tree(request.env, old_rel, new_rel)
        return {"ok": True}

    @http.route("/hm_filemanager/delete", type="jsonrpc", auth="user", methods=["POST"])
    def delete(self, path=""):
        self._check_access()
        abs_path = resolve_path(request.env, path)
        if abs_path == get_root(request.env):
            raise UserError(_("Das Stammverzeichnis kann nicht gelöscht werden."))
        if not os.path.exists(abs_path):
            raise UserError(_("Eintrag nicht gefunden."))
        rel = to_relative(request.env, abs_path)
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
        else:
            os.remove(abs_path)
        index_remove_tree(request.env, rel)
        return {"ok": True}

    @http.route("/hm_filemanager/upload", type="http", auth="user", methods=["POST"], csrf=False)
    def upload(self, path="", **kwargs):
        self._check_access()
        abs_dir = resolve_path(request.env, path)
        if not os.path.isdir(abs_dir):
            raise UserError(_("Zielordner nicht gefunden."))

        saved = []
        for f in request.httprequest.files.getlist("ufile"):
            name = safe_name(f.filename)
            target = os.path.join(abs_dir, name)
            to_relative(request.env, target)
            f.save(target)
            index_upsert(request.env, target)
            saved.append(name)
        return self._json_response({"ok": True, "saved": saved})

    # ---------------------------------------------------------------------
    # onlyoffice bridge
    # ---------------------------------------------------------------------

    @http.route("/hm_filemanager/open_editor", type="jsonrpc", auth="user", methods=["POST"])
    def open_editor(self, path=""):
        self._check_access()
        abs_path = resolve_path(request.env, path)
        if not os.path.isfile(abs_path):
            raise UserError(_("Datei nicht gefunden."))

        with open(abs_path, "rb") as f:
            raw = f.read()

        Attachment = request.env["ir.attachment"].sudo()
        attachment = Attachment.search([("hm_filemanager_path", "=", abs_path)], limit=1)
        vals = {
            "name": os.path.basename(abs_path),
            "raw": raw,
            "hm_filemanager_path": abs_path,
            "mimetype": mimetypes.guess_type(abs_path)[0] or "application/octet-stream",
        }
        if attachment:
            attachment.write(vals)
        else:
            attachment = Attachment.create(vals)

        return {"attachment_id": attachment.id}
