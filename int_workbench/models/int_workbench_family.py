import re

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError

# The name of a family and of a capability or transport as the service writes it.
FAMILY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}")
CODE_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,39}")


class IntWorkbenchFamily(models.Model):
    _name = "int.workbench.family"
    _description = "Family of controllers"
    _order = "name"

    name = fields.Char(required=True, index=True, readonly=True, help="The name the service uses for the family, for example micserv.")
    label = fields.Char(required=True, readonly=True, help="The name shown to people.")
    transports = fields.Char(readonly=True, help="The kinds of line the family can use, for example com, tcp.")
    capability_ids = fields.Many2many(
        "int.workbench.capability",
        "int_workbench_family_capability_rel",
        "family_id",
        "capability_id",
        string="Capabilities",
        readonly=True,
        help="Everything the family can do. A single controller can do less.",
    )
    device_ids = fields.One2many("int.workbench.device", "family_id", string="Controllers")

    _name_unique = models.Constraint("UNIQUE (name)", "A family with this name exists already.")

    @api.depends("label", "name")
    def _compute_display_name(self):
        for family in self:
            family.display_name = family.label or family.name

    # === THE SERVICE (JSON-2: POST /json/2/int.workbench.family/service_register) === #

    @api.model
    def service_register(self, device_ref, family=None, capabilities=None, families=None):
        """Take the families and capabilities that a service reports when it signs on.

        :param str device_ref: the id of the controller in the service (field "Controller id")
        :param str|None family: the name of the family of this controller
        :param list|None capabilities: the capabilities this controller has now (codes such as ``clamps``)
        :param list|None families: every family the service knows: ``[{"name", "label", "transports": [...], "capabilities": [...]}]``
        :return: ``{"family": name, "capabilities": [codes], "families": [names]}``

        Families are created or brought up to date, then family and capabilities are set on the controller. A new family needs no
        change of this module. Only a user of the group Workbench / Service can call it, for the controllers assigned to them.
        """
        device = self.env["int.workbench.device"]._service_device(device_ref)
        entries = self._register_entries(families)
        codes = self._register_codes(capabilities, "capabilities")
        if family is not None and (not isinstance(family, str) or not FAMILY_PATTERN.fullmatch(family)):
            raise ValidationError(self.env._("The family %s is not a family name.", family))
        # sudo: int.workbench.family: the families are written by the service, which has no right on them
        records = self.sudo()
        # sudo: int.workbench.capability: see above
        Capability = self.env["int.workbench.capability"].sudo()
        known = {entry["name"]: records._register_family(entry, Capability) for entry in entries}
        own = known.get(family) or (records.search([("name", "=", family)], limit=1) if family else records.browse())
        if family and not own:
            raise ValidationError(self.env._("The family %s is neither reported nor known.", family))
        vals = {}
        if own and device.family_id != own:
            vals["family_id"] = own.id
        wanted = Capability._get_or_create(codes)
        if set(wanted.ids) != set(device.capability_ids.ids):
            vals["capability_ids"] = [Command.set(wanted.ids)]
        if vals:
            device.write(vals)
        return {"family": own.name if own else "", "capabilities": wanted.mapped("code"), "families": list(known)}

    @api.model
    def _register_codes(self, codes, what):
        """Return the capability codes of a report as a list, or raise if they are not shaped as expected."""
        if codes is None:
            return []
        if not isinstance(codes, list) or not all(isinstance(code, str) and CODE_PATTERN.fullmatch(code) for code in codes):
            raise ValidationError(self.env._("The %s must be a list of capability names.", what))
        return codes

    @api.model
    def _register_entries(self, families):
        """Return the families of a report as a list of clean dicts, or raise if they are not shaped as expected."""
        if families is None:
            return []
        if not isinstance(families, list):
            raise ValidationError(self.env._("The families must be a list."))
        entries = []
        for entry in families:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not FAMILY_PATTERN.fullmatch(entry["name"]):
                raise ValidationError(self.env._("A family needs a name of letters, digits, dot, minus and underscore."))
            transports = entry.get("transports") or []
            if not isinstance(transports, list) or not all(isinstance(transport, str) and CODE_PATTERN.fullmatch(transport) for transport in transports):
                raise ValidationError(self.env._("The transports of the family %s must be a list of names.", entry["name"]))
            entries.append(
                {
                    "name": entry["name"],
                    "label": str(entry.get("label") or entry["name"])[:100],
                    "transports": ", ".join(transports),
                    "capabilities": self._register_codes(entry.get("capabilities"), "capabilities of the family"),
                }
            )
        return entries

    def _register_family(self, entry, Capability):
        """Create the family of a report or bring it up to date; write only what differs."""
        family = self.search([("name", "=", entry["name"])], limit=1)
        capabilities = Capability._get_or_create(entry["capabilities"])
        vals = {"label": entry["label"], "transports": entry["transports"]}
        if not family:
            return self.create({"name": entry["name"], **vals, "capability_ids": [Command.set(capabilities.ids)]})
        diff = {name: value for name, value in vals.items() if family[name] != value}
        if set(capabilities.ids) != set(family.capability_ids.ids):
            diff["capability_ids"] = [Command.set(capabilities.ids)]
        if diff:
            family.write(diff)
        return family
