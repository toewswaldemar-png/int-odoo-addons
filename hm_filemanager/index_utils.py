import os
from datetime import datetime

from odoo import fields

from .path_utils import to_relative


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
    Model = env["hm_filemanager.file"].sudo()
    vals = _entry_vals(env, abs_path)
    rec = Model.search([("path", "=", vals["path"])], limit=1)
    if rec:
        rec.write(vals)
    else:
        rec = Model.create(vals)
    return rec


def index_remove_tree(env, rel_path):
    """Remove the index record for rel_path and, if it was a folder, all descendants."""
    Model = env["hm_filemanager.file"].sudo()
    Model.search(["|", ("path", "=", rel_path), ("path", "=like", rel_path + "/%")]).unlink()


def index_move_tree(env, old_rel, new_rel):
    """Rewrite path/folder_path for a renamed or moved file/folder and all its descendants."""
    Model = env["hm_filemanager.file"].sudo()
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
