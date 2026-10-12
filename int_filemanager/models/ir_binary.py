from odoo import models


class IrBinary(models.AbstractModel):
    _inherit = "ir.binary"

    def _record_to_stream(self, record, field_name):
        # The hook the core offers: the file of a document lies in a blob, not in an attachment.
        if record._name == "int.filemanager.document" and field_name == "content":
            return record._to_http_stream()
        return super()._record_to_stream(record, field_name)
