import re

from odoo import Command, api, models
from odoo.exceptions import ValidationError

# The name of a family and of a capability or transport as the service writes it.
FAMILY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}")
CODE_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,39}")


class IntWorkbenchFamily(models.AbstractModel):
    """The sign-on of a service. It keeps no record: the original (the family) is a text on the controller, and what the controller can
    do is its list of capabilities. The model stays as the name the service calls (``int.workbench.family/service_register``)."""

    _name = "int.workbench.family"
    _description = "Sign-on of a service"

    # === THE SERVICE (JSON-2: POST /json/2/int.workbench.family/service_register) === #

    @api.model
    def service_register(self, device_ref, family=None, capabilities=None, families=None):
        """Take what a service reports when it signs on: the original of the controller and what the controller can do.

        :param str device_ref: the id of the controller in the service (field "Controller id")
        :param str|None family: the name of the family of this controller
        :param list|None capabilities: the capabilities this controller has now (codes such as ``clamps``)
        :param list|None families: the families the service knows: ``[{"name", "label", "transports": [...], "capabilities": [...]}]``; the
            label of the family of the controller is what is kept
        :return: ``{"family": name, "capabilities": [codes], "families": [names]}``

        A new family needs no change of this module. Only a user of the group Workbench / Service can call it, for the controllers
        assigned to them.
        """
        device = self.env["int.workbench.device"]._service_device(device_ref)
        entries = self._register_entries(families)
        codes = self._register_codes(capabilities, "capabilities")
        if family is not None and (not isinstance(family, str) or not FAMILY_PATTERN.fullmatch(family)):
            raise ValidationError(self.env._("The family %s is not a family name.", family))
        labels = {entry["name"]: entry["label"] for entry in entries}
        if family and family not in labels:
            raise ValidationError(self.env._("The family %s is not reported.", family))
        # sudo: int.workbench.capability: the capabilities are written by the service, which has no right on them
        wanted = self.env["int.workbench.capability"].sudo()._get_or_create(codes)
        vals = {}
        if family and device.family != labels[family]:
            vals["family"] = labels[family]
        if set(wanted.ids) != set(device.capability_ids.ids):
            vals["capability_ids"] = [Command.set(wanted.ids)]
        if vals:
            device.write(vals)
        return {"family": family or "", "capabilities": wanted.mapped("code"), "families": list(labels)}

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
            self._register_codes(entry.get("capabilities"), "capabilities of the family")
            entries.append({"name": entry["name"], "label": str(entry.get("label") or entry["name"])[:100]})
        return entries
