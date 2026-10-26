import time
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase


@tagged("post_install", "-at_install")
class TestLinkSearch(AccessCase, TransactionCase):
    """The records that have documents are found by the words in the files."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Link = cls.env["int.filemanager.link"]
        cls.Partner = cls.env["res.partner"]
        cls.Link._toggle_access_via_record(True)

    def setUp(self):
        super().setUp()
        self.secret_doc = self._document(self.secret, "s.txt", b"secret")
        self.p1 = self.Partner.create({"name": "P1"})
        self.p2 = self.Partner.create({"name": "P2"})
        self.link = self._link(self.secret_doc, self.p1)

    def _link(self, document, record):
        return self.Link.create({"document_id": document.id, "record_ref": f"{record._name},{record.id}"})

    def test_the_record_is_found_by_the_words_of_its_documents(self):
        document = self._document(self.shared, "t.txt", b"the invoice of the plumber")
        self._link(document, self.p2)
        Text = self.env["int.filemanager.text"]
        with patch.object(self.env.cr, "commit"):
            Text._create_rows(1000)
            for row in Text.search([("state", "=", "pending")]):
                row._read_text(time.monotonic() + 120)
        Text.flush_model()
        as_outsider = self.Partner.with_user(self.outsider)
        self.assertEqual(as_outsider.search([("document_search", "ilike", "plumber")]), self.p2)
        self.assertEqual(as_outsider.search([("document_search", "ilike", "secret")]), self.p1)
        self.assertFalse(as_outsider.search([("document_search", "ilike", "nothinghere")]))
        # without the link the secret document shows nothing
        self.link.unlink()
        self.assertFalse(as_outsider.search([("document_search", "ilike", "secret")]))
