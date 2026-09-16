import base64
import json
import logging
import mimetypes
import os
import shutil
import zipfile

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from .. import authz, write_service, zip_utils
from ..index_utils import index_move_tree, index_remove_tree, index_upsert, rename_entry
from ..path_utils import (
    friendly_fallback_name,
    get_root,
    make_shareable,
    resolve_path,
    safe_name,
    to_relative,
)

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

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data),
            headers=[("Content-Type", "application/json")],
            status=status,
        )

    # ---------------------------------------------------------------------
    # browsing
    # ---------------------------------------------------------------------

    # /int_filemanager/list (das eigene Pendant zu web_search_read, mit Pagination/Sortierung/
    # Breadcrumbs) wurde mit legacy_ui geloescht (2026-09-04) - die native ListView/SearchPanel
    # deckt Listing/Navigation vollstaendig ab, kein zweiter Endpunkt mehr dafuer noetig. tree_dir
    # unten bleibt bewusst stehen: eigene ACL-Tests (test_acl_http.py) belegen die
    # Record-Rule-Durchsetzung auf diesem Pfad, unabhaengig davon, ob ihn noch eine UI aufruft.
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
        # http.Stream statt manuellem open()+read()+make_response(): letzteres las die
        # komplette Datei in den Speicher und lieferte sie als einen Block ohne
        # HTTP-Range-Unterstuetzung - Spulen/Suchen im <video>-Player (native_ui/
        # native_list_view.js) funktionierte dadurch nicht. Stream.get_response() ruft intern
        # Werkzeugs send_file(conditional=True) auf, das 206 Partial Content/Range-Requests
        # automatisch beherrscht - dieselbe Mechanik, die Odoo fuer Attachment-Downloads nutzt.
        # Stream.from_path() scheidet aus (file_path() darin verlangt einen Pfad unterhalb eines
        # bekannten addons_path - unser konfigurierbares Filemanager-Stammverzeichnis liegt
        # ausserhalb davon), deshalb Stream direkt konstruiert - die eigene authz.require()-Pruefung
        # oben ersetzt die generische Pfadvalidierung, die from_path() sonst uebernehmen wuerde.
        stat = os.stat(abs_path)
        stream = http.Stream(
            type="path",
            path=abs_path,
            mimetype=mimetypes.guess_type(abs_path)[0] or "application/octet-stream",
            size=stat.st_size,
            download_name=os.path.basename(abs_path),
            last_modified=stat.st_mtime,
            etag=f"{int(stat.st_mtime)}-{stat.st_size}",
            public=False,
        )
        return stream.get_response(as_attachment=disposition != "inline")

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

    @http.route("/int_filemanager/zip_list", type="jsonrpc", auth="user", methods=["POST"])
    def zip_list(self, path=""):
        """Liest das Inhaltsverzeichnis einer ZIP-Datei fuer den Anzeige-Dialog
        (zip_contents_dialog.js) - zustandslos, kein Pending-State/Cron wie bei OCR/Thumbnails,
        da infolist() kein Dekomprimieren braucht (siehe zip_utils.py)."""
        self._check_access()
        abs_path = resolve_path(request.env, path)
        rel = to_relative(request.env, abs_path)
        authz.require(request.env, rel, "read")
        if not os.path.isfile(abs_path):
            raise UserError(_("Datei nicht gefunden."))
        try:
            return {"entries": zip_utils.list_entries(request.env, abs_path)}
        except zip_utils.ZipTooLarge as exc:
            raise UserError(str(exc)) from exc
        except zipfile.BadZipFile as exc:
            raise UserError(_("Keine gültige ZIP-Datei.")) from exc

    @http.route("/int_filemanager/zip_extract_entry", type="http", auth="user")
    def zip_extract_entry(self, path="", entry=""):
        """Streamt genau eine Datei aus dem Archiv - bewusst kein Entpacken aufs Dateisystem
        (Nutzerentscheidung 2026-09-12), siehe zip_utils.extract_entry()."""
        self._check_access()
        abs_path = resolve_path(request.env, path)
        rel = to_relative(request.env, abs_path)
        authz.require(request.env, rel, "read")
        if not os.path.isfile(abs_path):
            raise UserError(_("Datei nicht gefunden."))
        try:
            data = zip_utils.extract_entry(request.env, abs_path, entry)
        except zip_utils.ZipTooLarge as exc:
            raise UserError(str(exc)) from exc
        except KeyError as exc:
            raise UserError(_("Eintrag nicht im Archiv gefunden.")) from exc
        headers = [
            ("Content-Type", mimetypes.guess_type(entry)[0] or "application/octet-stream"),
            ("Content-Length", str(len(data))),
            ("Content-Disposition", f'attachment; filename="{os.path.basename(entry)}"'),
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
        """Delegiert komplett an rename_entry() (index_utils.py) - dieselbe Funktion, die
        auch int_filemanager.file.write() fuers direkte Umbenennen im Formular aufruft, damit
        die Authz-Pruefungen nur an einer Stelle existieren (siehe dort)."""
        self._check_access()
        abs_path = resolve_path(request.env, path)
        old_rel = to_relative(request.env, abs_path)
        rename_entry(request.env, old_rel, new_name)
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
        # shutil.move() wuerde das mit einer rohen Python-Fehlermeldung ("Cannot move a
        # directory into itself") ablehnen - hier vorher mit einer verstaendlichen deutschen
        # Meldung abgefangen (Drag&Drop-Verschieben, 2026-09-07).
        if dest_dir_rel == old_rel or dest_dir_rel.startswith(old_rel + "/"):
            raise UserError(_("Ein Ordner kann nicht in sich selbst oder einen eigenen Unterordner verschoben werden."))
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

    @http.route("/int_filemanager/write_text", type="jsonrpc", auth="user", methods=["POST"])
    def write_text(self, path="", content=""):
        self._check_access()
        abs_path = resolve_path(request.env, path)
        rel = to_relative(request.env, abs_path)
        authz.require(request.env, rel, "write")
        if not os.path.isfile(abs_path):
            raise UserError(_("Datei nicht gefunden."))
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        index_upsert(request.env, abs_path)
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
            # friendly_fallback_name() greift nur bei erkennbar bedeutungslosen Namen
            # (kein Buchstabe irgendwo drin, z.B. rein numerische Handy-/Cloud-Upload-IDs) -
            # sinnvoll benannte Uploads bleiben unveraendert.
            name = friendly_fallback_name(safe_name(f.filename))
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
                # FileStorage.save() erwartet in diesem Odoo-Build zwingend ein bereits offenes
                # Dateiobjekt, keinen Pfad-String mehr - Odoos eigener Monkeypatch
                # (_monkeypatches/werkzeug.py: "FileStorage.save = lambda self, dst, ...:
                # copyfileobj(self.stream, dst, ...)") ersetzt Werkzeugs Komfortvariante, die einen
                # String selbst geoeffnet haette. Gleiches Muster wie Odoos eigener Aufruf in
                # web/controllers/database.py ("with tempfile.NamedTemporaryFile(...) as data_file:
                # backup_file.save(data_file)") - live an einem 500er nachgewiesen, nicht vermutet.
                with open(target, "wb") as dst:
                    f.save(dst)
                make_shareable(target, is_dir=False)
                # index_upsert() direkt hier aufrufen (Kurswechsel 2026-09-16, live als Bug
                # gefunden: Upload lief fehlerfrei durch, Datei blieb aber dauerhaft
                # unindexiert). Vorherige Begruendung war, das ausschliesslich dem Watcher zu
                # ueberlassen (inotify-CREATE durch open() oben) - das setzt aber voraus, dass
                # der Watcher das Ereignis zuverlaessig bekommt. Laut Linux-Kernel-eigener
                # CIFS-Dokumentation (kernel.org/doc/html/.../cifs/todo.html) ist inotify auf
                # CIFS-Mounts nur unvollstaendig implementiert - live bestaetigt: derselbe
                # Schreibvorgang loeste mal CLOSE_WRITE, mal MODIFY, mal (beim lange
                # laufenden Watcher-Thread) GAR KEIN Ereignis aus. Die App kennt ihren eigenen
                # Schreibvorgang bereits - sie muss nicht auf ein bei CIFS unzuverlaessiges
                # Kernel-Feature warten, um ihn in der eigenen DB zu vermerken. Der
                # ehemalige Race mit dem Watcher (beide versuchen create() fuer denselben neuen
                # Pfad) ist jetzt in index_upsert() selbst abgefangen (siehe dort), nicht mehr
                # hier vermieden.
                index_upsert(request.env, target)
            saved.append(name)
        return self._json_response({"ok": True, "saved": saved})

    @http.route("/int_filemanager/analyze_document", type="jsonrpc", auth="user", methods=["POST"])
    def analyze_document(self, path=""):
        """Interaktiver Pfad A (Baustein 1, siehe docs/int_filemanager_paperoffice_recherche.md):
        wird direkt nach einem Drag&Drop-/Button-Upload fuer die betroffene Datei aufgerufen -
        extrahiert synchron Volltext (OCR bei Bedarf) und leitet einfache Vorschlaege daraus ab,
        zur Kontrolle im Dialog, nicht zur automatischen Uebernahme. "write"-Berechtigung, nicht
        nur "read": das Ergebnis wird auf dem Datensatz gespeichert (content_text/ocr_state)."""
        self._check_access()
        abs_path = resolve_path(request.env, path)
        rel = to_relative(request.env, abs_path)
        authz.require(request.env, rel, "write")
        return request.env["int_filemanager.file"].action_analyze_document(rel)

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
    # externe Freigabe (anonymer Link, kein Login)
    # ---------------------------------------------------------------------

    @http.route("/int_filemanager/share/<string:token>", type="http", auth="public")
    def share_download(self, token):
        """Bewusst OHNE ir.rule/authz.require - dieselbe Entscheidung wie in
        Runde 2/3 (siehe Ausbauplan): ein anonymer Aufrufer hat keinen
        sinnvollen ir.rule-Kontext, hier wird alles explizit selbst geprüft.
        Unbekannt/abgelaufen/widerrufen liefern bewusst dieselbe Fehlerseite -
        ein Unterschied würde verraten, ob ein Token je existiert hat."""
        record = request.env["int_filemanager.file"].sudo().search([("share_token", "=", token)], limit=1)
        if (
            not token
            or not record
            or not record.share_expires_at
            or record.share_expires_at < fields.Datetime.now()
        ):
            return request.not_found()

        root = get_root(request.env)
        abs_path = os.path.join(root, record.path)
        if not os.path.isfile(abs_path):
            return request.not_found()

        with open(abs_path, "rb") as f:
            data = f.read()
        request.env["int_filemanager.share_log"].sudo().create(
            {"file_id": record.id, "path": record.path, "filename": record.name, "event_type": "downloaded"}
        )
        mimetype = mimetypes.guess_type(record.name)[0] or "application/octet-stream"
        headers = [
            ("Content-Type", mimetype),
            ("Content-Length", str(len(data))),
            ("Content-Disposition", http.content_disposition(record.name, "attachment")),
            ("Cache-Control", "private, no-store"),
        ]
        return request.make_response(data, headers=headers)

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
