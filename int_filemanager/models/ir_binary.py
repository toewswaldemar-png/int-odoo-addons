from odoo import models


class IrBinary(models.AbstractModel):
    _inherit = "ir.binary"

    def _record_to_stream(self, record, field_name):
        # The hook the core offers: the file of a document lies in a blob, not in an attachment.
        if record._name == "int.filemanager.document":
            if field_name == "content":
                return record._to_http_stream()
            if field_name == "ocr_content":
                return record._to_ocr_http_stream()
        return super()._record_to_stream(record, field_name)

    def _find_record(self, xmlid=None, res_model="ir.attachment", res_id=None, access_token=None, field=None):
        # SPIKE (throw-away): the guest page reads the picture and the file of a document through
        # the core's routes (/web/image, /web/content); the cookie of the link opens the documents
        # of its folder, read as the creator of the folder (record rules included).
        if res_model == "int.filemanager.document" and res_id is not None and not xmlid:
            from ..controllers.spike import guest_document

            record = guest_document(self.env, res_id, field)
            if record:
                return record
        return super()._find_record(xmlid, res_model, res_id, access_token, field)
