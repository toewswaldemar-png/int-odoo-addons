import base64
import binascii
import re

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import software_check as check

# The fields that the content of the file decides: they never change after the file is read.
FROM_CONTENT = (
    "kind", "hardware", "app_name", "resource", "document", "document_codes", "os_version", "expected_os", "ranges", "size", "data_size", "sha256", "data",
)  # fmt: skip


class IntWorkbenchSoftware(models.Model):
    _name = "int.workbench.software"
    _description = "Program of the controllers"
    _inherit = ["mail.thread"]
    _order = "kind, app_name, os_version desc, id desc"

    name = fields.Char(required=True, tracking=True, help="What the program is called in lists. It comes from the content (the application or the version of the operating system).")
    kind = fields.Selection(
        [
            (check.KIND_OS, "Operating system"),
            (check.KIND_APPLICATION, "Application"),
            (check.KIND_COMBINED, "Operating system and application"),
            (check.KIND_BOOTLOADER, "Bootloader"),
            (check.KIND_PARAMETER, "Parameter block"),
            (check.KIND_TEXT, "Application text"),
            (check.KIND_UNKNOWN, "Unknown"),
        ],
        required=True,
        readonly=True,
        index=True,
        help="Told by where the file writes into the memory of the controller, not by its name or extension. An application text is "
        "sent as lines through the command line instead of as an image through the bootloader.",
    )
    hardware = fields.Selection(
        [(check.HARDWARE_HA3X, "11HA3x"), (check.HARDWARE_FAMILY_B, "Family B"), (check.HARDWARE_UNKNOWN, "Unknown")],
        string="Controller type",
        required=True,
        readonly=True,
        index=True,
        help="The type of controller that the image is made for, told by where it sits in the memory.",
    )
    active = fields.Boolean(default=True, help="An archived program is not offered any more and cannot be loaded.")
    app_name = fields.Char(string="Application", readonly=True, index=True, help="The name in the header of the application.")
    resource = fields.Char(readonly=True, help="The resource of the application (the second name in its header).")
    document = fields.Char(readonly=True, index=True, help="The document number of the application (3EGM, six digits, E, four digits). The tables of a project carry the same six digits.")
    document_codes = fields.Char(
        string="Document numbers",
        readonly=True,
        help="The numbers E2nnn, E3nnn and E4nnn that the image carries: the versions of the configuration documents it belongs to "
        "(E2 the CAN configuration, E3 confpdl, E4 the diagnosis and the error table with the same number).",
    )
    document_number = fields.Char(
        compute="_compute_document_number",
        store=True,
        index=True,
        help="The six digits of the document number: the link to the projects, whose tables carry the same digits.",
    )
    os_version = fields.Char(string="Operating system", readonly=True, help="The version of the operating system that is in the file (E0310 is 3.10).")
    expected_os = fields.Char(string="Made for", readonly=True, help="The operating system an application says it is made for (E9210 is 2.10). Assumed to mean that; not proven.")
    ranges = fields.Text(string="Memory ranges", readonly=True)
    size = fields.Integer(string="File size (bytes)", readonly=True)
    data_size = fields.Integer(string="Data (bytes)", readonly=True)
    sha256 = fields.Char(string="Checksum", required=True, readonly=True, index=True, copy=False, help="SHA-256 of the file. A program exists once, whatever it is called.")
    short_id = fields.Char(string="Id", compute="_compute_short_id")
    warnings = fields.Text(readonly=True, help="What reading the file found that deserves a look. A warning does not stop the loading; the dialog of the programming shows it.")
    sources = fields.Text(string="Names of the file", readonly=True, help="Every name under which the file was brought in, one in each line.")
    data = fields.Binary(string="File", attachment=True, prefetch=False, readonly=True)
    filename = fields.Char(readonly=True)
    note = fields.Text()

    _sha256_unique = models.Constraint("UNIQUE (sha256)", "A program exists once.")

    @api.depends("sha256")
    def _compute_short_id(self):
        for software in self:
            software.short_id = (software.sha256 or "")[:8]

    @api.depends("document")
    def _compute_document_number(self):
        for software in self:
            match = re.match(r"3EGM(\d{6})E", software.document or "")
            software.document_number = match.group(1) if match else False

    # === FROM A FILE === #

    @api.model
    def _from_file(self, filename, content):
        """Read a file and return ``(record, created)``: the record of the program, and whether it is new.

        A file that is already there (same content under any name) is not a second record: the name it came with is added to the names
        of the record. A file that is no program file raises a UserError that says why.
        """
        # whoever may not bring files in must not add to what is there either (the lookup below is sudo, for the whole stock)
        self.check_access("create")
        try:
            result = check.check_file(filename, content)
        except check.ImageError as error:
            raise UserError(self.env._("%(file)s: %(reason)s", file=filename, reason=self._error_text(error))) from error
        # sudo: int.workbench.software: the lookup is for the whole stock, whoever may upload
        existing = self.sudo().with_context(active_test=False).search([("sha256", "=", result.sha256)], limit=1)
        if existing:
            existing._add_source(filename)
            if not existing.active:  # the same file again: the old program is wanted again
                existing.active = True
            return existing, False
        values = {
            "name": self._name_of(filename, result),
            "kind": result.kind,
            "hardware": result.hardware,
            "app_name": result.app_name,
            "resource": result.resource,
            "document": result.document,
            "document_codes": " ".join(result.document_codes),
            "os_version": result.os_version,
            "expected_os": result.expected_os,
            "ranges": "\n".join("0x%06X - 0x%06X" % (first, last) for first, last in result.ranges),
            "size": result.size,
            "data_size": result.data_size,
            "sha256": result.sha256,
            "warnings": "\n".join(self._warning_text(code, found) for code, found in result.warnings),
            "sources": filename,
            "filename": filename,
            "data": base64.b64encode(content),
        }
        return self.create(values), True

    @api.model
    def import_file(self, filename, data):
        """Bring a file in (for the tool that takes over the stock of the original); ``data`` is the content as base64.

        Returns ``{"id", "created", "kind", "name"}``. A file that is no program raises a UserError that says why.
        """
        if not isinstance(filename, str) or not isinstance(data, str):
            raise UserError(self.env._("A file needs a name and its content as base64."))
        try:
            content = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            raise UserError(self.env._("The content of %s is not base64.", filename)) from None
        software, created = self._from_file(filename, content)
        return {"id": software.id, "created": created, "kind": software.kind, "name": software.name}

    def _add_source(self, filename):
        """Remember another name under which the same file was brought in."""
        for software in self:
            names = (software.sources or "").splitlines()
            if filename and filename not in names:
                # sudo: int.workbench.software: the names are kept for everybody who brings the same file in again, a technician too
                software.sudo().sources = "\n".join([*names, filename])

    @api.model
    def _name_of(self, filename, result):
        stem = filename.rsplit(".", 1)[0] if filename else ""
        if result.kind in (check.KIND_APPLICATION, check.KIND_COMBINED, check.KIND_TEXT) and result.app_name:
            return result.app_name
        if result.kind == check.KIND_OS and result.os_version:
            return self.env._("Operating system %s", result.os_version)
        if result.kind == check.KIND_PARAMETER:
            return self.env._("Parameters %s", stem)
        if result.kind == check.KIND_BOOTLOADER:
            return self.env._("Bootloader %s", stem)
        return stem or self.env._("Program")

    @api.model
    def _error_text(self, error):
        """The reason a file was refused, in the language of the user (one literal call for each reason, so that they are translated)."""
        values = error.values
        match error.code:
            case "empty":
                return self.env._("The file is empty.")
            case "too_large":
                return self.env._("The file is larger than %d MB.", values["megabytes"])
            case "not_a_program":
                return self.env._("The file is neither an S-Record image nor a program text of a controller.")
            case "bad_line":
                return self.env._("Line %d is not an S-Record.", values["line"])
            case "not_hex":
                return self.env._("Line %d has characters that are no hexadecimal digits.", values["line"])
            case "bad_length":
                return self.env._("Line %d has a wrong length.", values["line"])
            case "bad_checksum":
                return self.env._("Line %d has a wrong checksum.", values["line"])
            case "unknown_record":
                return self.env._("Line %(line)d has the unknown record type S%(record)s.", line=values["line"], record=values["record"])
            case "no_data":
                return self.env._("The file has no data records.")
            case "text_no_header":
                return self.env._("The program text has no header line with the application.")
            case "text_no_data":
                return self.env._("The program text has no data lines.")
        return error.code

    @api.model
    def _warning_text(self, code, values):
        match code:
            case "overlap":
                return self.env._("Records overlap at %s.", values["address"])
            case "no_end":
                return self.env._("The file has no end record.")
            case "unknown_ranges":
                return self.env._("The memory ranges (%s) are not those of a known image.", values["ranges"])
            case "no_header":
                return self.env._("The application header is missing: no name and no resource.")
            case "name_differs":
                return self.env._(
                    "The name of the file (%(file)s) differs from the application in it (%(app)s).", file=values["filename"], app=values["app_name"]
                )
            case "text_no_dl":
                return self.env._("The command `dl 1` is missing before the data.")
        return code

    def _check_loadable(self):
        """Raise if a program cannot be loaded into a controller: it is not placed in the memory of a known controller."""
        for software in self:
            if software.kind == check.KIND_UNKNOWN or software.hardware == check.HARDWARE_UNKNOWN and software.kind != check.KIND_TEXT:
                raise UserError(self.env._("%s cannot be loaded: it is not placed in the memory of a known controller.", software.name))

    # === ORM === #

    def write(self, vals):
        if any(field in vals for field in FROM_CONTENT) and not self.env.context.get("software_internal"):
            raise UserError(self.env._("What the file contains cannot be changed. Bring the changed file in as a new program."))
        return super().write(vals)
