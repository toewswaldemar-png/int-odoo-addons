from odoo import fields, models


class IntFilemanagerUpload(models.Model):
    """An in-progress chunked upload (Konzept 6/7): survives across the
    several requests one upload takes (init/chunk/finish) so any of them can
    be retried or resumed without losing what was already received."""

    _name = "int_filemanager.upload"
    _description = "Filemanager v2 chunked upload in progress"

    # One upload per idempotency key (Konzept 4 "operation_id (eindeutig)"): a repeated
    # chunk/finish request for the same key must find this same row, not create another.
    operation_id = fields.Many2one(
        "int_filemanager.operation", required=True, index=True
    )
    # Exactly one of the two is set: a new file (target_parent_id + target_name) or
    # a new revision of an existing one (target_node_id) - Konzept 6 "Hochladen (neu)"
    # / "Neue Fassung".
    target_parent_id = fields.Many2one(
        "int_filemanager.node", index=True, ondelete="cascade"
    )
    target_name = fields.Char()
    target_node_id = fields.Many2one(
        "int_filemanager.node", index=True, ondelete="cascade"
    )
    # Float and nullable: the client may not know the size upfront (Konzept 7), and
    # Float avoids the int4 ceiling (19.2) other size fields in this module work around.
    expected_size = fields.Float()
    received_size = fields.Float(default=0.0)
    temp_file = fields.Char()
    state = fields.Selection(
        [
            ("open", "Open"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="open",
        required=True,
    )
    expires_at = fields.Datetime()

    _operation_id_uniq = models.Constraint(
        "UNIQUE(operation_id)", "This operation already has an upload in progress."
    )
