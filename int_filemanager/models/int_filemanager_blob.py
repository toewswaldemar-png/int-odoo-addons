from odoo import fields, models


class IntFilemanagerBlob(models.Model):
    """Content-addressed storage row for one file's bytes (Konzept 5). No
    user-facing ACL at all (A1): the hash alone says nothing about who may
    read the content it names, so access only ever goes through a method
    that already checked the node under the caller's identity first."""

    _name = "int_filemanager.blob"
    _description = "Filemanager v2 blob (content, by hash)"

    sha256 = fields.Char(required=True, index=True)
    # Float, not Integer (int4 overflows above ~2 GiB, Pruefbericht Nr. 33-35/19.2).
    size = fields.Float(required=True)
    state = fields.Selection([("present", "Present")], default="present", required=True)
    # Set (or renewed) whenever a write reuses this blob; the cleanup job only removes
    # rows whose last_used is older than its grace period (A4, Konzept 5 "Aufraeumen").
    last_used = fields.Datetime(index=True)

    _sha256_uniq = models.Constraint(
        "UNIQUE(sha256)", "A blob with this hash already exists."
    )
