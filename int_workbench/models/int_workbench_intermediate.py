from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .int_workbench_signal import NAME_MAX, SELECTION_MAX, valid_operand
from .service_utils import _differs, clean_text

# What a row is, as far as the service needs to read it: the name, the address, byte or word, and the format of the display. A change
# of one of them is a new selection for the service; a reading that the service reports is not.
SELECTION_FIELDS = ("device_id", "sequence", "name", "address", "is_byte", "format")
# What the service reports about a row; everything else of the row is the selection.
READING_FIELDS = ("raw", "text", "value", "has_value", "unit", "answered", "locked", "error")
FORMATS = [("B", "Bits"), ("Z", "Number"), ("P", "Percent"), ("H", "Hex")]


class IntWorkbenchIntermediate(models.Model):
    _name = "int.workbench.intermediate"
    _description = "Intermediate value of a controller"
    _order = "device_id, sequence, id"

    # The rows of the selection (what the original keeps in "Zwischenw. auswählen") with the reading that the service reports for them.
    device_id = fields.Many2one("int.workbench.device", string="Device", required=True, index=True, ondelete="cascade")
    sequence = fields.Integer(help="The order in which the service reads the rows and in which they are shown.")
    label = fields.Char(
        string="Own name",
        help="What you call the value in the lists, for example Zulufttemperatur. The service reads the signal name and the address; this name is only shown.",
    )
    name = fields.Char(required=True, help="The signal name of the project (P1011), or a name of your own for a row that is not in the variable list.")
    address = fields.Char(required=True, help="Where the controller keeps the value, for example M0448 or I0000.0. For a row of your own the address is the point.")
    is_byte = fields.Boolean(string="Byte or bit", help="A byte or a bit is read with DB and written with JB, a word with DW and JW.")
    format = fields.Selection(
        FORMATS,
        required=True,
        default="Z",
        help="How the value is shown and typed: bits, a number, a percent value (tenths for the 11HA30, a hundredth of $1000 for other "
        "controllers) or hex. The original has the one choice for the whole screen; here every row has its own.",
    )
    raw = fields.Char(string="Answer", readonly=True, help="What the controller answered, as it came.")
    text = fields.Char(readonly=True)
    value = fields.Float(readonly=True, digits=(16, 3))
    has_value = fields.Boolean(readonly=True, help="The service could turn the answer into a number.")
    unit = fields.Char(readonly=True)
    answered = fields.Boolean(readonly=True)
    locked = fields.Boolean(readonly=True)
    error = fields.Char(readonly=True)
    can_write_value = fields.Boolean(related="device_id.cap_intermediate_write", string="The value may be written")

    _device_name_format_unique = models.Constraint(
        "UNIQUE (device_id, name, format)", "The controller has this value in this format already."
    )

    @api.constrains("name", "address")
    def _check_row(self):
        for row in self:
            if not row.name or not row.name.strip() or len(row.name) > NAME_MAX or any(ord(char) < 32 for char in row.name):
                raise ValidationError(self.env._("The name must be 1 to %s characters.", NAME_MAX))
            if not valid_operand(row.address):
                raise ValidationError(
                    self.env._("%s is not an address. It is the letters of the memory area, a number and for a bit a point and the bit number, for example M0448 or I0000.3.", row.address)
                )

    @api.constrains("device_id")
    def _check_count(self):
        for device in self.device_id:
            if self.search_count([("device_id", "=", device.id)]) > SELECTION_MAX:
                raise ValidationError(self.env._("A controller can have up to %s intermediate values.", SELECTION_MAX))

    # === THE SELECTION IS TOLD TO THE SERVICE BY ITS VERSION === #

    @api.model_create_multi
    def create(self, vals_list):
        """A new row is put at the end of the list of its controller. The service gets the new selection with its next call."""
        last = {}
        for vals in vals_list:
            if "sequence" not in vals and vals.get("device_id"):
                device_id = vals["device_id"]
                if device_id not in last:
                    rows = self.search([("device_id", "=", device_id)], order="sequence desc", limit=1)
                    last[device_id] = rows.sequence
                last[device_id] += 1
                vals["sequence"] = last[device_id]
            for key in ("name", "address"):
                if isinstance(vals.get(key), str):
                    vals[key] = vals[key].strip()
        rows = super().create(vals_list)
        rows.device_id._intermediate_changed()
        return rows

    def write(self, vals):
        for key in ("name", "address"):
            if isinstance(vals.get(key), str):
                vals[key] = vals[key].strip()
        selection_changes = any(key in vals for key in SELECTION_FIELDS)
        devices = self.device_id if selection_changes else self.env["int.workbench.device"]
        result = super().write(vals)
        if selection_changes:
            (devices | self.device_id)._intermediate_changed()
        return result

    def unlink(self):
        devices = self.device_id
        result = super().unlink()
        devices._intermediate_changed()
        return result

    def _sync(self, device, snapshot):
        """Bring the readings of the rows of one controller to what the report says. The rows themselves are the selection, which is
        Odoo's: a report neither creates nor removes one; a row that the report has no reading for keeps the one it has. A report whose
        part is not readable leaves the readings as they are. Returns whether a reading changed."""
        part = snapshot.get("intermediate") if isinstance(snapshot, dict) else None
        if not isinstance(part, dict) or part.get("status") != "ok" or not isinstance(part.get("items"), list):
            return False
        readings = {}
        for item in part["items"]:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            has_value = isinstance(value, (int, float)) and not isinstance(value, bool)
            key = (clean_text(item.get("name")), clean_text(item.get("address")), clean_text(item.get("format")))
            readings[key] = {
                "raw": clean_text(item.get("raw")),
                "text": clean_text(item.get("text")),
                "value": float(value) if has_value else 0.0,
                "has_value": has_value,
                "unit": clean_text(item.get("unit")),
                "answered": item.get("answered") is True,
                "locked": item.get("locked") is True,
                "error": clean_text(item.get("error")),
            }
        changed = False
        for row in self.search([("device_id", "=", device.id)]):
            wanted = readings.get((row.name, row.address, row.format))
            if wanted is None:
                continue
            diff = {name: value for name, value in wanted.items() if _differs(row[name], value)}
            if diff:
                row.write(diff)
                changed = True
        return changed

    # === THE BUTTONS === #

    def action_edit_value(self):
        """Open the dialog to write a value into the controller."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Edit the value"),
            "res_model": "int.workbench.intermediate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_intermediate_id": self.id},
        }

    def action_sort(self):
        """Put the rows of the controllers of the selected rows in the order of the variable list (what "Sort." of the original does):
        the rows that are in the list as it is, then the rows of your own in the order they were made."""
        for device in self.device_id:
            rows = self.search([("device_id", "=", device.id)])
            places = {(s.name, s.operand): s.sequence for s in self.env["int.workbench.signal"].search([("device_id", "=", device.id)])}
            ordered = rows.sorted(key=lambda row: (places.get((row.name, row.address), 10**9), row.sequence, row.id))
            for position, row in enumerate(ordered, start=1):
                if row.sequence != position:
                    row.sequence = position
        return True

