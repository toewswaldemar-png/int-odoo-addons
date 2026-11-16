import re

from odoo import api, fields, models
from odoo.exceptions import UserError

from .service_utils import clean_text

# What an address of the controller looks like: the letters of the memory area (I, Q, M, QW, ...), a number, and for a bit a point and the
# bit number. The service sends nothing else on the line (protocol.ValidOperand in the service), so the form is checked here as well.
OPERAND_PATTERN = re.compile(r"[A-Z]{1,2}[0-9]{1,5}(\.[0-7])?")
OPERAND_MAX = 8
# What the service takes: the longest name of a row of the original (a short string of 20), and how many rows may be read.
NAME_MAX = 20
SELECTION_MAX = 200
# What a report of the variable list may carry at most (the original has 5000 rows).
SIGNALS_MAX = 5000


def valid_operand(operand):
    """Say whether this is an address that may be sent to the controller."""
    return bool(operand) and len(operand) <= OPERAND_MAX and OPERAND_PATTERN.fullmatch(operand) is not None


class IntWorkbenchSignal(models.Model):
    _name = "int.workbench.signal"
    _description = "Variable of the project of a controller"
    _order = "device_id, sequence, id"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade", readonly=True)
    sequence = fields.Integer(readonly=True, help="The place in the variable list of the project, counted from 1.")
    name = fields.Char(readonly=True, index=True, help="The signal name of the project, for example P1011.")
    operand = fields.Char(string="Address", readonly=True, help="Where the controller keeps it, for example M0448 or I0000.0.")
    is_byte = fields.Boolean(string="Byte or bit", readonly=True, help="A byte or a bit is read with DB, a word with DW.")
    chosen = fields.Boolean(compute="_compute_chosen", string="Chosen", help="The variable is among the intermediate values of the controller.")

    @api.depends("device_id.intermediate_ids.name", "device_id.intermediate_ids.address")
    def _compute_chosen(self):
        for signal in self:
            signal.chosen = any(row.name == signal.name and row.address == signal.operand for row in signal.device_id.intermediate_ids)

    @api.model
    def _report(self, device, signals):
        """Replace the variable list of a controller by what the service has reported (rows that are not valid are left out).

        The service reports the list when it is new or has changed, so this is rare. The list is the one of the project the controller
        runs; it is what the original shows on the left of "Zwischenw. auswählen".
        """
        wanted = []
        for position, item in enumerate((signals or [])[:SIGNALS_MAX], start=1):
            if not isinstance(item, dict):
                continue
            name, operand = clean_text(item.get("name")), clean_text(item.get("operand"))
            if not name or not valid_operand(operand):
                continue
            wanted.append({"device_id": device.id, "sequence": position, "name": name[:NAME_MAX], "operand": operand, "is_byte": item.get("byte") is True})
        current = self.search([("device_id", "=", device.id)], order="sequence")
        if [(r.name, r.operand, r.is_byte) for r in current] == [(w["name"], w["operand"], w["is_byte"]) for w in wanted]:
            return False
        current.unlink()
        self.create(wanted)
        return True

    def action_choose(self):
        """Add the selected variables to the intermediate values of their controller (the "->" of the original). A variable that is
        among them already is not added again. They are shown as numbers, like the original does at first."""
        if not self:
            raise UserError(self.env._("Select the variables to add."))
        Intermediate = self.env["int.workbench.intermediate"]
        Intermediate.check_access("create")
        added = Intermediate
        for signal in self:
            if Intermediate.search_count([("device_id", "=", signal.device_id.id), ("name", "=", signal.name), ("format", "=", "Z")], limit=1):
                continue
            added |= Intermediate.create(
                {"device_id": signal.device_id.id, "name": signal.name, "address": signal.operand, "is_byte": signal.is_byte, "format": "Z"}
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Intermediate values"),
                "message": self.env._("%(added)s added, %(skipped)s were there already.", added=len(added), skipped=len(self) - len(added)),
                "type": "success",
                "sticky": False,
            },
        }
