from odoo import api, fields, models


class IntFilemanagerLinkable(models.AbstractModel):
    """Mixin for the models whose records can have documents of the filemanager.

    A model that inherits it gets the links to documents, the number of them, the action that
    shows them and a search by the words in the files. It also removes the links of a deleted
    record: the database cannot cascade over (model name, id), as with the messages of
    ``mail.thread``. Without the mixin the model does not appear in the choice of the links.
    """

    _name = "int.filemanager.linkable"
    _description = "Record with documents of the filemanager"

    link_ids = fields.One2many("int.filemanager.link", "res_id", string="Links to documents")
    document_count = fields.Integer(
        string="Filemanager documents", compute="_compute_document_count"
    )

    @api.depends("link_ids")
    @api.depends_context("uid")
    def _compute_document_count(self):
        # The links the user sees: the rule of the link follows the rules of the document.
        Link = self.env["int.filemanager.link"]
        counts = {}
        if Link.has_access("read"):
            counts = dict(
                Link._read_group(
                    [("res_model", "=", self._name), ("res_id", "in", self.ids)],
                    ["res_id"],
                    ["__count"],
                )
            )
        for record in self:
            record.document_count = counts.get(record.id, 0)

    def unlink(self):
        ids = self.ids
        result = super().unlink()
        self.env["int.filemanager.link"].sudo().search(
            [("res_model", "=", self._name), ("res_id", "in", ids)]
        ).unlink()
        return result

    def action_open_documents(self):
        """Show the documents of this record in the list of the filemanager."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "int_filemanager.int_filemanager_document_action"
        )
        # Without the panel of the folders: the user of the record may not see the folders. The
        # keys of the context tell the list where an upload goes (the record, not a folder).
        search_view = self.env.ref(
            "int_filemanager.int_filemanager_document_view_search_record"
        ).sudo()
        action.update(
            name=self.env._("Documents of %(record)s", record=self.display_name),
            domain=[
                ("link_ids", "any", [("res_model", "=", self._name), ("res_id", "=", self.id)])
            ],
            search_view_id=[search_view.id, search_view.name],
            context={
                "int_filemanager_link_model": self._name,
                "int_filemanager_link_id": self.id,
                "int_filemanager_link_name": self.display_name,
            },
        )
        return action
