import os

from odoo.exceptions import ValidationError

DEFAULT_ROOT = "/mnt/hm-daten"


def get_root(env):
    root = env["ir.config_parameter"].sudo().get_param("int_filemanager.root_path", DEFAULT_ROOT)
    return os.path.realpath(root)


def resolve_path(env, rel_path):
    """Resolve a client-supplied relative path to an absolute path, guaranteed
    to stay inside the configured filemanager root (blocks path traversal)."""
    root = get_root(env)
    rel_path = (rel_path or "").strip().lstrip("/\\")
    target = os.path.realpath(os.path.join(root, rel_path))
    if target != root and not target.startswith(root + os.sep):
        raise ValidationError("Ungültiger Pfad.")
    return target


def to_relative(env, abs_path):
    """Inverse of resolve_path: validates that abs_path is inside root and
    returns the path relative to it."""
    root = get_root(env)
    abs_path = os.path.realpath(abs_path)
    if abs_path == root:
        return ""
    if not abs_path.startswith(root + os.sep):
        raise ValidationError("Pfad liegt außerhalb des Filemanager-Stammverzeichnisses.")
    return os.path.relpath(abs_path, root)


def safe_name(name):
    """Validate a plain file/folder name (no path separators, no . / ..)."""
    name = (name or "").strip()
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValidationError("Ungültiger Name.")
    return name


def make_shareable(abs_path, is_dir):
    """The share's existing files/folders (created via Samba) are all 777/666
    so any Windows user can write to them regardless of SMB user mapping.
    os.makedirs/f.save() create with the container's own uid:gid (100:101)
    and default umask instead, which locks other users out - override it."""
    os.chmod(abs_path, 0o777 if is_dir else 0o666)
