import os
import unicodedata
from datetime import datetime

from odoo import fields

from .mediameta import media_type_of
from .path_utils import to_relative

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
        rec.write(vals)
    else:
        rec = Model.create(vals)
    _notify_change(env)
    return rec


def index_remove_tree(env, rel_path):
    """Remove the index record for rel_path and, if it was a folder, all descendants."""
    Model = env["int_filemanager.file"].sudo()
    Model.search(["|", ("path", "=", rel_path), ("path", "=like", rel_path + "/%")]).unlink()
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
        root.write({
            "path": new_rel,
            "name": os.path.basename(new_rel),
            "folder_path": new_parent or False,
            "parent_id": new_parent_rec.id,
        })

    prefix = old_rel + "/"
    for rec in Model.search([("path", "=like", prefix + "%")]):
        suffix = rec.path[len(old_rel):]
        new_child_path = new_rel + suffix
        new_child_parent = os.path.dirname(new_child_path)
        rec.write({"path": new_child_path, "folder_path": new_child_parent or False})
    _notify_change(env)
