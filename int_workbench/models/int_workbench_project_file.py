from odoo import fields, models

from . import project_check as check


class IntWorkbenchProjectFile(models.Model):
    _name = "int.workbench.project.file"
    _description = "File of a project version"
    _order = "version_id, name"

    version_id = fields.Many2one("int.workbench.project.version", required=True, index=True, ondelete="cascade", readonly=True)
    name = fields.Char(required=True, readonly=True)
    kind = fields.Selection(
        [
            (check.KIND_SETTINGS, "Settings"),
            (check.KIND_TABLE, "Table"),
            (check.KIND_SCRIPT, "Script"),
            (check.KIND_PROGRAM, "Program"),
            (check.KIND_OTHER, "Other"),
        ],
        required=True,
        readonly=True,
        index=True,
        help="Told by the content: the settings file (DEF.BIN), a table, a script for the command line (confcan, confdia ...), a program "
        "(image or program text, then also a record of the software) or any other file of the project.",
    )
    command = fields.Char(string="Command", readonly=True, help="The command in the first line of a script: confcan, confdia, confpdl, confpro, clr ...")
    size = fields.Integer(string="Size (bytes)", readonly=True)
    sha256 = fields.Char(string="Checksum", required=True, readonly=True)
    data = fields.Binary(string="File", attachment=True, prefetch=False, readonly=True)
    line_name = fields.Char(string="Name in version line", readonly=True)
    line_version = fields.Char(string="Version in version line", readonly=True)
    line_date = fields.Char(string="Date in version line", readonly=True)
    line_number = fields.Char(
        string="Number in version line",
        readonly=True,
        help="The four digits of the document number: the kind of the document (M2 signal addresses, M3 process values, M4 error table, "
        "E2 CAN, E3 confpdl, E4 diagnosis, with the letter) and its version (the last three digits).",
    )
    line_document = fields.Char(string="Document number", readonly=True, help="The six digits of the document number in the version line (3EGM, six digits, a letter, four digits).")
    line_author = fields.Char(string="Author", readonly=True)
    software_id = fields.Many2one("int.workbench.software", string="Software", readonly=True, ondelete="set null", help="The program that this file is, if it is one.")
    vehicle = fields.Char(related="version_id.folder_id.vehicle", string="Vehicle")
    project = fields.Char(related="version_id.folder_id.name", string="Project")
