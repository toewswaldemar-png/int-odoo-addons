from odoo import fields, models


class IntFilemanagerOperation(models.Model):
    """Idempotency-key ledger for the write path (Konzept 4/6): "Vorgangs-ID
    pruefen" before any disk or DB write, so a retried request (Odoo's own
    retrying(), a client retry, a double-click) finds the stored result
    instead of repeating the write (I9)."""

    _name = "int_filemanager.operation"
    _description = "Filemanager v2 write operation (idempotency key)"

    key = fields.Char(required=True, index=True)
    result = fields.Json()

    _key_uniq = models.Constraint("UNIQUE(key)", "This operation key was already used.")
