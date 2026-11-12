import json
import re
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

# What the service accepts as the id of a controller: letters, digits, minus and underscore.
DEVICE_REF_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
SERVICE_GROUP = "int_workbench.group_workbench_service"
# What a service may report in one call. A snapshot of a controller with all pages is some 100 kB.
MAX_SNAPSHOT_BYTES = 2_000_000
# What of a report is not kept in the Json of the controller: the process values, the clamps and the pages are the rows of int.workbench.parameter.
ROW_PARTS = ("values", "clamps", "pages")
# A clamp request that was not carried out this long after it was made is not carried out any more. The page waits longer than this
# (workbench_client.js), so it always gets an answer from Odoo, never a request that runs after the page has given up.
COMMAND_TTL = timedelta(seconds=15)
# A request that was handed out and has no result yet is handed out again after this long (the answer to the call may have been lost).
# Clamping and releasing can be repeated; the service recognizes the id and does not do it twice.
REDELIVER_AFTER = timedelta(seconds=3)
# How many requests one call of the service takes along.
COMMAND_BATCH = 20
# A message about changed rows names them up to this many; beyond that the page loads the whole list.
VALUES_MESSAGE_IDS = 30
RESULT_STATES = ("done", "failed", "unconfirmed", "unknown", "expired")
# The call of the service and the look of a person are written down at most this often (a write per call would be the load again).
SEEN_REFRESH = timedelta(seconds=5)
WATCH_REFRESH = timedelta(seconds=5)
# Somebody looks at the controller if the page said so this recently (the page says it every 10 s while it is open).
WATCHED_FOR = timedelta(seconds=30)
# How often the service asks and reports, by whether somebody looks. System parameters "int_workbench.<name>" change them.
DEFAULT_SETTINGS = {"poll_fast_ms": 250, "poll_idle_ms": 2000, "report_fast_ms": 2000, "report_idle_ms": 60000}
SETTING_LIMITS = {
    "poll_fast_ms": (100, 5000),
    "poll_idle_ms": (250, 60000),
    "report_fast_ms": (500, 60000),
    "report_idle_ms": (2000, 3600000),
}


class IntReglerDevice(models.Model):
    _name = "int.workbench.device"
    _inherit = ["bus.listener.mixin"]
    _description = "Controller reached through the controller service"
    _order = "name, id"

    name = fields.Char(required=True, index=True)
    device_ref = fields.Char(
        string="Controller id",
        required=True,
        default="main",
        help="The id of the controller in the configuration of the service.",
    )
    service_user_id = fields.Many2one(
        "res.users",
        string="Service user",
        required=True,
        ondelete="restrict",
        help="The user whose API key the controller service uses to report this controller and to fetch its clamp requests. "
        "The user must be in the group Controller / Service.",
    )
    active = fields.Boolean(default=True)
    note = fields.Text()
    snapshot = fields.Json(
        readonly=True,
        copy=False,
        help="What the service last reported: state, errors, clock. Written by the service only. The process values and the clamps are in the rows (int.workbench.parameter).",
    )
    snapshot_at = fields.Datetime(string="Last report", readonly=True, copy=False)
    seen_at = fields.Datetime(string="Service last seen", readonly=True, copy=False)
    viewer_at = fields.Datetime(
        string="Last looked at", readonly=True, copy=False, help="The last time the page said that somebody looks at this controller."
    )
    report_age = fields.Float(
        compute="_compute_ages",
        help="Seconds since the last report, by the clock of the server, so that a page does not depend on the clock of its computer.",
    )
    seen_age = fields.Float(compute="_compute_ages", help="Seconds since the service last asked, -1 if it never did.")
    watched = fields.Boolean(compute="_compute_ages", help="Somebody looks at this controller now: the service asks and reports faster.")
    command_ids = fields.One2many("int.workbench.command", "device_id", string="Clamp requests")

    _name_unique = models.Constraint(
        "UNIQUE (name)",
        "A controller with this name exists already.",
    )

    @api.depends("snapshot_at", "seen_at", "viewer_at")
    def _compute_ages(self):
        now = fields.Datetime.now()
        for device in self:
            device.report_age = (now - device.snapshot_at).total_seconds() if device.snapshot_at else -1.0
            device.seen_age = (now - device.seen_at).total_seconds() if device.seen_at else -1.0
            device.watched = bool(device.viewer_at and now - device.viewer_at <= WATCHED_FOR)

    @api.constrains("device_ref")
    def _check_device_ref(self):
        for device in self:
            if not DEVICE_REF_PATTERN.fullmatch(device.device_ref or ""):
                raise ValidationError(
                    self.env._(
                        "The controller id %s may contain only letters, digits, minus and underscore.",
                        device.device_ref,
                    )
                )

    @api.constrains("service_user_id")
    def _check_service_user(self):
        for device in self:
            if not device.service_user_id.has_group(SERVICE_GROUP):
                raise ValidationError(
                    self.env._(
                        "%s is not in the group Controller / Service, so its API key cannot serve a controller.",
                        device.service_user_id.display_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._normalized(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._normalized(vals))

    @api.model
    def _normalized(self, vals):
        vals = dict(vals)
        if isinstance(vals.get("device_ref"), str):
            vals["device_ref"] = vals["device_ref"].strip()
        return vals

    # ---- the page: somebody looks ----

    def watch(self):
        """The page says that somebody looks at these controllers now; it says so every 10 s while it is open.

        While somebody looks, the service asks and reports often (see service_sync); otherwise it keeps quiet. The time is written
        down at most every 5 s, however many people look.
        """
        self.check_access("read")
        now = fields.Datetime.now()
        for device in self.sudo():
            if not device.viewer_at or now - device.viewer_at >= WATCH_REFRESH:
                device.write({"viewer_at": now})
        return True

    # ---- the controller service (JSON-2: POST /json/2/int.workbench.device/service_sync) ----

    @api.model
    def service_sync(self, device_ref, snapshot=None, results=None):
        """The one call of the controller service: report, hand in results, fetch the new clamp requests.

        :param str device_ref: the id of the controller in the service (field "Controller id")
        :param dict|None snapshot: what the service has read from the controller; the service sends it as often as the answer
            says (``report_ms``), and with every result
        :param list|None results: how the requests fetched earlier ended: [{"id": 7, "state": "done" | "failed" | "unconfirmed" |
            "unknown" | "expired", "message": "..."}]
        :return: ``{"commands": [...], "watched": bool, "poll_ms": int, "report_ms": int}``. ``commands`` are the clamp requests to carry
            out: ``{"id", "code", "action": "set" | "release", "value", "user", "expires_in_ms"}``. A request is handed out again if no result
            came back within a few seconds, as long as it is valid (``expires_in_ms``): the service carries out each id once. ``poll_ms``
            says when to ask the next time and ``report_ms`` how often to send a snapshot: often while somebody looks at the controller
            in Odoo (``watched``), rarely otherwise.

        Only a user in the group Controller / Service can call it, and only for the controllers assigned to that user: the key of a
        service is the key of its controllers and nothing else.
        """
        user = self.env.user
        if not user.has_group(SERVICE_GROUP):
            raise AccessError(self.env._("Only a user of the group Controller / Service may call this."))
        device = self.sudo().search([("device_ref", "=", device_ref), ("service_user_id", "=", user.id)])
        if len(device) != 1:
            raise UserError(
                self.env._("No controller with the id %s is assigned to this service user.", device_ref)
            )
        device._service_touch()
        device._service_apply_results(results or [])
        if snapshot is not None:
            device._service_store_snapshot(snapshot)
        device._service_expire_commands()
        return device._service_answer()

    @api.model
    def _service_settings(self):
        params = self.env["ir.config_parameter"].sudo()
        out = {}
        for key, default in DEFAULT_SETTINGS.items():
            try:
                value = int(params.get_param(f"int_workbench.{key}", default))
            except (TypeError, ValueError):
                value = default
            low, high = SETTING_LIMITS[key]
            out[key] = min(high, max(low, value))
        return out

    def _service_touch(self):
        self.ensure_one()
        now = fields.Datetime.now()
        if not self.seen_at or now - self.seen_at >= SEEN_REFRESH:
            self.write({"seen_at": now})

    def _service_store_snapshot(self, snapshot):
        self.ensure_one()
        if not isinstance(snapshot, dict):
            raise ValidationError(self.env._("The snapshot must be an object."))
        if len(json.dumps(snapshot, separators=(",", ":"))) > MAX_SNAPSHOT_BYTES:
            raise ValidationError(self.env._("The snapshot is too large."))
        now = fields.Datetime.now()
        kept = {key: part for key, part in snapshot.items() if key not in ROW_PARTS}
        self.write({"snapshot": kept, "snapshot_at": now, "seen_at": now})
        changed, structure = self.env["int.workbench.parameter"].sudo()._sync(self, snapshot)
        # Telling the pages costs a NOTIFY after the commit (some 15 ms): only while somebody looks, and only if something changed.
        # The message names the rows that changed, so that a page loads these and not the whole list; if rows were created or removed,
        # or very many changed, it says that the list has to be loaded afresh.
        if (changed or structure) and self.watched:
            reload = structure or len(changed) > VALUES_MESSAGE_IDS
            self._bus_send("int_workbench/values", {"ids": [] if reload else changed.ids, "reload": reload})

    def _service_apply_results(self, results):
        self.ensure_one()
        if not isinstance(results, list):
            raise ValidationError(self.env._("The results must be a list."))
        Command = self.env["int.workbench.command"].sudo()
        now = fields.Datetime.now()
        for result in results:
            if not isinstance(result, dict) or not isinstance(result.get("id"), int) or result.get("state") not in RESULT_STATES:
                continue
            # only what was handed out, and only to this controller: nothing is overwritten that was settled already
            command = Command.search([("id", "=", result["id"]), ("device_id", "=", self.id), ("state", "=", "sent")])
            command.write(
                {"state": result["state"], "message": str(result.get("message") or "")[:500], "done_at": now}
            )
            self._service_notify(command)

    def _service_expire_commands(self):
        """A request that is too old is not carried out any more: one that was never handed out has expired, one that was handed out and
        has no result is unknown (it may have been carried out). Both are told to the page."""
        self.ensure_one()
        now = fields.Datetime.now()
        Command = self.env["int.workbench.command"].sudo()
        old = [("device_id", "=", self.id), ("create_date", "<", now - COMMAND_TTL)]
        never = Command.search(old + [("state", "=", "pending")])
        never.write({"state": "expired", "message": self.env._("Nobody carried it out in time."), "done_at": now})
        silent = Command.search(old + [("state", "=", "sent")])
        silent.write(
            {
                "state": "unknown",
                "message": self.env._("Handed to the service, but no result came back: it may or may not have been carried out."),
                "done_at": now,
            }
        )
        self._service_notify(never | silent)

    def _service_take_commands(self):
        self.ensure_one()
        now = fields.Datetime.now()
        commands = self.env["int.workbench.command"].sudo().search(
            [
                ("device_id", "=", self.id),
                "|",
                ("state", "=", "pending"),
                "&",
                ("state", "=", "sent"),
                ("sent_at", "<=", now - REDELIVER_AFTER),
            ],
            order="id",
            limit=COMMAND_BATCH,
        )
        commands.write({"state": "sent", "sent_at": now})
        return [
            {
                "id": command.id,
                "code": command.code,
                "action": command.action,
                "value": command.value,
                "user": command.user_id.login,
                # create_date has microseconds and now has none, so the age can come out a little negative: never more than the whole time
                "expires_in_ms": min(int(COMMAND_TTL.total_seconds() * 1000), max(0, int((COMMAND_TTL - (now - command.create_date)).total_seconds() * 1000))),
            }
            for command in commands
        ]

    def _service_answer(self):
        self.ensure_one()
        commands = self._service_take_commands()
        settings = self._service_settings()
        watched = self.watched
        mode = "fast" if watched else "idle"
        return {
            "commands": commands,
            "watched": watched,
            "poll_ms": settings[f"poll_{mode}_ms"],
            "report_ms": settings[f"report_{mode}_ms"],
        }

    def _service_notify(self, commands):
        """Tell the pages that look at this controller how requests ended (a small message; the page does not poll for it)."""
        self.ensure_one()
        for command in commands:
            self._bus_send("int_workbench/command", {"id": command.id, "state": command.state, "message": command.message or ""})
