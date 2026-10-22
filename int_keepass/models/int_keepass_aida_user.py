from odoo import fields, models


class IntKeepassAidaUser(models.Model):
    """A user name of the AIDA web login, offered in the list of the login page.

    Only the name is kept, taken over from the entries of the password manager whose address
    belongs to AIDA; no password, no entry. Names that are gone from the entries are archived.
    """

    _name = "int.keepass.aida.user"
    _description = "AIDA User Name"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint("UNIQUE (name)", "This AIDA user name exists already.")
