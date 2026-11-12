from odoo import api, fields, models


class IntWorkbenchCapability(models.Model):
    _name = "int.workbench.capability"
    _description = "Capability of a controller"
    _order = "sequence, code"

    # The capabilities that the views of the module know (a flag cap_<code> on int.workbench.device). A service may report others: they
    # are kept as records and shown, and a view that wants to use one adds the flag.
    CODES = (
        "clamps",
        "clock",
        "console",
        "can_control",
        "flash",
        "line_switch",
        "error_memory",
        "error_files",
        "intermediate",
        "project_files",
    )

    code = fields.Char(required=True, index=True, readonly=True, help="The name the service uses for the capability, for example clamps.")
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=100)

    _code_unique = models.Constraint("UNIQUE (code)", "A capability with this code exists already.")

    @api.model
    def _get_or_create(self, codes):
        """Return the capabilities with these codes, in the order of the codes; create those that are not known yet.

        A new family may bring a capability that this module has no record for. It is kept with its code as name, so that the
        module needs no change for it.
        """
        existing = {capability.code: capability for capability in self.search([("code", "in", list(codes))])}
        wanted = list(dict.fromkeys(codes))
        missing = [code for code in wanted if code not in existing]
        if missing:
            created = self.create([{"code": code, "name": code.replace("_", " ").capitalize(), "sequence": 1000} for code in missing])
            existing.update({capability.code: capability for capability in created})
        return self.browse([existing[code].id for code in wanted])
