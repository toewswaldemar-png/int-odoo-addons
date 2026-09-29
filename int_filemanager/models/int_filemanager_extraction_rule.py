import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class IntFilemanagerExtractionRule(models.Model):
    """One way to find a field's value in a document's text.

    Keyword mode is meant for users who do not write regular expressions: they
    list the labels printed next to the value, and the field's type decides what
    counts as the value. Regex mode is for the cases keywords cannot describe.
    """

    _name = "int_filemanager.extraction_rule"
    _description = "Filemanager v2 extraction rule"
    _order = "field_id, sequence, id"

    field_id = fields.Many2one(
        "int_filemanager.extraction_field",
        required=True,
        index=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    mode = fields.Selection(
        [("keyword", "Keywords"), ("regex", "Regular expression")],
        required=True,
        default="keyword",
    )
    # Not translated: these are the words printed in the documents, whatever the
    # language of the user.
    keywords = fields.Text(
        help="One label per line, as printed before, beside or above the value."
    )
    pattern = fields.Char(string="Regular expression")
    group_index = fields.Integer(
        default=0,
        help="Group of the regular expression that holds the value; 0 is the whole "
        "match.",
    )
    ignore_case = fields.Boolean(default=True)

    def _keyword_list(self):
        self.ensure_one()
        return [
            line.strip() for line in (self.keywords or "").splitlines() if line.strip()
        ]

    @api.constrains("mode", "keywords", "pattern", "group_index", "ignore_case")
    def _check_rule(self):
        for rule in self:
            if rule.mode == "keyword":
                if not rule._keyword_list():
                    raise ValidationError(self.env._("Enter at least one keyword."))
                continue
            if not rule.pattern:
                raise ValidationError(self.env._("Enter a regular expression."))
            try:
                compiled = re.compile(
                    rule.pattern, re.IGNORECASE if rule.ignore_case else 0
                )
            except re.error as e:
                raise ValidationError(
                    self.env._(
                        "The regular expression is not valid: %(error)s", error=e
                    )
                ) from e
            if not 0 <= rule.group_index <= compiled.groups:
                raise ValidationError(
                    self.env._(
                        "The regular expression has %(count)s group(s); "
                        "group %(index)s does not exist.",
                        count=compiled.groups,
                        index=rule.group_index,
                    )
                )
