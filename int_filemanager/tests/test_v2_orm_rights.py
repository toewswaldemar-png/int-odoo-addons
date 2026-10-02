"""Rights that must hold when a user writes the models directly through the ORM.

The ORM is reachable by any logged-in user (``call_kw``, ``/json/2``), so the
checks cannot live only in the helper methods of the node and upload models. Each
test plays the attack of a non-admin user with the narrowest rights that make it
possible.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestV2OrmRights(TransactionCase):
    def setUp(self):
        super().setUp()
        self.base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.writer_group = self._make_group("ORM rights writer")
        self.other_group = self._make_group("ORM rights other")
        self.writer = self._make_user("writer", [self.writer_group])
        # A scope the writer may read and write, and one it cannot see at all.
        self.own_scope = self._make_scope(
            "ORM rights own", read=self.writer_group, write=self.writer_group
        )
        self.foreign_scope = self._make_scope(
            "ORM rights foreign", read=self.other_group, write=self.other_group
        )
        self.own_folder = self._make_node("own", self.own_scope, is_dir=True)
        self.own_file = self._make_node(
            "own.txt", self.own_scope, parent=self.own_folder
        )
        self.foreign_folder = self._make_node(
            "foreign", self.foreign_scope, is_dir=True
        )
        self.foreign_file = self._make_node(
            "foreign.txt", self.foreign_scope, parent=self.foreign_folder
        )

    # -- helpers -------------------------------------------------------------

    def _make_group(self, name):
        return self.env["res.groups"].sudo().create({"name": name})

    def _make_user(self, login, groups):
        group_ids = [g.id for g in groups] + [self.base_group.id]
        return (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": f"ORM rights {login}",
                    "login": f"orm_rights_{login}",
                    "group_ids": [(6, 0, group_ids)],
                }
            )
        )

    def _make_scope(self, name, read=None, write=None):
        vals = {"name": name}
        if read:
            vals["read_group_ids"] = [(4, read.id)]
        if write:
            vals["write_group_ids"] = [(4, write.id)]
        return self.env["int_filemanager.scope"].sudo().create(vals)

    def _make_node(self, name, scope, is_dir=False, parent=None):
        return (
            self.env["int_filemanager.node"]
            .sudo()
            .create(
                {
                    "name": name,
                    "scope_id": scope.id,
                    "is_dir": is_dir,
                    "parent_id": parent.id if parent else False,
                }
            )
        )

    def _make_revision(self, node, sha256):
        blob = (
            self.env["int_filemanager.blob"]
            .sudo()
            .create({"sha256": sha256, "size": 1.0})
        )
        revision = (
            self.env["int_filemanager.revision"]
            .sudo()
            .create(
                {
                    "node_id": node.id,
                    "blob_id": blob.id,
                    "revision_no": 1,
                    "origin": "upload",
                }
            )
        )
        return revision

    def _as_writer(self, record):
        return record.with_user(self.writer)

    # -- upload: the temp file path must not be user input --------------------

    def test_upload_temp_file_cannot_be_set_on_create(self):
        operation = self._as_writer(self.env["int_filemanager.operation"]).create(
            {"key": "orm-rights-upload-create"}
        )
        with self.assertRaises(AccessError):
            self._as_writer(self.env["int_filemanager.upload"]).create(
                {"operation_id": operation.id, "temp_file": "/etc/hostname"}
            )

    def test_upload_temp_file_cannot_be_changed_by_its_owner(self):
        operation = self._as_writer(self.env["int_filemanager.operation"]).create(
            {"key": "orm-rights-upload-write"}
        )
        # Created as the writer (create_uid), but past the access check.
        upload = (
            self._as_writer(self.env["int_filemanager.upload"])
            .sudo()
            .create({"operation_id": operation.id})
        )
        with self.assertRaises(AccessError):
            self._as_writer(upload).write({"temp_file": "/etc/hostname"})

    def test_upload_cannot_be_deleted_directly_by_its_owner(self):
        """Deleting goes through cancel_upload, which removes the temp file itself."""
        operation = self._as_writer(self.env["int_filemanager.operation"]).create(
            {"key": "orm-rights-upload-unlink"}
        )
        upload = (
            self._as_writer(self.env["int_filemanager.upload"])
            .sudo()
            .create({"operation_id": operation.id})
        )
        with self.assertRaises(AccessError):
            self._as_writer(upload).unlink()

    # -- node: fields that carry rights or purge timing -----------------------

    def test_node_cannot_point_to_a_revision_the_user_cannot_read(self):
        revision = self._make_revision(self.foreign_file, "a" * 64)
        with self.assertRaises(AccessError):
            self._as_writer(self.own_file).write({"current_revision_id": revision.id})

    def test_node_cannot_be_marked_for_purge_by_a_user_without_purge_right(self):
        """The purge cron deletes as superuser: these fields decide who can delete."""
        long_ago = fields.Datetime.now() - timedelta(days=3650)
        with self.assertRaises(AccessError):
            self._as_writer(self.own_file).write(
                {
                    "active": False,
                    "removal_reason": "trash",
                    "trashed_at": long_ago,
                }
            )

    def test_node_cannot_change_scope_directly(self):
        with self.assertRaises(AccessError):
            self._as_writer(self.own_file).write({"scope_id": self.foreign_scope.id})

    def test_node_cannot_change_parent_directly(self):
        """Moving checks the target in rename_or_move only; write() must not skip it."""
        with self.assertRaises(AccessError):
            self._as_writer(self.own_file).write(
                {"parent_id": self.foreign_folder.id}
            )

    def test_node_cannot_be_created_below_a_folder_the_user_cannot_write(self):
        with self.assertRaises(AccessError):
            self._as_writer(self.env["int_filemanager.node"]).create(
                {
                    "name": "planted.txt",
                    "scope_id": self.own_scope.id,
                    "parent_id": self.foreign_folder.id,
                }
            )

    def test_node_derived_fields_cannot_be_written_directly(self):
        for vals in (
            {"size": 1.0},
            {"mime": "text/html"},
            {"review_state": "reviewed"},
        ):
            with self.subTest(vals=vals), self.assertRaises(AccessError):
                self._as_writer(self.own_file).write(vals)

    # -- revision: the blob must be one the user may use ----------------------

    def test_revision_cannot_reference_a_blob_of_a_foreign_file(self):
        foreign_revision = self._make_revision(self.foreign_file, "b" * 64)
        with self.assertRaises(AccessError):
            self._as_writer(self.env["int_filemanager.revision"]).create(
                {
                    "node_id": self.own_file.id,
                    "blob_id": foreign_revision.blob_id.id,
                    "revision_no": 1,
                    "origin": "upload",
                }
            )

    # -- scope: creating one must not grant its own manage right --------------

    def test_user_cannot_create_a_scope_managed_by_their_own_group(self):
        with self.assertRaises(AccessError):
            self.env["int_filemanager.scope"].with_user(self.writer).create(
                {
                    "name": "ORM rights self-made scope",
                    "manage_group_ids": [(4, self.base_group.id)],
                    "read_group_ids": [(4, self.base_group.id)],
                    "write_group_ids": [(4, self.base_group.id)],
                    "purge_group_ids": [(4, self.base_group.id)],
                }
            )

    # -- moving a folder: sub-folders of another scope ------------------------

    def _tree_with_foreign_subfolder(self):
        """``top`` (own scope) holds ``hidden`` (a scope the writer cannot read)."""
        top = self._make_node("top", self.own_scope, is_dir=True)
        hidden = self._make_node("hidden", self.foreign_scope, is_dir=True, parent=top)
        target_scope = self._make_scope(
            "ORM rights target", read=self.writer_group, write=self.writer_group
        )
        target = self._make_node("target", target_scope, is_dir=True)
        return top, hidden, target

    def test_move_does_not_hand_hidden_subfolder_to_the_target_scope(self):
        """Either the move is refused or the sub-folder keeps its own scope."""
        top, hidden, target = self._tree_with_foreign_subfolder()
        try:
            with self.env.cr.savepoint():
                self._as_writer(self.env["int_filemanager.node"]).rename_or_move(
                    top.id, target.id, "top", "orm-rights-move-hidden"
                )
        except (UserError, AccessError):
            return
        self.env.invalidate_all()
        self.assertEqual(
            hidden.sudo().scope_id,
            self.foreign_scope,
            "a sub-folder the user cannot read must not change its scope",
        )

    def _tree_with_nested_scope(self):
        """``top`` > ``mid`` share a scope; ``deep`` below has the target's scope."""
        target_scope = self._make_scope(
            "ORM rights target", read=self.writer_group, write=self.writer_group
        )
        top = self._make_node("top", self.own_scope, is_dir=True)
        mid = self._make_node("mid", self.own_scope, is_dir=True, parent=top)
        deep = self._make_node("deep", target_scope, is_dir=True, parent=mid)
        target = self._make_node("target", target_scope, is_dir=True)
        return top, mid, deep, target

    def test_move_to_other_scope_keeps_is_scope_root_consistent(self):
        """The stored flag must match its definition for every node of the subtree.

        ``deep`` stops being a scope root once ``mid`` has the scope it already had,
        two levels below the node that was moved.
        """
        top, mid, deep, target = self._tree_with_nested_scope()
        self._as_writer(self.env["int_filemanager.node"]).rename_or_move(
            top.id, target.id, "top", "orm-rights-move-flag"
        )
        self.env.invalidate_all()
        for node in (top, mid, deep):
            node = node.sudo()
            expected = not node.parent_id or node.parent_id.scope_id != node.scope_id
            self.assertEqual(
                node.is_scope_root,
                expected,
                f"is_scope_root of {node.name} does not match its parent's scope",
            )

    def test_move_to_other_scope_takes_the_descendants_along_that_share_the_scope(
        self,
    ):
        top, mid, deep, target = self._tree_with_nested_scope()
        self._as_writer(self.env["int_filemanager.node"]).rename_or_move(
            top.id, target.id, "top", "orm-rights-move-inherit"
        )
        self.env.invalidate_all()
        self.assertEqual(top.sudo().scope_id, target.sudo().scope_id)
        self.assertEqual(mid.sudo().scope_id, target.sudo().scope_id)
        self.assertEqual(deep.sudo().scope_id, target.sudo().scope_id)
