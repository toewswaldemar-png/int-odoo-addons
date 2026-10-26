from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged

USER_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_user"
ADMIN_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_admin"


@tagged("post_install", "-at_install")
class TestFolderOcrImages(TransactionCase):
    """Whether the images of a folder are read: its own choice, or the parent's, top folders off."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Folder = cls.env["int.filemanager.folder"]

    def _folder(self, name, parent=None, mode="inherit"):
        return self.Folder.create(
            {"name": name, "parent_id": parent.id if parent else False, "ocr_images": mode}
        )

    def test_a_top_folder_that_says_like_the_parent_is_off(self):
        self.assertFalse(self._folder("Top").ocr_images_active)

    def test_on_and_off_are_the_own_choice(self):
        self.assertTrue(self._folder("On", mode="on").ocr_images_active)
        top = self._folder("Top", mode="on")
        self.assertFalse(self._folder("Off", top, "off").ocr_images_active)

    def test_a_subfolder_takes_over_its_parent_by_default(self):
        top = self._folder("Top", mode="on")
        middle = self._folder("Middle", top)
        self.assertTrue(self._folder("Deep", middle).ocr_images_active)

    def test_a_choice_on_the_way_down_decides_for_what_is_below(self):
        top = self._folder("Top", mode="on")
        middle = self._folder("Middle", top, "off")
        self.assertFalse(self._folder("Deep", middle).ocr_images_active)

    def test_changing_a_folder_changes_what_is_below(self):
        top = self._folder("Top")
        deep = self._folder("Deep", self._folder("Middle", top))
        self.assertFalse(deep.ocr_images_active)
        top.ocr_images = "on"
        self.assertTrue(deep.ocr_images_active)
        top.ocr_images = "off"
        self.assertFalse(deep.ocr_images_active)

    def test_moving_a_folder_takes_over_the_new_parent(self):
        on, off = self._folder("On", mode="on"), self._folder("Off", mode="off")
        moved = self._folder("Moved", off)
        self.assertFalse(moved.ocr_images_active)
        moved.parent_id = on
        self.assertTrue(moved.ocr_images_active)

    def test_a_folder_made_in_the_old_way_is_off(self):
        # A folder without the choice (made before the field) has the default: like the parent.
        self.assertEqual(self.Folder.create({"name": "Old"}).ocr_images, "inherit")


@tagged("post_install", "-at_install")
class TestFolderOcrImagesRights(TransactionCase):
    """Only the administrators of the filemanager choose which folders have their images read."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Folder = cls.env["int.filemanager.folder"]
        cls.alice = new_test_user(cls.env, login="ocr_folder_alice", groups=USER_GROUPS)
        cls.boss = new_test_user(cls.env, login="ocr_folder_boss", groups=ADMIN_GROUPS)

    def test_a_user_cannot_switch_it_on_through_rpc(self):
        folder = self.Folder.with_user(self.alice).create({"name": "Alice's"})
        with self.assertRaises(AccessError):
            folder.write({"ocr_images": "on"})
        with self.assertRaises(AccessError):
            self.Folder.with_user(self.alice).create({"name": "Other", "ocr_images": "on"})
        self.assertFalse(folder.sudo().ocr_images_active)

    def test_a_user_makes_and_changes_folders_as_before(self):
        folder = self.Folder.with_user(self.alice).create({"name": "Plain"})
        folder.write({"name": "Renamed"})
        child = self.Folder.with_user(self.alice).create({"name": "Child", "parent_id": folder.id})
        self.assertEqual((folder.name, child.parent_id), ("Renamed", folder))
        self.assertEqual(child.sudo().ocr_images, "inherit")

    def test_a_user_moving_a_folder_gets_the_new_surroundings(self):
        # An open folder: a user moves a folder only into one the user may write into.
        on = self.Folder.with_user(self.boss).create({"name": "On", "ocr_images": "on", "access_mode": "open"})
        folder = self.Folder.with_user(self.alice).create({"name": "Moves"})
        folder.write({"parent_id": on.id})
        self.assertTrue(folder.sudo().ocr_images_active)

    def test_the_administrator_chooses(self):
        folder = self.Folder.with_user(self.boss).create({"name": "Scans"})
        folder.write({"ocr_images": "on"})
        self.assertTrue(folder.ocr_images_active)

    def test_the_list_of_folders_can_be_read_by_a_user(self):
        self.Folder.with_user(self.boss).create({"name": "Open", "access_mode": "open"})
        self.assertTrue(self.Folder.with_user(self.alice).search_read([("name", "=", "Open")], ["name"]))
