import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

# The type decides how a match is parsed and checked, and which column of
# int_filemanager.field_value holds the result.
VALUE_TYPES = [
    ("number", "Number"),
    ("word", "Word"),
    ("date", "Date"),
    ("period", "Period or duration"),
    ("amount", "Amount"),
    ("quantity", "Quantity with unit"),
    ("iban", "IBAN"),
    ("vat", "VAT number"),
    ("email", "Email"),
]


class IntFilemanagerExtractionField(models.Model):
    """A value to look for in documents, such as an invoice number or a due date.

    One field can have several rules (the ways to find it), but a document gets
    at most one value per field.
    """

    _name = "int_filemanager.extraction_field"
    _description = "Filemanager v2 extraction field"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    # Archive instead of delete: confirmed values keep pointing at the field.
    active = fields.Boolean(default=True)
    value_type = fields.Selection(VALUE_TYPES, required=True, default="number")
    unit = fields.Char(help="Unit a quantity is given in, for example kWh or ct/kWh.")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        help="Currency of an amount printed without one.",
    )
    page_area = fields.Selection(
        [("anywhere", "Anywhere"), ("address", "Address window")],
        required=True,
        default="anywhere",
        help="Where the value is printed. The address window is the addressee's "
        "address on the first page of a letter, top left.",
    )
    rule_ids = fields.One2many("int_filemanager.extraction_rule", "field_id")

    @api.constrains("name")
    def _check_name_unique(self):
        # Not an SQL constraint: the translated name is stored as JSON per language.
        for field in self:
            # =ilike compares without case but reads % and _ as wildcards.
            name = re.sub(r"([\\%_])", r"\\\1", field.name)
            clash = (
                self.with_context(active_test=False)
                .sudo()
                .search_count(
                    [("name", "=ilike", name), ("id", "!=", field.id)], limit=1
                )
            )
            if clash:
                raise ValidationError(
                    self.env._(
                        "A field named %(name)s already exists.", name=field.name
                    )
                )

    @api.constrains("value_type", "unit")
    def _check_unit(self):
        for field in self:
            if field.value_type == "quantity" and not (field.unit or "").strip():
                raise ValidationError(
                    self.env._("A quantity field needs a unit, for example kWh.")
                )

    def write(self, vals):
        if "value_type" in vals:
            changed = self.filtered(lambda f: f.value_type != vals["value_type"])
            # Stored values were parsed for the old type and would no longer match
            # their columns.
            if changed and self.env["int_filemanager.field_value"].sudo().search_count(
                [("field_id", "in", changed.ids)], limit=1
            ):
                raise UserError(
                    self.env._(
                        "The type of a field cannot change once documents have values "
                        "for it. Archive it and create a new field instead."
                    )
                )
        return super().write(vals)
