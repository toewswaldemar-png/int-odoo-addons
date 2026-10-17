from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

# Names shown when a restore is refused because they are taken.
CLASH_NAMES_SHOWN = 5
# Names tried for one new folder ("a", "a (2)", ...) before giving up.
NAME_TRIES = 1000
# The context key that the reading for the guests of a share sets (never the browser): the id of
# the folder that the share gives. Its parent is not shown, see ``_read_format``.
SHARE_ROOT_KEY = "int_filemanager_share_root"


class IntFilemanagerFolder(models.Model):
    """A folder: an ordinary record with a parent.

    Who sees a folder (and its documents) is decided by record rules: a folder is open to all
    filemanager users, or only to the users and groups listed on it. Followers
    (``mail.thread``, the creator is one) see it too, the pattern of ``project.project``.
    A subfolder takes over what its parent says, unless it says otherwise itself.
    Filemanager administrators see everything.
    """

    _name = "int.filemanager.folder"
    _description = "Filemanager folder"
    _inherit = ["mail.thread"]
    _parent_store = True
    _order = "name"

    name = fields.Char(required=True, tracking=True)
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
        help="Who sees this folder and its documents. A top folder that is not open to all is "
        "seen by the users and groups listed on it and by its followers (and by the "
        "administrators).",
    )
    access_user_ids = fields.Many2many(
        "res.users",
        "int_filemanager_folder_access_user_rel",
        "folder_id",
        "user_id",
        string="Allowed users",
        tracking=True,
    )
    access_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_folder_access_group_rel",
        "folder_id",
        "group_id",
        string="Allowed groups",
        tracking=True,
    )
    # The folder whose ``access_mode`` and followers decide for this one: itself, or the
    # nearest parent that does not say "like the parent". The record rules look at it.
    access_folder_id = fields.Many2one(
        "int.filemanager.folder",
        compute="_compute_access_folder_id",
        store=True,
        recursive=True,
        index=True,
    )

    ocr_images = fields.Selection(
        [
            ("inherit", "Like the parent folder"),
            ("on", "On"),
            ("off", "Off"),
        ],
        string="Text recognition in images",
        # The administrators only: a field that is only left out of the view could be written
        # through RPC by every user of the filemanager, and would start the recognition of images.
        groups="int_filemanager.int_filemanager_group_admin",
        required=True,
        default="inherit",
        help="Whether the text in the images of this folder (JPEG, PNG, TIFF ...) is recognized, "
        "so that the search finds it. A top folder that says 'like the parent folder' is off. "
        "Nothing is recognized unless the text recognition is switched on in the settings.",
    )
    model_folder_ids = fields.One2many(
        "int.filemanager.model.folder",
        "folder_id",
        string="Upload folder for",
        # The administrators only, like the settings themselves: they are the ones who have a
        # right on the model, and a field that is only left out of the view could be written
        # through RPC by every user of the filemanager.
        groups="int_filemanager.int_filemanager_group_admin",
        help="The kinds of record whose uploaded files go to this folder, for example "
        "contacts. Whoever may change such a record can upload files there, without access to "
        "the folder.",
    )
    # What ``ocr_images`` comes to for this folder after the parent is looked at.
    ocr_images_active = fields.Boolean(
        string="Images are recognized here",
        compute="_compute_ocr_images_active", store=True, recursive=True
    )

    # Names are unique per folder regardless of case, like on Windows. NULLS NOT
    # DISTINCT: otherwise two top folders (parent_id IS NULL) would never collide.
    _name_per_parent = models.UniqueIndex(
        '(parent_id, lower(name COLLATE "und-x-icu")) NULLS NOT DISTINCT WHERE active',
        "A folder with this name already exists here.",
    )

    @api.depends("access_mode", "parent_id.access_folder_id")
    def _compute_access_folder_id(self):
        for folder in self:
            inherits = folder.access_mode == "inherit" and folder.parent_id
            folder.access_folder_id = folder.parent_id.access_folder_id if inherits else folder

    @api.depends("ocr_images", "parent_id.ocr_images_active")
    def _compute_ocr_images_active(self):
        for folder in self:
            if folder.ocr_images == "inherit":
                # A top folder has no parent to ask: off.
                folder.ocr_images_active = folder.parent_id.ocr_images_active
            else:
                folder.ocr_images_active = folder.ocr_images == "on"

    @api.model
    def _create_numbered(self, name, parent, **values):
        """Create the folder under ``name`` below ``parent``, or under the first free ``name (2)``.

        Two active folders of a parent cannot share a name (case aside). The names that are taken
        are looked up in one go; one that slips through (another case, a parallel request) is
        caught by the unique index of the database. Odoo does not retry on that error.
        """

        def numbered(number):
            return name if number == 1 else f"{name} ({number})"

        taken = {
            folder.name.lower()
            for folder in self.search_fetch(
                [
                    ("parent_id", "=", parent.id),
                    ("name", "in", [numbered(number) for number in range(1, 101)]),
                ],
                ["name"],
            )
        }
        constraint = self._name_per_parent.full_name(self)
        for number in range(1, NAME_TRIES + 1):
            candidate = numbered(number)
            if candidate.lower() in taken:
                continue
            try:
                with self.env.cr.savepoint():
                    return self.create({**values, "name": candidate, "parent_id": parent.id})
            except IntegrityError as error:
                if error.diag.constraint_name != constraint:
                    raise
                taken.add(candidate.lower())
        raise UserError(self.env._("No free name for %(name)s in this folder.", name=name))

    def _read_format(self, fnames, load="_classic_read"):
        """The shared folder has no parent for the guests of its share.

        Its parent lies outside what they may reach, and its name must not be given away. The
        search panel of the guests needs it as well: it keeps a folder only if the chain of its
        parents lies in the result completely (``_search_panel_sanitized_parent_hierarchy``),
        so a root with a parent outside would leave the panel empty. Here, where every reading
        passes (``read``, ``search_read``, ``web_read``), the root has none.
        """
        result = super()._read_format(fnames, load)
        root_id = self.env.context.get(SHARE_ROOT_KEY)
        if root_id:
            for values in result:
                if values["id"] == root_id and "parent_id" in values:
                    values["parent_id"] = False
        return result

    def write(self, vals):
        # Archiving or restoring a folder does it on everything below, like a project does it on
        # its tasks (project.project.write). The core's docstring of action_archive says to
        # override write for that.
        cascade = "active" in vals and not self.env.context.get("int_filemanager_cascade")
        if cascade and vals["active"]:
            self._check_restorable()
        result = super().write(vals)
        if cascade:
            self._cascade_active(vals["active"])
        return result

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
        below.with_context(int_filemanager_cascade=True, mail_notrack=True).write(
            {"active": active}
        )
        documents.with_context(int_filemanager_cascade=True, mail_notrack=True).write(
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

    @api.ondelete(at_uninstall=False)
    def _unlink_except_not_empty(self):
        # active_test=False: an archived folder or document still keeps its place.
        Document = self.env["int.filemanager.document"].with_context(active_test=False)
        for folder in self.with_context(active_test=False):
            if folder.child_ids or Document.search_count([("folder_id", "=", folder.id)]):
                raise UserError(
                    self.env._(
                        "The folder %(name)s is not empty. Move or delete what is in it first.",
                        name=folder.name,
                    )
                )
