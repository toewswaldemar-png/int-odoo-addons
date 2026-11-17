from odoo import api, fields, models
from odoo.exceptions import ValidationError


class IntWorkbenchType(models.Model):
    _name = "int.workbench.type"
    _description = "Type of a device or of its controller"
    _order = "kind, name, id"
    _rec_names_search = ["name", "ident"]

    name = fields.Char(required=True, index=True, help="The name of the type, for example AC3 (device) or 11HA35D (controller).")
    ident = fields.Char(
        string="Type number",
        index=True,
        help="The number of the type (article number with revision), for example 3EGM064970R0001. It is the same for every piece of the type; "
        "the serial number is a field of the device.",
    )
    kind = fields.Selection(
        [("device", "Device"), ("controller", "Controller")],
        required=True,
        default="device",
        index=True,
        help="Device: what a technician tests (for example an air conditioner). Controller: the control unit inside it.",
    )
    family_id = fields.Many2one(
        "int.workbench.family",
        string="Family",
        ondelete="restrict",
        index=True,
        help="The family of controllers that serves this type. The families are reported by the services.",
    )
    project_version_id = fields.Many2one(
        "int.workbench.project.version",
        string="Default project version",
        ondelete="restrict",
        copy=False,
        help="The version that a device of this type gets when it is given the type and has no project version yet. "
        "Changing it later does not change the devices that have one.",
    )
    active = fields.Boolean(default=True)
    note = fields.Text()
    device_ids = fields.One2many("int.workbench.device", "device_type_id", string="Devices", readonly=True)
    controller_device_ids = fields.One2many("int.workbench.device", "controller_type_id", string="Devices with this controller", readonly=True)

    _kind_name_unique = models.Constraint("UNIQUE (kind, name)", "A type with this name exists already.")
    _kind_ident_unique = models.Constraint("UNIQUE (kind, ident)", "A type with this type number exists already.")

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._normalized(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._normalized(vals))

    @api.model
    def _normalized(self, vals):
        """Write the type number the way the documents do: without spaces and in capitals, so one number is one record.

        An empty number is no number (a database allows many of them, but only one of '').
        """
        vals = dict(vals)
        if "ident" in vals:
            vals["ident"] = (vals["ident"] or "").strip().upper() or False
        if isinstance(vals.get("name"), str):
            vals["name"] = vals["name"].strip()
        return vals

    @api.constrains("project_version_id", "kind")
    def _check_project_version(self):
        for record in self:
            if not record.project_version_id:
                continue
            if record.kind != "device":
                raise ValidationError(self.env._("%s: only a device type has a default project version.", record.display_name))

    @api.constrains("kind")
    def _check_kind_in_use(self):
        """A type that devices use keeps its kind: a device type is no controller type and the other way round."""
        for record in self:
            if (record.kind != "device" and record.device_ids) or (record.kind != "controller" and record.controller_device_ids):
                raise ValidationError(self.env._("%s is used by devices as the other kind of type.", record.display_name))
