from collections.abc import Collection
from math import floor

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain

from .int_workbench_device import COMMAND_TTL

# What of a reported row is kept, and how it is compared. ``time`` (when the service read the row) is left out on purpose: it changes
# with every read, so a row would count as changed in every report.
SYNCED_FIELDS = ("source_name", "status", "text", "value", "unit", "stale", "can_clamp", "analog", "clamped", "clamp_value", "last_clamp_value", "was_clamped", "clamp_step", "auto_text")
VALUE_DIGITS = 3
# How a digital row (0 or 1) is shown: what 1 and what 0 mean differs from row to row ("Heating chain OK": 1 is OK; "Fault CAN": 1 is a fault).
DISPLAY_WORDS = ("ok", "on", "open", "fault")
# New rows are put in the order of the report, a controller after the other (the list is ordered by "sequence"; a user changes it by
# dragging, see write): room for this many rows per controller.
SEQUENCE_PER_DEVICE = 1000
OPERATOR_GROUP = "int_workbench.int_workbench_group_operator"
# Who may arrange the rows. It is the same order for everybody, so it is not left to every reader of the list.
ARRANGE_GROUPS = (OPERATOR_GROUP, "int_workbench.int_workbench_group_manager")


def _number(value):
    try:
        return round(float(value), VALUE_DIGITS)
    except (TypeError, ValueError):
        return 0.0


def _to_step(value, step):
    """The value as a multiple of the step the controller takes for the row (21.7 in steps of 1 is 22). A row without a step takes it as it is."""
    if not step:
        return value
    return _number(floor(value / step + 0.5) * step)


class IntWorkbenchParameter(models.Model):
    _name = "int.workbench.parameter"
    _description = "Process value of a controller"
    _order = "sequence, device_id, code"

    device_id = fields.Many2one("int.workbench.device", string="Device", required=True, index=True, ondelete="cascade", readonly=True)
    code = fields.Char(string="Row code", required=True, readonly=True)
    source_name = fields.Char(string="Description of the project", readonly=True, help="The description of the row in the project, as the service reports it.")
    label = fields.Char(string="Own name", help="What you call the row instead of the description of the project. The report of the service keeps it.")
    name = fields.Char(
        string="Description",
        compute="_compute_name",
        store=True,
        index="trigram",
        help="What the row is called: the name you gave it, or else the description of the project.",
    )
    active = fields.Boolean(default=True, help="An archived row is not shown. The report of the service keeps it archived.")
    status = fields.Char(help="How the read went: ok, or what is wrong with the row.", readonly=True)
    text = fields.Char(
        string="Process text", help="The value the controller works with, as it shows it, for example 22.3°C. A clamped row shows the clamp.", readonly=True
    )
    # How a digital row is shown, set by hand (an operator) and the same for everybody; a report never touches it.
    display_kind = fields.Selection(
        [("number", "Number"), ("ok", "OK / not OK"), ("on", "On / Off"), ("open", "Open / Closed"), ("fault", "Fault / OK")],
        string="Display",
        default="number",
        required=True,
        help="How a row with 0 and 1 is shown: as the number, or in words that say what 0 and 1 mean for this row. Not for analog rows.",
    )
    # What the list shows as the process value, and how it is coloured (green: good, red: bad).
    text_shown = fields.Char(string="Process value", compute="_compute_text_shown", help="The value the controller works with, as the row is set to show it.")
    display_tone = fields.Selection([("good", "Good"), ("bad", "Bad")], compute="_compute_text_shown")
    value = fields.Float(string="Number", digits=(16, VALUE_DIGITS), help="The process value as a number; 0 where the row has none.", readonly=True)
    # Only some families have a value of their own for a clamped row (Micserv: what the control logic gives without the clamp).
    auto_text = fields.Char(
        string="Automatic value", help="What the controller's own logic gives for the row, without a clamp. Only some families report it.", readonly=True
    )
    unit = fields.Char(readonly=True)
    stale = fields.Boolean(help="The last read of the row did not succeed in time.", readonly=True)
    can_clamp = fields.Boolean(string="Can be clamped", readonly=True)
    analog = fields.Boolean(readonly=True)
    clamped = fields.Boolean(readonly=True, index=True)
    clamp_value = fields.Float(digits=(16, VALUE_DIGITS), help="The value the row is clamped to.", readonly=True)
    # What the switch of the list clamps a row to the next time. The report fills it whenever the row is clamped; it stays when the clamp
    # is released. A row that was never clamped has none, and the switch takes the value the row has.
    last_clamp_value = fields.Float(digits=(16, VALUE_DIGITS), help="The value the row was clamped to last.", readonly=True)
    clamp_step = fields.Float(
        digits=(16, VALUE_DIGITS), help="The steps the controller takes a clamp value in (1: whole degrees); 0 where the row has none.", readonly=True
    )
    was_clamped = fields.Boolean(help="The row has been clamped at least once (then the last clamp value says to what).", readonly=True)
    # The rows are tagged by hand (heating, cooling, ...), the same for everybody, as the order is. A report never touches them.
    tag_ids = fields.Many2many("int.workbench.parameter.tag", string="Tags")
    command_ids = fields.One2many("int.workbench.command", "parameter_id", string="Clamp requests")
    device_cap_clamps = fields.Boolean(related="device_id.cap_clamps", string="Controller can clamp")
    sequence = fields.Integer(help="The order of the rows in the list; changed by dragging (Operator, Manager).", index=True)
    # A star of the user, as Project has it for projects: who marked the row is kept in a table, is_favorite is what the current user did.
    favorite_user_ids = fields.Many2many(
        "res.users", "int_workbench_parameter_favorite_rel", "parameter_id", "user_id", string="Favorite of", copy=False, readonly=True
    )
    is_favorite = fields.Boolean(
        compute="_compute_is_favorite", readonly=False, search="_search_is_favorite", compute_sudo=True, string="Favorite"
    )
    # What the operator does in the list. Both are not stored: they show what the row is clamped to, or what was asked for and is on its
    # way to the controller, and writing them makes a clamp request (see write), as writing the star makes a mark.
    clamp_toggle = fields.Boolean(
        compute="_compute_clamp_request",
        readonly=False,
        string="Clamping",
        help="Clamped, or asked to be. Switching it on clamps the row to the value it was clamped to last (to the value it has, if it "
        "never was), switching it off releases it.",
    )
    clamp_input = fields.Float(
        compute="_compute_clamp_request",
        readonly=False,
        digits=(16, VALUE_DIGITS),
        string="Clamp value",
        help="The value the row is clamped to; while it is not, the value it was clamped to last (the value it has, if it never was). "
        "Writing it clamps the row to the value.",
    )

    # A combination is a row that the service does not report: it is made in Odoo (Combinations) and sets several rows
    # of the device at once. The levels and the rows they clamp are those of the template; the rows are looked up on the device by their code,
    # so nothing of the template is copied to the device. The report leaves the row alone (see _sync).
    is_combo = fields.Boolean(string="Combination", index=True, readonly=True, help="The row sets several rows of the device at once; it is not reported by the service.")
    template_id = fields.Many2one(
        "int.workbench.combo.template",
        string="Combination",
        index=True,
        readonly=True,
        ondelete="cascade",
        help="The combination that this row is. Its levels are changed there.",
    )
    combo_level_id = fields.Many2one(
        "int.workbench.combo.template.level",
        compute="_compute_combo_level",
        readonly=False,
        string="Level",
        help="The level of the combination that the device is clamped to now. Choosing one clamps the rows of that level and releases the "
        "rows of the other levels (or every clamp of the device, if the combination says so).",
    )

    _device_code_unique = models.Constraint("UNIQUE (device_id, code)", "A row exists once per controller.")

    @api.depends_context("uid")
    @api.depends("favorite_user_ids")
    def _compute_is_favorite(self):
        for row in self:
            row.is_favorite = self.env.uid in row.favorite_user_ids.ids

    @api.model
    def _search_is_favorite(self, operator, value):
        if operator not in ("in", "not in"):
            return NotImplemented
        values = set(value) if isinstance(value, Collection) and not isinstance(value, str) else {value}
        wanted = values if operator == "in" else {True, False} - values
        if wanted == {True}:
            return [("favorite_user_ids", "in", [self.env.uid])]
        if wanted == {False}:
            return [("favorite_user_ids", "not in", [self.env.uid])]
        return Domain.TRUE if wanted else Domain.FALSE

    def _set_favorite(self, is_favorite):
        """Mark or unmark the rows for the current user: whoever reads the rows may mark them, as in Project."""
        command = Command.link if is_favorite else Command.unlink
        # sudo: int.workbench.parameter: the star is the user's own, a reader has no right to write the row
        self.sudo().favorite_user_ids = [command(self.env.uid)]

    # Not depending on display_kind on purpose: a field that others depend on makes the list ask the server (onchange) when it is
    # edited, and that asks for the right to write the model, which an operator has only through write() below. write() clears
    # what was computed instead.
    @api.depends("text", "value", "analog", "is_combo", "template_id.level_ids.name", "template_id.level_ids.step_ids.value", "template_id.level_ids.step_ids.code")
    def _compute_text_shown(self):
        for row in self:
            if row.is_combo:
                row.text_shown, row.display_tone = row._active_combo_level().name or "-", False
            elif row.display_kind not in DISPLAY_WORDS or row.analog:
                row.text_shown, row.display_tone = row.text, False
            else:
                row.text_shown, row.display_tone = self._digital_words(row.display_kind, bool(row.value))

    def _digital_words(self, kind, on):
        """The words for 0 or 1 of a row and the tone of them: (text, "good" | "bad" | False)."""
        _ = self.env._
        if kind == "ok":
            return (_("OK"), "good") if on else (_("not OK"), "bad")
        if kind == "fault":
            return (_("Fault"), "bad") if on else (_("OK"), "good")
        if kind == "open":
            return (_("Open"), False) if on else (_("Closed"), False)
        return (_("On"), False) if on else (_("Off"), False)

    @api.depends("clamped", "clamp_value", "value", "last_clamp_value", "was_clamped", "clamp_step", "command_ids.state", "command_ids.action", "command_ids.value",
                 "is_combo", "template_id.level_ids.name", "template_id.level_ids.step_ids.value", "template_id.level_ids.step_ids.code")
    def _compute_clamp_request(self):
        on_their_way = self._clamp_requests_on_their_way()
        for row in self:
            if row.is_combo:
                # the switch of a combination is on while one of its levels is clamped; it has no value of its own
                row.clamp_toggle, row.clamp_input = bool(row._active_combo_level().step_ids), 0.0
                continue
            request = on_their_way.get(row.id)
            # what the switch would clamp the row to: the value it was clamped to last, or the value it has if it never was (in the
            # steps the controller takes: it refuses 21.7 degrees)
            next_value = row.last_clamp_value if row.was_clamped else _to_step(row.value, row.clamp_step)
            if request is None:
                row.clamp_toggle, row.clamp_input = row.clamped, (row.clamp_value if row.clamped else next_value)
            elif request.action == "set":
                row.clamp_toggle, row.clamp_input = True, request.value
            else:
                row.clamp_toggle, row.clamp_input = False, next_value

    def _clamp_requests_on_their_way(self):
        """The requests for these rows that the service has not answered yet, and that are still good: {row id: request}, the last one of
        a row counts. The list shows them at once, so that the switch does not jump back until the service has reported."""
        ids = [row_id for row_id in self.ids if isinstance(row_id, int)]
        if not ids:
            return {}
        # sudo: int.workbench.command: whoever reads the row sees that a request for it is on its way, whoever made it
        requests = self.env["int.workbench.command"].sudo().search_fetch(
            [("parameter_id", "in", ids), ("state", "in", ("pending", "sent")), ("create_date", ">=", fields.Datetime.now() - COMMAND_TTL)],
            ["parameter_id", "action", "value"],
            order="id",
        )
        return {request.parameter_id.id: request for request in requests}

    def _ask_for_clamps(self, switch, value):
        """What the operator did in the list: a value clamps the rows to it, the switch clamps them to the value they have (on) or
        releases them (off). Each row gets a request; the service carries it out and reports, and only then the row is clamped."""
        if not self.env.user.has_group(OPERATOR_GROUP):
            raise AccessError(self.env._("Only an operator may clamp rows."))
        requests = []
        combos = self.filtered("is_combo")
        for combo in combos:
            # the switch of a combination: on clamps its first level, off releases the rows of all its levels (it has no value of its own)
            if switch is True and not combo._active_combo_level().step_ids:
                requests += combo._combo_requests(combo.template_id.level_ids.sorted("sequence").filtered("step_ids")[:1])
            elif switch is False and combo._active_combo_level().step_ids:
                requests += combo._combo_requests(self.env["int.workbench.combo.template.level"])
        for row in self - combos:
            if value is not None:
                action, wanted = "set", value
            elif switch and not row.clamp_toggle:
                action, wanted = "set", row.clamp_input  # what the list shows next to the switch
            elif switch is False and row.clamp_toggle:
                action, wanted = "release", 0.0
            else:
                continue
            if action == "set" and not row.can_clamp:
                raise UserError(self.env._("The row %s cannot be clamped.", row.display_name))
            requests.append({"device_id": row.device_id.id, "code": row.code, "action": action, "value": wanted})
        if requests:
            self.env["int.workbench.command"].create(requests)

    # ---- combinations: one row that sets several rows of the device at once ----

    def _combo_rows(self):
        """{code: row} of the rows of this device that the levels of the combination clamp. A row that the device does not have is left out."""
        self.ensure_one()
        codes = self.template_id.level_ids.step_ids.mapped("code")
        if not codes:
            return {}
        rows = self.env["int.workbench.parameter"].search([("device_id", "=", self.device_id.id), ("is_combo", "=", False), ("code", "in", codes)])
        return {row.code: row for row in rows}

    def _effective_states(self, rows):
        """{row: (clamped, value)} for these rows as the device stands: a request that the service has not answered yet counts as done, as
        it does for the switch of a row (the list does not jump back until the service has reported)."""
        on_their_way = rows._clamp_requests_on_their_way()
        states = {}
        for row in rows:
            request = on_their_way.get(row.id)
            if request is None:
                states[row] = (row.clamped, row.clamp_value)
            else:
                states[row] = (True, request.value) if request.action == "set" else (False, 0.0)
        return states

    def _active_combo_level(self):
        """The level of this combination that the device is clamped to: all rows of the level (that the device has) are clamped to its values,
        and none of the other rows of the combination is clamped. A level without rows is "off": it is the state while none is clamped."""
        self.ensure_one()
        by_code = self._combo_rows()
        states = self._effective_states(self.env["int.workbench.parameter"].concat(*by_code.values()))
        levels = self.template_id.level_ids.sorted("sequence")
        for level in levels.filtered("step_ids"):
            wanted = {by_code[step.code]: step.value for step in level.step_ids if step.code in by_code}
            if wanted and all(states[row][0] and _number(states[row][1]) == _number(value) for row, value in wanted.items()) and not any(
                states[row][0] for row in states if row not in wanted
            ):
                return level
        if not any(clamped for clamped, _value in states.values()):
            return levels.filtered(lambda level: not level.step_ids)[:1]
        return self.env["int.workbench.combo.template.level"]

    @api.depends("is_combo", "template_id.level_ids.name", "template_id.level_ids.step_ids.value", "template_id.level_ids.step_ids.code")
    def _compute_combo_level(self):
        for row in self:
            row.combo_level_id = row._active_combo_level() if row.is_combo else False

    def _combo_requests(self, level):
        """The requests that bring the device to this level: the clamped rows that the level does not set are released, then its rows are
        clamped to its values. Released are the rows that other levels of the combination have, or (setting of the combination) every clamped
        row of the device. No level: the rows of all levels are released."""
        self.ensure_one()
        by_code = self._combo_rows()
        Parameter = self.env["int.workbench.parameter"]
        wanted = [(by_code[step.code], step.value) for step in level.step_ids.sorted("sequence") if step.code in by_code]
        level_rows = Parameter.concat(*[row for row, _value in wanted])
        if self.template_id.release_all and wanted:
            candidates = Parameter.search([("device_id", "=", self.device_id.id), ("is_combo", "=", False)])
        else:
            candidates = Parameter.concat(*by_code.values())
        states = self._effective_states(candidates)
        requests = [
            {"device_id": row.device_id.id, "code": row.code, "action": "release", "value": 0.0}
            for row in candidates
            if states[row][0] and row not in level_rows
        ]
        requests += [{"device_id": row.device_id.id, "code": row.code, "action": "set", "value": value} for row, value in wanted]
        return requests

    def _ask_for_combo_level(self, level_id):
        """What the operator did in the cell of the level: the device is brought to that level (or released, if the cell was emptied)."""
        if not self.env.user.has_group(OPERATOR_GROUP):
            raise AccessError(self.env._("Only an operator may clamp rows."))
        level = self.env["int.workbench.combo.template.level"].browse(level_id or [])
        requests = []
        for combo in self:
            if not combo.is_combo:
                raise UserError(self.env._("The row %s is not a combination.", combo.display_name))
            if level and level.template_id != combo.template_id:
                raise UserError(self.env._("This level belongs to another combination."))
            requests += combo._combo_requests(level)
        if requests:
            self.env["int.workbench.command"].create(requests)

    def write(self, vals):
        if "combo_level_id" in vals:
            vals = dict(vals)
            self._ask_for_combo_level(vals.pop("combo_level_id"))
            if not vals:
                return True
        if "is_favorite" in vals or "clamp_toggle" in vals or "clamp_input" in vals:
            vals = dict(vals)
            if "is_favorite" in vals:
                self._set_favorite(vals.pop("is_favorite"))
            if "clamp_toggle" in vals or "clamp_input" in vals:
                self._ask_for_clamps(vals.pop("clamp_toggle", None), vals.pop("clamp_input", None))
            if not vals:
                return True
        # dragging rows in the list writes the sequence and nothing else: that is allowed for those who arrange the rows, not more
        if set(vals) == {"sequence"} and any(self.env.user.has_group(group) for group in ARRANGE_GROUPS):
            # sudo: int.workbench.parameter: the order is the same for everybody, so it is written for them
            return super(IntWorkbenchParameter, self.sudo()).write(vals)
        # tagging rows and setting how they are shown write those and nothing else: that is for operators
        if vals and set(vals) <= {"tag_ids", "display_kind", "label", "active"} and self.env.user.has_group(OPERATOR_GROUP):
            # sudo: int.workbench.parameter: both are the same for everybody, so they are written for them
            result = super(IntWorkbenchParameter, self.sudo()).write(vals)
            self.invalidate_recordset(["text_shown", "display_tone"])
            return result
        return super().write(vals)

    @api.constrains("active")
    def _check_archived_not_clamped(self):
        for row in self:
            if not row.active and row.clamped:
                raise ValidationError(self.env._("Release the clamp of %s first: a clamped row cannot be archived.", row.display_name))

    @api.depends("label", "source_name")
    def _compute_name(self):
        for row in self:
            row.name = row.label or row.source_name or ""

    @api.depends("code", "name")
    def _compute_display_name(self):
        for row in self:
            row.display_name = f"{row.code} {row.name}" if row.name else row.code or ""

    # ---- the report of the service: rows are brought to what was reported, and only what changed is written ----

    def _sync(self, device, snapshot):
        """Bring the rows of one controller to what the report says. Returns ``(changed, structure)``: the rows that were created or
        changed, and whether rows were created or removed (the list is then loaded afresh, not row by row).

        The ORM writes a row even if nothing changed in it (and sets write_date), so the comparison is made here. Of some 120 rows a
        few change between two reports, and only those are written. The order of the rows (sequence) and the stars belong to the users:
        a report never touches them.
        """
        wanted = self._rows_from_report(snapshot)
        # the combinations are not in the report: they are left alone, they are neither compared nor removed
        known = {
            row.code: row
            for row in self.with_context(active_test=False).search_fetch([("device_id", "=", device.id), ("is_combo", "=", False)], ["code", *SYNCED_FIELDS])
        }
        changed = self.browse()
        create = []
        for position, (code, vals) in enumerate(wanted.items()):
            row = known.get(code)
            if row is None:
                create.append({"device_id": device.id, "code": code, "sequence": device.id * SEQUENCE_PER_DEVICE + position, **vals})
                continue
            diff = {name: value for name, value in vals.items() if self._differs(name, row[name], value)}
            if diff:
                row.write(diff)
                changed |= row
        if create:
            changed |= self.create(create)
        gone = self.browse(row.id for code, row in known.items() if code not in wanted)
        gone.unlink()
        return changed, bool(create or gone)

    @staticmethod
    def _differs(name, old, new):
        if name in ("value", "clamp_value", "last_clamp_value", "clamp_step"):
            return _number(old) != new
        return (old or "") != (new or "") if isinstance(new, str) else bool(old) != bool(new)

    @staticmethod
    def _rows_from_report(snapshot):
        """The rows of the report as {code: values}; what is not shaped as expected is left out (the report comes from outside)."""
        entries = ((snapshot.get("values") or {}).get("entries") or []) if isinstance(snapshot, dict) else []
        clamp_rows = {}
        for row in ((snapshot.get("clamps") or {}).get("rows") or []) if isinstance(snapshot, dict) else []:
            if isinstance(row, dict) and isinstance(row.get("code"), str):
                clamp_rows[row["code"]] = row
        rows = {}
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("code"), str) or not entry["code"]:
                continue
            clamp_row = clamp_rows.get(entry["code"])
            state = (clamp_row or {}).get("state") or {}
            # the value the controller works with ("p") and, where the family has one, what its logic gives without a clamp ("aw");
            # a family that reports neither is read from the entry itself
            process = entry.get("p") if isinstance(entry.get("p"), dict) else entry
            automatic = entry.get("aw") if isinstance(entry.get("aw"), dict) else None
            clamped = bool(clamp_row and (clamp_row.get("held") or state.get("clamped")))
            rows[entry["code"]] = {
                "source_name": str(entry.get("name") or ""),
                "status": str(entry.get("status") or ""),
                "text": str(process.get("text") or ""),
                "value": _number(process.get("value")),
                "auto_text": str(automatic.get("text") or "") if automatic else "",
                "unit": str(entry.get("unit") or ""),
                "stale": bool(entry.get("stale")),
                "can_clamp": clamp_row is not None,
                "analog": bool(clamp_row and clamp_row.get("analog")),
                "clamped": clamped,
                "clamp_value": _number(state.get("value")) if clamped else 0.0,
                "clamp_step": _number((clamp_row or {}).get("step")),
            }
            if clamped:
                # kept when the clamp is released: the switch of the list clamps the row to it again
                rows[entry["code"]].update(last_clamp_value=rows[entry["code"]]["clamp_value"], was_clamped=True)
        return rows

    # === RELEASING (the button of the list header; the switch and the value of a row are written, see write) === #

    def action_release(self):
        """Ask the service to release the clamp of these rows (the clamped ones among them)."""
        clamped = self.filtered("clamped")
        if not clamped:
            raise UserError(self.env._("None of the rows is clamped."))
        self.env["int.workbench.command"].create(
            [{"device_id": row.device_id.id, "code": row.code, "action": "release"} for row in clamped]
        )
        return self._requested_notification(len(clamped))

    def action_release_all(self):
        """The button at the top of the list, which needs no ticked rows: ask the service to release every clamp of the rows the list
        shows (its search and its controller; the list tells it as active_domain). The button gives no rows, so they are looked up."""
        domain = Domain.AND([self.env.context.get("active_domain") or [], [("clamped", "=", True)]])
        return self.search(domain).action_release()

    def _requested_notification(self, count):
        """Return the message that tells that the request is on its way; the result shows in the list and in the log."""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Requested"),
                "message": self.env._("%s request(s) sent to the service. The result shows in the clamp log.", count),
                "type": "info",
                "sticky": False,
            },
        }
