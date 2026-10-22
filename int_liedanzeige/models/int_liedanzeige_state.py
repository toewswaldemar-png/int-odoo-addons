import time

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

DIGITS = tuple("0123456789")
MAX_DIGITS = 4
CHANNEL_HYMN = "int_liedanzeige_hymn"
CHANNEL_CHOIR = "int_liedanzeige_choir"
CHANNEL_KIOSK = "int_liedanzeige_kiosk"
KIOSK_COMMANDS = ("fullscreen", "windowed", "reload", "swap_monitors", "quit")
NOTIFICATION_TYPE = "int_liedanzeige_notify"
OPERATOR_GROUP = "int_liedanzeige.group_liedanzeige_operator"
CONDUCTOR_GROUP = "int_liedanzeige.group_liedanzeige_conductor"
TARGETS = ("hymn", "choir")
FONTS = [
    ("segoe-ui", "Segoe UI"),
    ("arial", "Arial"),
    ("verdana", "Verdana"),
    ("trebuchet-ms", "Trebuchet MS"),
    ("georgia", "Georgia"),
    ("times", "Times New Roman"),
]
SETTING_RANGES = {
    "time_size": (10, 100),
    "sub_clock_size": (10, 100),
    "gap_time_date": (0, 100),
    "shadow_strength": (0, 100),
    "reset_delay": (1, 10),
}
SETTING_FIELDS = (*SETTING_RANGES, "font")


class IntLiedanzeigeState(models.Model):
    _name = "int_liedanzeige.state"
    _description = "Hymn display state"

    hymn_state = fields.Char(default="")
    choir_state = fields.Char(default="")
    control_state = fields.Char(
        default="",
        help="Number shown on every control page, set by any input.",
    )
    time_size = fields.Integer(default=75)
    sub_clock_size = fields.Integer(default=75)
    gap_time_date = fields.Integer(default=0)
    font = fields.Selection(FONTS, default="segoe-ui", required=True)
    shadow_strength = fields.Integer(default=40)
    reset_delay = fields.Integer(
        default=5,
        help="Minutes without input before a display returns to the clock.",
    )
    kiosk_fullscreen = fields.Boolean(
        default=True,
        help="Whether the kiosk windows are in fullscreen, as the kiosk last reported.",
    )

    _digits_only = models.Constraint(
        "CHECK (hymn_state ~ '^[0-9]{0,4}$' AND choir_state ~ '^[0-9]{0,4}$' "
        "AND control_state ~ '^[0-9]{0,4}$')",
        "A number has at most four digits.",
    )
    _settings_in_range = models.Constraint(
        "CHECK (time_size BETWEEN 10 AND 100 AND sub_clock_size BETWEEN 10 AND 100 "
        "AND gap_time_date BETWEEN 0 AND 100 AND shadow_strength BETWEEN 0 AND 100 "
        "AND reset_delay BETWEEN 1 AND 10)",
        "A display setting is outside its allowed range.",
    )

    @api.model
    def apply_action(self, action, target=None, value=None, values=None):
        """Apply one operator action to the display state and return the new state.

        :param action: ``input``, ``backspace``, ``reset`` or ``settings``
        :param target: ``hymn`` (hymn and choir display) or ``choir`` (choir display only)
        :param value: the digit for ``input``
        :param values: setting values for ``settings``
        """
        self._check_operator()
        handler = {
            "input": self._apply_input,
            "backspace": self._apply_backspace,
            "reset": self._apply_reset,
            "settings": self._apply_settings,
        }.get(action)
        if handler is None:
            raise UserError(self.env._("Unknown action."))
        if target is None:
            target = "hymn"
        if target not in TARGETS:
            raise UserError(self.env._("Unknown target."))
        state = self.env.ref("int_liedanzeige.state_main")
        handler(state, target, value, values)
        state._notify()
        return state._to_dict()

    @api.model
    def get_state(self):
        """Return the current state for an operator page that has just connected."""
        self._check_operator()
        return self.env.ref("int_liedanzeige.state_main")._to_dict()

    @api.model
    def get_conductor_state(self):
        """Return what the conductor view shows now, for a page that has just connected."""
        if not self.env.user.has_group(CONDUCTOR_GROUP):
            raise AccessError(self.env._("Only conductors can open the conductor view."))
        # sudo: a conductor has no access to the state model; the group was checked above and
        # the values returned are the ones a conductor may see.
        return self.env.ref("int_liedanzeige.state_main").sudo()._conductor_values()

    @api.model
    def send_kiosk_command(self, command):
        """Send a window command to the kiosk programs."""
        self._check_operator()
        if command not in KIOSK_COMMANDS:
            raise UserError(self.env._("Unknown kiosk command."))
        # The send time lets a kiosk drop a command the bus replays after a restart.
        self.env["bus.bus"]._sendone(
            CHANNEL_KIOSK, NOTIFICATION_TYPE, {"command": command, "sent_at": time.time()}
        )

    @api.model
    def report_kiosk_state(self, fullscreen):
        """Store whether the kiosk windows are in fullscreen and tell the operator pages."""
        self._check_operator()
        if not isinstance(fullscreen, bool):
            raise UserError(self.env._("The fullscreen state is true or false."))
        state = self.env.ref("int_liedanzeige.state_main")
        state.kiosk_fullscreen = fullscreen
        state._notify_operators()

    def _check_operator(self):
        if not self.env.user.has_group(OPERATOR_GROUP):
            raise AccessError(self.env._("Only hymn display operators can control the display."))

    def _apply_input(self, state, target, value, values):
        if value not in DIGITS:
            raise UserError(self.env._("An input is a single digit."))
        vals = {}
        if target == "choir":
            if len(state.choir_state) < MAX_DIGITS:
                vals["choir_state"] = state.choir_state + value
        elif len(state.hymn_state) < MAX_DIGITS:
            vals["hymn_state"] = state.hymn_state + value
            vals["choir_state"] = vals["hymn_state"]
        if len(state.control_state) < MAX_DIGITS:
            vals["control_state"] = state.control_state + value
        state.write(vals)

    def _apply_backspace(self, state, target, value, values):
        vals = {"control_state": state.control_state[:-1]}
        if target == "choir":
            vals["choir_state"] = state.choir_state[:-1]
        else:
            vals["hymn_state"] = state.hymn_state[:-1]
            vals["choir_state"] = vals["hymn_state"]
        state.write(vals)

    def _apply_reset(self, state, target, value, values):
        vals = {"choir_state": "", "control_state": ""}
        if target == "hymn":
            vals["hymn_state"] = ""
        state.write(vals)

    def _apply_settings(self, state, target, value, values):
        if not isinstance(values, dict):
            raise UserError(self.env._("Settings must be given as a dictionary."))
        unknown = set(values) - set(SETTING_FIELDS)
        if unknown:
            raise UserError(self.env._("Unknown setting: %s", ", ".join(sorted(unknown))))
        for name, setting in values.items():
            if name == "font":
                if setting not in dict(FONTS):
                    raise UserError(self.env._("Unknown font."))
            else:
                low, high = SETTING_RANGES[name]
                if not isinstance(setting, int) or isinstance(setting, bool) or not low <= setting <= high:
                    raise UserError(
                        self.env._("Setting %(name)s must be a whole number from %(low)s to %(high)s.", name=name, low=low, high=high)
                    )
        state.write(values)

    def _notify(self):
        """Push the state to the displays and to the operator pages."""
        self.ensure_one()
        Bus = self.env["bus.bus"]
        public = self._public_values()
        for target, channel in (("hymn", CHANNEL_HYMN), ("choir", CHANNEL_CHOIR)):
            Bus._sendone(
                channel,
                NOTIFICATION_TYPE,
                {"target": target, "number": public[f"{target}_state"], "settings": public["settings"]},
            )
        self._notify_operators()
        # Only a group record keeps the song text from clients that guess a channel name.
        Bus._sendone(
            self.env.ref(CONDUCTOR_GROUP),
            NOTIFICATION_TYPE,
            {"target": "conductor", **self._conductor_values()},
        )

    def _conductor_values(self):
        """Return the choir number with its song text, and the hymn number."""
        self.ensure_one()
        Song = self.env["int_liedanzeige.song"]
        song = Song.search([("number", "=", self.choir_state)], limit=1) if self.choir_state else Song
        return {
            "choir_number": self.choir_state,
            "hymn_number": self.hymn_state,
            "song_name": song.name or "",
            "song_text": song.text or "",
        }

    def _notify_operators(self):
        """Push the full state to the operator pages."""
        # Group records are the only bus channels a client cannot subscribe to by guessing a name.
        self.env["bus.bus"]._sendone(
            self.env.ref(OPERATOR_GROUP), NOTIFICATION_TYPE, {"target": "control", **self._to_dict()}
        )

    def _public_values(self):
        """Return what a display may know: the two numbers and the look, never the control number."""
        self.ensure_one()
        return {
            "hymn_state": self.hymn_state,
            "choir_state": self.choir_state,
            "settings": {name: self[name] for name in SETTING_FIELDS},
        }

    def _to_dict(self):
        """Return the display state and settings as plain values."""
        self.ensure_one()
        return {
            "hymn_state": self.hymn_state,
            "choir_state": self.choir_state,
            "control_state": self.control_state,
            "settings": {name: self[name] for name in SETTING_FIELDS},
            "ranges": {name: list(bounds) for name, bounds in SETTING_RANGES.items()},
            "kiosk_fullscreen": self.kiosk_fullscreen,
        }
