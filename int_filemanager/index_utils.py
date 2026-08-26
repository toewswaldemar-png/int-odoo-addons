import os
from datetime import datetime

from odoo import fields

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
    rel = to_relative(env, abs_path)
    parent_rel = os.path.dirname(rel) if rel else ""
    return {
        "name": os.path.basename(abs_path),
        "path": rel,
        "folder_path": parent_rel or False,
        "is_dir": os.path.isdir(abs_path),
        "size": 0 if os.path.isdir(abs_path) else st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime),
        "last_seen": fields.Datetime.now(),
    }


def index_upsert(env, abs_path):
    """Create or refresh the index record for a single filesystem path."""
    Model = env["int_filemanager.file"].sudo()
    vals = _entry_vals(env, abs_path)
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
        root.write({
            "path": new_rel,
            "name": os.path.basename(new_rel),
            "folder_path": new_parent or False,
        })

    prefix = old_rel + "/"
    for rec in Model.search([("path", "=like", prefix + "%")]):
        suffix = rec.path[len(old_rel):]
        new_child_path = new_rel + suffix
        new_child_parent = os.path.dirname(new_child_path)
        rec.write({"path": new_child_path, "folder_path": new_child_parent or False})
    _notify_change(env)
