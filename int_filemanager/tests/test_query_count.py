from odoo.tests.common import TransactionCase, tagged

from .test_folder_access import AccessCase

NAME = {"display_name": {}}


@tagged("post_install", "-at_install")
class TestQueryCount(AccessCase, TransactionCase):
    """What the user's lists cost does not grow with the number of folders and documents.

    The rules of the folders look at the folder that decides (``access_folder_id``) in the one
    query of the search; the names of the paths are asked in one batch. A rule or a name that asks
    for each folder would show here as a count that rises with the tree.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.opened = cls.Folder.create({"name": "Opened", "parent_id": cls.secret.id, "access_mode": "open"})

    def _grow(self, count):
        """``count`` more subfolders, each with a document, below the folder that is open."""
        for index in range(count):
            folder = self.Folder.create({"name": f"Folder {self.grown}-{index}", "parent_id": self.opened.id})
            self._document(folder, f"file-{self.grown}-{index}.txt", f"content {self.grown} {index}".encode())
        self.grown += count

    def _queries(self, action):
        self.env.invalidate_all()
        self.env.flush_all()
        before = self.env.cr.sql_log_count
        action()
        return self.env.cr.sql_log_count - before

    def _lists(self):
        folders = self.Folder.with_user(self.alice)
        documents = self.Document.with_user(self.alice)
        found = documents.web_search_read(
            [], {"name": {}, "is_favorite": {}, "folder_id": {"fields": NAME}}, limit=200
        )
        self.assertTrue(found["records"])
        folders.web_search_read([], {"name": {}, "is_favorite": {}, "parent_id": {"fields": NAME}}, limit=200)
        documents.search_panel_select_range("folder_id")

    def test_the_lists_of_a_user_cost_the_same_for_a_small_and_a_big_tree(self):
        self.grown = 0
        self._grow(3)
        # The caches of the rules and the rights are filled by the first call (made like the ones that
        # are counted: the rules of the users that the star reads load after the caches are emptied).
        self._queries(self._lists)
        small = self._queries(self._lists)
        self._grow(30)
        big = self._queries(self._lists)
        self.assertEqual(big, small)
