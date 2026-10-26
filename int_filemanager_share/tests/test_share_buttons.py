from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase


@tagged("post_install", "-at_install")
class TestShareButtons(AccessCase, TransactionCase):
    """The button "Share" of a folder and a file, and the number of shares at the target."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Share = cls.env["int.filemanager.share"]

    def setUp(self):
        super().setUp()
        self.document = self._document(self.shared)

    def _dialog(self, record):
        action = record.action_share()
        return action, Form(
            self.Share.with_user(record.env.user).with_context(**action["context"]),
            view=action["views"][0][0],
        )

    def test_the_button_opens_a_dialog_with_the_target_filled_in(self):
        for record, field in ((self.shared, "folder_id"), (self.document, "document_id")):
            with self.subTest(field):
                action = record.action_share()
                self.assertEqual(
                    (action["res_model"], action["target"], action["context"]),
                    ("int.filemanager.share", "new", {f"default_{field}": record.id}),
                )
                view = self.env["ir.ui.view"].browse(action["views"][0][0])
                self.assertEqual(view.xml_id, "int_filemanager_share.int_filemanager_share_view_form_dialog")
                # the dialog has its own buttons, not those of the head of the form, and no chatter
                arch = self.Share.get_view(view.id, "form")["arch"]
                self.assertIn("action_show_address", arch)
                self.assertNotIn("action_remove_password", arch)
                self.assertNotIn("<chatter", arch)

    def test_the_dialog_makes_a_share_with_the_usual_values_and_shows_its_address(self):
        for record, field in ((self.shared, "folder_id"), (self.document, "document_id")):
            with self.subTest(field):
                _action, form = self._dialog(record.with_user(self.alice))
                share = form.save()
                self.assertEqual(share[field], record)
                self.assertEqual(share.name, record.name)
                self.assertEqual(share.create_uid, self.alice)
                self.assertEqual(
                    (share.can_view, share.can_download, share.can_upload, share.has_password),
                    (True, True, False, False),
                )
                self.assertFalse(share.expiration_date)
                again = share.with_user(self.alice).action_show_address()
                self.assertEqual((again["res_id"], again["target"]), (share.id, "new"))
                self.assertTrue(share.url)

    def test_the_count_is_of_the_active_shares_that_the_user_sees(self):
        alices = self.Share.with_user(self.alice).create({"folder_id": self.shared.id})
        self.Share.with_user(self.bob).create({"folder_id": self.shared.id})
        self.Share.with_user(self.alice).create({"document_id": self.document.id})
        folders = self.shared + self.deep

        def counts(user):
            # the number is not stored: a request reads it fresh, a test must say so
            self.env.invalidate_all()
            return {folder.name: folder.with_user(user).share_count for folder in folders}

        self.assertEqual(counts(self.alice), {"Shared": 1, "Deep": 0})
        self.assertEqual(counts(self.bob), {"Shared": 1, "Deep": 0})
        self.assertEqual(counts(self.boss), {"Shared": 2, "Deep": 0})
        self.env.invalidate_all()
        self.assertEqual(self.document.with_user(self.alice).share_count, 1)
        self.assertEqual(self.document.with_user(self.bob).share_count, 0)
        alices.with_user(self.alice).action_archive()  # a blocked share is not counted
        self.assertEqual(counts(self.alice), {"Shared": 0, "Deep": 0})

    def test_the_count_of_a_new_record_is_zero(self):
        self.assertEqual(self.Folder.new({"name": "New"}).share_count, 0)

    def test_the_count_opens_the_shares_of_the_target(self):
        mine = self.Share.with_user(self.alice).create({"folder_id": self.shared.id})
        self.Share.with_user(self.alice).create({"document_id": self.document.id})
        action = self.shared.with_user(self.alice).action_open_shares()
        self.assertEqual(self.Share.with_user(self.alice).search(action["domain"]), mine)
        self.assertEqual(action["context"], {"default_folder_id": self.shared.id})

    def test_the_forms_show_the_button_the_count_and_the_origin_of_an_upload(self):
        folder_form = self.Folder.with_user(self.alice).get_view(view_type="form")["arch"]
        document_form = self.Document.with_user(self.alice).get_view(view_type="form")["arch"]
        for arch in (folder_form, document_form):
            self.assertIn('name="action_share"', arch)
            self.assertIn('name="action_open_shares"', arch)
            self.assertIn('name="share_count"', arch)
        self.assertIn('name="share_id"', document_form)
