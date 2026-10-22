import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

NUMBER_PATTERN = re.compile(r"[0-9]{1,4}")


def _number_taken_message(env, diag):
    """Name the clashing number in the message of the unique constraint."""
    match = re.search(r"=\((.*?)\)", diag.message_detail or "")
    if match:
        return env._("The song number %s is already used.", match.group(1))
    return env._("A song number can only be used once.")


class IntLiedanzeigeSong(models.Model):
    _name = "int_liedanzeige.song"
    _description = "Song with its number and text"
    # The number is text so that it matches what is typed on the pad, but it sorts as a number.
    _order = "number_value, number"

    number = fields.Char(required=True, index=True)
    number_value = fields.Integer(compute="_compute_number_value", store=True)
    name = fields.Char(string="Title")
    text = fields.Text()

    _number_unique = models.Constraint("UNIQUE (number)", _number_taken_message)

    @api.depends("number")
    def _compute_number_value(self):
        for song in self:
            song.number_value = int(song.number) if NUMBER_PATTERN.fullmatch(song.number or "") else 0

    @api.depends("number", "name")
    def _compute_display_name(self):
        for song in self:
            song.display_name = " ".join(part for part in (song.number, song.name) if part)

    @api.constrains("number")
    def _check_number(self):
        for song in self:
            if not NUMBER_PATTERN.fullmatch(song.number or ""):
                raise ValidationError(
                    self.env._("The song number %s must have one to four digits.", song.number)
                )
