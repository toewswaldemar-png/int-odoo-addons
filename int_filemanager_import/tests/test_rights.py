import io
import os

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestImportRights(TransactionCase):
    """What the import adds to the documents and the lists of the filemanager."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env["int.filemanager.document"]
        cls.boss = new_test_user(
            cls.env,
            login="import_boss",
            groups="base.group_user,int_filemanager.int_filemanager_group_admin",
        )
        cls.user = new_test_user(
            cls.env,
            login="import_user",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )
        cls.folder = cls.env["int.filemanager.folder"].create({"name": "Top", "access_mode": "open"})

    def test_the_origin_path_is_for_administrators_only(self):
        document = self.Document._create_from_stream(io.BytesIO(b"hello"), "a.txt", self.folder)
        self.addCleanup(self._remove_blob, document.checksum)
        document.sudo().origin_path = "/mnt/data/a.txt"
        as_user = document.with_user(self.user)
        with self.assertRaises(AccessError):
            as_user.origin_path  # noqa: B018
        self.assertNotIn("origin_path", self.Document.with_user(self.user).fields_get())
        self.assertEqual(document.sudo().origin_path, "/mnt/data/a.txt")

    def test_the_lists_of_the_import_are_for_the_administrators(self):
        for model in ("int.filemanager.import", "int.filemanager.import.line"):
            self.env[model].with_user(self.boss).check_access("read")
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.user).check_access("read")

    def _remove_blob(self, checksum):
        path = self.Document._blob_path(checksum)
        if os.path.exists(path):
            os.unlink(path)
