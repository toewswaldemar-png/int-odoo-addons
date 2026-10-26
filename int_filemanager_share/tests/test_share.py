import uuid
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, freeze_time, tagged
from odoo.tools import mute_logger

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase


PASSWORD = "a long password"


@tagged("post_install", "-at_install")
class TestShare(AccessCase, TransactionCase):
    """A link for guests: what it is made of, who may make it, what the code alone sets."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Share = cls.env["int.filemanager.share"]
        cls.Config = cls.env["ir.config_parameter"]
        cls.company2 = cls.env["res.company"].create({"name": "Other company"})

    def setUp(self):
        super().setUp()
        self.document = self._document(self.shared, "a.txt", b"hello")

    def _share(self, target, user=None, **values):
        key = "folder_id" if target._name == "int.filemanager.folder" else "document_id"
        return self.Share.with_user(user or self.alice).create({key: target.id, **values})

    # --- what it is made of -----------------------------------------------------------------

    def test_the_name_starts_as_the_name_of_the_target_and_can_be_chosen(self):
        self.assertEqual(self._share(self.shared).name, "Shared")
        self.assertEqual(self._share(self.document).name, "a.txt")
        self.assertEqual(self._share(self.shared, name="For Bob").name, "For Bob")

    def test_the_token_is_a_random_uuid_and_makes_the_address(self):
        first, second = self._share(self.shared), self._share(self.shared)
        self.assertEqual(str(uuid.UUID(first.token)), first.token)
        self.assertNotEqual(first.token, second.token)
        self.assertEqual(first.url, f"{first.get_base_url()}/int_filemanager/share/{first.token}")

    def test_a_share_has_a_folder_or_a_file_as_its_target(self):
        values = {"name": "x", "folder_id": self.shared.id, "document_id": self.document.id}
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Share.create(values)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Share.create({"name": "x"})

    def test_the_target_cannot_be_changed(self):
        share = self._share(self.shared)
        share.write({"folder_id": self.shared.id})  # the same: not a change
        with self.assertRaises(UserError):
            share.write({"folder_id": self.deep.id})
        with self.assertRaises(UserError):
            share.write({"folder_id": False, "document_id": self.document.id})
        with self.assertRaises(UserError):
            self._share(self.document).write({"document_id": False, "folder_id": self.shared.id})

    def test_the_guests_get_at_least_one_right(self):
        with self.assertRaises(ValidationError):
            self._share(self.shared, can_view=False, can_download=False)
        share = self._share(self.shared, can_view=False, can_download=False, can_upload=True)
        with self.assertRaises(ValidationError):
            share.can_upload = False

    def test_uploading_is_for_folders_and_a_limit_of_downloads_for_files(self):
        with self.assertRaises(ValidationError):
            self._share(self.document, can_upload=True)
        with self.assertRaises(ValidationError):
            self._share(self.shared, max_downloads=3)
        self._share(self.document, max_downloads=3)
        self._share(self.shared, can_upload=True)

    def test_the_expiration_date_is_in_the_future(self):
        with self.assertRaises(ValidationError):
            self._share(self.shared, expiration_date=fields.Datetime.now() - timedelta(minutes=1))
        share = self._share(self.shared, expiration_date=fields.Datetime.now() + timedelta(days=1))
        with self.assertRaises(ValidationError):
            share.expiration_date = fields.Datetime.now() - timedelta(minutes=1)

    def test_the_state_says_why_a_link_does_not_work(self):
        share = self._share(self.shared, expiration_date=fields.Datetime.now() + timedelta(days=1))
        self.assertEqual(share.state, "valid")
        with freeze_time(fields.Datetime.now() + timedelta(days=2)):
            share.invalidate_recordset(["state"])
            self.assertEqual(share.state, "expired")
        share.action_archive()
        self.assertEqual(share.state, "blocked")
        share.action_unarchive()
        self.assertEqual(share.state, "valid")

        limited = self._share(self.document, max_downloads=2)
        self.assertEqual(limited.state, "valid")
        limited.sudo().download_count = 2
        self.assertEqual(limited.state, "limit")
        unlimited = self._share(self.document)
        unlimited.sudo().download_count = 5
        self.assertEqual(unlimited.state, "valid")

        fresh = self._share(self.document)
        self.document.active = False
        self.assertEqual(fresh.state, "archived")

    def test_a_copy_gets_a_new_token_and_starts_from_nothing(self):
        share = self._share(self.document, password=PASSWORD, max_downloads=3)
        share.sudo().write({"download_count": 2, "view_count": 4, "last_access": fields.Datetime.now()})
        copy = share.copy()
        self.assertNotEqual(copy.token, share.token)
        self.assertFalse(copy.has_password)
        self.assertEqual((copy.download_count, copy.view_count, copy.upload_count), (0, 0, 0))
        self.assertFalse(copy.last_access)
        self.assertEqual(copy.max_downloads, 3)

    def test_the_company_is_that_of_the_target_and_cuts_the_rule(self):
        foreign = self.Folder.create(
            {"name": "Foreign", "access_mode": "open", "company_id": self.company2.id}
        )
        free = self.Folder.create({"name": "Free", "access_mode": "open", "company_id": False})
        mine, without = self._share(self.shared), self._share(free)
        other = self.Share.create({"folder_id": foreign.id})
        self.assertEqual((mine.company_id, other.company_id), (self.shared.company_id, self.company2))
        self.assertFalse(without.company_id)
        # The rule of the companies cuts the one of the administrators, who see all shares.
        seen = self.Share.with_user(self.boss).search([])
        self.assertCountEqual(seen.ids, (mine + without).ids)
        self.boss.company_ids += self.company2
        both = [self.company2.id, self.boss.company_id.id]
        seen = self.Share.with_user(self.boss).with_context(allowed_company_ids=both).search([])
        self.assertCountEqual(seen.ids, (mine + without + other).ids)

    def test_a_document_knows_the_share_it_came_in_through(self):
        share = self._share(self.shared)
        self.document.share_id = share
        self.assertNotIn("share_id", self.document.copy_data()[0])
        share.unlink()
        self.assertFalse(self.document.share_id)

    def test_a_share_ends_with_its_target(self):
        share = self._share(self.document)
        self.document.unlink()
        self.assertFalse(share.exists())

    # --- who may make one -------------------------------------------------------------------

    def test_a_user_gives_what_the_folders_show_to_them(self):
        with self.assertRaises(AccessError):
            self._share(self.secret)
        with self.assertRaises(AccessError):
            self._share(self._document(self.secret, "s.txt", b"secret"))
        self._invite(self.secret, self.alice)
        self._share(self.secret)
        self._share(self._document(self.secret, "t.txt", b"t"))

    def test_the_setting_can_leave_the_making_to_the_administrators(self):
        self.Config.set_param("int_filemanager.share_creators", "admin")
        with self.assertRaises(AccessError):
            self._share(self.shared)
        self._share(self.shared, user=self.boss)
        self.Config.set_param("int_filemanager.share_creators", "user")
        self._share(self.shared)

    def test_a_user_sees_and_changes_their_own_shares_the_administrators_all(self):
        share = self._share(self.shared)
        self.assertEqual(self.Share.with_user(self.alice).search([]), share)
        self.assertFalse(self.Share.with_user(self.bob).search([]))
        self.assertEqual(self.Share.with_user(self.boss).search([]), share)
        for operation in ("read", "write", "unlink"):
            with self.assertRaises(AccessError):
                share.with_user(self.bob).check_access(operation)
        share.with_user(self.boss).write({"name": "Changed"})
        with self.assertRaises(AccessError):
            self.Share.with_user(self.outsider).search([])

    def test_a_share_stays_when_the_maker_loses_the_folder(self):
        self._invite(self.secret, self.alice)
        share = self._share(self.secret)
        self.secret.write({"access_user_ids": [Command.unlink(self.alice.id)]})
        self.assertEqual(share.with_user(self.alice).name, "Secret")
        share.with_user(self.alice).write({"name": "Still mine"})

    # --- what only the code sets ------------------------------------------------------------

    def test_a_user_cannot_set_what_the_code_sets(self):
        values = {
            "token": "guessable",
            "view_count": 99,
            "download_count": 99,
            "upload_count": 99,
            "upload_size": 99,
            "last_access": fields.Datetime.now(),
            "upload_folder_id": self.deep.id,
        }
        share = self._share(self.shared, **values)
        self.assertEqual(str(uuid.UUID(share.token)), share.token)
        self.assertEqual((share.view_count, share.download_count, share.upload_count), (0, 0, 0))
        self.assertFalse(share.upload_size or share.last_access or share.upload_folder_id)
        token = share.token
        share.with_user(self.alice).write(values)
        self.assertEqual(share.token, token)
        self.assertEqual((share.view_count, share.download_count, share.upload_count), (0, 0, 0))
        self.assertFalse(share.upload_size or share.last_access or share.upload_folder_id)
        share.sudo().write({"view_count": 3})
        self.assertEqual(share.view_count, 3)

    def test_a_user_cannot_tell_a_document_which_share_it_came_through(self):
        share = self._share(self.shared)
        self.document.with_user(self.alice).write({"share_id": share.id, "name": "b.txt"})
        self.assertEqual(self.document.name, "b.txt")
        self.assertFalse(self.document.share_id)
        self.document.share_id = share
        self.assertEqual(self.document.share_id, share)

    def test_a_user_cannot_make_a_document(self):
        with self.assertRaises(AccessError):
            self.Document.with_user(self.alice).create(
                {"name": "x", "folder_id": self.shared.id, "checksum": "a" * 64, "share_id": False}
            )

    # --- limits of the uploads --------------------------------------------------------------

    def test_a_new_share_starts_with_the_limits_of_the_settings(self):
        share = self._share(self.shared, can_upload=True)
        self.assertEqual(
            (share.upload_max_file_mb, share.upload_max_total_mb, share.upload_max_files, share.upload_extensions),
            (25, 500, 100, False),
        )
        self.Config.set_param("int_filemanager.share_default_file_mb", "10")
        self.Config.set_param("int_filemanager.share_default_extensions", "pdf, jpg")
        share = self._share(self.shared, can_upload=True)
        self.assertEqual((share.upload_max_file_mb, share.upload_extensions), (10, "pdf, jpg"))

    def test_a_share_cannot_be_set_above_the_highest_values(self):
        self.Config.set_param("int_filemanager.share_max_file_mb", "50")
        self.Config.set_param("int_filemanager.share_max_files", "10")
        share = self._share(self.shared, can_upload=True, upload_max_file_mb=50, upload_max_files=10)
        with self.assertRaises(ValidationError):
            share.upload_max_file_mb = 51
        with self.assertRaises(ValidationError):
            share.upload_max_files = 11
        with self.assertRaises(ValidationError):
            share.upload_max_total_mb = 5 * 1024 + 1

    def test_the_limits_are_at_least_1(self):
        for name in ("upload_max_file_mb", "upload_max_total_mb", "upload_max_files"):
            with self.subTest(name), self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
                self._share(self.shared, can_upload=True, **{name: 0})

    # --- the password -----------------------------------------------------------------------

    def test_the_password_is_kept_as_a_hash_that_no_user_can_read(self):
        share = self._share(self.shared, password=PASSWORD)
        self.assertTrue(share.has_password)
        self.assertFalse(share.password)
        self.assertFalse(share.with_user(self.alice).password)
        with self.assertRaises(AccessError):
            share.with_user(self.alice).read(["password_hash"])
        with self.assertRaises(AccessError):
            share.with_user(self.alice).write({"password_hash": "x"})
        password_hash = share.sudo().password_hash
        self.assertNotIn(PASSWORD, password_hash)
        crypt_context = self.env["res.users"]._crypt_context()
        self.assertEqual(crypt_context.identify(password_hash), "pbkdf2_sha512")
        self.assertTrue(crypt_context.verify(PASSWORD, password_hash))
        self.assertFalse(crypt_context.verify("another password", password_hash))

    def test_a_new_password_replaces_the_old_and_an_empty_one_keeps_it(self):
        share = self._share(self.shared, password=PASSWORD)
        old = share.sudo().password_hash
        share.write({"password": False})
        self.assertEqual(share.sudo().password_hash, old)
        share.write({"password": "another long one"})
        self.assertNotEqual(share.sudo().password_hash, old)
        crypt_context = self.env["res.users"]._crypt_context()
        self.assertTrue(crypt_context.verify("another long one", share.sudo().password_hash))

    def test_the_password_has_a_length(self):
        with self.assertRaises(UserError):
            self._share(self.shared, password="short")
        with self.assertRaises(UserError):
            self._share(self.shared, password="x" * 129)
        self._share(self.shared, password="x" * 128)
        self.Config.set_param("int_filemanager.share_password_length", "20")
        with self.assertRaises(UserError):
            self._share(self.shared, password=PASSWORD)

    def test_the_password_can_be_removed_by_whoever_may_change_the_share(self):
        share = self._share(self.shared, password=PASSWORD)
        with self.assertRaises(AccessError):
            share.with_user(self.bob).action_remove_password()
        self.assertTrue(share.has_password)
        share.with_user(self.alice).action_remove_password()
        self.assertFalse(share.has_password)
        self.assertFalse(share.sudo().password_hash)

    # --- the folder for the uploads ---------------------------------------------------------

    def test_a_share_with_uploads_gets_a_folder_that_only_its_maker_sees(self):
        share = self._share(self.shared, can_upload=True)
        upload = share.upload_folder_id
        self.assertEqual(upload.name, "Uploads - Shared")
        self.assertEqual(upload.parent_id, self.shared)
        self.assertEqual(upload.sudo().access_mode, "restricted")
        self.assertEqual(upload.sudo().access_user_ids, self.alice)
        self.assertEqual(upload.company_id, self.shared.company_id)
        self.assertNotIn(upload, self._seen_by(self.bob))
        self.assertIn(upload, self._seen_by(self.alice))
        self.assertIn(upload, self._seen_by(self.boss))
        self.assertNotIn(self.alice.partner_id, upload.message_partner_ids)

    def test_a_share_without_uploads_gets_no_folder(self):
        self.assertFalse(self._share(self.shared).upload_folder_id)
        self.assertFalse(self._share(self.document).upload_folder_id)

    def test_saving_again_keeps_the_folder_and_switching_off_does_not_remove_it(self):
        share = self._share(self.shared, can_upload=True)
        upload = share.upload_folder_id
        share.name = "Renamed"
        self.assertEqual(share.upload_folder_id, upload)
        share.can_upload = False
        self.assertEqual(share.upload_folder_id, upload)
        self.assertTrue(upload.active)
        share.can_upload = True
        self.assertEqual(share.upload_folder_id, upload)
        self.assertEqual(self.Folder.search_count([("name", "like", "Uploads - %")]), 1)

    def test_a_folder_that_moved_out_or_is_archived_is_replaced_at_the_next_save(self):
        share = self._share(self.shared, can_upload=True)
        moved = share.upload_folder_id.sudo()
        moved.parent_id = self.secret
        share.name = "Again"
        self.assertNotEqual(share.upload_folder_id, moved)
        self.assertEqual(share.upload_folder_id.parent_id, self.shared)
        self.assertTrue(moved.active)  # the files in it are not ours to decide on
        archived = share.upload_folder_id.sudo()
        archived.active = False
        share.name = "Once more"
        self.assertNotEqual(share.upload_folder_id, archived)

    def test_a_taken_name_gets_a_number(self):
        self.Folder.create({"name": "uploads - shared", "parent_id": self.shared.id})
        share = self._share(self.shared, can_upload=True)
        self.assertEqual(share.upload_folder_id.name, "Uploads - Shared (2)")

    def test_the_folder_of_the_uploads_keeps_the_shared_folder_from_being_deleted(self):
        plain = self.Folder.create({"name": "Plain", "access_mode": "open"})
        share = self._share(plain, can_upload=True)
        with self.assertRaises(UserError):
            plain.unlink()
        share.upload_folder_id.unlink()
        plain.unlink()
        self.assertFalse(share.exists())
