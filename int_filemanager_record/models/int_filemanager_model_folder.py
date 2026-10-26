from odoo import api, fields, models


class IntFilemanagerModelFolder(models.Model):
    """The folder where the files go that are uploaded at a record of a model.

    Whoever may change a contact or a repair order uploads a file there, without knowing the
    folders of the filemanager and without any right on them: the file goes to the folder of
    this setting and is linked to the record, which is what shows it to the uploader. One
    setting per model and company; a setting without a company is for all companies.
    """

    _name = "int.filemanager.model.folder"
    _description = "Filemanager upload folder of a model"
    _order = "res_model, company_id"

    res_model = fields.Selection(
        selection="_selection_res_model", string="Model", required=True, index=True
    )
    folder_id = fields.Many2one(
        "int.filemanager.folder",
        string="Folder",
        required=True,
        ondelete="restrict",
        index=True,
        domain=[("active", "=", True)],
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)

    # COALESCE: no company is one company here too (NULLS NOT DISTINCT needs PostgreSQL 15, the
    # core of Odoo 19 runs on 13).
    _model_per_company = models.UniqueIndex(
        "(res_model, COALESCE(company_id, 0))",
        "There is a folder for this kind of record already.",
    )

    @api.depends("res_model")
    @api.depends_context("lang")
    def _compute_display_name(self):
        # the name of the kind of record, as the tags in the folder list show it
        labels = dict(self._fields["res_model"]._description_selection(self.env))
        for setting in self:
            setting.display_name = labels.get(setting.res_model, setting.res_model)

    @api.model
    def _selection_res_model(self):
        return self.env["int.filemanager.link"]._selection_record_ref()

    @api.model
    def _folder_for_record(self, record):
        """The folder for the files uploaded at ``record``, empty if there is none.

        The setting of the company of the record (its own, or the one of the user), else the
        one for all companies. Superuser: the user does not see the settings. A folder that is
        archived does not count.
        """
        company = (
            record.company_id
            if "company_id" in record._fields and record.company_id
            else self.env.company
        )
        settings = self.sudo().search(
            [("res_model", "=", record._name), ("company_id", "in", [company.id, False])]
        )
        # the setting of the company before the one for all
        settings = settings.sorted(lambda setting: not setting.company_id)
        return settings.folder_id.filtered("active")[:1]
