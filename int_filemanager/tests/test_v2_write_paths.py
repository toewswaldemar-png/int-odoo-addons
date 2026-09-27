"""Tests for the v2 write paths (Konzept 6). Covers int_filemanager.node.
create_file() - Konzept 6 "Hochladen (neu)" for content that fits a single
request/commit (Konzept 7)."""

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
