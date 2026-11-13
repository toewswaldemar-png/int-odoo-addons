from odoo import fields, models
from odoo.exceptions import AccessError, UserError

OPERATOR_GROUP = "int_workbench.int_workbench_group_operator"


class IntWorkbenchError(models.Model):
    _name = "int.workbench.error"
    _description = "Active error of a controller"
    _order = "device_id, word, bit"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade", readonly=True)
    word = fields.Char(string="Error word", required=True, readonly=True)
    bit = fields.Integer(required=True, readonly=True)
    text = fields.Char(string="Error", readonly=True)

    _device_word_bit_unique = models.Constraint("UNIQUE (device_id, word, bit)", "An error exists once per controller.")

    def action_clear_memory(self):
        """The button of the list: ask the service to clear the error memory of the controllers whose errors the list shows (its search
        and its controller; the list tells it as active_domain). The button gives no rows, so they are looked up. The result shows in
        the list when the service has reported (the list hears it from the bus), and in the clamp log."""
        if not self.env.user.has_group(OPERATOR_GROUP):
            raise AccessError(self.env._("Only an operator may clear the error memory."))
        devices = self.search(self.env.context.get("active_domain") or []).device_id
        if not devices:
            raise UserError(self.env._("The list shows no errors, so there is no controller whose error memory it could clear."))
        self.env["int.workbench.command"].create([{"device_id": device.id, "action": "clear_errors"} for device in devices])
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Requested"),
                "message": self.env._("The error memory of %s is being cleared.", ", ".join(devices.mapped("name"))),
                "type": "info",
                "sticky": False,
            },
        }

    def _sync(self, device, snapshot):
        """Bring the errors of one controller to what the report says: the active errors are the rows, the others are removed.
        Returns whether a row was created, changed or removed (the lists that look at the controller are told then)."""
        wanted = {}
        if isinstance(snapshot, dict) and isinstance(snapshot.get("errors"), dict):
            for entry in snapshot["errors"].get("active") or []:
                if isinstance(entry, dict) and isinstance(entry.get("word"), str) and isinstance(entry.get("bit"), int):
                    wanted[entry["word"], entry["bit"]] = str(entry.get("text") or "")
        known = {(row.word, row.bit): row for row in self.search_fetch([("device_id", "=", device.id)], ["word", "bit", "text"])}
        changed = False
        for key, row in known.items():
            if key not in wanted:
                row.unlink()
                changed = True
            elif (row.text or "") != wanted[key]:
                row.write({"text": wanted[key]})
                changed = True
        new = [{"device_id": device.id, "word": word, "bit": bit, "text": text} for (word, bit), text in wanted.items() if (word, bit) not in known]
        if new:
            self.create(new)
        return changed or bool(new)
