from collections.abc import Collection

from odoo import Command, api, fields, models
from odoo.fields import Domain

# What of a reported row is kept, and how it is compared. ``time`` (when the service read the row) is left out on purpose: it changes
# with every read, so a row would count as changed in every report.
SYNCED_FIELDS = ("name", "pages", "status", "text", "value", "unit", "stale", "can_clamp", "analog", "clamped", "clamp_value")
VALUE_DIGITS = 3
# New rows are put in the order of the report, a controller after the other (the list is ordered by "sequence"; a user changes it by
# dragging, see write): room for this many rows per controller.
SEQUENCE_PER_DEVICE = 1000
# Who may arrange the rows. It is the same order for everybody, so it is not left to every reader of the list.
ARRANGE_GROUPS = ("int_regler.group_regler_operator", "int_regler.group_regler_manager")


def _number(value):
    try:
        return round(float(value), VALUE_DIGITS)
    except (TypeError, ValueError):
        return 0.0


class IntReglerParameter(models.Model):
    _name = "int.regler.parameter"
    _description = "Process value of a controller"
    _order = "sequence, device_id, code"

    device_id = fields.Many2one("int.regler.device", string="Controller", required=True, index=True, ondelete="cascade", readonly=True)
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
    command_ids = fields.One2many("int.regler.command", "parameter_id", string="Clamp requests")
    sequence = fields.Integer(help="The order of the rows in the list; changed by dragging (Operator, Manager).", index=True)
    # A star of the user, as Project has it for projects: who marked the row is kept in a table, is_favorite is what the current user did.
    favorite_user_ids = fields.Many2many(
        "res.users", "int_regler_parameter_favorite_rel", "parameter_id", "user_id", string="Favorite of", copy=False, readonly=True
    )
    is_favorite = fields.Boolean(
        compute="_compute_is_favorite", readonly=False, search="_search_is_favorite", compute_sudo=True, string="Favorite"
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
        """Marks or unmarks the rows for the current user. Done with sudo: whoever reads the rows may mark them, as in Project."""
        command = Command.link if is_favorite else Command.unlink
        self.sudo().favorite_user_ids = [command(self.env.uid)]

    def write(self, vals):
        if "is_favorite" in vals:
            vals = dict(vals)
            self._set_favorite(vals.pop("is_favorite"))
            if not vals:
                return True
        # dragging rows in the list writes the sequence and nothing else: that is allowed for those who arrange the rows, not more
        if set(vals) == {"sequence"} and any(self.env.user.has_group(group) for group in ARRANGE_GROUPS):
            return super(IntReglerParameter, self.sudo()).write(vals)
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
        if name in ("value", "clamp_value"):
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
            }
        return rows
