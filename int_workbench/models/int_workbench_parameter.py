from collections.abc import Collection
from math import floor

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

from .int_workbench_device import COMMAND_TTL

# What of a reported row is kept, and how it is compared. ``time`` (when the service read the row) is left out on purpose: it changes
# with every read, so a row would count as changed in every report.
SYNCED_FIELDS = ("name", "pages", "status", "text", "value", "unit", "stale", "can_clamp", "analog", "clamped", "clamp_value", "last_clamp_value", "was_clamped", "clamp_step")
VALUE_DIGITS = 3
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

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade", readonly=True)
    code = fields.Char(string="Row", required=True, readonly=True)
    name = fields.Char(readonly=True, index="trigram")
    pages = fields.Char(help="The pages of the controller the row is shown on.", readonly=True)
    status = fields.Char(help="How the read went: ok, or what is wrong with the row.", readonly=True)
    text = fields.Char(string="Value", help="As the controller shows it, for example 22.3°C.", readonly=True)
    value = fields.Float(string="Number", digits=(16, VALUE_DIGITS), help="The value as a number; 0 where the row has none.", readonly=True)
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
        string="Clamp",
        help="Clamped, or asked to be. Switching it on clamps the row to the value it was clamped to last (to the value it has, if it "
        "never was), switching it off releases it.",
    )
    clamp_input = fields.Float(
        compute="_compute_clamp_request",
        readonly=False,
        digits=(16, VALUE_DIGITS),
        string="Clamp to",
        help="The value the row is clamped to; while it is not, the value it was clamped to last (the value it has, if it never was). "
        "Writing it clamps the row to the value.",
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

    @api.depends("clamped", "clamp_value", "value", "last_clamp_value", "was_clamped", "clamp_step", "command_ids.state", "command_ids.action", "command_ids.value")
    def _compute_clamp_request(self):
        on_their_way = self._clamp_requests_on_their_way()
        for row in self:
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
        for row in self:
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

    def write(self, vals):
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
        return super().write(vals)

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
        known = {row.code: row for row in self.search_fetch([("device_id", "=", device.id)], ["code", *SYNCED_FIELDS])}
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
            clamped = bool(clamp_row and (clamp_row.get("held") or state.get("clamped")))
            rows[entry["code"]] = {
                "name": str(entry.get("name") or ""),
                "pages": ",".join(str(page) for page in entry.get("pages") or []),
                "status": str(entry.get("status") or ""),
                "text": str(entry.get("text") or ""),
                "value": _number(entry.get("value")),
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
