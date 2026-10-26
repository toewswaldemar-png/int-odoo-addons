import collections

from psycopg2 import IntegrityError

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, ConcurrencyError, UserError
from odoo.tools import SQL
from odoo.tools.sql import escape_psql

from ..tools.clash import CLASH_NAMES_SHOWN
from ..tools.zip_stream import export_name, export_names, folder_entry
from .int_filemanager_named import NAME_MAX_LENGTH

# The context key that makes the name of a folder its path ("Club / 2026 / Invoices"), as the core
# does for ``product.category`` and ``hr.department``: on unless the context says ``False``. The
# search panel of the core asks for the plain name; the chatter keeps it too (see ``write``).
PATH_KEY = "hierarchical_naming"
# The context key of the cascades (archive, restore, company down a tree): what they write below the
# folder the user acted on was checked at that folder. Only a superuser is believed: the context is
# sent by the client, and a key in it must not take a check away from a user.
CASCADE_KEY = "int_filemanager_cascade"
# The separator of the path, and what stands for the folders above that the user may not read.
PATH_SEPARATOR = " / "
PATH_HIDDEN = "…"
# The route that sends the ZIP of a folder (the id follows).
FOLDER_ZIP_PATH = "/int_filemanager/folder_zip/"
# The most paths of one call of ``action_make_paths`` (the browser sends its folders in packages),
# and how many folders one path may have.
MAKE_PATHS_MAX = 500
PATH_DEPTH_MAX = 50


class IntFilemanagerFolder(models.Model):
    """A folder: an ordinary record with a parent.

    Who sees a folder (and its documents) is decided by record rules: a folder is open to all
    filemanager users, or only to the users and groups listed on it (the creator of a top
    folder is listed). Followers (``mail.thread``) only get its notices; whoever may invite
    people to a folder is the administrator, who edits the lists.
    A subfolder takes over what its parent says, unless it says otherwise itself.
    Filemanager administrators see everything.
    """

    _name = "int.filemanager.folder"
    _description = "Filemanager folder"
    _inherit = ["mail.thread", "int.filemanager.named"]
    _parent_store = True
    # The full path, like ``product.category`` and ``stock.location``: a folder stands right below
    # its parent in every list and every picker (by ``name`` alone "Root / Hallo" would come before
    # "Root").
    _order = "complete_name, id"

    name = fields.Char(tracking=True)
    # Only there to sort: it names every folder above, also the ones the user may not read. So only
    # the administrators read, search or group by it; ordering by it is open to all
    # (``_order_field_to_sql``), as it gives no name away. The path that is shown is ``display_name``.
    complete_name = fields.Char(
        compute="_compute_complete_name",
        recursive=True,
        store=True,
        groups="int_filemanager.int_filemanager_group_admin",
    )
    parent_id = fields.Many2one(
        "int.filemanager.folder", index=True, ondelete="restrict", tracking=True
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("int.filemanager.folder", "parent_id")
    document_ids = fields.One2many("int.filemanager.document", "folder_id")
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    access_mode = fields.Selection(
        [
            ("inherit", "Like the parent folder"),
            ("restricted", "Only the users and groups allowed"),
            ("open", "All filemanager users"),
        ],
        required=True,
        default="inherit",
        tracking=True,
        groups="int_filemanager.int_filemanager_group_admin",
        help="Who sees this folder and its documents. A top folder that is not open to all is "
        "seen by the users and groups listed on it (and by the administrators).",
    )
    access_user_ids = fields.Many2many(
        "res.users",
        "int_filemanager_folder_access_user_rel",
        "folder_id",
        "user_id",
        string="Allowed users",
        tracking=True,
        groups="int_filemanager.int_filemanager_group_admin",
    )
    access_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_folder_access_group_rel",
        "folder_id",
        "group_id",
        string="Allowed groups",
        tracking=True,
        groups="int_filemanager.int_filemanager_group_admin",
    )
    # The folder whose ``access_mode`` and lists decide for this one: itself, or the
    # nearest parent that does not say "like the parent". The record rules look at it.
    access_folder_id = fields.Many2one(
        "int.filemanager.folder",
        compute="_compute_access_folder_id",
        store=True,
        recursive=True,
        index=True,
    )

    # Names are unique per folder regardless of case, like on Windows. COALESCE: otherwise two top
    # folders (parent_id IS NULL) would never collide, and NULLS NOT DISTINCT needs PostgreSQL 15,
    # where Odoo 19 runs on 13 (``MIN_PG_VERSION``).
    _name_per_parent = models.UniqueIndex(
        '(COALESCE(parent_id, 0), lower(name COLLATE "und-x-icu")) WHERE active',
        "A folder with this name already exists here.",
    )

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for folder in self:
            if folder.parent_id:
                folder.complete_name = f"{folder.parent_id.complete_name}{PATH_SEPARATOR}{folder.name}"
            else:
                folder.complete_name = folder.name

    @api.depends("access_mode", "parent_id.access_folder_id")
    def _compute_access_folder_id(self):
        for folder in self:
            inherits = folder.access_mode == "inherit" and folder.parent_id
            folder.access_folder_id = folder.parent_id.access_folder_id if inherits else folder

    @api.model
    def _create_numbered(self, name, parent, **values):
        """Create the folder under ``name`` below ``parent``, or under the first free ``name (2)``.

        No message in the chatter for it, like the folders of ``action_make_paths``: an import
        makes a lot of them.
        """
        folders = self.with_context(mail_create_nolog=True)
        return self._create_numbered_name(
            name,
            [("parent_id", "=", parent.id)],
            self._name_per_parent,
            lambda candidate: folders.create({**values, "name": candidate, "parent_id": parent.id}),
        )

    @api.model
    def _path_names(self, path):
        """The names of the folders of a path of the browser, cleaned; refuses a path that is none.

        A path leads down from a folder: no slash at the start, no ``.`` or ``..``, no empty part.
        The names are cleaned like every name (``_normalize_name``).
        """
        names = []
        if isinstance(path, str) and path and "\\" not in path and not path.startswith("/"):
            names = [self._normalize_name(part) for part in path.split("/")]
        if (
            not names
            or len(names) > PATH_DEPTH_MAX
            or any(name in ("", ".", "..") or len(name) > NAME_MAX_LENGTH for name in names)
        ):
            raise UserError(self.env._("This is not a valid folder path: %(path)s", path=str(path)[:100]))
        return names

    def _find_or_make(self, parent, name):
        """The folder ``name`` of ``parent`` that the user sees, made if there is none.

        Two uploads that make the same folder at once: the second one runs into the unique index
        when the first has committed. Odoo's transactions see the data as of their start, so a
        new search here would not find the folder. ``ConcurrencyError`` makes Odoo roll back, take
        a new view of the data and call ``action_make_paths`` again (``service.model.retrying``).
        """
        domain = [("parent_id", "=", parent.id), ("name", "=ilike", escape_psql(name))]
        found = self.search(domain, limit=1)
        if found:
            return found
        try:
            with self.env.cr.savepoint():
                return self.create({"name": name, "parent_id": parent.id})
        except IntegrityError as error:
            if error.diag.constraint_name != self._name_per_parent.full_name(self):
                raise
        if self.sudo().search_count(domain):
            # A folder of that name is there that the user does not see: no word of what it is.
            raise UserError(self.env._("The name %(name)s is not available here.", name=name))
        raise ConcurrencyError(f"The folder {name} was made by another transaction")

    @api.model
    def _order_field_to_sql(self, alias, field_name, direction, nulls, query):
        """Order by the path without asking for the right to read it (see ``complete_name``)."""
        if field_name == "complete_name":
            sql_field = self._fields[field_name].to_sql(self, alias)
            query._order_groupby.append(sql_field)
            return SQL("%s %s %s", sql_field, direction, nulls)
        return super()._order_field_to_sql(alias, field_name, direction, nulls, query)

    @api.depends("name", "parent_path")
    @api.depends_context(PATH_KEY, "uid", "allowed_company_ids")
    def _compute_display_name(self):
        """The path, or with ``hierarchical_naming`` off the name, as far as the user may read it.

        Which folders above are named is the user's to see (the record rules): the path stops at
        the first one the user may not read and starts with "…", so a name is never given away.
        A folder can be seen though its parent is not (the rules look at ``access_folder_id``).
        The core reads the name of a Many2one as superuser, so the rules are asked as the user and
        not as the environment of the call. (The name of the direct parent that a visible folder
        points to is shown with that Many2one, as the core does for every record.)
        """
        if not self.env.context.get(PATH_KEY, True):
            return super()._compute_display_name()
        chains = {
            folder: [int(folder_id) for folder_id in (folder.parent_path or "").split("/") if folder_id]
            for folder in self
        }
        above = {folder_id for chain in chains.values() for folder_id in chain[:-1]}
        viewer = self.with_user(self.env.uid).with_context(active_test=False)
        try:
            readable = {
                folder.id: folder.name for folder in viewer.search_fetch([("id", "in", list(above))], ["name"])
            }
        except AccessError:
            # No right to folders at all (a document that is seen through a record): none above is named.
            readable = {}
        for folder, chain in chains.items():
            parts = [folder.name]
            for folder_id in reversed(chain[:-1]):
                if folder_id not in readable:
                    parts.append(PATH_HIDDEN)
                    break
                parts.append(readable[folder_id])
            folder.display_name = PATH_SEPARATOR.join(reversed(parts))

    @api.model_create_multi
    def create(self, vals_list):
        """A subfolder has the company of its parent, and the parent has to be in use.

        A folder that decides for itself (a top folder) lists whoever made it: the lists are the
        administrators' to edit, so without this the creator would not see the folder again. A
        subfolder is seen as its parent is.
        """
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            # The default of the parent (the list puts the folder of its panel there) counts too.
            parent_id = vals.get("parent_id") if "parent_id" in vals else self.env.context.get("default_parent_id")
            if parent_id:
                parent = self.browse(parent_id).sudo()
                parent._check_active_target()
                vals["company_id"] = parent.company_id.id
        folders = super().create(vals_list)
        folders._list_current_user()
        return folders

    def _list_current_user(self):
        """List the user on the folders that decide for themselves and are not open to all.

        As superuser: the user may not read the folder yet (it was just made, or put at the top),
        and that is what is being fixed. Not done for the superuser, who sees everything.
        """
        if self.env.su:
            return
        own = self.sudo().filtered(
            lambda folder: folder.access_folder_id == folder and folder.access_mode != "open"
        )
        own.with_context(tracking_disable=True).write({"access_user_ids": [Command.link(self.env.uid)]})

    def write(self, vals):
        # Archiving or restoring a folder does it on everything below, like a project does it on
        # its tasks (project.project.write). The core's docstring of action_archive says to
        # override write for that.
        in_cascade = self.env.su and self.env.context.get(CASCADE_KEY)
        cascade = "active" in vals and not in_cascade
        if cascade and vals["active"]:
            self._check_restorable()
        moving = not in_cascade and ("parent_id" in vals or "company_id" in vals)
        if moving:
            vals = self._check_move(vals)
        # A subfolder put at the top no longer takes over its parent: it decides for itself, and
        # the lists are the administrators' to edit, so the one who moved it would not see it again.
        lifted = self.browse()
        if moving and "parent_id" in vals and not vals["parent_id"]:
            # sudo: ``access_mode`` is the administrators' to read; the records keep the user's env
            lifted = self.browse(
                self.sudo().filtered(lambda folder: folder.parent_id and folder.access_mode == "inherit").ids
            )
        # The name that the tracking keeps of a folder is the plain one, whatever the context.
        plain = self.with_context(**{PATH_KEY: False})
        result = super(IntFilemanagerFolder, plain).write(vals)
        lifted._list_current_user()
        if cascade:
            self._cascade_active(vals["active"])
        if moving and "company_id" in vals:
            self._cascade_company()
        return result

    def _check_active_target(self):
        """Refuse a folder that is archived as the place for something."""
        for folder in self:
            if not folder.active:
                raise UserError(
                    self.env._(
                        "The folder %(name)s is archived. Restore it first.", name=folder.name
                    )
                )

    def _check_move(self, vals):
        """Check where the folders go, and give back the values with the company of the target.

        Two layers. The rights of the user (not asked of the superuser, whose acts the storage
        and the cascades are): the target has to be one the user may write into, as for an
        upload. The rules of the tree, which hold for the superuser too: the target is in use,
        no name is taken twice, and a subfolder has the company of its parent. Where the folders
        are put below a parent, the company of the whole tree below comes along
        (``_cascade_company``); a subfolder cannot have another company on its own.
        """
        if "parent_id" in vals:
            moved = self.filtered(lambda folder: folder.parent_id.id != (vals["parent_id"] or False))
            target = self.browse(vals["parent_id"]).exists()
            if moved and target:
                if not self.env.su:
                    target.check_access("write")
                target.sudo()._check_active_target()
                vals = {**vals, "company_id": target.sudo().company_id.id}
            taken = moved._names_taken("parent_id", target)
            if taken:
                raise UserError(self.env._("These names are taken here: %(names)s", names=taken))
        elif "company_id" in vals and self.filtered(
            lambda folder: folder.parent_id and folder.company_id.id != (vals["company_id"] or False)
        ):
            raise UserError(
                self.env._("The company of a subfolder is the one of its parent. Change the top folder.")
            )
        return vals

    def _cascade_company(self):
        """Give what lies below these folders their company (the documents follow their folder)."""
        folders = self.sudo().with_context(active_test=False)
        for folder in folders:
            tree = folders.search([("id", "child_of", folder.id)]) - folder
            tree = tree.filtered(lambda child: child.company_id != folder.company_id)
            # mail_notrack: the change is logged once, on the folder the user moved.
            tree.with_context(**{CASCADE_KEY: True}, mail_notrack=True).write(
                {"company_id": folder.company_id.id}
            )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_not_empty(self):
        # active_test=False: an archived folder or document still keeps its place.
        Document = self.env["int.filemanager.document"].with_context(active_test=False)
        with_documents = {
            folder.id for [folder] in Document._read_group([("folder_id", "in", self.ids)], ["folder_id"])
        }
        for folder in self.with_context(active_test=False):
            if folder.child_ids or folder.id in with_documents:
                raise UserError(
                    self.env._(
                        "The folder %(name)s is not empty. Move or delete what is in it first.",
                        name=folder.name,
                    )
                )

    def action_make_paths(self, paths):
        """Make the folders of these paths below this folder, as far as they are not there.

        What the browser does before it uploads a folder of the disk: the folders come first, in
        a package, and the files follow one by one to the folder that each path gives. A folder
        that is there (the case of the name aside, as the unique index sees it) is used, so the
        folders of an upload grow into the ones that exist. Everything runs as the user: the
        folders are made by ``create`` under the rules for a new folder, and a folder is found
        only if the user sees it.

        :param paths: ``["Photos/2025/June", "Photos/empty"]``, relative to this folder
        :return: ``{path: id of its last folder}``
        """
        self.ensure_one()
        self.check_access("write")
        self._check_active_target()
        if len(paths) > MAKE_PATHS_MAX:
            raise UserError(self.env._("Too many folders at once."))
        # Nobody needs a message in the chatter for each of the folders of an upload.
        folders = self.with_context(mail_create_nolog=True)
        made = {(): folders}
        result = {}
        for path in paths:
            names = self._path_names(path)
            for depth in range(1, len(names) + 1):
                key = tuple(name.lower() for name in names[:depth])
                if key not in made:
                    made[key] = folders._find_or_make(made[key[:-1]], names[depth - 1])
            result[path] = made[tuple(name.lower() for name in names)].id
        return result

    def action_download(self):
        """Let the browser download the folder, with what is below it, as one ZIP.

        The route makes the list again when the browser asks. Here the user is told at once what
        cannot work, instead of getting an error page in a new tab: a folder that is archived,
        or more bytes than one ZIP may hold. The list of the files is not made here, the size
        is added up by the database.
        """
        self.ensure_one()
        self._check_active_target()
        Document = self.env["int.filemanager.document"]
        [[total]] = Document._read_group([("folder_id", "in", list(self._zip_tree()))], [], ["size:sum"])
        Document._check_zip_size(total or 0)
        return {"type": "ir.actions.act_url", "url": f"{FOLDER_ZIP_PATH}{self.id}", "target": "download"}

    def _zip_tree(self):
        """The folders of the ZIP of this folder: ``{id: [subfolders]}``, this one and what lies below.

        A subfolder is in it if the user sees it and every folder between it and this one: the
        chain is walked from here downwards, so a hidden folder takes everything below it with
        it, whatever the rules say of that. (``child_of`` would not do: it ignores the rules of
        the folders.) A folder that is archived is not in it.
        """
        self.ensure_one()
        below = self.search_fetch(
            [("parent_path", "=like", f"{self.parent_path}%"), ("id", "!=", self.id)],
            ["name", "parent_id", "write_date"],
        )
        children = collections.defaultdict(list)
        for folder in below:
            children[folder.parent_id.id].append(folder)
        tree, stack = {}, [self]
        while stack:
            folder = stack.pop()
            tree[folder.id] = sorted(children[folder.id], key=lambda child: child.id)
            stack.extend(tree[folder.id])
        return tree

    def _zip_entries(self):
        """The entries of the ZIP of this folder, with its structure.

        The files of the documents that the user reads in the folders of ``_zip_tree``, each
        in its folder; a folder with nothing in it is an entry of its own. The folder itself is
        the top of the archive. Folders keep their names, a file that has the name of a folder
        or of another file is numbered (``_zip_files`` refuses a file that is gone, and
        ``_check_zip_size`` too many bytes).
        """
        self.ensure_one()
        self._check_active_target()
        tree = self._zip_tree()
        documents = self.env["int.filemanager.document"].search_fetch(
            [("folder_id", "in", list(tree))], ["name", "checksum", "size", "write_date", "folder_id"]
        )
        files = collections.defaultdict(list)
        for document in documents:
            files[document.folder_id.id].append(document)
        names, empty = {}, []
        stack = [(self, export_name(self.name))]
        while stack:
            folder, path = stack.pop()
            subfolders = tree[folder.id]
            folder_names = export_names(((child.id, child.name) for child in subfolders), folders=True)
            file_names = export_names(
                ((document.id, document.name) for document in files[folder.id]),
                taken={name.lower() for name in folder_names.values()},
            )
            names.update({document.id: f"{path}/{file_names[document.id]}" for document in files[folder.id]})
            if not subfolders and not files[folder.id]:
                empty.append(folder_entry(path, folder.write_date))
            stack.extend((child, f"{path}/{folder_names[child.id]}") for child in subfolders)
        entries = documents._zip_files(names)
        self.env["int.filemanager.document"]._check_zip_size(sum(entry.size for entry in entries))
        return sorted(entries + empty, key=lambda entry: entry.name.lower())

    def _below(self, active):
        """The folders and documents below these folders (they included) that are not yet ``active``.

        Superuser: archiving is one act for the whole tree, also for what the user does not see.
        """
        folders = self.sudo().with_context(active_test=False)
        below = folders.search([("id", "child_of", self.ids), ("active", "!=", active)])
        documents = (
            self.env["int.filemanager.document"]
            .sudo()
            .with_context(active_test=False)
            .search([("folder_id", "child_of", self.ids), ("active", "!=", active)])
        )
        return below, documents

    def _cascade_active(self, active):
        # mail_notrack: the change is logged once, on the folder the user archived or restored;
        # not once more for each folder and document below it.
        below, documents = self._below(active)
        below.with_context(**{CASCADE_KEY: True}, mail_notrack=True).write(
            {"active": active}
        )
        documents.with_context(**{CASCADE_KEY: True}, mail_notrack=True).write(
            {"active": active}
        )

    def _check_restorable(self):
        """Refuse to restore what cannot come back: below an archived folder, or with a name
        that is taken (the names are unique among the active ones, case aside)."""
        for folder in self:
            if folder.parent_id and not folder.parent_id.active:
                raise UserError(
                    self.env._(
                        "Restore the folder %(parent)s first, it contains %(name)s.",
                        parent=folder.parent_id.display_name,
                        name=folder.name,
                    )
                )
        below, _documents = self._below(True)
        folders = below | self
        taken = self.env.execute_query(
            SQL(
                """
                SELECT min(name) FROM int_filemanager_folder
                WHERE (active OR id IN %(folders)s)
                  AND (coalesce(parent_id, 0) IN (
                        SELECT coalesce(parent_id, 0) FROM int_filemanager_folder
                        WHERE id IN %(roots)s)
                       OR parent_id IN %(folders)s)
                GROUP BY parent_id, lower(name COLLATE "und-x-icu")
                HAVING count(*) > 1
                UNION ALL
                SELECT min(name) FROM int_filemanager_document
                WHERE folder_id IN %(folders)s
                GROUP BY folder_id, lower(name COLLATE "und-x-icu")
                HAVING count(*) > 1
                """,
                folders=tuple(folders.ids) or (0,),
                roots=tuple(self.ids),
            )
        )
        if taken:
            names = ", ".join(sorted({name for [name] in taken})[:CLASH_NAMES_SHOWN])
            raise UserError(
                self.env._("Restoring is not possible, these names are taken: %(names)s", names=names)
            )
