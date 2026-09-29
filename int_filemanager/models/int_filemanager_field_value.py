from odoo import api, fields, models
from odoo.exceptions import ValidationError


class IntFilemanagerFieldValue(models.Model):
    """A field's value for one document, as confirmed by a user.

    value_text always holds the normalized value, so every value can be shown and
    searched the same way; the typed columns next to it make dates and numbers
    filterable and sortable. Only the column that fits the field's type is set.
    Users never write here directly: values are created through the node's methods,
    which check the user's right on the node first.
    """

    _name = "int_filemanager.field_value"
    _description = "Filemanager v2 field value"
    _order = "node_id, field_id"

    node_id = fields.Many2one(
        "int_filemanager.node", required=True, index=True, ondelete="cascade"
    )
    field_id = fields.Many2one(
        "int_filemanager.extraction_field",
        required=True,
        index=True,
        ondelete="restrict",
    )
    value_type = fields.Selection(related="field_id.value_type")
    # The revision whose text the value was read from, so that a newer revision can
    # be told apart from the one the values belong to.
    revision_id = fields.Many2one(
        "int_filemanager.revision", index="btree_not_null", ondelete="set null"
    )
    rule_id = fields.Many2one("int_filemanager.extraction_rule", ondelete="set null")
    source = fields.Selection(
        [("rule", "Rule"), ("manual", "Manual")], required=True, default="manual"
    )
    source_text = fields.Char(help="The text as printed in the document.")
    value_text = fields.Char(required=True, index="trigram")
    value_date = fields.Date()
    # End of a period; value_date is its start.
    value_date_to = fields.Date()
    # An amount, a quantity, or the length of a duration (with unit, e.g. months).
    value_number = fields.Float()
    currency_id = fields.Many2one("res.currency")
    unit = fields.Char()
    # Where the value is printed, in PDF points from the top left of the page.
    page = fields.Integer()
    x0 = fields.Float()
    top = fields.Float()
    x1 = fields.Float()
    bottom = fields.Float()

    _node_field_uniq = models.Constraint(
        "UNIQUE(node_id, field_id)", "A document has one value per field."
    )
    _field_date_idx = models.Index("(field_id, value_date)")
    _field_number_idx = models.Index("(field_id, value_number)")

    @api.constrains(
        "field_id", "value_date", "value_date_to", "value_number", "currency_id", "unit"
    )
    def _check_typed_value(self):
        # Exactly the columns of the type are set, so that a filter on one column
        # never meets a value that means something else. A number of 0 counts as
        # unset: the ORM stores a missing float as 0.
        for value in self:
            present = {
                name
                for name in (
                    "value_date",
                    "value_date_to",
                    "value_number",
                    "currency_id",
                    "unit",
                )
                if value[name]
            }
            kind = value.field_id.value_type
            if kind == "date":
                ok = present == {"value_date"}
            elif kind == "period":
                ok = present in (
                    {"value_date", "value_date_to"},
                    {"value_number", "unit"},
                ) and not (
                    value.value_date_to and value.value_date_to < value.value_date
                )
            elif kind == "amount":
                ok = present <= {"value_number", "currency_id"} and bool(
                    value.currency_id
                )
            elif kind == "quantity":
                ok = present <= {"value_number", "unit"} and bool(value.unit)
            else:
                ok = not present
            if not ok:
                raise ValidationError(
                    self.env._(
                        "The value of %(field)s does not fit its type.",
                        field=value.field_id.name,
                    )
                )

    @api.constrains("node_id", "field_id", "revision_id", "rule_id")
    def _check_origin(self):
        # The revision is what tells a stale value from a current one, so it must be
        # one of this document's own.
        for value in self:
            if (value.revision_id and value.revision_id.node_id != value.node_id) or (
                value.rule_id and value.rule_id.field_id != value.field_id
            ):
                raise ValidationError(
                    self.env._(
                        "The value of %(field)s names a revision or rule that belongs "
                        "elsewhere.",
                        field=value.field_id.name,
                    )
                )
