import io
import os

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


@tagged("post_install", "-at_install")
class TestChatter(TransactionCase):
    """What the chatter keeps of a folder or a document: its changes and its activities."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Folder = cls.env["int.filemanager.folder"]
        cls.Document = cls.env["int.filemanager.document"]
        cls.user = new_test_user(
            cls.env,
            login="chatter_user",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )
        cls.outsider = new_test_user(cls.env, login="chatter_outsider", groups="base.group_user")
        cls.top = cls.Folder.create({"name": "Top", "access_mode": "open"})
        cls.sub = cls.Folder.create({"name": "Sub", "parent_id": cls.top.id})
        cls.env.cr.precommit.run()

    def _document(self, name="a.txt", folder=None):
        document = self.Document._create_from_stream(io.BytesIO(b"x"), name, folder or self.sub)
        self.addCleanup(remove, self.Document._blob_path(document.checksum))
        return document

    def _flush_tracking(self):
        # The tracking of Odoo writes its messages just before the commit. A record that was
        # created in the same transaction is not tracked until then (as in the core's tests).
        self.env.cr.precommit.run()

    def _tracking_values(self, record):
        self._flush_tracking()
        return self.env["mail.tracking.value"].search(
            [("mail_message_id.model", "=", record._name), ("mail_message_id.res_id", "=", record.id)]
        )

    def _changes(self, record):
        """The names of the fields the chatter of the record shows as changed."""
        return sorted(self._tracking_values(record).field_id.mapped("name"))

    # --- changes -------------------------------------------------------------

    def test_a_new_document_shows_no_change(self):
        self.assertEqual(self._changes(self._document()), [])

    def test_an_upload_is_no_news_in_the_chatter_and_nobody_follows_it(self):
        # 20,000 files of one folder would be 20,000 messages and 20,000 follower rows.
        document = self.Document.with_user(self.user)._create_from_stream(
            io.BytesIO(b"x"), "mine.txt", self.sub.with_user(self.user)
        )
        self.addCleanup(remove, self.Document._blob_path(document.checksum))
        self._flush_tracking()
        self.assertFalse(document.sudo().message_ids)
        self.assertFalse(document.sudo().message_follower_ids)
        # What is done to it later is logged as usual.
        document.name = "yours.txt"
        self.assertEqual(self._changes(document), ["name"])

    def test_the_folders_of_an_import_are_no_news_either(self):
        folder = self.Folder._create_numbered("Imported", self.top)
        self._flush_tracking()
        self.assertFalse(folder.message_ids)

    def test_a_rename_is_shown_with_the_old_and_the_new_name(self):
        document = self._document("a.txt")
        document.name = "b.txt"
        value = self._tracking_values(document)
        self.assertEqual(value.field_id.name, "name")
        self.assertEqual((value.old_value_char, value.new_value_char), ("a.txt", "b.txt"))

    def test_a_move_of_a_document_is_shown(self):
        document = self._document()
        document.folder_id = self.top
        self.assertEqual(self._changes(document), ["folder_id"])

    def test_archiving_a_document_is_shown(self):
        document = self._document()
        document.action_archive()
        self.assertEqual(self._changes(document), ["active"])

    def test_archiving_a_folder_is_shown_on_that_folder_only(self):
        document = self._document()
        self.top.action_archive()
        self.assertEqual(self._changes(self.top), ["active"])
        self.assertEqual(self._changes(self.sub), [])
        self.assertEqual(self._changes(document), [])

    def test_a_change_of_who_sees_a_folder_is_shown(self):
        folder = self.Folder.create({"name": "Private", "access_mode": "open"})
        self._flush_tracking()
        folder.write(
            {"access_mode": "restricted", "access_user_ids": [Command.link(self.user.id)]}
        )
        self.assertEqual(self._changes(folder), ["access_mode", "access_user_ids"])

    def test_a_move_of_a_folder_is_shown(self):
        self.sub.parent_id = False
        self.assertEqual(self._changes(self.sub), ["parent_id"])

    # --- activities ----------------------------------------------------------

    def test_a_user_schedules_an_activity_on_a_document(self):
        document = self._document()
        activity = document.with_user(self.user).activity_schedule(
            "mail.mail_activity_data_todo", user_id=self.user.id, summary="Check"
        )
        self.assertEqual(document.activity_ids, activity)
        self.assertEqual(document.activity_state, "today")
        self.assertEqual(
            self.Document.search([("activity_user_id", "=", self.user.id)]), document
        )

    def test_activities_follow_the_rights_on_the_document(self):
        document = self._document()
        with self.assertRaises(AccessError):
            document.with_user(self.outsider).activity_schedule(
                "mail.mail_activity_data_todo", user_id=self.user.id
            )

    def test_the_views_know_the_activities(self):
        # As a user: the activity column is for internal users (the group of the field).
        views = self.Document.with_user(self.user).get_views(
            [(False, "list"), (False, "form"), (False, "search")]
        )
        self.assertTrue(views["models"][self.Document._name]["has_activities"])
        self.assertIn('widget="list_activity"', views["views"]["list"]["arch"])
        # What the activity menu of the top bar sets as search defaults.
        for name in (
            "filter_activities_my",
            "activities_overdue",
            "activities_today",
            "activities_upcoming_all",
        ):
            self.assertIn(f'name="{name}"', views["views"]["search"]["arch"])
