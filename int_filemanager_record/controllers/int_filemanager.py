from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.int_filemanager.controllers.int_filemanager import IntFilemanager, _NotFound


class IntFilemanagerRecord(IntFilemanager):
    """Upload a file at a record: ``link_model`` and ``link_id`` of the form name the record.

    The file goes to the folder that the settings name for the model of the record and is linked
    to the record. Whoever may change the record may do that, the folders are not checked.
    """

    def _upload_folder(self, folder_id, link_model=None, link_id=None, **kwargs):
        if not link_model:
            return super()._upload_folder(folder_id, **kwargs)
        return self._record_folder(self._record_to_link(link_model, link_id))

    def _upload_values(self, link_model=None, **kwargs):
        return {} if link_model else super()._upload_values(**kwargs)

    def _after_upload(self, document, link_model=None, link_id=None, **kwargs):
        super()._after_upload(document, **kwargs)
        if not link_model:
            return
        record = self._record_to_link(link_model, link_id)
        # sudo: int.filemanager.link: the right to change the record was checked, so the
        # uploader need not see the folder
        request.env["int.filemanager.link"].sudo().create(
            {
                "document_id": document.id,
                "res_model_id": request.env["ir.model"]._get_id(record._name),
                "res_id": record.id,
            }
        )

    def _record_to_link(self, link_model, link_id):
        env = request.env
        if link_model not in env["int.filemanager.link"]._linkable_models():
            raise UserError(env._("Documents cannot be linked to this kind of record."))
        try:
            record = env[link_model].browse(int(link_id)).exists()
        except (TypeError, ValueError):
            record = None
        if not record:
            raise _NotFound(env._("This record does not exist."))
        record.check_access("write")
        return record

    def _record_folder(self, record):
        folder = request.env["int.filemanager.model.folder"]._folder_for_record(record)
        if not folder:
            raise UserError(
                request.env._(
                    "No folder is set for the files of this kind of record. Ask the administrator "
                    "of the filemanager to choose an upload folder."
                )
            )
        return folder
