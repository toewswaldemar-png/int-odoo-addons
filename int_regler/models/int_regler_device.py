import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# What the service accepts as the id of a controller: letters, digits, minus and underscore.
DEVICE_REF_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
# An absolute address of the service ("http://127.0.0.1:8085", "https://host/regler") or a path on the
# server of Odoo ("/regler") when a reverse proxy puts the service on the same origin.
CORE_URL_PATTERN = re.compile(r"(?:https?://[^\s/?#]+)?(?:/[^\s?#]*)?")


class IntReglerDevice(models.Model):
    _name = "int.regler.device"
    _description = "Controller reached through the controller service"
    _order = "name, id"

    name = fields.Char(required=True, index=True)
    core_url = fields.Char(
        string="Service address",
        required=True,
        default="http://127.0.0.1:8085",
        help="Where the browser reaches the controller service: an address such as "
        "http://127.0.0.1:8085, or a path such as /regler when a reverse proxy serves the service "
        "on the address of Odoo. Odoo itself never calls it.",
    )
    device_ref = fields.Char(
        string="Controller id",
        required=True,
        default="main",
        help="The id of the controller in the configuration of the service.",
    )
    active = fields.Boolean(default=True)
    note = fields.Text()

    _name_unique = models.Constraint(
        "UNIQUE (name)",
        "A controller with this name exists already.",
    )

    @api.constrains("core_url")
    def _check_core_url(self):
        for device in self:
            url = (device.core_url or "").strip()
            if not url or not CORE_URL_PATTERN.fullmatch(url):
                raise ValidationError(
                    self.env._(
                        "The service address %s must be an address such as http://127.0.0.1:8085 or a path such as /regler.",
                        device.core_url,
                    )
                )

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

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._normalized(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._normalized(vals))

    @api.model
    def _normalized(self, vals):
        """Cut spaces and the closing slashes, so the page can add its paths to the address."""
        vals = dict(vals)
        if isinstance(vals.get("core_url"), str):
            vals["core_url"] = vals["core_url"].strip().rstrip("/")
        if isinstance(vals.get("device_ref"), str):
            vals["device_ref"] = vals["device_ref"].strip()
        return vals
