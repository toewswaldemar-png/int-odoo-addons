from odoo import fields, models


class IntFilemanagerShareAttempt(models.TransientModel):
    """A wrong password for a share, from an address: what the rate limit on passwords counts.

    It is kept in the database, not in memory: trying passwords is the one attack that the rate
    limit must hold against over all the workers and over a restart (each try costs the server
    a long hash). Built like ``auth.totp.rate.limit.log``; Odoo removes old rows of a transient
    model itself.
    """

    _name = "int.filemanager.share.attempt"
    _description = "Filemanager share: wrong password"

    share_id = fields.Many2one(
        "int.filemanager.share", required=True, index=True, ondelete="cascade"
    )
    ip = fields.Char(required=True)
