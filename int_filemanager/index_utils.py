import os
import unicodedata
from datetime import datetime

from odoo import _, fields
from odoo.exceptions import UserError
from odoo.tools.sql import escape_psql

from . import authz
from .fulltext import fulltext_type_of
from .mediameta import media_type_of
from .path_utils import resolve_path, safe_name, to_relative

BUS_CHANNEL = "int_filemanager"
BUS_NOTIFICATION_TYPE = "int_filemanager.change"


def _notify_change(env):
    """Tell any open Filemanager view to refresh - queued for delivery on
    commit (bus.bus._sendone writes via env.cr.precommit), so it only
    actually reaches clients once the caller's transaction lands."""
    env["bus.bus"]._sendone(BUS_CHANNEL, BUS_NOTIFICATION_TYPE, {})


def _entry_vals(env, abs_path):
    st = os.stat(abs_path)
    # NFC-Normalisierung: Unicode-aequivalente, aber unterschiedlich kodierte
    # Pfade (z.B. von macOS-SMB-Clients, NFD) sonst als unterschiedliche Pfade
    # behandelt - relevant fuer die Schutzordner-Pfadpraefix-Erkennung.
    rel = unicodedata.normalize("NFC", to_relative(env, abs_path))
    parent_rel = os.path.dirname(rel) if rel else ""
    is_dir = os.path.isdir(abs_path)
    vals = {
        "name": unicodedata.normalize("NFC", os.path.basename(abs_path)),
        "path": rel,
        "folder_path": parent_rel or False,
        "is_dir": is_dir,
        "size": 0 if is_dir else st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime),
        "last_seen": fields.Datetime.now(),
    }
    if not is_dir:
        # Watcher-getriebenes CREATE/MODIFY markiert den Inhalt immer als neu
        # zu hashen - der asynchrone Hash-Cron berechnet content_sha256 danach.
        vals["hash_state"] = "pending"
        if media_type_of(vals["name"]):
            # Dasselbe unbedingt-pending-Verhalten fuer unterstuetzte
            # Medientypen - der Metadaten-Cron extrahiert danach neu. Alte
            # Werte (Thumbnail etc.) bleiben bis dahin unveraendert stehen,
            # write() unten aendert nur die hier gesetzten Felder.
            vals["meta_state"] = "pending"
        if fulltext_type_of(vals["name"]):
            # Gleiches Prinzip fuer den Volltext (Baustein 1) - eigener Zustand (ocr_state), siehe
            # filemanager_file.py fuer die Begruendung der Trennung von meta_state. Bewusst KEIN
            # Backfill fuer bereits vor dieser Aenderung indexierte Bestandsdateien (Entscheidung
            # 2026-09-05) - nur neu ankommende/geaenderte Dateien ab jetzt.
            vals["ocr_state"] = "pending"
    return vals


def index_upsert(env, abs_path):
    """Create or refresh the index record for a single filesystem path."""
    Model = env["int_filemanager.file"].sudo()
    vals = _entry_vals(env, abs_path)
    parent_rel = vals["folder_path"]
    # Unmittelbarer Elternordner ist bei Watcher-/Mkdir-getriebenen Einzelaenderungen immer
    # schon selbst indexiert (er muss existieren, damit dieser Pfad ueberhaupt entstehen
    # konnte) - anders als beim BFS-Ersteinlese-Scan reicht hier eine einzelne Query.
    vals["parent_id"] = Model.search([("path", "=", parent_rel)], limit=1).id if parent_rel else False
    rec = Model.search([("path", "=", vals["path"])], limit=1)
    if rec:
        # int_filemanager_syncing_index: Watcher-getriebenes CREATE/MODIFY auf einem
        # unveraenderten Pfad (nur Inhalt/Metadaten aktualisiert) - vals enthaelt "name"
        # immer (aus _entry_vals), aber das ist keine Rename-Absicht. Ohne den Guard wuerde
        # int_filemanager.file.write() (siehe dort) hier bei JEDER Inhaltsaenderung
        # faelschlich rename_entry() ausloesen, inkl. dessen Authz-Pruefungen - die dieser
        # sudo()-Aufruf hier bewusst NICHT durchlaufen soll (Watcher-Indexierung muss immer
        # durchlaufen, unabhaengig von Schutzordner-Rechten).
        rec.with_context(int_filemanager_syncing_index=True).write(vals)
    else:
        rec = Model.create(vals)
    _notify_change(env)
    return rec


def index_remove_tree(env, rel_path):
    """Remove the index record for rel_path and, if it was a folder, all descendants."""
    Model = env["int_filemanager.file"].sudo()
    # escape_psql(): rel_path kommt aus einem echten Datei-/Ordnernamen, der "%"/"_" enthalten
    # kann - beides SQL-LIKE-Wildcards. Ungeschaetzt wuerde z.B. "Plan_2026" auch Zeilen eines
    # unbeteiligten Nachbarn wie "PlanX2026" treffen ("_" matcht ein beliebiges Zeichen). Gleiche
    # Absicherung wie bereits in acl_rules.py/authz.py fuer denselben "=like"-Praefix-Aufbau.
    Model.search(["|", ("path", "=", rel_path), ("path", "=like", escape_psql(rel_path) + "/%")]).unlink()
    _notify_change(env)


def index_move_tree(env, old_rel, new_rel):
    """Rewrite path/folder_path for a renamed or moved file/folder and all its descendants."""
    Model = env["int_filemanager.file"].sudo()
    new_parent = os.path.dirname(new_rel) if new_rel else ""

    root = Model.search([("path", "=", old_rel)], limit=1)
    if root:
        # Nur die verschobene Wurzel braucht ein neues parent_id - Nachfahren behalten
        # denselben unmittelbaren Elternordner (dieselbe ID) innerhalb des mitverschobenen
        # Teilbaums, _parent_store kaskadiert deren parent_path automatisch mit.
        new_parent_rec = Model.search([("path", "=", new_parent)], limit=1) if new_parent else Model.browse()
        # int_filemanager_syncing_index: reine Index-Nachpflege, kein neuer Rename-Wunsch -
        # ohne den Kontext wuerde int_filemanager.file.write() (siehe dort) "name" hier als
        # Auftrag missverstehen, die (bereits umbenannte!) Datei ein zweites Mal
        # umzubenennen, mit dem inzwischen falschen alten Pfad.
        root.with_context(int_filemanager_syncing_index=True).write({
            "path": new_rel,
            "name": os.path.basename(new_rel),
            "folder_path": new_parent or False,
            "parent_id": new_parent_rec.id,
        })

    prefix = old_rel + "/"
    # escape_psql(): dieselbe Wildcard-Absicherung wie in index_remove_tree() oben.
    for rec in Model.search([("path", "=like", escape_psql(prefix) + "%")]):
        suffix = rec.path[len(old_rel):]
        new_child_path = new_rel + suffix
        new_child_parent = os.path.dirname(new_child_path)
        rec.write({"path": new_child_path, "folder_path": new_child_parent or False})
    _notify_change(env)


def rename_entry(env, old_rel, new_name):
    """Bennent eine Datei/einen Ordner tatsaechlich auf der Platte um (nicht nur den
    DB-Spiegel) und pflegt danach den Index nach (index_move_tree).

    Einzige Stelle mit den sicherheitsrelevanten Authz-Pruefungen fuers Umbenennen -
    sowohl die /int_filemanager/rename-Route (controllers/main.py, "Umbenennen" in der
    Toolbar) als auch int_filemanager.file.write() (models/filemanager_file.py, direktes
    Bearbeiten des Namensfelds im Formular) rufen ausschliesslich diese Funktion auf,
    damit es nur eine Kopie dieser Pruefungen gibt statt einer driftgefaehrdeten zweiten.

    Gibt den neuen relativen Pfad zurueck.
    """
    new_name = safe_name(new_name)
    abs_path = resolve_path(env, old_rel)
    authz.require(env, old_rel, "write")
    authz.require_rename_or_move_allowed(env, old_rel, os.path.dirname(old_rel))
    if not os.path.exists(abs_path):
        raise UserError(_("Eintrag nicht gefunden."))
    new_abs = os.path.join(os.path.dirname(abs_path), new_name)
    new_rel = to_relative(env, new_abs)
    if new_abs != abs_path:
        if os.path.exists(new_abs):
            raise UserError(_("Es existiert bereits ein Eintrag mit diesem Namen."))
        os.rename(abs_path, new_abs)
    index_move_tree(env, old_rel, new_rel)
    return new_rel
