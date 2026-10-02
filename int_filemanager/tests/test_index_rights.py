"""Rights that must hold when a user writes the file index through the ORM.

``int_filemanager.file`` mirrors the disk and drives what the server does with
files, yet the ORM is open to every logged-in user (``call_kw``, ``/json/2``).
Each test plays the attack of a user with the narrowest rights that make it
possible: a row pointed at a path must never be deleted, read, published or
restored, and the methods that work as superuser must not be callable without
the rights check of their route.
"""

import os
import shutil
import tempfile
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.service.model import get_public_method
from odoo.tests.common import HttpCase, TransactionCase, tagged

from .. import publish_service, write_service
from ..index_utils import index_trash_tree, index_upsert, trash_destination
from ..models.filemanager_file import USER_WRITABLE_FIELDS

MAGIC_FIELDS = {
    "id",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "display_name",
}
SECRET_VIA_DOTS = "Open/../Secret/secret.txt"


class IndexRightsCase:
    """Shared fixture: a root with an open and a protected folder, and a second tree."""

    def server_fields(self):
        """Return the fields of the index model a user must not write."""
        return [
            field
            for name, field in self.File._fields.items()
            if field._module == "int_filemanager"
            and name not in USER_WRITABLE_FIELDS
            and name not in MAGIC_FIELDS
        ]

    def setup_tree(self):
        # Crons commit per record; a test cannot commit.
        self.env.cr.commit = lambda: None
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="int_fm_rights_root_"))
        self.outside_dir = os.path.realpath(
            tempfile.mkdtemp(prefix="int_fm_rights_out_")
        )
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.outside_dir, ignore_errors=True)
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("int_filemanager.root_path", self.root)
        self.File = self.env["int_filemanager.file"].sudo()

        self.base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.secret_group = (
            self.env["res.groups"].sudo().create({"name": "Index rights secret"})
        )
        self.env["int_filemanager.protected_folder"].sudo().create(
            {
                "path": "Secret",
                "read_group_ids": [(4, self.secret_group.id)],
                "write_group_ids": [(4, self.secret_group.id)],
                "unlink_group_ids": [(4, self.secret_group.id)],
            }
        )
        self.member = self._make_user("member")
        self.other = self._make_user("other")

        self.open_folder = self._make_entry("Open", is_dir=True)
        self.secret_folder = self._make_entry("Secret", is_dir=True)
        self.mine = self._make_entry("Open/mine.txt", b"mine")
        self.secret = self._make_entry("Secret/secret.txt", b"top secret")

        self.outside_file = os.path.join(self.outside_dir, "loot.txt")
        with open(self.outside_file, "wb") as f:
            f.write(b"outside the root")
        self.outside_rel = os.path.relpath(self.outside_file, self.root)

    def _make_user(self, login):
        internal_group = self.env.ref("base.group_user")
        return (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": f"Index rights {login}",
                    "login": f"index_rights_{login}",
                    "group_ids": [(6, 0, [internal_group.id, self.base_group.id])],
                }
            )
        )

    def _make_entry(self, rel, content=b"x", is_dir=False):
        abs_path = os.path.join(self.root, rel)
        if is_dir:
            os.makedirs(abs_path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "wb") as f:
                f.write(content)
        return index_upsert(self.env, abs_path)

    def _forged_row(self, path, **vals):
        """Create a row of the kind a user used to be able to create."""
        return self.File.create(
            {"name": os.path.basename(path), "path": path, "is_dir": False, **vals}
        )

    def _trash(self, rel, user):
        trash_rel = trash_destination(self.env, rel)
        shutil.move(os.path.join(self.root, rel), os.path.join(self.root, trash_rel))
        return index_trash_tree(self.env(user=user), rel, trash_rel)

    def _pattern(self):
        return (
            self.env["int_filemanager.extraction_pattern"]
            .sudo()
            .create({"name": "IBAN", "target_field": "iban", "pattern": r"DE\d+"})
        )


@tagged("post_install", "-at_install")
class TestIndexRights(IndexRightsCase, TransactionCase):
    def setUp(self):
        super().setUp()
        self.setup_tree()

    def _as_member(self, record):
        return record.with_user(self.member)

    def _disk(self, rel):
        return os.path.join(self.root, rel)

    # -- the index is not the user's to create or rewrite ---------------------

    def test_user_cannot_create_an_index_row(self):
        with self.assertRaises(AccessError):
            self._as_member(self.File).create(
                {
                    "name": "planted",
                    "path": SECRET_VIA_DOTS,
                    "trashed": True,
                    "trashed_by": self.member.id,
                }
            )

    def test_user_cannot_write_any_server_field(self):
        server_fields = self.server_fields()
        self.assertGreater(len(server_fields), 40, "the loop did not see the model")
        for field in server_fields:
            with self.subTest(field=field.name), self.assertRaises(AccessError):
                self._as_member(self.mine).write({field.name: False})

    def test_fields_get_marks_every_server_field_readonly(self):
        description = self._as_member(self.File).fields_get()
        for field in self.server_fields():
            with self.subTest(field=field.name):
                self.assertTrue(description[field.name]["readonly"])

    def test_user_writable_fields_exist_and_stay_writable(self):
        self.assertLessEqual(USER_WRITABLE_FIELDS, set(self.File._fields))
        self._as_member(self.mine).write(
            {"partner_id": False, "tag_ids": [(5, 0, 0)], "status_id": False}
        )
        self._as_member(self.mine).write({"shared_partner_ids": [(5, 0, 0)]})

    def test_share_link_cannot_be_forged_through_write(self):
        with self.assertRaises(AccessError):
            self._as_member(self.mine).write(
                {
                    "share_token": "known-token",
                    "share_expires_at": fields.Datetime.now() + timedelta(days=30),
                }
            )

    def test_server_fields_stay_writable_for_the_server(self):
        self.mine.write({"ocr_state": "pending", "content_text": "text"})
        self.assertEqual(self.mine.ocr_state, "pending")

    def test_public_methods_of_the_index_model_are_the_reviewed_ones(self):
        """A new public method must check the rights first, like ``action_restore``."""
        cls = type(self.File)
        own = {
            name
            for name in dir(cls)
            if not name.startswith("_")
            and callable(getattr(cls, name))
            and getattr(getattr(cls, name), "__module__", "").startswith(
                "odoo.addons.int_filemanager"
            )
        }
        self.assertEqual(
            own,
            {
                "write",
                "unlink",
                "action_restore",
                "action_generate_share_token",
                "action_revoke_share_token",
            },
        )

    # -- N1: the methods that work as superuser are not reachable by RPC ------

    def test_analyze_and_apply_are_not_public_methods(self):
        Model = self._as_member(self.File)
        for name in ("action_analyze_document", "action_apply_extracted_values"):
            with self.subTest(name=name), self.assertRaises(AttributeError):
                get_public_method(Model, name)
        for name in ("_analyze_document", "_apply_extracted_values"):
            with self.subTest(name=name), self.assertRaises(AccessError):
                get_public_method(Model, name)

    # -- recognised values: input of the review dialog ------------------------

    def test_confirmed_values_are_validated(self):
        pattern = self._pattern()
        valid = {"pattern_id": pattern.id, "value": "DE1"}
        invalid = [
            "text",
            valid,
            [1],
            [{**valid, "pattern_id": str(pattern.id)}],
            [{**valid, "pattern_id": True}],
            [{**valid, "pattern_id": 999999999}],
            [{**valid, "value": ["DE1"]}],
            [{**valid, "value": "x" * 1001}],
            [{**valid, "page": "1"}],
            [{**valid, "page": -1}],
            [{**valid, "x0": "1.0"}],
            [{**valid, "y1": float("nan")}],
            [{}] * 201,
        ]
        for values in invalid:
            with self.subTest(values=str(values)[:60]), self.assertRaises(UserError):
                self.File._clean_extracted_values(values)

    def test_confirmed_values_are_turned_into_rows(self):
        pattern = self._pattern()
        box = {"page": 1, "x0": 1.5, "y0": 2, "x1": 3, "y1": 4}
        rows = self.File._clean_extracted_values(
            [
                {"pattern_id": pattern.id, "value": "DE1", **box},
                {"pattern_id": pattern.id, "value": ""},
                {},
            ]
        )
        self.assertEqual(rows, [(pattern.id, "DE1", 1, 1.5, 2, 3, 4)])

    def test_invalid_values_keep_the_existing_ones(self):
        pattern = self._pattern()
        good = [{"pattern_id": pattern.id, "value": "DE1"}]
        bad = [{"pattern_id": pattern.id, "value": 5}]
        self.File._apply_extracted_values("Open/mine.txt", good)
        self.assertEqual(self.mine.extracted_value_ids.mapped("value"), ["DE1"])
        with self.assertRaises(UserError):
            self.File._apply_extracted_values("Open/mine.txt", bad)
        self.assertEqual(self.mine.extracted_value_ids.mapped("value"), ["DE1"])

    # -- deleting: only the trash, only below .trash --------------------------

    def test_user_cannot_delete_a_live_row(self):
        with self.assertRaises(AccessError):
            self._as_member(self.mine).unlink()
        self.assertTrue(self.mine.exists())
        self.assertTrue(os.path.isfile(self._disk("Open/mine.txt")))

    def test_user_deletes_the_own_trash_entry_with_its_bytes(self):
        trashed = self._trash("Open/mine.txt", self.member)
        trash_abs = self._disk(trashed.path)
        self.assertTrue(os.path.exists(trash_abs))
        self._as_member(trashed).unlink()
        self.assertFalse(trashed.exists())
        self.assertFalse(os.path.exists(trash_abs))

    def test_user_cannot_delete_the_trash_entry_of_another_user(self):
        trashed = self._trash("Open/mine.txt", self.other)
        with self.assertRaises(AccessError):
            self._as_member(trashed).unlink()
        self.assertTrue(os.path.exists(self._disk(trashed.path)))

    def test_trashed_row_outside_the_trash_never_deletes_the_disk(self):
        """What the old unlink did: ``rmtree`` of whatever ``path`` said."""
        targets = {
            "protected": SECRET_VIA_DOTS,
            "dot dot": ".trash/../Secret/secret.txt",
            "outside the root": self.outside_rel,
            "absolute": self.outside_file,
        }
        for label, path in targets.items():
            with self.subTest(target=label):
                row = self._forged_row(path, trashed=True, trashed_by=self.member.id)
                with self.assertRaises(AccessError):
                    self._as_member(row).unlink()
                row.unlink()
                self.assertTrue(os.path.isfile(self._disk("Secret/secret.txt")))
                self.assertTrue(os.path.isfile(self.outside_file))

    def test_trashed_folder_row_outside_the_trash_keeps_the_folder(self):
        row = self._forged_row(
            "Open/../Open", trashed=True, trashed_by=self.member.id, is_dir=True
        )
        row.unlink()
        self.assertTrue(os.path.isdir(self._disk("Open")))
        self.assertTrue(os.path.isfile(self._disk("Open/mine.txt")))

    # -- restoring ------------------------------------------------------------

    def test_user_restores_the_own_trash_entry(self):
        trashed = self._trash("Open/mine.txt", self.member)
        action = self._as_member(trashed).action_restore()
        self.assertEqual(action["tag"], "display_notification")
        self.assertTrue(os.path.isfile(self._disk("Open/mine.txt")))
        self.assertFalse(trashed.trashed)

    def test_live_entry_cannot_be_restored(self):
        with self.assertRaises(UserError):
            self._as_member(self.mine).action_restore()

    def test_trash_entry_of_another_user_cannot_be_restored(self):
        trashed = self._trash("Open/mine.txt", self.other)
        with self.assertRaises(AccessError):
            self._as_member(trashed).action_restore()
        self.assertTrue(os.path.exists(self._disk(trashed.path)))

    def test_restore_into_a_folder_the_user_may_no_longer_write_is_refused(self):
        trashed = self._trash("Open/mine.txt", self.member)
        self.env["int_filemanager.protected_folder"].sudo().create(
            {"path": "Open", "write_group_ids": [(4, self.secret_group.id)]}
        )
        with self.assertRaises(AccessError):
            self._as_member(trashed).action_restore()
        self.assertTrue(os.path.exists(self._disk(trashed.path)))

    def test_forged_original_path_cannot_restore_a_live_file(self):
        """The row points at a live file as if it were in the trash."""
        row = self._forged_row(
            SECRET_VIA_DOTS,
            trashed=True,
            trashed_by=self.member.id,
            original_path="Open/moved.txt",
            folder_path=".trash",
        )
        with self.assertRaises(UserError):
            self._as_member(row).action_restore()
        self.assertTrue(os.path.isfile(self._disk("Secret/secret.txt")))
        self.assertFalse(os.path.exists(self._disk("Open/moved.txt")))

    # -- renaming and sharing keep working for the user -----------------------

    def test_user_renames_one_entry_on_the_disk(self):
        self._as_member(self.mine).write({"name": "renamed.txt"})
        self.assertTrue(os.path.isfile(self._disk("Open/renamed.txt")))
        self.assertFalse(os.path.exists(self._disk("Open/mine.txt")))

    def test_name_cannot_be_written_to_several_rows_at_once(self):
        second = self._make_entry("Open/second.txt")
        with self.assertRaises(UserError):
            self._as_member(self.mine | second).write({"name": "same.txt"})
        self.assertEqual(self.mine.name, "mine.txt")

    def test_user_creates_and_revokes_a_share_link(self):
        self._as_member(self.mine).action_generate_share_token()
        self.assertTrue(self.mine.share_token)
        self.assertTrue(self.mine.share_expires_at)
        self._as_member(self.mine).action_revoke_share_token()
        self.assertFalse(self.mine.share_token)

    def test_share_link_needs_the_write_right_on_the_file(self):
        with self.assertRaises(AccessError):
            self._as_member(self.secret).action_generate_share_token()
        self.assertFalse(self.secret.share_token)

    # -- every place that turns a path into a disk access ---------------------

    def test_hash_cron_does_not_read_outside_the_root(self):
        row = self._forged_row(self.outside_rel, hash_state="pending")
        self.File._cron_compute_hashes()
        self.assertEqual(row.hash_state, "error")
        self.assertFalse(row.content_sha256)

    def test_text_extraction_does_not_read_outside_the_root(self):
        row = self._forged_row(self.outside_rel, ocr_state="pending")
        self.File._cron_extract_fulltext()
        self.assertEqual(row.ocr_state, "error")
        self.assertFalse(row.content_text)

    def test_metadata_cron_does_not_read_outside_the_root(self):
        outside_pdf = os.path.join(self.outside_dir, "loot.pdf")
        with open(outside_pdf, "wb") as f:
            f.write(b"%PDF-1.4")
        rel = os.path.relpath(outside_pdf, self.root)
        row = self._forged_row(rel, meta_state="pending")
        self.File._cron_extract_media_meta()
        self.assertEqual(row.meta_state, "error")
        self.assertEqual(row.meta_error, "path outside the root")

    def test_publishing_refuses_a_path_outside_the_root(self):
        row = self._forged_row(self.outside_rel)
        with self.assertRaises(ValidationError):
            publish_service.stage_overwrite(self.env, row, b"overwritten")
        with open(self.outside_file, "rb") as f:
            self.assertEqual(f.read(), b"outside the root")

    def test_snapshot_write_refuses_a_path_outside_the_root(self):
        row = self._forged_row(self.outside_rel)
        with self.assertRaises(ValidationError):
            write_service.snapshot_and_write(
                self.env, row, b"overwritten", operation="restore"
            )
        with open(self.outside_file, "rb") as f:
            self.assertEqual(f.read(), b"outside the root")


@tagged("post_install", "-at_install")
class TestIndexRightsHttp(IndexRightsCase, HttpCase):
    def setUp(self):
        super().setUp()
        self.setup_tree()
        partner = self.env["res.partner"].sudo().create({"name": "Index rights portal"})
        self.portal_user = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Index rights portal",
                    "login": "index_rights_portal",
                    "partner_id": partner.id,
                    "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
                }
            )
        )

    def _rpc(self, route, params):
        return self.url_open(
            route,
            json={"jsonrpc": "2.0", "method": "call", "params": params, "id": 1},
        ).json()

    def _soon(self):
        return fields.Datetime.now() + timedelta(days=1)

    def _login(self, login):
        self.authenticate(login, login)

    def _error_name(self, answer):
        return answer["error"]["data"]["name"]

    # -- anonymous share link -------------------------------------------------

    def test_share_link_serves_a_file_inside_the_root(self):
        self.mine.write({"share_token": "tok-inside", "share_expires_at": self._soon()})
        response = self.url_open("/int_filemanager/share/tok-inside")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"mine")

    def test_share_link_never_serves_a_path_outside_the_root(self):
        row = self._forged_row(
            self.outside_rel, share_token="tok-outside", share_expires_at=self._soon()
        )
        self.assertTrue(row.exists())
        response = self.url_open("/int_filemanager/share/tok-outside")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"outside the root", response.content)

    # -- portal download ------------------------------------------------------

    def test_portal_download_serves_a_shared_file_inside_the_root(self):
        self.mine.write({"shared_partner_ids": [(4, self.portal_user.partner_id.id)]})
        self._login("index_rights_portal")
        response = self.url_open(f"/my/shared_files/{self.mine.id}/download")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"mine")

    def test_portal_download_never_serves_a_path_outside_the_root(self):
        row = self._forged_row(
            self.outside_rel,
            shared_partner_ids=[(4, self.portal_user.partner_id.id)],
        )
        self._login("index_rights_portal")
        response = self.url_open(f"/my/shared_files/{row.id}/download")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"outside the root", response.content)

    # -- N1: the routes check the rights on the real path ---------------------

    def test_analyze_route_refuses_a_protected_path(self):
        self._login("index_rights_member")
        answer = self._rpc(
            "/int_filemanager/analyze_document", {"path": "Secret/secret.txt"}
        )
        self.assertEqual(self._error_name(answer), "odoo.exceptions.AccessError")
        self.assertNotIn("result", answer)

    def test_analyze_route_works_on_a_writable_path(self):
        self._login("index_rights_member")
        answer = self._rpc(
            "/int_filemanager/analyze_document", {"path": "Open/mine.txt"}
        )
        self.assertEqual(answer["result"]["res_id"], self.mine.id)

    def test_apply_route_refuses_a_protected_path(self):
        pattern = self._pattern()
        self._login("index_rights_member")
        answer = self._rpc(
            "/int_filemanager/apply_extracted_values",
            {
                "path": "Secret/secret.txt",
                "values": [{"pattern_id": pattern.id, "value": "DE1"}],
            },
        )
        self.assertEqual(self._error_name(answer), "odoo.exceptions.AccessError")
        self.assertFalse(self.secret.extracted_value_ids)

    def test_apply_route_answers_bad_input_with_a_message(self):
        self._login("index_rights_member")
        bad_inputs = (
            "text",
            [1],
            [{"pattern_id": "x", "value": "v"}],
            [{"pattern_id": 999999999, "value": "v"}],
        )
        for values in bad_inputs:
            with self.subTest(values=str(values)):
                answer = self._rpc(
                    "/int_filemanager/apply_extracted_values",
                    {"path": "Open/mine.txt", "values": values},
                )
                self.assertEqual(self._error_name(answer), "odoo.exceptions.UserError")

    def test_apply_route_stores_valid_values(self):
        pattern = self._pattern()
        self._login("index_rights_member")
        answer = self._rpc(
            "/int_filemanager/apply_extracted_values",
            {
                "path": "Open/mine.txt",
                "values": [{"pattern_id": pattern.id, "value": "DE1", "page": 1}],
            },
        )
        self.assertIs(answer["result"], True)
        self.assertEqual(self.mine.extracted_value_ids.mapped("value"), ["DE1"])
