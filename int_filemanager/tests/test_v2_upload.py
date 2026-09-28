"""Tests for the v2 chunked upload (Konzept 7): init/chunk/finish, the
large-file async path, and orphaned-upload cleanup."""

import os

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from .. import blobstore


@tagged("post_install", "-at_install")
class TestUploadFlow(TransactionCase):
    def setUp(self):
        super().setUp()
        self.write_group = (
            self.env["res.groups"].sudo().create({"name": "Upload test writer"})
        )
        self.scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Upload test scope",
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
                    "name": "Upload writer",
                    "login": "upload_writer",
                    "group_ids": [(6, 0, [base_group.id, self.write_group.id])],
                }
            )
        )
        self.outsider = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Upload outsider",
                    "login": "upload_outsider",
                    "group_ids": [(6, 0, [base_group.id])],
                }
            )
        )

    def _upload_env(self, user=None):
        return self.env["int_filemanager.upload"].with_user(user or self.writer)

    def _init_new_file(self, name="big.bin", size=None, key="op-init-1"):
        return self._upload_env().init_upload(
            self.folder.id, name, False, False, size, key
        )

    def test_init_upload_requires_exactly_one_target(self):
        with self.assertRaises(UserError):
            self._upload_env().init_upload(False, False, False, False, 10, "op-none")
        with self.assertRaises(UserError):
            self._upload_env().init_upload(
                self.folder.id, "a.txt", 999999, False, 10, "op-both"
            )

    def test_init_upload_denied_without_write_group(self):
        with self.assertRaises(AccessError):
            self._upload_env(self.outsider).init_upload(
                self.folder.id, "denied.bin", False, False, 10, "op-denied"
            )

    def test_init_upload_repeated_key_is_idempotent(self):
        first = self._init_new_file(key="op-init-repeat")
        second = self._init_new_file(key="op-init-repeat")
        self.assertEqual(first, second)

    def test_chunk_appends_and_tracks_received_size(self):
        result = self._init_new_file(key="op-chunk-1")
        upload_id = result["upload_id"]

        r1 = self._upload_env().upload_chunk(upload_id, 0, b"hello ")
        self.assertEqual(r1["received_size"], 6)
        r2 = self._upload_env().upload_chunk(upload_id, 6, b"world")
        self.assertEqual(r2["received_size"], 11)

        upload = self.env["int_filemanager.upload"].sudo().browse(upload_id)
        with open(upload.temp_file, "rb") as f:
            self.assertEqual(f.read(), b"hello world")

    def test_chunk_repeat_at_same_offset_is_a_noop(self):
        result = self._init_new_file(key="op-chunk-2")
        upload_id = result["upload_id"]
        self._upload_env().upload_chunk(upload_id, 0, b"hello ")

        repeated = self._upload_env().upload_chunk(upload_id, 0, b"hello ")

        self.assertEqual(repeated["received_size"], 6)
        upload = self.env["int_filemanager.upload"].sudo().browse(upload_id)
        with open(upload.temp_file, "rb") as f:
            self.assertEqual(f.read(), b"hello ")

    def test_chunk_with_a_gap_is_rejected(self):
        result = self._init_new_file(key="op-chunk-3")
        upload_id = result["upload_id"]
        self._upload_env().upload_chunk(upload_id, 0, b"hello ")

        with self.assertRaises(UserError):
            self._upload_env().upload_chunk(upload_id, 100, b"gap")

    def test_finish_small_file_creates_node_synchronously(self):
        result = self._init_new_file(name="small.txt", key="op-finish-1")
        upload_id = result["upload_id"]
        self._upload_env().upload_chunk(upload_id, 0, b"small content")

        finish = self._upload_env().finish_upload(upload_id, "op-finish-1-done")

        self.assertNotIn("state", finish)
        node = self.env["int_filemanager.node"].sudo().browse(finish["node_id"])
        self.assertEqual(node.name, "small.txt")
        self.assertTrue(node.current_revision_id)
        upload = self.env["int_filemanager.upload"].sudo().browse(upload_id)
        self.assertEqual(upload.state, "done")
        blob_path = blobstore.blob_path(self.env, finish["sha256"])
        with open(blob_path, "rb") as f:
            self.assertEqual(f.read(), b"small content")

    def test_finish_new_revision_of_existing_node(self):
        created = (
            self.env["int_filemanager.node"]
            .with_user(self.writer)
            .create_file(self.folder.id, "doc.txt", b"v1", "op-upload-doc-setup")
        )
        node_id = created["node_id"]
        base_revision_id = created["revision_id"]

        init = self._upload_env().init_upload(
            False, False, node_id, base_revision_id, 2, "op-init-revise"
        )
        self._upload_env().upload_chunk(init["upload_id"], 0, b"v2")
        finish = self._upload_env().finish_upload(init["upload_id"], "op-finish-revise")

        node = self.env["int_filemanager.node"].sudo().browse(node_id)
        self.assertEqual(node.current_revision_id.id, finish["revision_id"])
        self.assertEqual(node.current_revision_id.revision_no, 2)

    def test_finish_name_conflict_raises_user_error(self):
        """A real request that raises rolls back its whole transaction
        (Odoo only commits after a fully successful dispatch), so the
        upload cannot be durably marked "failed" in the same call that
        raises - it stays "open" with its bytes intact, so the client can
        retry finish_upload once the name is free (or let the orphan-expiry
        cron reclaim it eventually)."""
        self.env["int_filemanager.node"].with_user(self.writer).create_file(
            self.folder.id, "taken.txt", b"x", "op-upload-taken-setup"
        )
        result = self._init_new_file(name="taken.txt", key="op-finish-conflict")
        self._upload_env().upload_chunk(result["upload_id"], 0, b"y")

        with self.assertRaises(UserError):
            self._upload_env().finish_upload(
                result["upload_id"], "op-finish-conflict-2"
            )

        upload = self.env["int_filemanager.upload"].sudo().browse(result["upload_id"])
        self.assertEqual(upload.state, "open")

    def test_finish_into_a_trashed_folder_is_rejected(self):
        result = self._init_new_file(name="late.bin", key="op-init-trashed-target")
        self._upload_env().upload_chunk(result["upload_id"], 0, b"data")
        self.env["int_filemanager.node"].with_user(self.writer).trash(
            self.folder.id, "op-trash-upload-target"
        )

        with self.assertRaises(UserError):
            self._upload_env().finish_upload(result["upload_id"], "op-finish-trashed")

    def test_finish_repeated_operation_key_is_idempotent(self):
        result = self._init_new_file(name="once.bin", key="op-finish-repeat-init")
        self._upload_env().upload_chunk(result["upload_id"], 0, b"data")

        first = self._upload_env().finish_upload(
            result["upload_id"], "op-finish-repeat"
        )
        second = self._upload_env().finish_upload(
            result["upload_id"], "op-finish-repeat"
        )

        self.assertEqual(first, second)

    def test_finish_large_upload_defers_to_cron(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "int_filemanager.upload_large_file_threshold_mb", "0"
        )
        result = self._init_new_file(name="huge.bin", key="op-large-1")
        self._upload_env().upload_chunk(result["upload_id"], 0, b"more than zero bytes")

        finish = self._upload_env().finish_upload(
            result["upload_id"], "op-large-1-done"
        )
        self.assertEqual(finish["state"], "processing")
        upload = self.env["int_filemanager.upload"].sudo().browse(result["upload_id"])
        self.assertEqual(upload.state, "processing")

        # Not _cron_finish_pending() itself: it commits per item (Odoo's own
        # per-item progress commit), which TestCursor forbids inside a test.
        self.env["int_filemanager.upload"].sudo()._finish_pending_one(upload)

        upload.invalidate_recordset()
        self.assertEqual(upload.state, "done")
        found = (
            self.env["int_filemanager.node"]
            .sudo()
            .search([("parent_id", "=", self.folder.id), ("name", "=", "huge.bin")])
        )
        self.assertTrue(found)
        self.assertEqual(found.create_uid, self.writer)
        self.assertEqual(upload.result["node_id"], found.id)
        self.assertFalse(upload.error)

    def _large_pending_upload(self, name, key):
        self.env["ir.config_parameter"].sudo().set_param(
            "int_filemanager.upload_large_file_threshold_mb", "0"
        )
        result = self._init_new_file(name=name, key=key)
        self._upload_env().upload_chunk(result["upload_id"], 0, b"payload")
        self._upload_env().finish_upload(result["upload_id"], f"{key}-done")
        return self.env["int_filemanager.upload"].sudo().browse(result["upload_id"])

    def test_cron_finish_uses_the_uploaders_rights_not_the_crons(self):
        """The cron runs as superuser; a user whose write right was revoked while the
        upload sat in the queue must get a failed upload, not a file (I7)."""
        upload = self._large_pending_upload("revoked.bin", "op-revoked")
        self.writer.sudo().write({"group_ids": [(3, self.write_group.id)]})

        self.env["int_filemanager.upload"].sudo()._finish_pending_one(upload)

        upload.invalidate_recordset()
        self.assertEqual(upload.state, "failed")
        self.assertTrue(upload.error)
        self.assertFalse(
            self.env["int_filemanager.node"]
            .sudo()
            .search([("parent_id", "=", self.folder.id), ("name", "=", "revoked.bin")])
        )

    def test_cron_finish_failure_is_recorded_with_its_reason(self):
        self.env["int_filemanager.node"].with_user(self.writer).create_file(
            self.folder.id, "clash.bin", b"x", "op-clash-setup"
        )
        upload = self._large_pending_upload("clash.bin", "op-clash")

        self.env["int_filemanager.upload"].sudo()._finish_pending_one(upload)

        upload.invalidate_recordset()
        self.assertEqual(upload.state, "failed")
        self.assertIn("clash.bin", upload.error)

    def test_status_reports_progress_and_the_final_result(self):
        init = self._init_new_file(name="status.bin", key="op-status", size=10)
        upload_id = init["upload_id"]
        self.assertEqual(
            self._upload_env().upload_status(upload_id)["received_size"], 0
        )

        self._upload_env().upload_chunk(upload_id, 0, b"12345")
        status = self._upload_env().upload_status(upload_id)
        self.assertEqual(status["received_size"], 5)
        self.assertEqual(status["state"], "open")
        self.assertEqual(status["expected_size"], 10)

        self._upload_env().upload_chunk(upload_id, 5, b"67890")
        finish = self._upload_env().finish_upload(upload_id, "op-status-done")
        status = self._upload_env().upload_status(upload_id)
        self.assertEqual(status["state"], "done")
        self.assertEqual(status["result"]["node_id"], finish["node_id"])

    def test_cancel_removes_the_row_and_its_temp_file(self):
        init = self._init_new_file(name="cancel.bin", key="op-cancel")
        self._upload_env().upload_chunk(init["upload_id"], 0, b"partial")
        upload = self.env["int_filemanager.upload"].sudo().browse(init["upload_id"])
        temp_file = upload.temp_file
        self.assertTrue(os.path.exists(temp_file))

        self._upload_env().cancel_upload(init["upload_id"])

        self.assertFalse(upload.exists())
        # postcommit hooks do not run inside a test cursor; run what was registered
        for hook in list(self.env.cr.postcommit._funcs):
            hook()
        self.assertFalse(os.path.exists(temp_file))

    def test_cancel_of_something_gone_is_fine_and_of_others_is_denied(self):
        self.assertTrue(self._upload_env().cancel_upload(999999999))
        init = self._init_new_file(name="not-yours.bin", key="op-cancel-denied")
        with self.assertRaises(AccessError):
            self._upload_env(self.outsider).cancel_upload(init["upload_id"])

    def test_a_processing_upload_cannot_be_cancelled(self):
        upload = self._large_pending_upload("busy.bin", "op-cancel-busy")
        with self.assertRaises(UserError):
            self._upload_env().cancel_upload(upload.id)

    def test_status_of_someone_elses_upload_is_denied(self):
        init = self._init_new_file(name="mine.bin", key="op-status-mine")

        with self.assertRaises(AccessError):
            self._upload_env(self.outsider).upload_status(init["upload_id"])

    def test_finish_with_a_new_name_after_a_conflict(self):
        self.env["int_filemanager.node"].with_user(self.writer).create_file(
            self.folder.id, "taken2.txt", b"x", "op-taken2-setup"
        )
        result = self._init_new_file(name="taken2.txt", key="op-rename-finish")
        self._upload_env().upload_chunk(result["upload_id"], 0, b"y")
        with self.assertRaises(UserError):
            self._upload_env().finish_upload(result["upload_id"], "op-rename-finish-1")

        finish = self._upload_env().finish_upload(
            result["upload_id"], "op-rename-finish-2", "taken2 (1).txt"
        )

        node = self.env["int_filemanager.node"].sudo().browse(finish["node_id"])
        self.assertEqual(node.name, "taken2 (1).txt")

    def test_finish_of_a_new_revision_rechecks_the_write_right(self):
        created = (
            self.env["int_filemanager.node"]
            .with_user(self.writer)
            .create_file(self.folder.id, "recheck.txt", b"v1", "op-recheck-setup")
        )
        init = self._upload_env().init_upload(
            False, False, created["node_id"], created["revision_id"], 2, "op-recheck"
        )
        self._upload_env().upload_chunk(init["upload_id"], 0, b"v2")
        self.writer.sudo().write({"group_ids": [(3, self.write_group.id)]})

        with self.assertRaises(AccessError):
            self._upload_env().finish_upload(init["upload_id"], "op-recheck-done")


@tagged("post_install", "-at_install")
class TestUploadCleanupCron(TransactionCase):
    def setUp(self):
        super().setUp()
        self.write_group = (
            self.env["res.groups"].sudo().create({"name": "Upload gc writer"})
        )
        self.scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Upload gc scope",
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
                    "name": "Upload gc writer",
                    "login": "upload_gc_writer",
                    "group_ids": [(6, 0, [base_group.id, self.write_group.id])],
                }
            )
        )

    def test_expired_open_upload_and_its_temp_file_are_removed(self):
        Upload = self.env["int_filemanager.upload"].with_user(self.writer)
        result = Upload.init_upload(
            self.folder.id, "abandoned.bin", False, False, 100, "op-gc-1"
        )
        Upload.upload_chunk(result["upload_id"], 0, b"partial")
        upload = self.env["int_filemanager.upload"].sudo().browse(result["upload_id"])
        upload.write({"expires_at": "2000-01-01 00:00:00"})
        temp_path = upload.temp_file
        self.assertTrue(temp_path)

        self.env["int_filemanager.upload"].sudo()._cron_expire_orphaned_uploads()

        self.assertFalse(
            self.env["int_filemanager.upload"].sudo().search([("id", "=", upload.id)])
        )
        self.assertFalse(os.path.exists(temp_path))

    def test_unexpired_open_upload_survives(self):
        Upload = self.env["int_filemanager.upload"].with_user(self.writer)
        result = Upload.init_upload(
            self.folder.id, "fresh.bin", False, False, 100, "op-gc-2"
        )

        self.env["int_filemanager.upload"].sudo()._cron_expire_orphaned_uploads()

        self.assertTrue(
            self.env["int_filemanager.upload"]
            .sudo()
            .search([("id", "=", result["upload_id"])])
        )
