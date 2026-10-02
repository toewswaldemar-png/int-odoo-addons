"""Public methods of the node model: wrong arguments, read-only marks, copying a
folder in few calls, and the purge job of the trash."""

from datetime import timedelta
from unittest.mock import patch

import psycopg2

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

BAD_IDS = (None, False, 0, -1, "1", [1], {"id": 1}, 1.5, True)


@tagged("post_install", "-at_install")
class TestNodeArguments(TransactionCase):
    def setUp(self):
        super().setUp()
        self.group = self.env["res.groups"].sudo().create({"name": "Argument writer"})
        self.scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Argument scope",
                    "read_group_ids": [(4, self.group.id)],
                    "write_group_ids": [(4, self.group.id)],
                    "purge_group_ids": [(4, self.group.id)],
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
                    "name": "Argument writer",
                    "login": "argument_writer",
                    "group_ids": [
                        (6, 0, [base_group.id, self.group.id]),
                        (4, self.env.ref("base.group_user").id),
                    ],
                }
            )
        )
        self.Node = self.env["int_filemanager.node"].with_user(self.writer)
        self.file = self._file("file.txt")
        self.number = (
            self.env["int_filemanager.extraction_field"]
            .sudo()
            .create({"name": "Arg number", "value_type": "number"})
        )

    def _file(self, name, content=b"x"):
        result = self.Node.create_file(self.root.id, name, content, f"op-arg-{name}")
        return self.env["int_filemanager.node"].sudo().browse(result["node_id"])

    def _rejects(self, call, bad_values):
        for bad in bad_values:
            with self.subTest(value=bad), self.assertRaises(UserError):
                call(bad)

    # --- ids -----------------------------------------------------------------

    def test_an_id_that_is_none_is_a_message_not_a_server_error(self):
        Node, file = self.Node, self.file
        self._rejects(lambda b: Node.create_folder(b, "x", "op-a1"), BAD_IDS)
        self._rejects(lambda b: Node.create_file(b, "x.txt", b"x", "op-a2"), BAD_IDS)
        self._rejects(lambda b: Node.copy_node(b, self.root.id, "c", "op-a3"), BAD_IDS)
        self._rejects(lambda b: Node.copy_node(file.id, b, "c", "op-a4"), BAD_IDS)
        self._rejects(lambda b: Node.trash(b, "op-a5"), BAD_IDS)
        self._rejects(lambda b: Node.restore(b, "op-a6"), BAD_IDS)
        self._rejects(lambda b: Node.delete_permanently(b, "op-a7"), BAD_IDS)
        self._rejects(lambda b: Node.rename_or_move(b, False, "n", "op-a8"), BAD_IDS)
        self._rejects(lambda b: Node.breadcrumb(b), BAD_IDS)
        self._rejects(lambda b: Node.suggest_field_values(b), BAD_IDS)
        self._rejects(lambda b: Node.page_words(b, 1, 1), BAD_IDS)
        self._rejects(lambda b: Node.request_text(b), BAD_IDS)
        self._rejects(lambda b: Node.read_selection(b, 1, 1, 0, 1), BAD_IDS)
        self._rejects(lambda b: Node.apply_field_values(b, 1, []), BAD_IDS)
        self._rejects(
            lambda b: Node.create_new_revision(b, False, b"y", "op-a9"), BAD_IDS
        )
        self._rejects(lambda b: Node.restore_version(b, 1, False, "op-a10"), BAD_IDS)
        self._rejects(
            lambda b: Node.restore_version(file.id, b, False, "op-a11"), BAD_IDS
        )

    def test_the_optional_ids_accept_nothing_but_reject_wrong_types(self):
        Node = self.Node
        self.assertEqual(Node.tree_children(False), Node.tree_children(None))
        self.assertEqual(Node.existing_names(None, []), [])
        bad = ("1", [1], {"id": 1}, 1.5, True, -1)
        self._rejects(lambda b: Node.tree_children(b), bad)
        self._rejects(lambda b: Node.existing_names(b, ["a"]), bad)
        self._rejects(
            lambda b: Node.rename_or_move(self.file.id, b, "n", "op-a12"), bad
        )
        self._rejects(
            lambda b: Node.create_new_revision(self.file.id, b, b"y", "op-a13"), bad
        )

    def test_copying_a_folder_into_nothing_is_a_message(self):
        folder = self.Node.create_folder(self.root.id, "folder", "op-a14")
        with self.assertRaises(UserError):
            self.Node.copy_node(folder["node_id"], False, "again", "op-a15")

    # --- text and bytes ------------------------------------------------------

    def test_names_must_be_text(self):
        self._rejects(
            lambda b: self.Node.create_folder(self.root.id, b, "op-a16"),
            (None, 5, ["a"], {"a": 1}),
        )
        self._rejects(
            lambda b: self.Node.rename_or_move(self.file.id, False, b, "op-a17"),
            (None, 5, ["a"]),
        )

    def test_an_operation_key_must_be_a_short_text(self):
        self._rejects(
            lambda b: self.Node.create_folder(self.root.id, "key", b),
            (None, 5, "", ["k"], "k" * 201),
        )

    def test_content_must_be_bytes_or_base64(self):
        parent = self.root.id
        self._rejects(
            lambda b: self.Node.create_file(parent, "bad.txt", b, "op-a18"),
            (None, 5, ["x"], {"x": 1}, "abc"),
        )
        self._rejects(
            lambda b: self.Node.create_new_revision(
                self.file.id, self.file.current_revision_id.id, b, "op-a19"
            ),
            (None, 5, "abc"),
        )

    def test_the_names_of_an_availability_check_must_be_a_list_of_texts(self):
        self._rejects(
            lambda b: self.Node.existing_names(self.root.id, b),
            (None, "a", [1], [["a"]], ["a"] * 10001),
        )

    # --- origin --------------------------------------------------------------

    def test_a_client_cannot_name_an_origin_only_the_server_has(self):
        base = self.file.current_revision_id.id
        self._rejects(
            lambda b: self.Node.create_new_revision(
                self.file.id, base, b"new", "op-a20", origin=b
            ),
            ("import", "webdav", "office", "restore", "copy", None, 5),
        )
        for origin in ("upload", "edit"):
            result = self.Node.create_new_revision(
                self.file.id, base, origin.encode(), f"op-a21-{origin}", origin=origin
            )
            base = result["revision_id"]
            revision = self.env["int_filemanager.revision"].sudo().browse(base)
            self.assertEqual(revision.origin, origin)

    # --- values --------------------------------------------------------------

    def test_confirmed_values_are_checked_before_anything_is_stored(self):
        revision = self.file.current_revision_id.id
        field = self.number
        bad_values = (
            None,
            "x",
            [None],
            ["x"],
            [{}],
            [{"field_id": "1"}],
            [{"field_id": field.id, "text": 5}],
            [{"field_id": field.id, "text": "1", "rule_id": "7"}],
            [{"field_id": 0, "text": "1"}],
            [{"field_id": field.id, "text": "1"}] * 201,
        )
        self._rejects(
            lambda b: self.Node.apply_field_values(self.file.id, revision, b),
            bad_values,
        )
        self._rejects(
            lambda b: self.Node.apply_field_values(self.file.id, revision, [], b),
            ("1", [1], True, -1),
        )
        self._rejects(
            lambda b: self.Node.apply_field_values(
                self.file.id, revision, [], False, b
            ),
            ("1", [None], ["1"], [1] * 101),
        )
        self.assertFalse(self.file.field_value_ids)

    def test_a_rule_deleted_since_the_suggestion_is_no_longer_named(self):
        revision = self.file.current_revision_id.id
        stored = self.Node.apply_field_values(
            self.file.id,
            revision,
            [
                {
                    "field_id": self.number.id,
                    "text": "4711",
                    "source": "rule",
                    "rule_id": 987654,
                }
            ],
        )
        self.assertEqual(stored, {self.number.id: "4711"})
        self.assertFalse(self.file.field_value_ids.rule_id)

    def test_a_marking_needs_a_field_id(self):
        revision = self.file.current_revision_id.id
        self._rejects(
            lambda b: self.Node.read_selection(self.file.id, revision, b, 0, 1),
            BAD_IDS,
        )

    # --- read-only marks -----------------------------------------------------

    def test_the_reading_methods_are_marked_read_only(self):
        reading = (
            "tree_children",
            "breadcrumb",
            "existing_names",
            "suggest_field_values",
            "page_words",
            "read_selection",
        )
        for name in reading:
            with self.subTest(method=name):
                self.assertTrue(getattr(getattr(self.Node, name), "_readonly", False))

    def test_the_writing_methods_are_not_marked_read_only(self):
        writing = (
            "create_file",
            "create_folder",
            "create_new_revision",
            "restore_version",
            "copy_node",
            "rename_or_move",
            "trash",
            "restore",
            "delete_permanently",
            "request_previews",
            "request_text",
            "apply_field_values",
        )
        for name in writing:
            with self.subTest(method=name):
                self.assertFalse(getattr(getattr(self.Node, name), "_readonly", False))

    # --- values_json ---------------------------------------------------------

    def test_values_json_is_not_computed_for_nodes_the_caller_cannot_read(self):
        hidden_scope = (
            self.env["int_filemanager.scope"].sudo().create({"name": "Hidden"})
        )
        hidden = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "hidden.txt", "scope_id": hidden_scope.id})
        )
        nodes = self.Node.browse([self.file.id, hidden.id])
        # Reading one of them computes the field for the whole prefetch set.
        with patch.object(
            type(self.env["int_filemanager.node"]),
            "_suggest_values",
            autospec=True,
            side_effect=lambda *a, **k: {"state": "none"},
        ) as suggest:
            self.assertEqual(nodes[0].values_json, {"state": "none"})
        self.assertEqual(
            [call.args[1].id for call in suggest.call_args_list], [self.file.id]
        )

    def test_values_json_of_a_folder_is_empty(self):
        self.assertFalse(self.Node.browse(self.root.id).values_json)


@tagged("post_install", "-at_install")
class TestCopyAndPurge(TransactionCase):
    def setUp(self):
        super().setUp()
        self.scope = (
            self.env["int_filemanager.scope"].sudo().create({"name": "Copy scope"})
        )
        self.Node = self.env["int_filemanager.node"].sudo()
        self.root = self.Node.create(
            {"name": "copy-root", "scope_id": self.scope.id, "is_dir": True}
        )

    def _folder(self, parent, name):
        return self.Node.browse(
            self.Node.create_folder(parent.id, name, f"op-cp-{name}-{parent.id}")[
                "node_id"
            ]
        )

    def _file(self, parent, name):
        result = self.Node.create_file(
            parent.id, name, name.encode(), f"op-cp-{name}-{parent.id}"
        )
        return self.Node.browse(result["node_id"])

    # --- copy ----------------------------------------------------------------

    def test_a_folder_is_copied_in_a_call_per_level_not_per_node(self):
        top = self._folder(self.root, "top")
        sub = self._folder(top, "sub")
        for i in range(5):
            self._file(top, f"a{i}.txt")
            self._file(sub, f"b{i}.txt")
        Revision = self.env["int_filemanager.revision"]
        node_create = type(self.Node)._create_nodes
        revision_create = type(Revision).create

        with (
            patch.object(
                type(self.Node),
                "_create_nodes",
                autospec=True,
                side_effect=lambda *a, **k: node_create(*a, **k),
            ) as nodes,
            patch.object(
                type(Revision),
                "create",
                autospec=True,
                side_effect=lambda *a, **k: revision_create(*a, **k),
            ) as revisions,
        ):
            result = self.Node.copy_node(top.id, self.root.id, "top copy", "op-cp-1")

        self.assertEqual(result["copied"], 12)
        # the copy of the folder itself, then one call for each level below it
        self.assertEqual(nodes.call_count, 3)
        self.assertEqual(revisions.call_count, 1)

    def test_copied_files_say_they_are_copies(self):
        top = self._folder(self.root, "top")
        self._file(top, "one.txt")
        single = self._file(self.root, "single.txt")

        result = self.Node.copy_node(top.id, self.root.id, "top copy", "op-cp-2")
        single_copy = self.Node.copy_node(single.id, self.root.id, "s2.txt", "op-cp-3")

        copied = self.Node.browse(result["node_id"]).search(
            [("id", "child_of", result["node_id"]), ("is_dir", "=", False)]
        )
        revisions = (
            copied.revision_ids | self.Node.browse(single_copy["node_id"]).revision_ids
        )
        self.assertEqual(len(revisions), 2)
        self.assertEqual(set(revisions.mapped("origin")), {"copy"})
        self.assertEqual(set(revisions.mapped("revision_no")), {1})
        self.assertEqual(
            single_copy["revision_id"],
            self.Node.browse(single_copy["node_id"]).current_revision_id.id,
        )

    # --- purge ---------------------------------------------------------------

    def _expired(self, count):
        files = [self._file(self.root, f"old{i}.txt") for i in range(count)]
        for i, node in enumerate(files):
            self.Node.trash(node.id, f"op-cp-trash-{i}")
        self.Node.browse([n.id for n in files]).with_context(active_test=False).write(
            {"trashed_at": fields.Datetime.now() - timedelta(days=60)}
        )
        return self.Node.browse([n.id for n in files])

    def test_the_purge_takes_at_most_a_limit_of_subtrees(self):
        expired = self._expired(3)
        self.assertEqual(len(self.Node._expired_trash_roots(2)), 2)
        self.assertEqual(self.Node._expired_trash_roots(), expired)
        self.assertEqual(self.Node._purge_expired_trash(limit=2), 2)
        self.assertEqual(len(expired.with_context(active_test=False).exists()), 1)

    def test_only_the_top_of_an_expired_subtree_is_a_root(self):
        folder = self._folder(self.root, "folder")
        child = self._file(folder, "child.txt")
        self.Node.trash(folder.id, "op-cp-trash-folder")
        (folder + child).with_context(active_test=False).write(
            {"trashed_at": fields.Datetime.now() - timedelta(days=60)}
        )
        self.assertEqual(self.Node._expired_trash_roots(), folder)

    def test_the_cron_reports_its_progress_and_commits_per_subtree(self):
        expired = self._expired(3)
        cron = type(self.env["ir.cron"])
        with patch.object(
            cron, "_commit_progress", autospec=True, return_value=float("inf")
        ) as progress:
            self.Node._cron_purge_trash(limit=2)
        self.assertEqual(
            [(c.args[1:], c.kwargs) for c in progress.call_args_list],
            [((), {"remaining": 3}), ((1,), {}), ((1,), {})],
        )
        self.assertEqual(len(expired.with_context(active_test=False).exists()), 1)

    def test_the_cron_stops_when_the_time_is_up(self):
        expired = self._expired(3)
        cron = type(self.env["ir.cron"])
        answers = iter([float("inf"), 0.0])  # the start, then no time left
        with patch.object(
            cron,
            "_commit_progress",
            autospec=True,
            side_effect=lambda *a, **k: next(answers),
        ):
            self.Node._cron_purge_trash()
        self.assertEqual(len(expired.with_context(active_test=False).exists()), 2)

    def test_a_subtree_that_cannot_go_does_not_stop_the_others(self):
        expired = self._expired(2)
        unlink = type(self.Node)._unlink_subtree

        def unlink_unless_first(this, root):
            if root == expired[0]:
                raise psycopg2.Error("held back")
            return unlink(this, root)

        with patch.object(
            type(self.Node),
            "_unlink_subtree",
            autospec=True,
            side_effect=unlink_unless_first,
        ):
            self.assertEqual(self.Node._purge_expired_trash(), 1)
        self.assertTrue(expired[0].with_context(active_test=False).exists())
        self.assertFalse(expired[1].with_context(active_test=False).exists())
