from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase


@tagged("post_install", "-at_install")
class TestLinkRights(AccessCase, TransactionCase):
    """What the way over a record leaves to the folders, and what stays with the administrators."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Link = cls.env["int.filemanager.link"]
        cls.partner = cls.env["res.partner"].create({"name": "Linked"})

    def setUp(self):
        super().setUp()
        self.hidden = self._document(self.inner, "hidden.txt", b"hidden")
        self.shown = self._document(self.deep, "shown.txt", b"shown")
        self.Link.create({"document_id": self.hidden.id, "record_ref": f"res.partner,{self.partner.id}"})
        self.Link._toggle_access_via_record(True)

    def test_the_record_shows_what_the_folders_hide(self):
        both = (self.hidden + self.shown).with_user(self.alice)
        self.assertEqual(both._filtered_access("read"), both)
        self.assertEqual(self._seen_by(self.alice, "int.filemanager.document"), self.hidden + self.shown)

    def test_the_folder_filter_asks_the_folders_only(self):
        both = (self.hidden + self.shown).with_user(self.alice)
        self.assertEqual(both._filtered_folder_access("read"), self.shown.with_user(self.alice))
        self._invite(self.secret, self.alice)
        self.assertEqual(both._filtered_folder_access("read"), both)
        self.assertEqual(
            (self.hidden + self.shown).with_user(self.outsider)._filtered_folder_access("read"),
            self.env["int.filemanager.document"],
        )

    def test_a_document_that_a_link_points_to_is_referenced(self):
        self.assertEqual((self.hidden + self.shown)._documents_referenced(), self.hidden)

    def test_the_fields_of_the_administrators_stay_closed_to_the_users(self):
        as_alice = self.shared.with_user(self.alice)
        with self.assertRaises(AccessError):
            as_alice.model_folder_ids  # noqa: B018
        with self.assertRaises(AccessError):
            as_alice.write({"model_folder_ids": False})
