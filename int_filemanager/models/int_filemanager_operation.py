import psycopg2

from odoo import api, fields, models


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

    @api.model
    def _get_or_create(self, key):
        """Returns (operation, is_new). When not new, operation.result
        already holds the original request's outcome (I9) - the caller must
        return it as-is instead of repeating the write. Same savepoint
        pattern as int_filemanager.blob._get_or_create (A3: retrying() does
        not retry a UniqueViolation)."""
        operation = self.search([("key", "=", key)], limit=1)
        if operation:
            return operation, False
        try:
            with self.env.cr.savepoint():
                return self.create({"key": key}), True
        except psycopg2.errors.UniqueViolation:
            return self.search([("key", "=", key)], limit=1), False
