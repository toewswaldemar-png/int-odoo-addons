import base64
import binascii

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from . import project_check as check

FROM_CONTENT = ("folder_id", "checksum", "size", "expected_document", "expected_names", "config_numbers", "file_ids")
MANAGER_GROUP = "int_workbench.int_workbench_group_manager"


class IntWorkbenchProjectVersion(models.Model):
    _name = "int.workbench.project.version"
    _description = "Version of a project"
    _inherit = ["mail.thread"]
    _order = "folder_id, create_date desc, id desc"

    folder_id = fields.Many2one("int.workbench.project.folder", string="Project", required=True, index=True, ondelete="restrict", readonly=True)
    vehicle = fields.Char(related="folder_id.vehicle", store=True, index=True)
    project = fields.Char(related="folder_id.name", store=True, index=True)
    checksum = fields.Char(required=True, readonly=True, index=True, copy=False, help="The name of the version: the checksum of its files (the rule of the project library of the service).")
    short_id = fields.Char(string="Id", compute="_compute_short_id")
    state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved"), ("retired", "Retired")],
        default="draft",
        required=True,
        index=True,
        tracking=True,
        copy=False,
        help="Only an approved version can be assigned to a controller. A manager approves it; a retired version stays and can be approved again.",
    )
    file_ids = fields.One2many("int.workbench.project.file", "version_id", string="Files", readonly=True)
    file_count = fields.Integer(compute="_compute_file_count")
    size = fields.Integer(string="Size (bytes)", readonly=True)
    expected_document = fields.Char(
        string="Application (document number)",
        readonly=True,
        index=True,
        help="The six digits of the document number that the tables of the project carry. They are the same in the application the tables are made for.",
    )
    expected_names = fields.Char(string="Names in the tables", readonly=True, help="The names that the version lines of the tables carry.")
    config_numbers = fields.Char(
        string="Document numbers",
        readonly=True,
        help="The numbers of the documents of the project that its version lines carry (letter and four digits): E2 CAN, E3 confpdl, E4 diagnosis, "
        "M2 signal addresses, M3 process values, M4 error table.",
    )
    software_exact_ids = fields.Many2many(
        "int.workbench.software",
        string="Software that fits",
        compute="_compute_software_ids",
        help="The programs of this project whose numbers (E2, E3, E4) are the ones of this version: the program was built with these tables and scripts. "
        "Only what both sides say is compared.",
    )
    software_ids = fields.Many2many("int.workbench.software", string="Matching software", compute="_compute_software_ids", help="The programs whose document number is the one of the tables.")
    device_ids = fields.One2many("int.workbench.device", "project_version_id", string="Controllers", readonly=True)
    origins = fields.Text(readonly=True, help="Where the version was brought in from, one in each line.")
    approved_by_id = fields.Many2one("res.users", string="Approved by", readonly=True, copy=False)
    approved_at = fields.Datetime(string="Approved at", readonly=True, copy=False)
    note = fields.Text()

    _checksum_unique = models.Constraint("UNIQUE (checksum)", "A version exists once.")

    @api.depends("checksum")
    def _compute_short_id(self):
        for version in self:
            version.short_id = (version.checksum or "")[:8]

    @api.depends("file_ids")
    def _compute_file_count(self):
        counts = {
            version.id: count for version, count in self.env["int.workbench.project.file"]._read_group([("version_id", "in", self.ids)], ["version_id"], ["__count"])
        }
        for version in self:
            version.file_count = counts.get(version.id, 0)

    @api.depends("expected_document")
    def _compute_software_ids(self):
        Software = self.env["int.workbench.software"]
        for version in self:
            same = Software.search([("document_number", "=", version.expected_document)]) if version.expected_document else Software
            version.software_ids = same
            version.software_exact_ids = same.filtered(lambda software, version=version: version._software_level(software) == check.MATCH_EXACT)

    def _software_level(self, software):
        """How well a program fits this version: ``exact``, ``other_version``, ``same_project``, ``unrelated`` or ``unknown``."""
        self.ensure_one()
        return check.match_level(self.expected_document, self.config_numbers, software.document_number, (software.document_codes or "").split())

    @api.depends("folder_id", "checksum")
    def _compute_display_name(self):
        for version in self:
            version.display_name = f"{version.folder_id.display_name or ''} {version.short_id or ''}".strip()

    # === FROM FILES === #

    @api.model
    def _from_files(self, vehicle, project, files, origin=""):
        """Make a draft of the version that the files of a project folder are and return ``(record, created)``.

        ``files`` is ``[(name, bytes)]``. A version that is already there (same files, wherever they came from) is not made again: the origin
        is added to it. The programs among the files (images, program texts) also become records of the software.
        """
        # whoever may not bring files in must not add to what is there either (the lookups below are sudo, for the whole stock)
        self.check_access("create")
        vehicle, project = (vehicle or "").strip().strip("/"), (project or "").strip()
        if not vehicle or not project:
            raise UserError(self.env._("A project needs a vehicle and a name."))
        try:
            info = check.build(files)
        except check.VersionError as error:
            raise UserError(self._error_text(error)) from error
        # sudo: int.workbench.project.version: the lookup is for the whole stock, whoever may bring files in
        existing = self.sudo().search([("checksum", "=", info.checksum)], limit=1)
        if existing:
            existing._add_origin(origin or f"{vehicle}/{project}")
            return existing, False
        Folder = self.env["int.workbench.project.folder"]
        # sudo: int.workbench.project.folder: the lookup of the folder for the whole stock
        folder = Folder.sudo().search([("vehicle", "=", vehicle), ("name", "=", project)], limit=1) or Folder.create({"vehicle": vehicle, "name": project})
        Software = self.env["int.workbench.software"]
        lines = []
        for file in info.files:
            software = Software
            kind = file.kind
            if kind == check.KIND_PROGRAM:
                try:
                    software, _created = Software._from_file(file.name, file.content)
                except UserError:
                    kind = check.KIND_OTHER
            lines.append(
                (
                    0,
                    0,
                    {
                        "name": file.name,
                        "kind": kind,
                        "command": file.command,
                        "size": file.size,
                        "sha256": file.sha256,
                        "data": base64.b64encode(file.content),
                        "line_name": file.line_name,
                        "line_version": file.line_version,
                        "line_date": file.line_date,
                        "line_document": file.line_document,
                        "line_number": file.line_letter + file.line_number if file.line_number else "",
                        "line_author": file.line_author,
                        "software_id": software.id or False,
                    },
                )
            )
        version = self.create(
            {
                "folder_id": folder.id,
                "checksum": info.checksum,
                "size": info.size,
                "expected_document": info.expected_document,
                "expected_names": info.expected_names,
                "config_numbers": info.config_numbers,
                "origins": origin or f"{vehicle}/{project}",
                "file_ids": lines,
            }
        )
        return version, True

    def _add_origin(self, origin):
        """Remember another place the same version was brought in from."""
        for version in self:
            places = (version.origins or "").splitlines()
            if origin and origin not in places:
                # sudo: int.workbench.project.version: the places are kept for everybody who brings the same files in again
                version.sudo().origins = "\n".join([*places, origin])

    @api.model
    def import_version(self, vehicle, project, files, origin=""):
        """Bring the files of a project folder in as a draft (for the tool that takes over the stock of the original).

        ``files`` is a list of ``{"name", "data"}`` with the content as base64. Returns ``{"id", "checksum", "created"}``.
        """
        decoded = []
        for item in files or []:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not isinstance(item.get("data"), str):
                raise UserError(self.env._("Each file needs a name and its content as base64."))
            try:
                decoded.append((item["name"], base64.b64decode(item["data"], validate=True)))
            except (binascii.Error, ValueError):
                raise UserError(self.env._("The content of %s is not base64.", item["name"])) from None
        version, created = self._from_files(vehicle, project, decoded, origin if isinstance(origin, str) else "")
        return {"id": version.id, "checksum": version.checksum, "created": created}

    @api.model
    def _error_text(self, error):
        """Why files are no version, in the language of the user (one literal call for each reason, so that they are translated)."""
        values = error.values
        match error.code:
            case "no_files":
                return self.env._("There is no file that belongs to a project.")
            case "no_settings":
                return self.env._("The project has no settings file (DEF.BIN).")
            case "too_big":
                return self.env._("The files are more than %d MB together.", values["megabytes"])
            case "file_too_big":
                return self.env._("%(name)s is larger than %(megabytes)d MB.", name=values["name"], megabytes=values["megabytes"])
            case "name_clash":
                return self.env._("%(first)s and %(second)s differ only in upper and lower case.", first=values["first"], second=values["second"])
            case "bad_name":
                return self.env._("%s is not a name of a file of a project.", values["name"])
            case "bad_archive":
                return self.env._("The file is not a ZIP archive.")
            case "too_many_files":
                return self.env._("The archive has %d files, too many for one project.", values["count"])
        return error.code

    # === STATES === #

    def _check_manager(self):
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(self.env._("Only a manager approves or retires a version."))

    def action_approve(self):
        """Release the version for assignment to controllers (a manager)."""
        self._check_manager()
        for version in self:
            if version.state != "approved":
                version.write({"state": "approved", "approved_by_id": self.env.user.id, "approved_at": fields.Datetime.now()})

    def action_retire(self):
        """Take the version out of use: it can no longer be assigned (a manager). A controller that has it keeps it until another is assigned."""
        self._check_manager()
        self.write({"state": "retired"})

    def action_draft(self):
        """Set a version back to draft (a manager); a version that a controller has cannot go back."""
        self._check_manager()
        for version in self:
            if version.device_ids:
                raise UserError(self.env._("%s is assigned to a controller; assign another version first.", version.display_name))
        self.write({"state": "draft", "approved_by_id": False, "approved_at": False})

    # === ORM === #

    def write(self, vals):
        if any(name in vals for name in FROM_CONTENT) and not self.env.context.get("version_internal"):
            raise UserError(self.env._("What a version consists of cannot be changed. Bring the changed files in as a new version."))
        if {"state", "approved_by_id", "approved_at"} & set(vals) and not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(self.env._("Only a manager approves or retires a version."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_drafts(self):
        if any(version.state != "draft" for version in self):
            raise UserError(self.env._("Only a draft can be deleted. Retire a version that is not used any more."))
