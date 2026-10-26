from odoo import models

# The binary fields of a document that ``ir.binary`` streams, and what streams each of them.
STREAMS = {
    "content": "_to_http_stream",
    "viewer_pdf_content": "_to_viewer_pdf_http_stream",
}


class IrBinary(models.AbstractModel):
    _inherit = "ir.binary"

    def _record_to_stream(self, record, field_name):
        # The hook the core offers: the file of a document lies in a blob, not in an attachment.
        if record._name == "int.filemanager.document" and field_name in STREAMS:
            # Like the core for every field that is not an attachment's: the field has its own
            # rights (``groups``), also when it is not read through the ORM.
            record._check_field_access(record._fields[field_name], "read")
            return getattr(record, STREAMS[field_name])()
        return super()._record_to_stream(record, field_name)
