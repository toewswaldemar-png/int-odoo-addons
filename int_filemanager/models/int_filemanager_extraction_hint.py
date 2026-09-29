from odoo import fields, models


class IntFilemanagerExtractionHint(models.Model):
    """A label learned from a confirmed value: at this sender, it names this field.

    Like base_import.mapping remembers which column of an import file goes to which
    field, the last confirmation wins. Written only by the node's method that stores
    confirmed values and read only by the suggestions; users have no access, as the
    list would show which senders there are documents from.
    """

    _name = "int_filemanager.extraction_hint"
    _description = "Filemanager v2 learned label"
    _order = "partner_id, label"

    partner_id = fields.Many2one(
        "res.partner", required=True, index=True, ondelete="cascade"
    )
    # Compared without case, punctuation and spaces (value_suggest.normalize).
    label = fields.Char(required=True)
    field_id = fields.Many2one(
        "int_filemanager.extraction_field", required=True, ondelete="cascade"
    )
    direction = fields.Selection(
        [("before", "Before"), ("left", "Left"), ("above", "Above"), ("below", "Below")]
    )
    # Where the label was printed, for senders whose documents always look alike.
    page = fields.Integer()
    x0 = fields.Float()
    top = fields.Float()
    hit_count = fields.Integer(default=1)
    last_date = fields.Datetime(default=fields.Datetime.now)

    _partner_label_uniq = models.Constraint(
        "UNIQUE(partner_id, label)", "A sender's label names one field."
    )
