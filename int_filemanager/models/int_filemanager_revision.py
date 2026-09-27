from odoo import fields, models


class IntFilemanagerRevision(models.Model):
    """One immutable version of a file's content (Konzept 4/6). Never
    written to after creation - a "new version" is always a new row, so a
    conflicting concurrent write (I6, A3) can never overwrite one silently."""

    _name = "int_filemanager.revision"
    _description = "Filemanager v2 revision"
    _order = "node_id, revision_no"

    node_id = fields.Many2one(
        "int_filemanager.node", required=True, index=True, ondelete="cascade"
    )
    revision_no = fields.Integer(required=True)
    blob_id = fields.Many2one(
        "int_filemanager.blob", required=True, index=True, ondelete="restrict"
    )
    # Denormalised from blob_id.size so the node list/tree can show it without a join
    # (same reasoning as node.size); Float for the same int4 ceiling as node.size.
    size = fields.Float()
    origin = fields.Selection(
        [
            ("upload", "Upload"),
            ("webdav", "WebDAV"),
            ("office", "Office"),
            ("edit", "Edit"),
            ("restore", "Restore"),
            ("import", "Import"),
        ],
        required=True,
    )
    # Which idempotency-key record (Konzept 6 "Vorgangs-ID pruefen") produced this
    # revision; not unique here (unlike upload.operation_id) - restoring an old version
    # or copying a node creates a revision without a write-in-progress of its own.
    operation_id = fields.Many2one("int_filemanager.operation", index=True)

    _revision_no_uniq = models.Constraint(
        "UNIQUE(node_id, revision_no)",
        "A node cannot have two revisions with the same number.",
    )
