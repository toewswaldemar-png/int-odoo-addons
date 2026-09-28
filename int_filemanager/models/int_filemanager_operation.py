import psycopg2

from odoo import api, fields, models


class IntFilemanagerOperation(models.Model):
    """One write operation, identified by the client's operation key.

    A repeated request (retry, double-click) finds the stored result instead
    of writing a second time.
    """

    _name = "int_filemanager.operation"
    _description = "Filemanager v2 write operation (idempotency key)"

    key = fields.Char(required=True, index=True)
    result = fields.Json()

    _key_uniq = models.Constraint("UNIQUE(key)", "This operation key was already used.")

    @api.model
    def _get_or_create(self, key):
        """Return ``(operation, is_new)`` for ``key``.

        If the operation is not new, the caller returns ``operation.result``
        instead of writing again.
        """
        operation = self.search([("key", "=", key)], limit=1)
        if operation:
            return operation, False
        try:
            with self.env.cr.savepoint():
                return self.create({"key": key}), True
        except psycopg2.errors.UniqueViolation:
            return self.search([("key", "=", key)], limit=1), False
