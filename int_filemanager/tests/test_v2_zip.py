"""ZIP downloads (Schritt 4a-4): what goes into the archive under whose rights, the
streamed archive itself, the direct route and the background job for big selections."""

import io
import os
import zipfile
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import HttpCase, TransactionCase, tagged
from odoo.tools import config

from .. import zip_stream


class _ZipFixture:
    """A scope everybody in the group can use, a second scope nobody in it can read, and
    a small tree: root/{a.txt, sub/{b.txt, empty/}, secret/(other scope){s.txt}}."""

    def _make_fixture(self):
        env = self.env
        Group = env["res.groups"].sudo()
        self.group = Group.create({"name": "Zip group"})
        self.other_group = Group.create({"name": "Zip other group"})
        Scope = env["int_filemanager.scope"].sudo()
        scope = Scope.create(
            {
                "name": "Zip scope",
                "read_group_ids": [(4, self.group.id)],
                "write_group_ids": [(4, self.group.id)],
            }
        )
        secret_scope = Scope.create(
            {
                "name": "Zip secret scope",
                "read_group_ids": [(4, self.other_group.id)],
                "write_group_ids": [(4, self.other_group.id)],
            }
        )
        base_group = env.ref("int_filemanager.group_filemanager_user")
        Users = env["res.users"].sudo()
        self.user = Users.create(
            {
                "name": "Zip user",
                "login": "zip_user",
                "password": "zip_user_pw_1",
                "group_ids": [(6, 0, [base_group.id, self.group.id])],
            }
        )
        self.other_user = Users.create(
            {
                "name": "Zip other user",
                "login": "zip_other_user",
                "password": "zip_other_user_pw_1",
                "group_ids": [(6, 0, [base_group.id, self.group.id])],
            }
        )
        self.outsider = Users.create(
            {
                "name": "Zip outsider",
                "login": "zip_outsider",
                "password": "zip_outsider_pw_1",
                "group_ids": [(6, 0, [base_group.id])],
            }
        )
        Node = env["int_filemanager.node"].sudo()
        self.root = Node.create({"name": "root", "scope_id": scope.id, "is_dir": True})
        sub = Node.create(
            {
                "name": "sub",
                "scope_id": scope.id,
                "is_dir": True,
                "parent_id": self.root.id,
            }
        )
        Node.create(
            {"name": "empty", "scope_id": scope.id, "is_dir": True, "parent_id": sub.id}
        )
        secret = Node.create(
            {
                "name": "secret",
                "scope_id": secret_scope.id,
                "is_dir": True,
                "parent_id": self.root.id,
            }
        )
        self.sub = sub
        self.secret = secret
        self.a = self._file(self.root, "a.txt", b"AAA", scope)
        self.b = self._file(sub, "b.txt", b"BBBB", scope)
        self.s = self._file(secret, "s.txt", b"secret!", secret_scope)

    def _file(self, parent, name, content, scope):
        node = (
            self.env["int_filemanager.node"]
            .sudo()
            .create(
                {
                    "name": name,
                    "scope_id": scope.id,
                    "parent_id": parent.id,
                    "is_dir": False,
                }
            )
        )
        result = (
            self.env["int_filemanager.node"]
            .sudo()
            .create_new_revision(node.id, False, content, f"op-zip-{name}-{parent.id}")
        )
        del result
        return node

    def _names(self, entries):
        return sorted(e.arcname for e in entries)


@tagged("post_install", "-at_install")
class TestZipEntries(_ZipFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self._make_fixture()

    def test_folder_selection_lists_files_and_folders_with_relative_paths(self):
        entries, total, name = zip_stream.collect_entries(
            self.env(user=self.user), [self.root.id]
        )

        self.assertEqual(
            self._names(entries),
            ["root/", "root/a.txt", "root/sub/", "root/sub/b.txt", "root/sub/empty/"],
        )
        self.assertEqual(total, 3 + 4)
        self.assertEqual(name, "root.zip")

    def test_nodes_the_user_cannot_read_are_left_out(self):
        entries, _total, _name = zip_stream.collect_entries(
            self.env(user=self.user), [self.root.id]
        )
        self.assertFalse([e for e in entries if "secret" in e.arcname])

    def test_a_selected_node_the_user_cannot_read_is_denied(self):
        with self.assertRaises(AccessError):
            zip_stream.collect_entries(self.env(user=self.user), [self.s.id])

    def test_trashed_nodes_are_left_out(self):
        self.env["int_filemanager.node"].with_user(self.user).trash(
            self.b.id, "op-zip-trash-b"
        )
        entries, _total, _name = zip_stream.collect_entries(
            self.env(user=self.user), [self.root.id]
        )
        self.assertNotIn("root/sub/b.txt", self._names(entries))

    def test_several_selected_items_share_one_archive_name(self):
        entries, _total, name = zip_stream.collect_entries(
            self.env(user=self.user), [self.a.id, self.sub.id]
        )
        self.assertEqual(
            self._names(entries), ["a.txt", "sub/", "sub/b.txt", "sub/empty/"]
        )
        self.assertEqual(name, "files.zip")

    def test_equal_top_level_names_get_a_suffix(self):
        other = self._file(self.sub, "a.txt", b"other", self.root.scope_id)
        entries, _total, _name = zip_stream.collect_entries(
            self.env(user=self.user), [self.a.id, other.id]
        )
        self.assertEqual(self._names(entries), ["a (2).txt", "a.txt"])

    def test_nothing_selected_is_an_error(self):
        with self.assertRaises(UserError):
            zip_stream.collect_entries(self.env(user=self.user), [999999999])

    def test_streamed_archive_is_a_valid_zip_with_the_right_content(self):
        entries, _total, _name = zip_stream.collect_entries(
            self.env(user=self.user), [self.root.id]
        )

        data = b"".join(zip_stream.stream_zip(entries))

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read("root/a.txt"), b"AAA")
            self.assertEqual(archive.read("root/sub/b.txt"), b"BBBB")
            self.assertIn("root/sub/empty/", archive.namelist())

    def test_unicode_names_survive(self):
        node = self._file(self.root, "Grüße ✓.txt", b"x", self.root.scope_id)
        entries, _total, _name = zip_stream.collect_entries(
            self.env(user=self.user), [node.id]
        )
        data = b"".join(zip_stream.stream_zip(entries))
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.namelist(), ["Grüße ✓.txt"])


@tagged("post_install", "-at_install")
class TestZipRoutes(_ZipFixture, HttpCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.dict(config.options, {"x_sendfile": False}))
        self._make_fixture()

    def _get(self, path, login="zip_user"):
        self.authenticate(login, f"{login}_pw_1")
        return self.url_open(path)

    def test_direct_zip_download(self):
        res = self._get(f"/int_filemanager/v2/zip?ids={self.root.id}")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["Content-Type"], "application/zip")
        self.assertIn("root.zip", res.headers["Content-Disposition"])
        with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
            self.assertEqual(archive.read("root/a.txt"), b"AAA")
            self.assertFalse([n for n in archive.namelist() if "secret" in n])

    def test_direct_zip_of_something_unreadable_is_403(self):
        res = self._get(f"/int_filemanager/v2/zip?ids={self.root.id}", "zip_outsider")
        self.assertEqual(res.status_code, 403)

    def test_direct_zip_above_the_limit_is_refused(self):
        self.env["ir.config_parameter"].sudo().set_param(
            zip_stream.DIRECT_MAX_PARAM, "0"
        )
        res = self._get(f"/int_filemanager/v2/zip?ids={self.root.id}")
        self.assertEqual(res.status_code, 409)

    def test_bad_ids_are_400(self):
        self.assertEqual(self._get("/int_filemanager/v2/zip?ids=abc").status_code, 400)
        self.assertEqual(self._get("/int_filemanager/v2/zip").status_code, 400)

    def test_request_zip_small_selection_returns_a_direct_url(self):
        result = (
            self.env["int_filemanager.zip_job"]
            .with_user(self.user)
            .request_zip([self.root.id], "op-zip-req-small")
        )
        self.assertEqual(result["mode"], "direct")
        self.assertIn(str(self.root.id), result["url"])

    def test_request_zip_big_selection_becomes_a_job_built_with_the_users_rights(self):
        self.env["ir.config_parameter"].sudo().set_param(
            zip_stream.DIRECT_MAX_PARAM, "0"
        )
        Job = self.env["int_filemanager.zip_job"]
        result = Job.with_user(self.user).request_zip([self.root.id], "op-zip-req-big")
        self.assertEqual(result["mode"], "job")
        job = Job.sudo().browse(result["job_id"])
        self.assertEqual(job.state, "pending")
        self.assertEqual(job.create_uid, self.user)
        self.assertEqual(
            Job.with_user(self.user).request_zip([self.root.id], "op-zip-req-big"),
            result,
        )

        Job.sudo()._build_one(job)

        self.assertEqual(job.state, "done")
        self.assertTrue(os.path.exists(job._path()))
        status = Job.with_user(self.user).zip_job_status(job.id)
        self.assertEqual(status["state"], "done")
        res = self._get(status["url"])
        self.assertEqual(res.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
            self.assertEqual(archive.read("root/sub/b.txt"), b"BBBB")
            self.assertFalse([n for n in archive.namelist() if "secret" in n])

    def test_someone_elses_job_cannot_be_downloaded_or_seen(self):
        self.env["ir.config_parameter"].sudo().set_param(
            zip_stream.DIRECT_MAX_PARAM, "0"
        )
        Job = self.env["int_filemanager.zip_job"]
        job = Job.sudo().browse(
            Job.with_user(self.user).request_zip([self.root.id], "op-zip-req-priv")[
                "job_id"
            ]
        )
        Job.sudo()._build_one(job)

        res = self._get(f"/int_filemanager/v2/zip/job/{job.id}", "zip_other_user")
        self.assertIn(res.status_code, (403, 404))
        with self.assertRaises(AccessError):
            Job.with_user(self.other_user).zip_job_status(job.id)

    def test_a_job_of_a_user_who_lost_the_right_fails_instead_of_packing(self):
        self.env["ir.config_parameter"].sudo().set_param(
            zip_stream.DIRECT_MAX_PARAM, "0"
        )
        Job = self.env["int_filemanager.zip_job"]
        job = Job.sudo().browse(
            Job.with_user(self.user).request_zip([self.root.id], "op-zip-req-lost")[
                "job_id"
            ]
        )
        self.user.sudo().write({"group_ids": [(3, self.group.id)]})

        Job.sudo()._build_one(job)

        self.assertEqual(job.state, "failed")
        self.assertTrue(job.error)

    def test_users_cannot_create_or_edit_jobs_themselves(self):
        Job = self.env["int_filemanager.zip_job"].with_user(self.user)
        with self.assertRaises(AccessError):
            Job.create({"name": "x.zip", "node_ids_json": [1], "state": "done"})

    def test_expired_jobs_and_their_files_are_removed(self):
        self.env["ir.config_parameter"].sudo().set_param(
            zip_stream.DIRECT_MAX_PARAM, "0"
        )
        Job = self.env["int_filemanager.zip_job"]
        job = Job.sudo().browse(
            Job.with_user(self.user).request_zip([self.root.id], "op-zip-req-exp")[
                "job_id"
            ]
        )
        Job.sudo()._build_one(job)
        path = job._path()
        job.write({"expires_at": "2000-01-01 00:00:00"})

        Job.sudo()._cron_expire_zips()

        self.assertFalse(os.path.exists(path))
        self.assertFalse(job.exists())
