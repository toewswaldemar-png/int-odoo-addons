"""Reads groups and entries from a .kdbx file; no Odoo imports, so it can run on its own."""

from pykeepass import PyKeePass


def read_kdbx(path, password=None, keyfile=None):
    """Return the raw content of a KeePass database.

    ``{"groups": [{"uuid", "name", "parent"}], "entries": [{"uuid", "title",
    "username", "url", "group"}]}``; ``parent`` and ``group`` are the uuid of the
    containing group or ``None`` at the top. Passwords and notes are never read.
    The recycle bin is left out.
    """
    database = PyKeePass(path, password=password, keyfile=keyfile)
    recycle_bin = database.recyclebin_group
    recycle_uuid = recycle_bin.uuid if recycle_bin else None

    def uuid_of(group):
        return None if group is None or group.is_root_group else str(group.uuid)

    def in_recycle_bin(group):
        while group is not None:
            if recycle_uuid is not None and group.uuid == recycle_uuid:
                return True
            group = group.parentgroup
        return False

    groups = [
        {"uuid": str(group.uuid), "name": group.name, "parent": uuid_of(group.parentgroup)}
        for group in database.groups
        if not group.is_root_group and not in_recycle_bin(group)
    ]
    entries = [
        {
            "uuid": str(entry.uuid),
            "title": entry.title,
            "username": entry.username,
            "url": entry.url,
            "group": uuid_of(entry.parentgroup),
        }
        for entry in database.entries
        if not in_recycle_bin(entry.parentgroup)
    ]
    return {"groups": groups, "entries": entries}
