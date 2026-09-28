"""Tests for what the v2 browser UI needs from the tree model (Schritt 4a-1):
folder creation, name rules, copying a whole folder, and the "never into yourself"
rules for move and copy."""

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNodeTree(TransactionCase):
    def setUp(self):
        super().setUp()
        self.write_group = self.env["res.groups"].sudo().create({"name": "Tree writer"})
        self.scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Tree test scope",
                    "read_group_ids": [(4, self.write_group.id)],
                    "write_group_ids": [(4, self.write_group.id)],
                }
            )
        )
        self.root = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "root", "scope_id": self.scope.id, "is_dir": True})
        )
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.writer = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Tree writer",
                    "login": "tree_writer",
                    "group_ids": [(6, 0, [base_group.id, self.write_group.id])],
                }
            )
        )
        self.outsider = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Tree outsider",
                    "login": "tree_outsider",
                    "group_ids": [(6, 0, [base_group.id])],
                }
            )
        )

    def _node(self, user=None):
        return self.env["int_filemanager.node"].with_user(user or self.writer)

    def _folder(self, name, parent=None):
        result = self._node().create_folder(
            (parent or self.root).id, name, f"op-folder-{name}-{parent and parent.id}"
        )
        return self.env["int_filemanager.node"].sudo().browse(result["node_id"])

    def _file(self, parent, name, content=b"x"):
        result = self._node().create_file(
            parent.id, name, content, f"op-file-{name}-{parent.id}"
        )
        return self.env["int_filemanager.node"].sudo().browse(result["node_id"])

    # --- create_folder -------------------------------------------------------

    def test_create_folder_makes_a_folder_in_the_parents_scope(self):
        folder = self._folder("docs")

        self.assertTrue(folder.is_dir)
        self.assertEqual(folder.parent_id, self.root)
        self.assertEqual(folder.scope_id, self.scope)
        self.assertFalse(folder.current_revision_id)

    def test_create_folder_name_conflict_raises_user_error(self):
        self._folder("docs")
        with self.assertRaises(UserError):
            self._node().create_folder(self.root.id, "DOCS", "op-folder-conflict")

    def test_create_folder_is_idempotent_for_the_same_operation_key(self):
        first = self._node().create_folder(self.root.id, "once", "op-folder-repeat")
        second = self._node().create_folder(self.root.id, "once", "op-folder-repeat")
        self.assertEqual(first, second)

    def test_create_folder_denied_without_write_group(self):
        with self.assertRaises(AccessError):
            self._node(self.outsider).create_folder(
                self.root.id, "x", "op-folder-denied"
            )

    def test_create_folder_under_a_file_is_rejected(self):
        a_file = self._file(self.root, "file.txt")
        with self.assertRaises(UserError):
            self._node().create_folder(a_file.id, "inside", "op-folder-under-file")

    def test_create_file_under_a_file_is_rejected(self):
        a_file = self._file(self.root, "file.txt")
        with self.assertRaises(UserError):
            self._node().create_file(
                a_file.id, "inside.txt", b"x", "op-file-under-file"
            )

    # --- names ---------------------------------------------------------------

    def test_invalid_names_are_rejected_on_every_path(self):
        for bad in ("", "  ", ".", "..", "a/b", "a\\b", "a\x00b"):
            with self.subTest(name=bad):
                with self.assertRaises(UserError):
                    self._node().create_folder(self.root.id, bad, f"op-bad-{bad!r}")
        with self.assertRaises(UserError):
            self._node().create_file(self.root.id, "a/b.txt", b"x", "op-bad-file")
        sub = self._file(self.root, "fine.txt")
        with self.assertRaises(UserError):
            self._node().rename_or_move(sub.id, False, "../evil", "op-bad-rename")

    def test_name_is_normalised_to_nfc_and_trimmed(self):
        decomposed = "Rückblick "  # "u" + combining diaeresis, trailing blank
        folder = self._folder(decomposed)
        self.assertEqual(folder.name, "Rückblick")

    def test_decomposed_and_precomposed_spelling_collide(self):
        self._folder("Rückblick")
        with self.assertRaises(UserError):
            self._node().create_folder(self.root.id, "Rückblick", "op-nfc-clash")

    # --- move / copy into itself ----------------------------------------------

    def test_move_folder_into_its_own_subtree_is_rejected(self):
        outer = self._folder("outer")
        inner = self._folder("inner", outer)
        with self.assertRaises(UserError):
            self._node().rename_or_move(outer.id, inner.id, "outer", "op-move-self-1")
        with self.assertRaises(UserError):
            self._node().rename_or_move(outer.id, outer.id, "outer", "op-move-self-2")

    def test_copy_folder_into_its_own_subtree_is_rejected(self):
        outer = self._folder("outer")
        inner = self._folder("inner", outer)
        with self.assertRaises(UserError):
            self._node().copy_node(outer.id, inner.id, "outer copy", "op-copy-self")

    # --- copy a folder ---------------------------------------------------------

    def test_copy_folder_copies_the_whole_subtree_on_the_same_blobs(self):
        src = self._folder("src")
        self._file(src, "a.txt", b"aaa")
        sub = self._folder("sub", src)
        leaf = self._file(sub, "b.txt", b"bbb")
        dst = self._folder("dst")

        result = self._node().copy_node(src.id, dst.id, "src", "op-copy-folder")

        self.assertEqual(result["copied"], 4)  # src, a.txt, sub, b.txt
        new_src = self.env["int_filemanager.node"].sudo().browse(result["node_id"])
        self.assertEqual(new_src.parent_id, dst)
        names = set(
            self.env["int_filemanager.node"]
            .sudo()
            .search([("id", "child_of", new_src.id)])
            .mapped("name")
        )
        self.assertEqual(names, {"src", "a.txt", "sub", "b.txt"})
        new_leaf = (
            self.env["int_filemanager.node"]
            .sudo()
            .search([("id", "child_of", new_src.id), ("name", "=", "b.txt")])
        )
        self.assertNotEqual(new_leaf.id, leaf.id)
        self.assertEqual(
            new_leaf.current_revision_id.blob_id, leaf.current_revision_id.blob_id
        )
        # the original is untouched
        self.assertEqual(
            len(
                self.env["int_filemanager.node"]
                .sudo()
                .search([("id", "child_of", src.id)])
            ),
            4,
        )

    def test_copy_folder_carries_tags_status_and_partner(self):
        tag = self.env["int_filemanager.tag"].create({"name": "tree-tag"})
        partner = self.env["res.partner"].create({"name": "Tree partner"})
        src = self._folder("tagged")
        src.write({"tag_ids": [(4, tag.id)], "partner_id": partner.id})
        dst = self._folder("dst2")

        result = self._node().copy_node(src.id, dst.id, "tagged", "op-copy-tags")

        new = self.env["int_filemanager.node"].sudo().browse(result["node_id"])
        self.assertEqual(new.tag_ids, tag)
        self.assertEqual(new.partner_id, partner)

    def test_copy_folder_skips_trashed_children(self):
        src = self._folder("with-trash")
        keep = self._file(src, "keep.txt")
        gone = self._file(src, "gone.txt")
        self._node().trash(gone.id, "op-trash-gone")
        dst = self._folder("dst3")

        result = self._node().copy_node(src.id, dst.id, "with-trash", "op-copy-trash")

        self.assertEqual(result["copied"], 2)  # the folder and keep.txt
        self.assertTrue(keep.active)

    def test_copy_name_conflict_in_target_raises_user_error(self):
        src = self._folder("clash")
        dst = self._folder("dst4")
        self._folder("clash", dst)
        with self.assertRaises(UserError):
            self._node().copy_node(src.id, dst.id, "clash", "op-copy-clash")

    # --- trash timestamp -------------------------------------------------------

    def test_trash_sets_and_restore_clears_trashed_at(self):
        folder = self._folder("stamped")
        child = self._file(folder, "child.txt")

        self._node().trash(folder.id, "op-stamp-trash")
        self.assertTrue(folder.trashed_at)
        self.assertEqual(folder.trashed_at, child.trashed_at)

        self._node().restore(folder.id, "op-stamp-restore")
        self.assertFalse(folder.trashed_at)
        self.assertFalse(child.trashed_at)
