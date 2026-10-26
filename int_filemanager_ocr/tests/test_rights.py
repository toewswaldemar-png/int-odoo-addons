from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestOcrRights(TransactionCase):
    """What the text search adds to the rights: the lists of the texts and the setting of a folder
    are for the administrators."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.boss = new_test_user(
            cls.env,
            login="ocr_boss",
            groups="base.group_user,int_filemanager.int_filemanager_group_admin",
        )
        cls.alice = new_test_user(
            cls.env,
            login="ocr_alice_rights",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )
        cls.reader = new_test_user(
            cls.env,
            login="ocr_reader",
            groups="base.group_user,int_filemanager.int_filemanager_group_reader",
        )
        cls.outsider = new_test_user(cls.env, login="ocr_outsider", groups="base.group_user")
        cls.folder = cls.env["int.filemanager.folder"].create({"name": "Shared", "access_mode": "open"})

    def test_the_lists_of_the_texts_are_for_the_administrators(self):
        for model in ("int.filemanager.text", "int.filemanager.text.page"):
            self.env[model].with_user(self.boss).check_access("read")
            for user in (self.reader, self.alice, self.outsider):
                with self.assertRaises(AccessError):
                    self.env[model].with_user(user).check_access("read")

    def test_the_setting_of_the_images_stays_closed_to_the_users(self):
        as_alice = self.folder.with_user(self.alice)
        with self.assertRaises(AccessError):
            as_alice.ocr_images  # noqa: B018
        with self.assertRaises(AccessError):
            as_alice.write({"ocr_images": "on"})
