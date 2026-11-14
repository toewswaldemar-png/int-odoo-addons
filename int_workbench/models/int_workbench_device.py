import json
import logging
import re
from datetime import timedelta

import psycopg2
import requests

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .service_utils import notification

_logger = logging.getLogger(__name__)

# What the service accepts as the id of a controller: letters, digits, minus and underscore.
DEVICE_REF_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
SERVICE_GROUP = "int_workbench.int_workbench_group_service"
MANAGER_GROUP = "int_workbench.int_workbench_group_manager"
# What a service may report in one call. A snapshot of a controller with all pages is some 100 kB.
MAX_SNAPSHOT_BYTES = 2_000_000
# What of a report is not kept in the Json of the controller: the process values and the clamps are the rows of int.workbench.parameter,
# the active errors the rows of int.workbench.error, the history and the status records of the error memory the rows of
# int.workbench.error.history and int.workbench.error.status (only its state stays in the Json), and the pages are not kept at all.
ROW_PARTS = ("values", "clamps", "pages", "errors", "errors_memory", "can", "intermediate", "fs2_files", "fs2_records")
# The same for the CAN modules and the intermediate values: the rows are in int.workbench.can.module and int.workbench.intermediate.
CAN_STATE_KEYS = ("status", "count", "configured_count", "error", "stale", "time")
INTERMEDIATE_STATE_KEYS = ("status", "read_at", "stale")
# The saved error files are rows of int.workbench.fs2.file and int.workbench.fs2.record; the Json keeps only whether files may be written.
FS2_STATE_KEYS = ("write_enabled",)
# How many files Odoo asks the records of in one answer (they are many; the service sends them with its next report).
FS2_FILES_PER_ANSWER = 3
# What of the error memory stays in the Json of the controller: how it was read, not what it holds.
MEMORY_STATE_KEYS = ("status", "reason", "error", "read_at", "stale", "connected", "clear_enabled", "history_count", "status_total", "active_count")
# A clamp request that was not carried out this long after it was made is not carried out any more. The list waits longer than this
# (parameter_list.js), so it always gets an answer from Odoo, never a request that runs after the list has given up.
COMMAND_TTL = timedelta(seconds=15)
# A request that takes longer on the line than a clamp is valid for longer (the service waits for the controller: a restart takes
# half a minute, a console command may run for a while).
ACTION_TTL = {
    "clock_set": timedelta(seconds=60),
    "can_control": timedelta(seconds=120),
    "reset": timedelta(seconds=180),
    "console": timedelta(seconds=120),
    "console_write": timedelta(seconds=180),
    "fs2_save": timedelta(seconds=120),
    "fs2_delete": timedelta(seconds=60),
}
# What of the output of a request is kept (the service sends at most this much).
OUTPUT_LIMIT = 200_000
# A request that was handed out and has no result yet is handed out again after this long (the answer to the call may have been lost).
# Clamping and releasing can be repeated; the service recognizes the id and does not do it twice.
REDELIVER_AFTER = timedelta(seconds=3)
# How many requests one call of the service takes along.
COMMAND_BATCH = 20
# A message about changed rows names them up to this many; beyond that the list loads everything afresh.
VALUES_MESSAGE_IDS = 30
RESULT_STATES = ("done", "failed", "unconfirmed", "unknown", "expired")
# The call of the service and the look of a person are written down at most this often (a write per call would be the load again).
SEEN_REFRESH = timedelta(seconds=5)
WATCH_REFRESH = timedelta(seconds=5)
# Somebody looks at the controller if the list said so this recently (the list says it every 10 s while it is open).
WATCHED_FOR = timedelta(seconds=30)
# How often the service asks and reports, by whether somebody looks. System parameters "int_workbench.<name>" change them.
DEFAULT_SETTINGS = {"poll_fast_ms": 250, "poll_idle_ms": 2000, "report_fast_ms": 2000, "report_idle_ms": 60000}
SETTING_LIMITS = {
    "poll_fast_ms": (100, 5000),
    "poll_idle_ms": (250, 60000),
    "report_fast_ms": (500, 60000),
    "report_idle_ms": (2000, 3600000),
}
# How long Odoo waits for the service when it calls it (the lists of users, log and projects, the import of project folders).
SERVICE_TIMEOUT = 120


class IntWorkbenchDevice(models.Model):
    _name = "int.workbench.device"
    _inherit = ["bus.listener.mixin"]
    _description = "Controller reached through the service"
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
        help="The user whose API key the service uses to report this controller and to fetch its clamp requests. "
        "The user must be in the group Workbench / Service.",
    )
    active = fields.Boolean(default=True)
    note = fields.Text()
    # === SERVICE ADDRESS === #
    service_url = fields.Char(
        string="Service address",
        help="Where Odoo reaches the service, for example http://workbench:8080. Needed only for what Odoo asks of the service "
        "(users, log, projects); the reports and the clamp requests go the other way and need no address.",
    )
    service_token = fields.Char(
        string="Service token",
        groups="int_workbench.int_workbench_group_manager",
        copy=False,
        help="The token with which Odoo signs in to the service when it asks for users, log and projects.",
    )
    # === REPORT === #
    snapshot = fields.Json(
        readonly=True,
        copy=False,
        help="What the service last reported: state, clock. Written by the service only. The process values, the clamps and the errors are rows of their own.",
    )
    snapshot_at = fields.Datetime(string="Last report", readonly=True, copy=False)
    seen_at = fields.Datetime(string="Service last seen", readonly=True, copy=False)
    viewer_at = fields.Datetime(
        string="Last looked at", readonly=True, copy=False, help="The last time the list of process values said that somebody looks at this controller."
    )
    report_age = fields.Float(
        compute="_compute_ages",
        help="Seconds since the last report, by the clock of the server, so that a page does not depend on the clock of its computer.",
    )
    seen_age = fields.Float(compute="_compute_ages", help="Seconds since the service last asked, -1 if it never did.")
    watched = fields.Boolean(compute="_compute_ages", help="Somebody looks at this controller now: the service asks and reports faster.")
    # === FAMILY AND CAPABILITIES === #
    family_id = fields.Many2one(
        "int.workbench.family",
        string="Family",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
        help="The kind of controller. The service tells it when it signs on.",
    )
    capability_ids = fields.Many2many(
        "int.workbench.capability",
        "int_workbench_device_capability_rel",
        "device_id",
        "capability_id",
        string="Capabilities",
        readonly=True,
        copy=False,
        help="What this controller may be asked to do now. It can be less than its family can do.",
    )
    cap_clamps = fields.Boolean(compute="_compute_capabilities", string="Can clamp")
    cap_clock = fields.Boolean(compute="_compute_capabilities", string="Can set the clock")
    cap_console = fields.Boolean(compute="_compute_capabilities", string="Has a console")
    cap_can_control = fields.Boolean(compute="_compute_capabilities", string="Can control the CAN bus")
    cap_flash = fields.Boolean(compute="_compute_capabilities", string="Can be programmed")
    cap_line_switch = fields.Boolean(compute="_compute_capabilities", string="Can switch the line")
    cap_error_memory = fields.Boolean(compute="_compute_capabilities", string="Can clear the error memory")
    cap_error_files = fields.Boolean(compute="_compute_capabilities", string="Can evaluate error files")
    cap_intermediate = fields.Boolean(compute="_compute_capabilities", string="Has intermediate values")
    cap_project_files = fields.Boolean(compute="_compute_capabilities", string="Uses project files")
    # === RECORDS OF THE CONTROLLER === #
    command_ids = fields.One2many("int.workbench.command", "device_id", string="Clamp requests")
    error_ids = fields.One2many("int.workbench.error", "device_id", string="Errors")
    error_history_ids = fields.One2many("int.workbench.error.history", "device_id", string="Error history")
    error_status_ids = fields.One2many("int.workbench.error.status", "device_id", string="Error status")
    can_module_ids = fields.One2many("int.workbench.can.module", "device_id", string="CAN modules")
    intermediate_ids = fields.One2many("int.workbench.intermediate", "device_id", string="Intermediate values")
    fs2_file_ids = fields.One2many("int.workbench.fs2.file", "device_id", string="Error files")
    clock_local_time = fields.Char(compute="_compute_clock", string="Clock of the controller", help="Date and time the controller shows, as the service read them (no time zone).")
    clock_read_at = fields.Char(compute="_compute_clock", string="Clock read at")
    clock_write_enabled = fields.Boolean(compute="_compute_clock", string="The clock may be set")
    can_count = fields.Char(compute="_compute_can_count", string="CAN modules (actual of configured)")

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

    @api.depends("snapshot")
    def _compute_clock(self):
        for device in self:
            clock = (device.snapshot or {}).get("clock")
            clock = clock if isinstance(clock, dict) else {}
            device.clock_local_time = str(clock.get("local_time") or "")
            device.clock_read_at = str(clock.get("read_at") or "") if clock.get("local_time") else ""
            device.clock_write_enabled = clock.get("write_enabled") is True

    @api.depends("snapshot")
    def _compute_can_count(self):
        for device in self:
            part = (device.snapshot or {}).get("can")
            part = part if isinstance(part, dict) else {}
            actual, configured = part.get("count"), part.get("configured_count")
            device.can_count = f"{actual if actual is not None else '?'} / {configured if configured is not None else '?'}" if part else ""

    @api.depends("family_id", "capability_ids.code")
    def _compute_capabilities(self):
        """Set one flag per capability, for the views to show or hide what a controller cannot do.

        A controller whose service has not signed on yet (an older service) has no family: it keeps the one thing the module
        did before families existed, clamping.
        """
        for device in self:
            codes = set(device.capability_ids.mapped("code"))
            for code in self.env["int.workbench.capability"].CODES:
                device[f"cap_{code}"] = code in codes
            if not device.family_id:
                device.cap_clamps = True

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
                        "%s is not in the group Workbench / Service, so its API key cannot serve a controller.",
                        device.service_user_id.display_name,
                    )
                )

    @api.constrains("service_url")
    def _check_service_url(self):
        for device in self:
            if device.service_url and not re.match(r"https?://[^\s/]+", device.service_url):
                raise ValidationError(self.env._("The service address %s must start with http:// or https://.", device.service_url))

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
        if isinstance(vals.get("service_url"), str):
            vals["service_url"] = vals["service_url"].strip().rstrip("/")
        return vals

    # === THE LIST: SOMEBODY LOOKS === #

    def watch(self):
        """Tell that somebody looks at these controllers now; the list of process values says so every 10 s while it is open.

        While somebody looks, the service asks and reports often (see service_sync); otherwise it keeps quiet. The time is written
        down at most every 5 s, however many people look.
        """
        self.check_access("read")
        now = fields.Datetime.now()
        # sudo: int.workbench.device: a reader writes only the time of the look, not a record they may change
        for device in self.sudo():
            if not device.viewer_at or now - device.viewer_at >= WATCH_REFRESH:
                device.write({"viewer_at": now})
        return True

    # === THE SERVICE (JSON-2: POST /json/2/int.workbench.device/service_sync) === #

    @api.model
    def _service_device(self, device_ref):
        """Return the controller that the service user of this call may serve, or raise.

        Only a user in the group Workbench / Service can call the service methods, and only for the controllers assigned to that
        user: the key of a service is the key of its controllers and nothing else.
        """
        user = self.env.user
        if not user.has_group(SERVICE_GROUP):
            raise AccessError(self.env._("Only a user of the group Workbench / Service may call this."))
        # sudo: int.workbench.device: the service user has no right on the model, only on the calls of the service
        device = self.sudo().search([("device_ref", "=", device_ref), ("service_user_id", "=", user.id)])
        if len(device) != 1:
            raise UserError(self.env._("No controller with the id %s is assigned to this service user.", device_ref))
        return device

    @api.model
    def service_sync(self, device_ref, snapshot=None, results=None):
        """Take the one call of the service: the report, the results, and hand out the new clamp requests.

        :param str device_ref: the id of the controller in the service (field "Controller id")
        :param dict|None snapshot: what the service has read from the controller; the service sends it as often as the answer
            says (``report_ms``), and with every result
        :param list|None results: how the requests fetched earlier ended: [{"id": 7, "state": "done" | "failed" | "unconfirmed" |
            "unknown" | "expired", "message": "..."}]
        :return: ``{"commands": [...], "watched": bool, "poll_ms": int, "report_ms": int}``. ``commands`` are the clamp requests to carry
            out: ``{"id", "code", "action": "set" | "release" | "clear_errors", "value", "user", "expires_in_ms"}`` (``clear_errors`` is about the
            controller, its ``code`` is "errors" and its ``value`` 0). A request is handed out again if no result
            came back within a few seconds, as long as it is valid (``expires_in_ms``): the service carries out each id once. ``poll_ms``
            says when to ask the next time and ``report_ms`` how often to send a snapshot: often while somebody looks at the controller
            in Odoo (``watched``), rarely otherwise.
        """
        device = self._service_device(device_ref)
        device._service_touch()
        device._service_apply_results(results or [])
        if snapshot is not None:
            device._service_store_snapshot(snapshot)
        device._service_expire_commands()
        return device._service_answer()

    @api.model
    def _service_settings(self):
        # sudo: ir.config_parameter: the settings of the module are read for the service user, who has no right on parameters
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
        memory = snapshot.get("errors_memory")
        previous_read_at = ((self.snapshot or {}).get("errors_memory") or {}).get("read_at")
        if isinstance(memory, dict):
            kept["errors_memory"] = {key: memory[key] for key in MEMORY_STATE_KEYS if key in memory}
        for part, keys in (("can", CAN_STATE_KEYS), ("intermediate", INTERMEDIATE_STATE_KEYS), ("fs2_files", FS2_STATE_KEYS)):
            if isinstance(snapshot.get(part), dict):
                kept[part] = {key: snapshot[part][key] for key in keys if key in snapshot[part]}
        previous = self.snapshot or {}
        self.write({"snapshot": kept, "snapshot_at": now, "seen_at": now})
        # sudo: int.workbench.parameter: the rows are written by the report of the service, which has no right on them
        changed, structure = self.env["int.workbench.parameter"].sudo()._sync(self, snapshot)
        # sudo: int.workbench.error: the rows are written by the report of the service, which has no right on them
        errors_changed = self.env["int.workbench.error"].sudo()._sync(self, snapshot)
        # The CAN modules and the intermediate values are read by the service at its own pace: new rows only for a new reading
        can, intermediate = snapshot.get("can"), snapshot.get("intermediate")
        if isinstance(can, dict) and (can.get("time") != (previous.get("can") or {}).get("time") or not self.can_module_ids):
            # sudo: int.workbench.can.module: the rows are written by the report of the service
            self._sync_mirror("int.workbench.can.module", snapshot)
        if isinstance(intermediate, dict) and (intermediate.get("read_at") != (previous.get("intermediate") or {}).get("read_at") or not self.intermediate_ids):
            # sudo: int.workbench.intermediate: the rows are written by the report of the service
            self._sync_mirror("int.workbench.intermediate", snapshot)
        # The list of the error files comes with every report, the records of the files that changed only when Odoo asked for them
        if isinstance(snapshot.get("fs2_files"), dict):
            self._sync_mirror("int.workbench.fs2.file", snapshot)
        if isinstance(snapshot.get("fs2_records"), dict):
            self._sync_mirror("int.workbench.fs2.record", snapshot)
        # The service reads the error memory now and then; the rows are brought up to date only for a new reading (or if there are none)
        if isinstance(memory, dict) and (memory.get("read_at") != previous_read_at or not self.error_status_ids):
            # sudo: int.workbench.error.history, int.workbench.error.status: the rows are written by the report of the service
            self._sync_mirror("int.workbench.error.history", snapshot)
            self._sync_mirror("int.workbench.error.status", snapshot)
        # Telling the pages costs a NOTIFY after the commit (some 15 ms): only while somebody looks, and only if something changed.
        # The message names the rows that changed, so that a list loads these and not everything; if rows were created or removed,
        # or very many changed, it says that the list has to be loaded afresh.
        if (changed or structure) and self.watched:
            reload = structure or len(changed) > VALUES_MESSAGE_IDS
            self._bus_send("int_workbench/values", {"ids": [] if reload else changed.ids, "reload": reload})
        # the list of errors loads itself afresh (it is small and has no rows to keep in place)
        if errors_changed and self.watched:
            self._bus_send("int_workbench/errors", {})

    def _sync_mirror(self, model_name, snapshot):
        """Bring the rows of one optional part of the report (CAN modules, error memory, ...) up to date. A part that cannot be stored
        is logged and left out: the rest of the report, and the requests that go with the call, must not be lost for it."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                return self.env[model_name].sudo()._sync(self, snapshot)  # sudo: the rows are written by the report of the service
        except (ValueError, TypeError, psycopg2.Error):
            _logger.exception("The part of the report for %s of controller %s could not be stored.", model_name, self.name)
            return False

    def _service_apply_results(self, results):
        self.ensure_one()
        if not isinstance(results, list):
            raise ValidationError(self.env._("The results must be a list."))
        # sudo: int.workbench.command: the service settles the requests of its own controller, as a user it has no right on them
        Command = self.env["int.workbench.command"].sudo()
        now = fields.Datetime.now()
        for result in results:
            if not isinstance(result, dict) or not isinstance(result.get("id"), int) or result.get("state") not in RESULT_STATES:
                continue
            # only what was handed out, and only to this controller: nothing is overwritten that was settled already
            command = Command.search([("id", "=", result["id"]), ("device_id", "=", self.id), ("state", "=", "sent")])
            command.write(
                {
                    "state": result["state"],
                    "message": str(result.get("message") or "")[:500],
                    "output": str(result.get("output") or "")[:OUTPUT_LIMIT] or False,
                    "done_at": now,
                }
            )
            self._service_notify(command)

    def _service_expire_commands(self):
        """Settle the requests that are too old: they are not carried out any more.

        One that was never handed out has expired, one that was handed out and has no result is unknown (it may have been carried
        out). Both are told to the list.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        # sudo: int.workbench.command: see _service_apply_results
        Command = self.env["int.workbench.command"].sudo()
        old = [("device_id", "=", self.id), ("create_date", "<", now - COMMAND_TTL)]
        # the requests that take longer on the line are valid for longer: only those past their own time are settled

        def late(command):
            return now - command.create_date > ACTION_TTL.get(command.action, COMMAND_TTL)

        never = Command.search(old + [("state", "=", "pending")]).filtered(late)
        never.write({"state": "expired", "message": self.env._("Nobody carried it out in time."), "done_at": now})
        silent = Command.search(old + [("state", "=", "sent")]).filtered(late)
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
        # sudo: int.workbench.command: see _service_apply_results
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
                "payload": command._payload_dict(),
                "user": command.user_id.login,
                # create_date has microseconds and now has none, so the age can come out a little negative: never more than the whole time
                "expires_in_ms": self._command_expires_in_ms(command, now),
            }
            for command in commands
        ]

    @staticmethod
    def _command_expires_in_ms(command, now):
        """Return how long a request is still valid for the service when it is handed out."""
        ttl = ACTION_TTL.get(command.action, COMMAND_TTL)
        return min(int(ttl.total_seconds() * 1000), max(0, int((ttl - (now - command.create_date)).total_seconds() * 1000)))

    def _service_want(self):
        """Return what Odoo asks the service to put into its next report: the records of the error files whose records it has not
        fetched yet, or fetched when the file was different (a few files at a time)."""
        self.ensure_one()
        # sudo: int.workbench.fs2.file: the answer to the service is made for the controller, whoever the service is
        stale = self.env["int.workbench.fs2.file"].sudo().search([("device_id", "=", self.id)]).filtered(lambda file: file.loaded_signature != file._signature())
        return {"fs2_records": stale.mapped("name")[:FS2_FILES_PER_ANSWER]} if stale else {}

    def action_save_error_files(self):
        """Open the dialog that saves the error memory of the controller as error files."""
        return self._open_wizard("int.workbench.fs2.wizard", self.env._("Save the error memory"))

    def _service_answer(self):
        self.ensure_one()
        commands = self._service_take_commands()
        settings = self._service_settings()
        watched = self.watched
        mode = "fast" if watched else "idle"
        return {
            "commands": commands,
            "want": self._service_want(),
            "watched": watched,
            "poll_ms": settings[f"poll_{mode}_ms"],
            "report_ms": settings[f"report_{mode}_ms"],
        }

    def _service_notify(self, commands):
        """Tell the lists that look at this controller how requests ended (a small message; the list does not poll for it)."""
        self.ensure_one()
        for command in commands:
            self._bus_send(
                "int_workbench/command", {"id": command.id, "action": command.action, "state": command.state, "message": command.message or ""}
            )

    # === ODOO ASKS THE SERVICE === #

    def _service_request(self, method, path, payload=None, params=None):
        """Call a route of the service and return its answer as parsed JSON.

        The service signs Odoo in by the token of the controller. A failure of any kind becomes a UserError with the reason the
        service gave, so that it shows in the dialog of the button that asked.
        """
        self.ensure_one()
        if not self.service_url:
            raise UserError(self.env._("The controller %s has no service address.", self.name))
        # sudo: int.workbench.device: the token is read for the call only; it is shown to managers only
        token = self.sudo().service_token
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            response = requests.request(
                method, self.service_url + path, json=payload, params=params, headers=headers, timeout=SERVICE_TIMEOUT
            )
        except requests.RequestException as error:
            raise UserError(self.env._("The service of %s does not answer: %s", self.name, error)) from error
        if response.status_code >= 400:
            try:
                reason = response.json().get("error") or response.text
            except ValueError:
                reason = response.text
            raise UserError(self.env._("The service of %s refused (%s): %s", self.name, response.status_code, reason[:300]))
        try:
            return response.json()
        except ValueError as error:
            raise UserError(self.env._("The service of %s sent no JSON.", self.name)) from error

    def action_reset(self):
        """Ask the service to restart the controller. The result shows in the log of the requests."""
        self.ensure_one()
        self.env["int.workbench.command"].create({"device_id": self.id, "action": "reset"})
        return notification(self.env._("Requested"), self.env._("The controller %s is being restarted.", self.name))

    def _open_wizard(self, model, name):
        """Return the action that opens the dialog of a button for this controller."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "form",
            "target": "new",
            "context": {"default_device_id": self.id},
        }

    def action_set_clock(self):
        """Open the dialog that sets the clock of the controller."""
        return self._open_wizard("int.workbench.clock.wizard", self.env._("Set the clock"))

    def action_control_can(self):
        """Open the dialog that stops, starts or baptizes the CAN bus of the controller."""
        return self._open_wizard("int.workbench.can.wizard", self.env._("CAN bus"))

    def action_open_console(self):
        """Open the dialog that sends a console command to the controller."""
        return self._open_wizard("int.workbench.console.wizard", self.env._("Console"))

    def action_fetch_users(self):
        """Fetch the accounts of the service into the list of users."""
        self.check_access("write")
        self.env["int.workbench.user"]._fetch(self)
        return self._open_list("int.workbench.user", self.env._("Users"))

    def action_fetch_log(self):
        """Fetch the newest entries of the write log of the service."""
        self.check_access("write")
        self.env["int.workbench.log"]._fetch(self)
        return self._open_list("int.workbench.log", self.env._("Log"))

    def action_fetch_projects(self):
        """Fetch the versions of the project library of the service."""
        self.check_access("write")
        self.env["int.workbench.project"]._fetch(self)
        return self._open_list("int.workbench.project", self.env._("Projects"))

    def action_import_projects(self):
        """Open the dialog that brings the new project folders of the service into its library."""
        self.ensure_one()
        wizard = self.env["int.workbench.project.import"].create({"device_id": self.id})
        return wizard._reopen()

    def _open_list(self, model, name):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "context": {"default_device_id": self.id},
        }
