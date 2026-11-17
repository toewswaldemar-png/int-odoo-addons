import base64
import binascii

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import project_check as check

FROM_CONTENT = ("checksum", "size", "expected_document", "expected_names", "config_numbers", "file_ids")


class IntWorkbenchProjectVersion(models.Model):
    _name = "int.workbench.project.version"
    _description = "Version of a project"
    _inherit = ["mail.thread"]
    _order = "project, create_date desc, id desc"

    project = fields.Char(
        string="Project",
        required=True,
        index=True,
        tracking=True,
        help="What the versions of one project have in common, for example TRAXX3002/Pro_1. The versions of the same name are shown together.",
    )
    checksum = fields.Char(required=True, readonly=True, index=True, copy=False, help="The name of the version: the checksum of its files (the rule of the project library of the service).")
    short_id = fields.Char(string="Id", compute="_compute_short_id")
    active = fields.Boolean(default=True, help="An archived version is not offered any more; a controller that has it keeps it.")
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
    device_ids = fields.One2many("int.workbench.device", "project_version_id", string="Devices", readonly=True)
    origins = fields.Text(readonly=True, help="Where the version was brought in from, one in each line.")
    note = fields.Text()

    _checksum_unique = models.Constraint("UNIQUE (checksum)", "A version exists once.")

    def _service_description(self):
        """What the service needs to fetch the version: the checksum, where it belongs and its files with their checksums."""
        self.ensure_one()
        return {
            "checksum": self.checksum,
            "vehicle": "",  # the service still knows the field; the name of the project holds what it said
            "project": self.project or "",
            "files": [{"name": file.name, "sha256": file.sha256, "size": file.size} for file in self.file_ids],
        }

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

    @api.depends("project")
    def _compute_display_name(self):
        for version in self:
            version.display_name = version.project or ""

    # === FROM FILES === #

    @api.model
    def _from_files(self, project, files, origin=""):
        """Make the version that the files of a project folder are and return ``(record, created)``.

        ``project`` is the name of the project the version belongs to. ``files`` is ``[(name, bytes)]``. A version that is already there (same files, wherever they came from) is not made again: the origin
        is added to it. The programs among the files (images, program texts) also become records of the software.
        """
        # whoever may not bring files in must not add to what is there either (the lookups below are sudo, for the whole stock)
        self.check_access("create")
        project = (project or "").strip().strip("/")
        if not project:
            raise UserError(self.env._("A project needs a name."))
        try:
            info = check.build(files)
        except check.VersionError as error:
            raise UserError(self._error_text(error)) from error
        # sudo: int.workbench.project.version: the lookup is for the whole stock, whoever may bring files in
        existing = self.sudo().with_context(active_test=False).search([("checksum", "=", info.checksum)], limit=1)
        if existing:
            existing._add_origin(origin or project)
            if not existing.active:  # the same files again: the old version is wanted again
                existing.active = True
            return existing, False
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
                "project": project,
                "checksum": info.checksum,
                "size": info.size,
                "expected_document": info.expected_document,
                "expected_names": info.expected_names,
                "config_numbers": info.config_numbers,
                "origins": origin or project,
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
                version.sudo().message_post(body=self.env._("Also imported from: %s", origin), message_type="notification")

    @api.model
    def import_version(self, project, files, origin="", vehicle=""):
        """Bring the files of a project folder in (for the tool that takes over the stock of the original).

        ``vehicle`` is only taken for the callers that still give it: it goes in front of the name (``vehicle/project``). ``files`` is a list of ``{"name", "data"}`` with the content as base64. Returns ``{"id", "checksum", "created"}``.
        """
        decoded = []
        for item in files or []:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not isinstance(item.get("data"), str):
                raise UserError(self.env._("Each file needs a name and its content as base64."))
            try:
                decoded.append((item["name"], base64.b64decode(item["data"], validate=True)))
            except (binascii.Error, ValueError):
                raise UserError(self.env._("The content of %s is not base64.", item["name"])) from None
        vehicle = vehicle.strip().strip("/") if isinstance(vehicle, str) else ""
        name = f"{vehicle}/{project}" if vehicle and isinstance(project, str) and project else project
        version, created = self._from_files(name, decoded, origin if isinstance(origin, str) else "")
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

    # === ORM === #

    def write(self, vals):
        if any(name in vals for name in FROM_CONTENT) and not self.env.context.get("version_internal"):
            raise UserError(self.env._("What a version consists of cannot be changed. Bring the changed files in as a new version."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_unassigned(self):
        if any(version.device_ids for version in self):
            raise UserError(self.env._("A controller has this version. Archive it instead."))
