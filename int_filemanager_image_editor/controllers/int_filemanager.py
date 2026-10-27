import json

from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.int_filemanager.controllers.int_filemanager import IntFilemanager

# The most bytes of editor state (marks, filters, crop and the small pictures put into the editor)
# that are stored with a picture.
EDIT_STATE_MAX_SIZE = 8 * 1024**2


class IntFilemanagerImageEditor(IntFilemanager):
    def _upload_values(self, edit_state=None, edit_source_id=None, **kwargs):
        """Add the editor state and the source picture of the form to the values of the document.

        The picture editor sends ``edit_state`` (its state as JSON) and ``edit_source_id`` (the
        picture it started from) with the picture it stored, so that the next edit finds the marks
        again. A source that the user may not read is dropped: the picture is then stored flat.
        """
        values = super()._upload_values(**kwargs)
        if not edit_state:
            return values
        if len(edit_state.encode()) > EDIT_STATE_MAX_SIZE:
            raise UserError(request.env._("The state of the editor is too large to be kept."))
        try:
            state = json.loads(edit_state)
            source_id = int(edit_source_id)
        except (TypeError, ValueError):
            raise UserError(request.env._("The state of the editor is not valid.")) from None
        if not isinstance(state, dict):
            raise UserError(request.env._("The state of the editor is not valid."))
        # The rules of the user decide: the marks are kept only with a picture they could start from.
        source = request.env["int.filemanager.document"].search([("id", "=", source_id)])
        if source:
            values = {**values, "edit_state": state, "edit_source_id": source.id}
        return values
