from odoo import fields, models

# Set by the upload only, like the storage fields of ``int_filemanager`` (see ``write``).
EDIT_FIELDS = ("edit_source_id", "edit_state")


class IntFilemanagerDocument(models.Model):
    _inherit = "int.filemanager.document"

    # What the picture editor leaves with a picture it stored: the picture it started from and the
    # state of the editor (marks, filters, crop) on that picture, so that the next edit finds the
    # marks as objects again. Both are set by the storage only; the editor reads them through
    # ``get_edit_session``, which hands out the source only to someone who may read it.
    edit_source_id = fields.Many2one(
        "int.filemanager.document",
        string="Edited from",
        readonly=True,
        copy=False,
        index="btree_not_null",
        ondelete="set null",
        groups="base.group_system",
    )
    edit_state = fields.Json(
        string="Editor state",
        readonly=True,
        copy=False,
        exportable=False,
        groups="base.group_system",
    )

    def write(self, vals):
        # ``readonly`` holds in the interface only: through RPC a user could give a picture the
        # state of another one. As in ``int_filemanager``, drop such values; the storage runs as superuser.
        if not self.env.su:
            vals = {key: value for key, value in vals.items() if key not in EDIT_FIELDS}
        return super().write(vals)

    def get_edit_session(self):
        """Return what the picture editor needs to go on with a picture that it stored before.

        That is the state of the editor and the picture that it was made on. The picture is handed
        out only if the user may read it (their rules, and not archived): the one who may read the
        edited picture need not see where it came from. The editor then starts with the flat
        picture.

        :return: ``{"state": dict, "source": {"id", "name", "mimetype", "checksum", "size"}}``,
            or ``{}`` if there is nothing to go on with
        """
        self.ensure_one()
        self.check_access("read")
        # sudo: int.filemanager.document: the editor fields are readable by system administrators only
        stored = self.sudo()
        if not stored.edit_state or not stored.edit_source_id:
            return {}
        source = self.search([("id", "=", stored.edit_source_id.id)])
        if not source:
            return {}
        return {
            "state": stored.edit_state,
            "source": {
                "id": source.id,
                "name": source.name,
                "mimetype": source.mimetype,
                "checksum": source.checksum,
                "size": source.size,
            },
        }
