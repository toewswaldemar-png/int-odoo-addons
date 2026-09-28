"""Tests for what the v2 browser UI needs from the tree model (Schritt 4a-1):
folder creation, name rules, copying a whole folder, and the "never into yourself"
rules for move and copy."""

from datetime import timedelta

from odoo import fields
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


@tagged("post_install", "-at_install")
class TestTrashPurge(TransactionCase):
    """The 30-day purge (Konzept 17.4): rows only, blobs stay for the blob cleanup."""

    def setUp(self):
        super().setUp()
        Scope = self.env["int_filemanager.scope"].sudo()
        self.scope = Scope.create({"name": "Purge scope"})
        self.Node = self.env["int_filemanager.node"].sudo()
        self.root = self.Node.create(
            {"name": "purge-root", "scope_id": self.scope.id, "is_dir": True}
        )

    def _file(self, parent, name, content=b"x"):
        node = self.Node.create(
            {"name": name, "scope_id": self.scope.id, "parent_id": parent.id}
        )
        self.Node.create_new_revision(node.id, False, content, f"op-purge-{name}")
        return node

    def _age(self, nodes, days):
        nodes.with_context(active_test=False).write(
            {"trashed_at": fields.Datetime.now() - timedelta(days=days)}
        )

    def test_expired_trash_is_purged_with_its_whole_subtree(self):
        folder = self.Node.create(
            {
                "name": "old",
                "scope_id": self.scope.id,
                "parent_id": self.root.id,
                "is_dir": True,
            }
        )
        child = self._file(folder, "child.txt", b"old bytes")
        sha = child.current_revision_id.blob_id.sha256
        self.Node.trash(folder.id, "op-purge-trash-old")
        self._age(folder + child, 31)

        self.Node._purge_expired_trash()

        self.assertFalse((folder + child).exists())
        self.assertFalse(
            self.env["int_filemanager.revision"].search([("node_id", "=", child.id)])
        )
        # the blob is not touched here: the blob cleanup job owns that (I4)
        self.assertTrue(self.env["int_filemanager.blob"].search([("sha256", "=", sha)]))

    def test_recent_trash_stays(self):
        node = self._file(self.root, "recent.txt")
        self.Node.trash(node.id, "op-purge-trash-recent")
        self._age(node, 29)

        self.Node._purge_expired_trash()

        self.assertTrue(node.with_context(active_test=False).exists())

    def test_nodes_that_are_not_trashed_are_never_purged(self):
        node = self._file(self.root, "alive.txt")
        node.write({"trashed_at": fields.Datetime.now() - timedelta(days=400)})

        self.Node._purge_expired_trash()

        self.assertTrue(node.exists())

    def test_a_node_trashed_on_its_own_earlier_expires_before_its_folder(self):
        folder = self.Node.create(
            {
                "name": "mixed",
                "scope_id": self.scope.id,
                "parent_id": self.root.id,
                "is_dir": True,
            }
        )
        early = self._file(folder, "early.txt")
        late = self._file(folder, "late.txt")
        self.Node.trash(early.id, "op-purge-early")
        self._age(early, 40)
        self.Node.trash(late.id, "op-purge-late")

        self.Node._purge_expired_trash()

        self.assertFalse(early.with_context(active_test=False).exists())
        self.assertTrue(late.with_context(active_test=False).exists())

    def test_retention_is_configurable(self):
        node = self._file(self.root, "short.txt")
        self.Node.trash(node.id, "op-purge-short")
        self._age(node, 8)
        self.env["ir.config_parameter"].sudo().set_param(
            "int_filemanager.trash_retention_days", "7"
        )

        self.Node._purge_expired_trash()

        self.assertFalse(node.with_context(active_test=False).exists())


@tagged("post_install", "-at_install")
class TestTreeNavigation(TransactionCase):
    """What the sidebar tree, the breadcrumb and the upload conflict dialog ask
    the server (Schritt 4b-1)."""

    def setUp(self):
        super().setUp()
        env = self.env
        Group = env["res.groups"].sudo()
        self.group = Group.create({"name": "Nav group"})
        self.narrow_group = Group.create({"name": "Nav narrow group"})
        Scope = env["int_filemanager.scope"].sudo()
        self.scope = Scope.create(
            {"name": "Nav scope", "read_group_ids": [(4, self.group.id)]}
        )
        self.narrow_scope = Scope.create(
            {
                "name": "Nav narrow scope",
                "read_group_ids": [(4, self.narrow_group.id), (4, self.group.id)],
            }
        )
        base_group = env.ref("int_filemanager.group_filemanager_user")
        Users = env["res.users"].sudo()
        self.user = Users.create(
            {
                "name": "Nav user",
                "login": "nav_user",
                "group_ids": [(6, 0, [base_group.id, self.group.id])],
            }
        )
        self.narrow_user = Users.create(
            {
                "name": "Nav narrow user",
                "login": "nav_narrow_user",
                "group_ids": [(6, 0, [base_group.id, self.narrow_group.id])],
            }
        )
        self.Node = env["int_filemanager.node"].sudo()
        self.root = self._folder("Root", None)
        self.beta = self._folder("beta", self.root)
        self.alpha = self._folder("Alpha", self.root)
        self.deep = self._folder("deep", self.beta)
        # only the narrow group may read below here: the user's chain must not show it
        self.private = self._folder("private", self.root, self.narrow_scope)
        self.private_child = self._folder("inner", self.private, self.narrow_scope)

    def _folder(self, name, parent, scope=None):
        return self.Node.create(
            {
                "name": name,
                "parent_id": parent.id if parent else False,
                "scope_id": (scope or self.scope).id,
                "is_dir": True,
            }
        )

    def _as(self, user):
        return self.env["int_filemanager.node"].with_user(user)

    def test_roots_are_listed_when_no_parent_is_given(self):
        result = self._as(self.user).tree_children(False)
        self.assertEqual([r["name"] for r in result], ["Root"])
        self.assertTrue(result[0]["has_children"])

    def test_children_are_sorted_without_case_and_flag_their_own_children(self):
        result = self._as(self.user).tree_children(self.root.id)
        # the narrow scope lists self.group too, so "private" is visible here; the
        # test for unreadable folders below covers a real exclusion
        self.assertEqual([r["name"] for r in result], ["Alpha", "beta", "private"])
        flags = {r["name"]: r["has_children"] for r in result}
        self.assertEqual(flags, {"Alpha": False, "beta": True, "private": True})

    def test_files_and_trashed_folders_are_not_in_the_tree(self):
        self.Node.create_new_revision(
            self.Node.create(
                {"name": "f.txt", "parent_id": self.root.id, "scope_id": self.scope.id}
            ).id,
            False,
            b"x",
            "op-nav-file",
        )
        self.Node.trash(self.alpha.id, "op-nav-trash")
        result = self._as(self.user).tree_children(self.root.id)
        self.assertEqual([r["name"] for r in result], ["beta", "private"])

    def test_unreadable_folders_are_left_out_of_the_tree(self):
        outsider_scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Nav closed scope",
                    "read_group_ids": [(4, self.narrow_group.id)],
                }
            )
        )
        closed = self._folder("closed", self.root, outsider_scope)
        result = self._as(self.user).tree_children(self.root.id)
        self.assertNotIn(closed.name, [r["name"] for r in result])
        narrow = self._as(self.narrow_user).tree_children(self.root.id)
        self.assertIn("closed", [r["name"] for r in narrow])

    def test_breadcrumb_runs_from_the_top_to_the_node(self):
        crumbs = self._as(self.user).breadcrumb(self.deep.id)
        self.assertEqual([c["name"] for c in crumbs], ["Root", "beta", "deep"])
        self.assertEqual(crumbs[-1]["id"], self.deep.id)

    def test_breadcrumb_leaves_out_ancestors_the_caller_cannot_read(self):
        # the narrow user reads only the narrow scope: the chain starts at "private"
        crumbs = self._as(self.narrow_user).breadcrumb(self.private_child.id)
        self.assertEqual([c["name"] for c in crumbs], ["private", "inner"])

    def test_breadcrumb_of_a_missing_or_unreadable_node(self):
        self.assertEqual(self._as(self.user).breadcrumb(999999999), [])
        with self.assertRaises(AccessError):
            self._as(self.narrow_user).breadcrumb(self.deep.id)

    def test_existing_names_match_without_case_and_nfc(self):
        self.Node.create(
            {
                "name": "R\u00fcckblick.txt",
                "parent_id": self.root.id,
                "scope_id": self.scope.id,
            }
        )
        result = self._as(self.user).existing_names(
            self.root.id,
            ["ALPHA", "rU\u0308CKBLICK.TXT", "not-there.txt"],
        )
        self.assertEqual(
            sorted(r["name"] for r in result), ["Alpha", "R\u00fcckblick.txt"]
        )
        alpha = next(r for r in result if r["name"] == "Alpha")
        self.assertTrue(alpha["is_dir"])
        self.assertFalse(alpha["current_revision_id"])

    def test_existing_names_reports_the_current_revision_of_files(self):
        node = self.Node.create(
            {"name": "doc.txt", "parent_id": self.root.id, "scope_id": self.scope.id}
        )
        created = self.Node.create_new_revision(node.id, False, b"v1", "op-nav-doc")
        result = self._as(self.user).existing_names(self.root.id, ["doc.txt"])
        self.assertEqual(result[0]["current_revision_id"], created["revision_id"])

    def test_existing_names_at_the_root_level_and_for_no_names(self):
        self.assertEqual(
            [r["name"] for r in self._as(self.user).existing_names(False, ["root"])],
            ["Root"],
        )
        self.assertEqual(self._as(self.user).existing_names(self.root.id, []), [])

    def test_existing_names_never_shows_what_the_caller_cannot_read(self):
        result = self._as(self.narrow_user).existing_names(self.private.id, ["inner"])
        self.assertEqual([r["name"] for r in result], ["inner"])
        with self.assertRaises(AccessError):
            self._as(self.narrow_user).existing_names(self.deep.id, ["x"])

    def test_mtime_follows_the_current_revision(self):
        node = self.Node.create(
            {"name": "m.txt", "parent_id": self.root.id, "scope_id": self.scope.id}
        )
        self.assertFalse(node.mtime)
        created = self.Node.create_new_revision(node.id, False, b"v1", "op-nav-m")
        revision = self.env["int_filemanager.revision"].browse(created["revision_id"])
        self.assertEqual(node.mtime, revision.create_date)


@tagged("post_install", "-at_install")
class TestTrashListButtons(TransactionCase):
    """The two buttons of the trash list call these node methods."""

    def setUp(self):
        super().setUp()
        Group = self.env["res.groups"].sudo()
        self.group = Group.create({"name": "Trash buttons group"})
        self.purge_group = Group.create({"name": "Trash buttons purge group"})
        scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Trash buttons scope",
                    "read_group_ids": [(4, self.group.id)],
                    "write_group_ids": [(4, self.group.id)],
                    "purge_group_ids": [(4, self.purge_group.id)],
                }
            )
        )
        base = self.env.ref("int_filemanager.group_filemanager_user")
        Users = self.env["res.users"].sudo()
        self.user = Users.create(
            {
                "name": "Trash buttons user",
                "login": "trash_buttons_user",
                "group_ids": [(6, 0, [base.id, self.group.id])],
            }
        )
        self.purger = Users.create(
            {
                "name": "Trash buttons purger",
                "login": "trash_buttons_purger",
                "group_ids": [(6, 0, [base.id, self.group.id, self.purge_group.id])],
            }
        )
        self.folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "tb", "scope_id": scope.id, "is_dir": True})
        )
        self.node = (
            self.env["int_filemanager.node"]
            .sudo()
            .create(
                {"name": "x.txt", "scope_id": scope.id, "parent_id": self.folder.id}
            )
        )
        self.env["int_filemanager.node"].sudo().trash(self.node.id, "op-tb-trash")

    def test_restore_button(self):
        self.node.with_user(self.user).with_context(active_test=False).action_restore()
        self.assertTrue(self.node.active)

    def test_delete_permanently_button_needs_the_purge_right(self):
        with self.assertRaises(AccessError):
            self.node.with_user(self.user).with_context(
                active_test=False
            ).action_delete_permanently()
        self.node.with_user(self.purger).with_context(
            active_test=False
        ).action_delete_permanently()
        self.assertFalse(self.node.with_context(active_test=False).exists())
