"""Tests for the v2 write paths (Konzept 6). Covers int_filemanager.node.
create_file() - Konzept 6 "Hochladen (neu)" for content that fits a single
request/commit (Konzept 7)."""

import base64

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from .. import blobstore


@tagged("post_install", "-at_install")
class TestNodeCreateFile(TransactionCase):
    def setUp(self):
        super().setUp()
        self.write_group = (
            self.env["res.groups"].sudo().create({"name": "Write path test writer"})
        )
        self.scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Write path test scope",
                    "read_group_ids": [(4, self.write_group.id)],
                    "write_group_ids": [(4, self.write_group.id)],
                }
            )
        )
        self.parent = (
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
                    "name": "Write path writer",
                    "login": "write_path_writer",
                    "group_ids": [(6, 0, [base_group.id, self.write_group.id])],
                }
            )
        )
        self.outsider = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Write path outsider",
                    "login": "write_path_outsider",
                    "group_ids": [(6, 0, [base_group.id])],
                }
            )
        )

    def _node_env(self, user=None):
        return self.env["int_filemanager.node"].with_user(user or self.writer)

    def test_creates_node_with_first_revision(self):
        result = self._node_env().create_file(
            self.parent.id, "hello.txt", b"hello world", "op-create-1"
        )

        node = self.env["int_filemanager.node"].sudo().browse(result["node_id"])
        self.assertEqual(node.name, "hello.txt")
        self.assertEqual(node.parent_id, self.parent)
        self.assertEqual(node.scope_id, self.scope)
        self.assertEqual(node.size, 11)
        self.assertTrue(node.current_revision_id)
        self.assertEqual(node.current_revision_id.revision_no, 1)
        self.assertEqual(node.current_revision_id.origin, "upload")

        blob_path = blobstore.blob_path(self.env, result["sha256"])
        with open(blob_path, "rb") as f:
            self.assertEqual(f.read(), b"hello world")

    def test_accepts_base64_text_content_same_as_raw_bytes(self):
        """JSON-2/call_kw cannot carry binary data at all (Konzept 12/19.16)
        - a caller going through either route must send base64 text."""
        encoded = base64.b64encode(b"hello world").decode()

        result = self._node_env().create_file(
            self.parent.id, "b64.txt", encoded, "op-create-b64"
        )

        blob_path = blobstore.blob_path(self.env, result["sha256"])
        with open(blob_path, "rb") as f:
            self.assertEqual(f.read(), b"hello world")

    def test_empty_content_still_gets_a_revision_on_the_empty_blob(self):
        result = self._node_env().create_file(
            self.parent.id, "empty.txt", b"", "op-create-empty"
        )

        node = self.env["int_filemanager.node"].sudo().browse(result["node_id"])
        self.assertTrue(node.current_revision_id)
        self.assertEqual(result["sha256"], blobstore.EMPTY_SHA256)

    def test_name_conflict_raises_user_error_and_creates_only_one_node(self):
        self._node_env().create_file(self.parent.id, "dup.txt", b"first", "op-dup-1")

        with self.assertRaises(UserError):
            self._node_env().create_file(
                self.parent.id, "dup.txt", b"second", "op-dup-2"
            )

        nodes = (
            self.env["int_filemanager.node"]
            .sudo()
            .search([("parent_id", "=", self.parent.id), ("name", "=", "dup.txt")])
        )
        self.assertEqual(len(nodes), 1)

    def test_repeated_operation_key_returns_stored_result_without_a_second_node(self):
        first = self._node_env().create_file(
            self.parent.id, "once.txt", b"content", "op-repeat"
        )
        second = self._node_env().create_file(
            self.parent.id, "once.txt", b"content", "op-repeat"
        )

        self.assertEqual(first, second)
        nodes = (
            self.env["int_filemanager.node"]
            .sudo()
            .search([("parent_id", "=", self.parent.id), ("name", "=", "once.txt")])
        )
        self.assertEqual(len(nodes), 1)

    def test_same_content_two_names_share_one_blob(self):
        result_a = self._node_env().create_file(
            self.parent.id, "a.txt", b"shared content", "op-share-a"
        )
        result_b = self._node_env().create_file(
            self.parent.id, "b.txt", b"shared content", "op-share-b"
        )

        self.assertEqual(result_a["sha256"], result_b["sha256"])
        blobs = (
            self.env["int_filemanager.blob"]
            .sudo()
            .search([("sha256", "=", result_a["sha256"])])
        )
        self.assertEqual(len(blobs), 1)

    def test_denied_without_write_group_on_scope(self):
        with self.assertRaises(AccessError):
            self._node_env(self.outsider).create_file(
                self.parent.id, "denied.txt", b"x", "op-denied"
            )


@tagged("post_install", "-at_install")
class TestNodeCreateNewRevision(TransactionCase):
    def setUp(self):
        super().setUp()
        self.write_group = (
            self.env["res.groups"].sudo().create({"name": "New revision test writer"})
        )
        self.scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "New revision test scope",
                    "read_group_ids": [(4, self.write_group.id)],
                    "write_group_ids": [(4, self.write_group.id)],
                }
            )
        )
        self.parent = (
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
                    "name": "New revision writer",
                    "login": "new_revision_writer",
                    "group_ids": [(6, 0, [base_group.id, self.write_group.id])],
                }
            )
        )
        self.outsider = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "New revision outsider",
                    "login": "new_revision_outsider",
                    "group_ids": [(6, 0, [base_group.id])],
                }
            )
        )
        first = (
            self.env["int_filemanager.node"]
            .with_user(self.writer)
            .create_file(self.parent.id, "doc.txt", b"version one", "op-nr-setup")
        )
        self.node = self.env["int_filemanager.node"].sudo().browse(first["node_id"])
        self.base_revision_id = first["revision_id"]

    def _node_env(self, user=None):
        return self.env["int_filemanager.node"].with_user(user or self.writer)

    def test_creates_second_revision_keeps_the_first(self):
        result = self._node_env().create_new_revision(
            self.node.id, self.base_revision_id, b"version two", "op-nr-1"
        )

        self.node.invalidate_recordset()
        self.assertEqual(self.node.current_revision_id.id, result["revision_id"])
        self.assertEqual(self.node.current_revision_id.revision_no, 2)
        revisions = (
            self.env["int_filemanager.revision"]
            .sudo()
            .search([("node_id", "=", self.node.id)])
        )
        self.assertEqual(len(revisions), 2)
        self.assertEqual(
            revisions.filtered(lambda r: r.revision_no == 1).origin, "upload"
        )

        blob_path = blobstore.blob_path(self.env, result["sha256"])
        with open(blob_path, "rb") as f:
            self.assertEqual(f.read(), b"version two")

    def test_stale_base_revision_raises_conflict_not_silent_overwrite(self):
        """I6: a write from a stale base revision must not overwrite silently."""
        with self.assertRaises(UserError):
            self._node_env().create_new_revision(
                self.node.id,
                self.base_revision_id + 999999,
                b"clobber",
                "op-nr-conflict",
            )

        self.node.invalidate_recordset()
        self.assertEqual(self.node.current_revision_id.id, self.base_revision_id)
        revisions = (
            self.env["int_filemanager.revision"]
            .sudo()
            .search([("node_id", "=", self.node.id)])
        )
        self.assertEqual(len(revisions), 1)

    def test_same_content_is_a_noop_no_new_revision(self):
        result = self._node_env().create_new_revision(
            self.node.id, self.base_revision_id, b"version one", "op-nr-same"
        )

        self.assertTrue(result.get("unchanged"))
        self.assertEqual(result["revision_id"], self.base_revision_id)
        revisions = (
            self.env["int_filemanager.revision"]
            .sudo()
            .search([("node_id", "=", self.node.id)])
        )
        self.assertEqual(len(revisions), 1)

    def test_dedup_check_works_without_a_warm_cache(self):
        """Regression: the same-content dedup check (`current.blob_id.sha256`)
        read the blob's own field un-sudo'd, which passed every existing test
        here only because setUp's create_file() already warmed this
        transaction's shared field cache for that exact blob row via a sudo'd
        create() - so the later non-sudo read never actually needed a fresh
        fetch, and ir.rule (blob has zero user-facing ACL, Konzept 12/A1)
        never got a chance to reject it. A real HTTP request never shares
        that cache with anything before it (found this way: a real two-worker
        run over JSON-2 on Tower raised AccessError on 'Filemanager v2 blob'
        for every writer, every time - not a race, a plain per-request bug).
        invalidate_all() reproduces that cold-cache condition here."""
        self.env.invalidate_all()

        result = self._node_env().create_new_revision(
            self.node.id, self.base_revision_id, b"version two", "op-nr-cold-cache"
        )

        self.node.invalidate_recordset()
        self.assertEqual(self.node.current_revision_id.id, result["revision_id"])

    def test_repeated_operation_key_is_idempotent(self):
        first = self._node_env().create_new_revision(
            self.node.id, self.base_revision_id, b"version two", "op-nr-repeat"
        )
        second = self._node_env().create_new_revision(
            self.node.id, self.base_revision_id, b"version two", "op-nr-repeat"
        )

        self.assertEqual(first, second)
        revisions = (
            self.env["int_filemanager.revision"]
            .sudo()
            .search([("node_id", "=", self.node.id)])
        )
        self.assertEqual(len(revisions), 2)

    def test_denied_without_write_group_on_scope(self):
        with self.assertRaises(AccessError):
            self._node_env(self.outsider).create_new_revision(
                self.node.id, self.base_revision_id, b"denied", "op-nr-denied"
            )


@tagged("post_install", "-at_install")
class TestNodeRenameOrMove(TransactionCase):
    def setUp(self):
        super().setUp()
        self.write_group = (
            self.env["res.groups"].sudo().create({"name": "Rename test writer"})
        )
        self.scope_a = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Rename test scope A",
                    "read_group_ids": [(4, self.write_group.id)],
                    "write_group_ids": [(4, self.write_group.id)],
                }
            )
        )
        self.other_write_group = (
            self.env["res.groups"].sudo().create({"name": "Rename test other writer"})
        )
        self.scope_b = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Rename test scope B",
                    "read_group_ids": [(4, self.other_write_group.id)],
                    "write_group_ids": [(4, self.other_write_group.id)],
                }
            )
        )
        self.folder_a = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "folder_a", "scope_id": self.scope_a.id, "is_dir": True})
        )
        self.folder_b = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "folder_b", "scope_id": self.scope_b.id, "is_dir": True})
        )
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.writer = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Rename writer",
                    "login": "rename_writer",
                    "group_ids": [(6, 0, [base_group.id, self.write_group.id])],
                }
            )
        )
        self.both_scopes_writer = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Rename both-scopes writer",
                    "login": "rename_both_writer",
                    "group_ids": [
                        (
                            6,
                            0,
                            [
                                base_group.id,
                                self.write_group.id,
                                self.other_write_group.id,
                            ],
                        )
                    ],
                }
            )
        )
        created = (
            self.env["int_filemanager.node"]
            .with_user(self.writer)
            .create_file(self.folder_a.id, "doc.txt", b"content", "op-rn-setup")
        )
        self.node = self.env["int_filemanager.node"].sudo().browse(created["node_id"])

    def _node_env(self, user=None):
        return self.env["int_filemanager.node"].with_user(user or self.writer)

    def test_rename_changes_name_only(self):
        result = self._node_env().rename_or_move(
            self.node.id, False, "renamed.txt", "op-rename-1"
        )

        self.node.invalidate_recordset()
        self.assertEqual(result["node_id"], self.node.id)
        self.assertEqual(self.node.name, "renamed.txt")
        self.assertEqual(self.node.parent_id, self.folder_a)

    def test_rename_conflict_raises_user_error(self):
        self._node_env().create_file(self.folder_a.id, "taken.txt", b"x", "op-rn-taken")

        with self.assertRaises(UserError):
            self._node_env().rename_or_move(self.node.id, False, "taken.txt", "op-rn-2")

        self.node.invalidate_recordset()
        self.assertEqual(self.node.name, "doc.txt")

    def test_move_within_same_scope_keeps_scope(self):
        sibling_folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "sibling", "scope_id": self.scope_a.id, "is_dir": True})
        )

        self._node_env().rename_or_move(
            self.node.id, sibling_folder.id, "doc.txt", "op-move-same-scope"
        )

        self.node.invalidate_recordset()
        self.assertEqual(self.node.parent_id, sibling_folder)
        self.assertEqual(self.node.scope_id, self.scope_a)

    def test_move_to_different_scope_updates_whole_subtree(self):
        parent_folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create(
                {"name": "parent_folder", "scope_id": self.scope_a.id, "is_dir": True}
            )
        )
        leaf_result = self._node_env().create_file(
            parent_folder.id, "leaf.txt", b"y", "op-subtree-leaf"
        )
        leaf = self.env["int_filemanager.node"].sudo().browse(leaf_result["node_id"])

        self._node_env(self.both_scopes_writer).rename_or_move(
            parent_folder.id, self.folder_b.id, "parent_folder", "op-move-subtree"
        )

        parent_folder.invalidate_recordset()
        leaf.invalidate_recordset()
        self.assertEqual(parent_folder.scope_id, self.scope_b)
        self.assertEqual(leaf.scope_id, self.scope_b)

    def test_move_denied_without_write_on_destination_scope(self):
        with self.assertRaises(AccessError):
            self._node_env().rename_or_move(
                self.node.id, self.folder_b.id, "doc.txt", "op-move-denied"
            )

    def test_move_into_a_trashed_folder_is_rejected(self):
        """No active node below a trashed folder (write-skew rule, see
        _touch_active_parent); the real overlap is tests/tower move_against_delete."""
        target = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "target", "scope_id": self.scope_a.id, "is_dir": True})
        )
        self._node_env().trash(target.id, "op-trash-move-target")

        with self.assertRaises(UserError):
            self._node_env().rename_or_move(
                self.node.id, target.id, "doc.txt", "op-move-into-trash"
            )

        self.node.invalidate_recordset()
        self.assertEqual(self.node.parent_id, self.folder_a)

    def test_moving_a_trashed_node_is_rejected(self):
        self._node_env().trash(self.node.id, "op-trash-moved-node")

        with self.assertRaises(UserError):
            self._node_env().rename_or_move(
                self.node.id, False, "renamed.txt", "op-rename-trashed"
            )

    def test_repeated_operation_key_is_idempotent(self):
        first = self._node_env().rename_or_move(
            self.node.id, False, "once.txt", "op-rename-repeat"
        )
        second = self._node_env().rename_or_move(
            self.node.id, False, "once.txt", "op-rename-repeat"
        )
        self.assertEqual(first, second)


@tagged("post_install", "-at_install")
class TestNodeTrashRestoreDelete(TransactionCase):
    def setUp(self):
        super().setUp()
        self.write_group = (
            self.env["res.groups"].sudo().create({"name": "Trash test writer"})
        )
        self.purge_group = (
            self.env["res.groups"].sudo().create({"name": "Trash test purger"})
        )
        self.scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Trash test scope",
                    "read_group_ids": [(4, self.write_group.id)],
                    "write_group_ids": [(4, self.write_group.id)],
                    "purge_group_ids": [(4, self.purge_group.id)],
                }
            )
        )
        self.folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "folder", "scope_id": self.scope.id, "is_dir": True})
        )
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.writer = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Trash writer",
                    "login": "trash_writer",
                    "group_ids": [(6, 0, [base_group.id, self.write_group.id])],
                }
            )
        )
        self.purger = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Trash purger",
                    "login": "trash_purger",
                    "group_ids": [
                        (
                            6,
                            0,
                            [base_group.id, self.write_group.id, self.purge_group.id],
                        )
                    ],
                }
            )
        )
        created = (
            self.env["int_filemanager.node"]
            .with_user(self.writer)
            .create_file(self.folder.id, "doc.txt", b"content", "op-trash-setup")
        )
        self.node = self.env["int_filemanager.node"].sudo().browse(created["node_id"])
        self.revision_id = created["revision_id"]
        self.sha256 = created["sha256"]

    def _node_env(self, user=None):
        return self.env["int_filemanager.node"].with_user(user or self.writer)

    def test_trash_marks_whole_subtree_inactive_and_hides_from_search(self):
        child = (
            self.env["int_filemanager.node"]
            .with_user(self.writer)
            .create_file(self.folder.id, "child.txt", b"c", "op-trash-child")
        )
        child_node = self.env["int_filemanager.node"].sudo().browse(child["node_id"])

        self._node_env().trash(self.folder.id, "op-trash-1")

        self.folder.invalidate_recordset()
        child_node.invalidate_recordset()
        self.assertFalse(self.folder.active)
        self.assertEqual(self.folder.removal_reason, "trash")
        self.assertFalse(child_node.active)
        self.assertEqual(child_node.removal_reason, "trash")
        found = (
            self.env["int_filemanager.node"]
            .sudo()
            .search([("id", "=", self.folder.id)])
        )
        self.assertFalse(found)

    def test_restore_reactivates_subtree(self):
        self._node_env().trash(self.folder.id, "op-trash-2")

        self._node_env().restore(self.folder.id, "op-restore-1")

        self.folder.invalidate_recordset()
        self.assertTrue(self.folder.active)
        self.assertFalse(self.folder.removal_reason)

    def test_restore_conflict_raises_user_error(self):
        self._node_env().trash(self.node.id, "op-trash-3")
        self._node_env().create_file(
            self.folder.id, "doc.txt", b"new one", "op-trash-new-doc"
        )

        with self.assertRaises(UserError):
            self._node_env().restore(self.node.id, "op-restore-conflict")

        self.node.invalidate_recordset()
        self.assertFalse(self.node.active)

    def test_create_file_in_a_trashed_folder_is_rejected(self):
        self._node_env().trash(self.folder.id, "op-trash-create-target")

        with self.assertRaises(UserError):
            self._node_env().create_file(
                self.folder.id, "late.txt", b"x", "op-create-in-trash"
            )

    def test_restore_below_a_trashed_folder_is_rejected(self):
        """Restoring only the file while its folder is still in the trash would
        leave an active node under an inactive one."""
        self._node_env().trash(self.folder.id, "op-trash-whole-folder")

        with self.assertRaises(UserError):
            self._node_env().restore(self.node.id, "op-restore-child-first")

        self.node.invalidate_recordset()
        self.assertFalse(self.node.active)

    def test_restore_of_the_folder_restores_children_under_it(self):
        self._node_env().trash(self.folder.id, "op-trash-whole-folder-2")

        self._node_env().restore(self.folder.id, "op-restore-folder-first")

        self.node.invalidate_recordset()
        self.assertTrue(self.node.active)

    def test_delete_permanently_removes_rows_but_keeps_blob(self):
        self._node_env(self.purger).delete_permanently(self.node.id, "op-delete-1")

        self.assertFalse(
            self.env["int_filemanager.node"]
            .sudo()
            .with_context(active_test=False)
            .search([("id", "=", self.node.id)])
        )
        self.assertFalse(
            self.env["int_filemanager.revision"]
            .sudo()
            .search([("id", "=", self.revision_id)])
        )
        self.assertTrue(
            self.env["int_filemanager.blob"]
            .sudo()
            .search([("sha256", "=", self.sha256)])
        )

    def test_delete_permanently_denied_without_purge_group(self):
        with self.assertRaises(AccessError):
            self._node_env().delete_permanently(self.node.id, "op-delete-denied")

    def test_repeated_operation_key_is_idempotent_for_trash(self):
        first = self._node_env().trash(self.node.id, "op-trash-repeat")
        second = self._node_env().trash(self.node.id, "op-trash-repeat")
        self.assertEqual(first, second)


@tagged("post_install", "-at_install")
class TestNodeCopy(TransactionCase):
    def setUp(self):
        super().setUp()
        self.write_group = (
            self.env["res.groups"].sudo().create({"name": "Copy test writer"})
        )
        self.scope_a = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Copy test scope A",
                    "read_group_ids": [(4, self.write_group.id)],
                    "write_group_ids": [(4, self.write_group.id)],
                }
            )
        )
        self.other_write_group = (
            self.env["res.groups"].sudo().create({"name": "Copy test other writer"})
        )
        self.scope_b = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Copy test scope B",
                    "read_group_ids": [(4, self.other_write_group.id)],
                    "write_group_ids": [(4, self.other_write_group.id)],
                }
            )
        )
        self.folder_a = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "folder_a", "scope_id": self.scope_a.id, "is_dir": True})
        )
        self.folder_b = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "folder_b", "scope_id": self.scope_b.id, "is_dir": True})
        )
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.writer = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Copy writer",
                    "login": "copy_writer",
                    "group_ids": [(6, 0, [base_group.id, self.write_group.id])],
                }
            )
        )
        self.both_scopes_writer = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Copy both-scopes writer",
                    "login": "copy_both_writer",
                    "group_ids": [
                        (
                            6,
                            0,
                            [
                                base_group.id,
                                self.write_group.id,
                                self.other_write_group.id,
                            ],
                        )
                    ],
                }
            )
        )
        created = (
            self.env["int_filemanager.node"]
            .with_user(self.writer)
            .create_file(self.folder_a.id, "source.txt", b"copy me", "op-copy-setup")
        )
        self.source = self.env["int_filemanager.node"].sudo().browse(created["node_id"])
        self.sha256 = created["sha256"]

    def _node_env(self, user=None):
        return self.env["int_filemanager.node"].with_user(user or self.writer)

    def test_copy_creates_new_node_on_same_blob(self):
        result = self._node_env().copy_node(
            self.source.id, self.folder_a.id, "copy.txt", "op-copy-1"
        )

        copy_node = self.env["int_filemanager.node"].sudo().browse(result["node_id"])
        self.assertNotEqual(copy_node.id, self.source.id)
        self.assertEqual(copy_node.current_revision_id.blob_id.sha256, self.sha256)
        self.assertEqual(copy_node.current_revision_id.revision_no, 1)
        blobs = (
            self.env["int_filemanager.blob"]
            .sudo()
            .search([("sha256", "=", self.sha256)])
        )
        self.assertEqual(len(blobs), 1)

    def test_copy_across_scopes_requires_destination_write_right(self):
        with self.assertRaises(AccessError):
            self._node_env().copy_node(
                self.source.id, self.folder_b.id, "copy.txt", "op-copy-denied"
            )

        self._node_env(self.both_scopes_writer).copy_node(
            self.source.id, self.folder_b.id, "copy.txt", "op-copy-2"
        )
        found = (
            self.env["int_filemanager.node"]
            .sudo()
            .search([("parent_id", "=", self.folder_b.id), ("name", "=", "copy.txt")])
        )
        self.assertTrue(found)

    def test_copy_name_conflict_raises_user_error(self):
        with self.assertRaises(UserError):
            self._node_env().copy_node(
                self.source.id, self.folder_a.id, "source.txt", "op-copy-conflict"
            )

    def test_copy_into_a_trashed_folder_is_rejected(self):
        self._node_env().trash(self.folder_a.id, "op-copy-trash-target")

        with self.assertRaises(UserError):
            self._node_env().copy_node(
                self.source.id, self.folder_a.id, "late-copy.txt", "op-copy-in-trash"
            )

    def test_copy_directory_without_content_raises_user_error(self):
        empty_folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "empty_dir", "scope_id": self.scope_a.id, "is_dir": True})
        )
        with self.assertRaises(UserError):
            self._node_env().copy_node(
                empty_folder.id, self.folder_a.id, "empty_dir_copy", "op-copy-nodir"
            )

    def test_repeated_operation_key_is_idempotent(self):
        first = self._node_env().copy_node(
            self.source.id, self.folder_a.id, "copy_once.txt", "op-copy-repeat"
        )
        second = self._node_env().copy_node(
            self.source.id, self.folder_a.id, "copy_once.txt", "op-copy-repeat"
        )
        self.assertEqual(first, second)


@tagged("post_install", "-at_install")
class TestNodeRestoreVersion(TransactionCase):
    def setUp(self):
        super().setUp()
        self.write_group = (
            self.env["res.groups"].sudo().create({"name": "Restore version writer"})
        )
        self.scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Restore version scope",
                    "read_group_ids": [(4, self.write_group.id)],
                    "write_group_ids": [(4, self.write_group.id)],
                }
            )
        )
        self.folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "folder", "scope_id": self.scope.id, "is_dir": True})
        )
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.writer = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Restore version writer",
                    "login": "restore_version_writer",
                    "group_ids": [(6, 0, [base_group.id, self.write_group.id])],
                }
            )
        )
        self.outsider = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Restore version outsider",
                    "login": "restore_version_outsider",
                    "group_ids": [(6, 0, [base_group.id])],
                }
            )
        )
        v1 = self._node_env().create_file(
            self.folder.id, "doc.txt", b"v1", "op-rv-setup-1"
        )
        self.node = self.env["int_filemanager.node"].sudo().browse(v1["node_id"])
        self.v1_revision_id = v1["revision_id"]
        v2 = self._node_env().create_new_revision(
            self.node.id, self.v1_revision_id, b"v2", "op-rv-setup-2"
        )
        self.v2_revision_id = v2["revision_id"]

    def _node_env(self, user=None):
        return self.env["int_filemanager.node"].with_user(user or self.writer)

    def test_restore_creates_new_revision_on_old_blob(self):
        result = self._node_env().restore_version(
            self.node.id, self.v1_revision_id, self.v2_revision_id, "op-rv-1"
        )

        self.node.invalidate_recordset()
        self.assertEqual(self.node.current_revision_id.id, result["revision_id"])
        self.assertEqual(self.node.current_revision_id.revision_no, 3)
        self.assertEqual(
            self.node.current_revision_id.blob_id.sha256,
            self.env["int_filemanager.revision"]
            .sudo()
            .browse(self.v1_revision_id)
            .blob_id.sha256,
        )

    def test_restoring_the_current_version_is_a_noop(self):
        result = self._node_env().restore_version(
            self.node.id, self.v2_revision_id, self.v2_revision_id, "op-rv-noop"
        )
        self.assertTrue(result.get("unchanged"))
        self.assertEqual(result["revision_id"], self.v2_revision_id)

    def test_stale_base_revision_raises_conflict(self):
        with self.assertRaises(UserError):
            self._node_env().restore_version(
                self.node.id, self.v1_revision_id, self.v1_revision_id, "op-rv-stale"
            )

    def test_revision_from_another_node_is_rejected(self):
        other = self._node_env().create_file(
            self.folder.id, "other.txt", b"other", "op-rv-other-setup"
        )
        with self.assertRaises(UserError):
            self._node_env().restore_version(
                self.node.id,
                other["revision_id"],
                self.v2_revision_id,
                "op-rv-wrong-node",
            )

    def test_denied_without_write_group(self):
        with self.assertRaises(AccessError):
            self._node_env(self.outsider).restore_version(
                self.node.id, self.v1_revision_id, self.v2_revision_id, "op-rv-denied"
            )
