import json
import re
from datetime import datetime

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

# The code of a row in the service: "0016", "4200", "9000".
ROW_CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,20}")
# What the page may fill in; everything else (state, user, times) is set by the server.
CLIENT_FIELDS = ("device_id", "code", "action", "value", "payload")
# A request that is about the controller and not about a row has this as its row: the clamp log shows it, the service ignores it.
CONTROLLER_CODE = "errors"
TECHNICIAN_GROUP = "int_workbench.int_workbench_group_technician"
# The actions that an operator may ask for (clamping and clearing the error memory); every other action needs a technician.
OPERATOR_ACTIONS = ("set", "release", "clear_errors")
# The actions about the controller as a whole: they have a payload and no row.
CONTROLLER_ACTIONS = ("clear_errors", "clock_set", "can_control", "reset", "console", "console_write", "fs2_save", "fs2_delete")
# The capability that a family has to report for an action.
ACTION_CAPABILITY = {
    "clear_errors": "error_memory",
    "clock_set": "clock",
    "can_control": "can_control",
    "reset": "console",
    "console": "console",
    "console_write": "console",
    "fs2_save": "error_files",
    "fs2_delete": "error_files",
}
CAN_ACTIONS = ("stop", "start", "baptize")
CLOCK_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
CONSOLE_LIMIT = 120
# What a name of an error file looks like, and how many a request may name.
FILE_NAME_PATTERN = re.compile(r"[A-Za-z0-9._ -]{1,64}")
FILE_NAMES_LIMIT = 100
# The error file has fixed fields for them: the wagon number takes 12 characters, the train 4.
WAGON_LIMIT = 12
TRAIN_LIMIT = 4
# What the output of a request may be (the service sends at most this much).
OUTPUT_LIMIT = 200_000


class IntWorkbenchCommand(models.Model):
    _name = "int.workbench.command"
    _description = "Clamp request for a controller"
    _order = "id desc"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", string="Requested by", required=True, readonly=True, index=True, ondelete="restrict")
    code = fields.Char(string="Row", required=True)
    parameter_id = fields.Many2one(
        "int.workbench.parameter",
        string="Process value",
        readonly=True,
        index=True,
        ondelete="set null",
        help="The row of the controller this request is about, if the service has reported it. The service works with the code.",
    )
    action = fields.Selection(
        [
            ("set", "Clamp"),
            ("release", "Release"),
            ("clear_errors", "Clear error memory"),
            ("clock_set", "Set the clock"),
            ("can_control", "Control the CAN bus"),
            ("reset", "Restart the controller"),
            ("console", "Console command"),
            ("console_write", "Console command that changes something"),
            ("fs2_save", "Save the error memory as files"),
            ("fs2_delete", "Delete error files"),
        ],
        required=True,
    )
    value = fields.Float(help="The value to clamp the row to (only for Clamp).")
    payload = fields.Text(readonly=True, help="What the request carries to the service as a JSON object, for example the command of the console.")
    detail = fields.Char(compute="_compute_detail", help="What the request asks for, in a few words.")
    output = fields.Text(readonly=True, help="What the controller answered, for the requests that have an answer (the console, the CAN bus).")
    state = fields.Selection(
        [
            ("pending", "Waiting for the service"),
            ("sent", "Handed to the service"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("unconfirmed", "Not confirmed"),
            ("unknown", "Result not reported"),
            ("expired", "Expired"),
        ],
        default="pending",
        required=True,
        readonly=True,
        index=True,
    )
    message = fields.Char(readonly=True)
    sent_at = fields.Datetime(readonly=True)
    done_at = fields.Datetime(readonly=True)

    @api.depends("action", "payload", "value")
    def _compute_detail(self):
        for command in self:
            payload = command._payload_dict()
            if command.action == "set":
                command.detail = str(command.value)
            elif command.action == "clock_set":
                command.detail = payload.get("local_time", "")
            elif command.action == "can_control":
                command.detail = payload.get("action", "")
            elif command.action in ("console", "console_write"):
                command.detail = payload.get("command", "")
            elif command.action == "fs2_save":
                command.detail = " ".join(part for part in (payload.get("wagon"), payload.get("train")) if part)
            elif command.action == "fs2_delete":
                command.detail = ", ".join(payload.get("names") or [])
            else:
                command.detail = ""

    def _payload_dict(self):
        """Return the payload as a dict (empty if there is none or it is not an object)."""
        self.ensure_one()
        try:
            payload = json.loads(self.payload or "{}")
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @api.model
    def _clean_payload(self, action, payload):
        """Return the payload of a request as JSON text, after checking it for the action; raise a ValidationError if it is not right.
        Only what the action needs goes through, so that nobody can send the service anything else."""
        if isinstance(payload, str):
            try:
                payload = json.loads(payload or "{}")
            except ValueError:
                raise ValidationError(self.env._("The payload of the request is not JSON.")) from None
        payload = payload or {}
        if not isinstance(payload, dict):
            raise ValidationError(self.env._("The payload of the request must be an object."))
        if action == "clock_set":
            local_time = payload.get("local_time")
            if not isinstance(local_time, str) or not CLOCK_PATTERN.fullmatch(local_time):
                raise ValidationError(self.env._("The time must look like 2026-11-14T09:30:00."))
            try:
                datetime.fromisoformat(local_time)
            except ValueError:
                raise ValidationError(self.env._("The time %s does not exist.", local_time)) from None
            return json.dumps({"local_time": local_time})
        if action == "can_control":
            if payload.get("action") not in CAN_ACTIONS:
                raise ValidationError(self.env._("The CAN bus can be stopped, started or baptized."))
            return json.dumps({"action": payload["action"]})
        if action in ("console", "console_write"):
            text = payload.get("command")
            if not isinstance(text, str) or not text.strip() or len(text) > CONSOLE_LIMIT or any(ord(char) < 32 for char in text):
                raise ValidationError(self.env._("The command must be one line of up to %s characters.", CONSOLE_LIMIT))
            return json.dumps({"command": text.strip()})
        if action == "fs2_save":
            wagon, train, complete = payload.get("wagon"), payload.get("train") or "", payload.get("complete")
            for label, limit in ((wagon, WAGON_LIMIT), (train, TRAIN_LIMIT)):
                if not isinstance(label, str) or len(label.strip()) > limit or any(ord(char) < 32 for char in label):
                    raise ValidationError(self.env._("The wagon number takes up to %(wagon)s characters, the train up to %(train)s.", wagon=WAGON_LIMIT, train=TRAIN_LIMIT))
            if not wagon.strip() or not isinstance(complete, bool):
                raise ValidationError(self.env._("The error files need a wagon number and say whether they are complete."))
            return json.dumps({"wagon": wagon.strip(), "train": train.strip(), "complete": complete})
        if action == "fs2_delete":
            names = payload.get("names")
            if not isinstance(names, list) or not 0 < len(names) <= FILE_NAMES_LIMIT or not all(isinstance(name, str) and FILE_NAME_PATTERN.fullmatch(name) for name in names):
                raise ValidationError(self.env._("Name the error files to delete (up to %s), by their file names.", FILE_NAMES_LIMIT))
            return json.dumps({"names": names})
        return "{}"

    @api.constrains("code")
    def _check_code(self):
        for command in self:
            if not ROW_CODE_PATTERN.fullmatch(command.code or ""):
                raise ValidationError(self.env._("The row %s is not a row code.", command.code))

    @api.model_create_multi
    def create(self, vals_list):
        """A request is made by the page (or by a program in the name of a user): who asked, and how it stands, is not up to them."""
        cleaned = []
        for vals in vals_list:
            vals = {key: value for key, value in vals.items() if key in CLIENT_FIELDS}
            vals["user_id"] = self.env.uid
            action = vals.get("action")
            if action not in OPERATOR_ACTIONS and not self.env.user.has_group(TECHNICIAN_GROUP):
                raise AccessError(self.env._("Only a technician may ask for this."))
            if action in CONTROLLER_ACTIONS:
                vals["code"] = CONTROLLER_CODE  # it is about the controller, not about a row
            vals["payload"] = self._clean_payload(action, vals.get("payload")) if action in CONTROLLER_ACTIONS else False
            cleaned.append(vals)
        # sudo: int.workbench.parameter: the row is looked up by its code, whoever asks may not read every row
        Parameter = self.env["int.workbench.parameter"].sudo()
        for vals in cleaned:
            if vals.get("device_id") and vals.get("code") and vals.get("action") not in CONTROLLER_ACTIONS:
                vals["parameter_id"] = Parameter.search([("device_id", "=", vals["device_id"]), ("code", "=", vals["code"])], limit=1).id
        commands = super().create(cleaned)
        for command in commands:
            if not command.device_id.active:
                raise UserError(self.env._("The controller %s is archived.", command.device_id.name))
            # a controller whose service has not signed on has no family yet and is not refused (for clamping; clearing the error
            # memory is something a family has to say it can, as a service has to be started for it)
            device = command.device_id
            if command.action in ACTION_CAPABILITY:
                if not device["cap_" + ACTION_CAPABILITY[command.action]]:
                    raise UserError(self.env._("The controller %s cannot do this.", device.name))
            elif device.family_id and not device.cap_clamps:
                raise UserError(self.env._("The controller %s cannot be clamped.", device.name))
        return commands
