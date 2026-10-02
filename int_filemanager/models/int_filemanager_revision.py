from odoo import fields, models


class IntFilemanagerRevision(models.Model):
    """One version of a file's content; never changed after creation."""

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
    # Copied from the blob, to show it without a join. Float: int4 overflows above
    # 2 GiB.
    size = fields.Float()
    origin = fields.Selection(
        [
            ("upload", "Upload"),
            ("webdav", "WebDAV"),
            ("office", "Office"),
            ("edit", "Edit"),
            ("restore", "Restore"),
            ("copy", "Copy"),
            ("import", "Import"),
        ],
        required=True,
    )
    # The operation that created this revision; not unique, because copying a
    # folder creates many revisions in one operation.
    operation_id = fields.Many2one("int_filemanager.operation", index=True)

    _revision_no_uniq = models.Constraint(
        "UNIQUE(node_id, revision_no)",
        "A node cannot have two revisions with the same number.",
    )
