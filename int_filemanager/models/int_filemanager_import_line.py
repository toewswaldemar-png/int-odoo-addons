import fnmatch
import os
import posixpath
import unicodedata
from datetime import datetime, timezone

import psycopg2
from psycopg2 import IntegrityError
from werkzeug.security import safe_join

from odoo import fields, models
from odoo.exceptions import UserError

# Files that are not read in (compared in lower case with the lower case name).
EXCLUDED_NAMES = ("thumbs.db", "desktop.ini", ".ds_store", "~$*", "*.tmp", "*.part", "*.crdownload")
# A file that changes while it is copied is copied again, this often.
STABLE_TRIES = 3
# Names tried for one folder ("a", "a (2)", ...) before giving up.
NAME_TRIES = 1000


def _clash_key(name):
    """What the filemanager takes for the same name: composed, trimmed, case aside."""
    return unicodedata.normalize("NFC", name).strip().lower()


class IntFilemanagerImportLine(models.Model):
    """A folder or file of an order: the queue of the reading in and its protocol."""

    _name = "int.filemanager.import.line"
    _description = "Filemanager import line"
    _rec_name = "path"
    _order = "id"

    import_id = fields.Many2one(
        "int.filemanager.import", required=True, index=True, ondelete="cascade"
    )
    parent_id = fields.Many2one(
        "int.filemanager.import.line",
        index=True,
        ondelete="cascade",
        help="The line of the folder this one lies in.",
    )
    kind = fields.Selection(
        [("folder", "Folder"), ("file", "File")], required=True, default="file"
    )
    path = fields.Char(string="Path", required=True, help="Below the folder to read in.")
    name = fields.Char(required=True)
    size = fields.Float()
    mtime = fields.Datetime(string="Modified on the disk")
    state = fields.Selection(
        [
            ("pending", "To do"),
            ("done", "Done"),
            ("skipped", "Skipped"),
            ("excluded", "Excluded"),
            ("error", "Failed"),
        ],
        required=True,
        default="pending",
    )
    message = fields.Char()
    clash = fields.Boolean(
        string="Name taken",
        help="Another one of this folder has the same name (case, spaces and composed or "
        "decomposed letters aside): this one gets a number.",
    )
    listed = fields.Boolean(help="A folder: its content was listed by the check.")
    folder_id = fields.Many2one("int.filemanager.folder", ondelete="set null")
    document_id = fields.Many2one("int.filemanager.document", ondelete="set null")

    _import_path = models.UniqueIndex(
        "(import_id, md5(path))", "This path is in the order already."
    )
    _import_state = models.Index("(import_id, state)")

    # ---- Check -------------------------------------------------------------------------

    def _list_directory(self, source):
        """Make a line for everything in the folder of this line.

        A link, a file of an odd kind, a name that is not valid and an excluded file get a
        line too, so the report shows them; they are not read in.
        """
        self.ensure_one()
        relative = posixpath.join(source.relative, self.path)
        directory = safe_join(source.root, relative)
        real = os.path.realpath(directory)
        if real != source.root and not real.startswith(source.root + os.sep):
            self.write(
                {
                    "listed": True,
                    "state": "error",
                    "message": self.env._("The folder is not below the root folder."),
                }
            )
            return
        try:
            with os.scandir(real) as scanner:
                entries = sorted(scanner, key=lambda entry: entry.name)
        except OSError as error:
            self.write({"listed": True, "state": "error", "message": error.strerror})
            return
        taken = {"folder": set(), "file": set()}
        values = []
        for entry in entries:
            path = posixpath.join(self.path, entry.name)
            vals = {
                "import_id": self.import_id.id,
                "parent_id": self.id,
                "path": path,
                "name": entry.name,
            }
            try:
                path.encode()
            except UnicodeEncodeError:
                # Not valid UTF-8: the database could not keep it, and neither could a name.
                escaped = path.encode("utf-8", "backslashreplace").decode()
                vals.update(
                    path=escaped,
                    name=entry.name.encode("utf-8", "backslashreplace").decode(),
                    state="error",
                    message=self.env._("The name is not valid UTF-8."),
                )
                values.append(vals)
                continue
            vals.update(self._describe_entry(entry))
            if vals.get("state", "pending") in ("pending", "excluded"):
                kind = vals.get("kind", "file")
                key = _clash_key(entry.name)
                vals["clash"] = key in taken[kind]
                taken[kind].add(key)
            values.append(vals)
        self.env["int.filemanager.import.line"].create(values)
        self.listed = True

    def _describe_entry(self, entry):
        """The values of a line for an entry of the disk."""
        try:
            if entry.is_symlink():
                return {"state": "skipped", "message": self.env._("A symbolic link.")}
            if entry.is_dir(follow_symlinks=False):
                return {"kind": "folder"}
            if not entry.is_file(follow_symlinks=False):
                return {"state": "skipped", "message": self.env._("Not a regular file.")}
            status = entry.stat(follow_symlinks=False)
        except OSError as error:
            return {"state": "error", "message": error.strerror}
        vals = {"size": status.st_size, "mtime": self._mtime(status.st_mtime)}
        name = entry.name.lower()
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in EXCLUDED_NAMES):
            vals.update(state="excluded", message=self.env._("Excluded by its name."))
        return vals

    @staticmethod
    def _mtime(timestamp):
        try:
            return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
        except (OSError, OverflowError, ValueError):
            return False

    # ---- Reading in --------------------------------------------------------------------

    def _read_in(self, source):
        """Make the folder or document of this line, or say why not; one line, one savepoint.

        The result is written with the document, so both are committed together.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                if self.kind == "folder":
                    vals = self._read_in_folder()
                else:
                    vals = self._read_in_file(source)
        except (OSError, UserError, ValueError, psycopg2.Error) as error:
            message = (
                error.args[0] if isinstance(error, UserError) else getattr(error, "strerror", None)
            )
            self.write({"state": "error", "message": message or str(error)})
        else:
            self.write(vals)

    def _parent_folder(self):
        """The folder of the filemanager for the folder this line lies in."""
        folder = self.parent_id.folder_id
        if not folder:
            raise UserError(self.env._("The folder above could not be read in."))
        return folder

    def _read_in_folder(self):
        Folder = self.env["int.filemanager.folder"].sudo().with_context(tracking_disable=True)
        parent = self._parent_folder()
        name = self.env["int.filemanager.document"]._clean_name(self.name)
        taken = {
            folder.name.lower(): folder
            for folder in Folder.search_fetch([("parent_id", "=", parent.id)], ["name"])
        }
        existing = taken.get(name.lower())
        if existing and not self.search_count(
            [("import_id", "=", self.import_id.id), ("folder_id", "=", existing.id)]
        ):
            # A folder of this name is there, and no other folder of this order took it.
            return {"state": "done", "folder_id": existing.id, "message": self.env._("Folder used.")}
        constraint = Folder._name_per_parent.full_name(Folder)
        for number in range(1, NAME_TRIES + 1):
            candidate = name if number == 1 else f"{name} ({number})"
            if candidate.lower() in taken:
                continue
            try:
                with self.env.cr.savepoint():
                    folder = Folder.create(
                        {
                            "name": candidate,
                            "parent_id": parent.id,
                            "company_id": self.import_id.company_id.id,
                        }
                    )
            except IntegrityError as error:
                if error.diag.constraint_name != constraint:
                    raise
                taken[candidate.lower()] = None
            else:
                message = False if candidate == name else self.env._("Renamed, the name was taken.")
                return {"state": "done", "folder_id": folder.id, "message": message}
        raise UserError(self.env._("No free name for the folder %(name)s.", name=name))

    def _read_in_file(self, source):
        Document = (
            self.env["int.filemanager.document"].sudo().with_context(tracking_disable=True)
        )
        parent = self._parent_folder()
        origin = posixpath.join(source.relative, self.path)
        known = Document.with_context(active_test=False).search_fetch(
            [("origin_path", "=", origin)], ["name"], limit=1
        )
        if known:
            return {
                "state": "skipped",
                "document_id": known.id,
                "message": self.env._("Read in before."),
            }
        path = safe_join(source.root, origin)
        if not path or os.path.islink(path):
            raise UserError(self.env._("The file is a link or not below the root folder."))
        real = os.path.realpath(path)
        if not real.startswith(source.root + os.sep):
            raise UserError(self.env._("The file is not below the root folder."))
        for _attempt in range(STABLE_TRIES):
            before = os.stat(real)
            with open(real, "rb") as stream:
                document = Document._create_from_stream(
                    stream, self.name, parent, origin_path=origin
                )
            after = os.stat(real)
            if (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and (
                document.size == after.st_size
            ):
                return {
                    "state": "done",
                    "document_id": document.id,
                    "size": document.size,
                    "message": False if document.name == self.name else self.env._("Renamed."),
                }
            # Changed while it was copied: the copy is wrong, try again.
            document.sudo().unlink()
        raise UserError(self.env._("The file keeps changing while it is copied."))
