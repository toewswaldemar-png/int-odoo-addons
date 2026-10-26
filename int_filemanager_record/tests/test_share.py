from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase


@tagged("post_install", "-at_install")
class TestShareOfLinked(AccessCase, TransactionCase):
    """With the share links installed: a file seen through a record is not given away."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()

    def setUp(self):
        super().setUp()
        # optional: this module does not depend on the share links
        self.Share = self.env.get("int.filemanager.share")
        if self.Share is None:
            self.skipTest("int_filemanager_share is not installed")

    def test_a_file_seen_only_through_a_record_cannot_be_given(self):
        hidden = self._document(self.secret, "h.txt", b"hidden")
        partner = self.env["res.partner"].create({"name": "P"})
        self.env["int.filemanager.link"].create(
            {"document_id": hidden.id, "record_ref": f"res.partner,{partner.id}"}
        )
        self.env["int.filemanager.link"]._toggle_access_via_record(True)
        self.assertIn(hidden, self.Document.with_user(self.alice).search([]))
        with self.assertRaises(AccessError):
            self.Share.with_user(self.alice).create({"document_id": hidden.id})
        self.Share.with_user(self.boss).create({"document_id": hidden.id})
