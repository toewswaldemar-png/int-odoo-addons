import io
import os

from odoo import Command, http
from odoo.exceptions import AccessError
from odoo.tests.common import HttpCase, TransactionCase, new_test_user, tagged

USER_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_user"
ADMIN_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_admin"


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


class AccessCase:
    """A tree of folders and the people who may see them."""

    @classmethod
    def _set_up_access(cls):
        cls.Folder = cls.env["int.filemanager.folder"]
        cls.Document = cls.env["int.filemanager.document"]
        cls.alice = new_test_user(cls.env, login="access_alice", groups=USER_GROUPS)
        cls.bob = new_test_user(cls.env, login="access_bob", groups=USER_GROUPS)
        cls.boss = new_test_user(cls.env, login="access_boss", groups=ADMIN_GROUPS)
        cls.outsider = new_test_user(cls.env, login="access_outsider", groups="base.group_user")
        # secret (restricted) > inner (like the parent); shared (open) > deep (like the parent)
        cls.secret = cls.Folder.create({"name": "Secret", "access_mode": "restricted"})
        cls.inner = cls.Folder.create({"name": "Inner", "parent_id": cls.secret.id})
        cls.shared = cls.Folder.create({"name": "Shared", "access_mode": "open"})
        cls.deep = cls.Folder.create({"name": "Deep", "parent_id": cls.shared.id})

    def _document(self, folder, name="a.txt", content=b"hello"):
        document = self.Document._create_from_stream(io.BytesIO(content), name, folder)
        self.addCleanup(remove, self.Document._blob_path(document.checksum))
        return document

    def _invite(self, folder, *users):
        """List the users on the folder, as an administrator does."""
        folder.write({"access_user_ids": [Command.link(user.id) for user in users]})

    def _seen_by(self, user, model="int.filemanager.folder"):
        return self.env[model].with_user(user).search([])


@tagged("post_install", "-at_install")
class TestFolderAccess(AccessCase, TransactionCase):
    """Who sees a folder: open to all, or the users and groups listed on the folder that decides."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()

    def test_a_folder_takes_over_its_parent_by_default(self):
        self.assertEqual(self.inner.access_mode, "inherit")
        self.assertEqual(self.inner.access_folder_id, self.secret)
        self.assertEqual(self.deep.access_folder_id, self.shared)
        self.assertEqual(self.secret.access_folder_id, self.secret)

    def test_a_top_folder_that_says_like_the_parent_is_for_the_allowed_only(self):
        top = self.Folder.create({"name": "Plain"})
        self.assertEqual((top.access_mode, top.access_folder_id), ("inherit", top))
        self.assertNotIn(top, self._seen_by(self.alice))

    def test_nothing_is_seen_without_an_invitation_except_open_folders(self):
        seen = self._seen_by(self.alice)
        self.assertEqual(seen, self.shared + self.deep)

    def test_an_invitation_opens_the_folder_and_what_is_below(self):
        self._invite(self.secret, self.alice)
        self.assertEqual(self._seen_by(self.alice), self.secret + self.inner + self.shared + self.deep)
        self.assertEqual(self._seen_by(self.bob), self.shared + self.deep)

    def test_the_administrators_see_everything(self):
        self.assertEqual(self._seen_by(self.boss), self.secret + self.inner + self.shared + self.deep)

    def test_a_user_without_the_group_sees_nothing(self):
        with self.assertRaises(AccessError):
            self._seen_by(self.outsider)

    def test_a_folder_can_say_otherwise_than_its_parent(self):
        private = self.Folder.create({"name": "Private", "parent_id": self.shared.id, "access_mode": "restricted"})
        self.assertEqual(private.access_folder_id, private)
        self.assertNotIn(private, self._seen_by(self.alice))
        self.assertIn(self.deep, self._seen_by(self.alice))
        opened = self.Folder.create({"name": "Opened", "parent_id": self.secret.id, "access_mode": "open"})
        self.assertIn(opened, self._seen_by(self.alice))

    def test_changing_the_parent_changes_what_is_seen_below(self):
        self.shared.access_mode = "restricted"
        self.assertEqual(self._seen_by(self.alice), self.env["int.filemanager.folder"])
        self.assertEqual(self.deep.access_folder_id, self.shared)
        self.shared.access_mode = "open"
        self.assertIn(self.deep, self._seen_by(self.alice))

    def test_moving_a_folder_changes_its_rights(self):
        self.assertNotIn(self.inner, self._seen_by(self.alice))
        self.inner.parent_id = self.shared
        self.assertEqual(self.inner.access_folder_id, self.shared)
        self.assertIn(self.inner, self._seen_by(self.alice))
        self.inner.parent_id = self.secret
        self.assertNotIn(self.inner, self._seen_by(self.alice))

    def test_the_documents_follow_their_folder(self):
        hidden = self._document(self.inner, "hidden.txt")
        shown = self._document(self.deep, "shown.txt")
        self.assertEqual(self._seen_by(self.alice, "int.filemanager.document"), shown)
        self._invite(self.secret, self.alice)
        self.assertEqual(self._seen_by(self.alice, "int.filemanager.document"), hidden + shown)
        self.assertEqual(self._seen_by(self.bob, "int.filemanager.document"), shown)

    def test_a_hidden_document_cannot_be_read_or_changed(self):
        hidden = self._document(self.inner)
        as_alice = hidden.with_user(self.alice)
        with self.assertRaises(AccessError):
            as_alice.name  # noqa: B018
        with self.assertRaises(AccessError):
            as_alice.write({"name": "mine.txt"})
        with self.assertRaises(AccessError):
            as_alice.unlink()

    def test_a_hidden_folder_cannot_be_read_changed_or_deleted(self):
        as_alice = self.secret.with_user(self.alice)
        with self.assertRaises(AccessError):
            as_alice.name  # noqa: B018
        with self.assertRaises(AccessError):
            as_alice.write({"name": "mine"})
        with self.assertRaises(AccessError):
            as_alice.unlink()

    def test_an_outsider_cannot_follow_a_hidden_folder_nor_invite_anyone(self):
        as_alice = self.secret.with_user(self.alice)
        # Following needs the right to read: the call is refused or does nothing.
        as_alice.message_subscribe(partner_ids=[self.alice.partner_id.id])
        self.assertNotIn(self.secret, self._seen_by(self.alice))
        with self.assertRaises(AccessError):
            as_alice.message_subscribe(partner_ids=[self.bob.partner_id.id])
        self.assertNotIn(self.secret, self._seen_by(self.bob))

    def test_a_listed_user_sees_the_folder_and_what_is_below(self):
        self.secret.access_user_ids = self.alice
        self.assertEqual(self._seen_by(self.alice), self.secret + self.inner + self.shared + self.deep)
        self.assertEqual(self._seen_by(self.bob), self.shared + self.deep)

    def test_a_listed_group_sees_the_folder_and_whoever_leaves_the_group_does_not(self):
        family = self.env["res.groups"].create({"name": "Family"})
        self.alice.group_ids = [Command.link(family.id)]
        self.secret.access_group_ids = family
        self.assertEqual(self._seen_by(self.alice), self.secret + self.inner + self.shared + self.deep)
        self.assertEqual(self._seen_by(self.bob), self.shared + self.deep)
        self.alice.group_ids = [Command.unlink(family.id)]
        self.assertEqual(self._seen_by(self.alice), self.shared + self.deep)

    def test_a_group_that_implies_a_listed_group_sees_it_too(self):
        family = self.env["res.groups"].create({"name": "Family"})
        relatives = self.env["res.groups"].create({"name": "Relatives", "implied_ids": [Command.link(family.id)]})
        self.bob.group_ids = [Command.link(relatives.id)]
        self.secret.access_group_ids = family
        self.assertIn(self.secret, self._seen_by(self.bob))

    def test_the_lists_of_a_folder_that_says_like_the_parent_do_not_count(self):
        self.inner.access_user_ids = self.bob
        self.assertNotIn(self.inner, self._seen_by(self.bob))

    def test_a_subfolder_may_have_a_list_of_its_own(self):
        self.inner.write({"access_mode": "restricted", "access_user_ids": [Command.link(self.bob.id)]})
        self.assertEqual(self.inner.access_folder_id, self.inner)
        self.assertIn(self.inner, self._seen_by(self.bob))
        self.assertNotIn(self.secret, self._seen_by(self.bob))

    def test_a_listed_user_may_make_a_folder_below(self):
        self.secret.access_user_ids = self.alice
        sub = self.Folder.with_user(self.alice).create({"name": "Sub", "parent_id": self.secret.id})
        self.assertIn(sub, self._seen_by(self.alice))

    def test_the_lists_are_read_by_the_administrators_only(self):
        self.secret.access_user_ids = self.alice
        self.assertEqual(self.secret.with_user(self.boss).access_user_ids, self.alice)

    def test_a_follower_gets_the_notices_but_does_not_see_the_folder_for_it(self):
        self.secret.message_subscribe(partner_ids=[self.alice.partner_id.id])
        self.assertNotIn(self.secret, self._seen_by(self.alice))

    def test_a_listed_user_cannot_let_others_in_by_following_or_listing(self):
        self._invite(self.secret, self.alice)
        as_alice = self.secret.with_user(self.alice)
        as_alice.message_subscribe(partner_ids=[self.bob.partner_id.id])
        self.assertNotIn(self.secret, self._seen_by(self.bob))
        with self.assertRaises(AccessError):
            as_alice.write({"access_user_ids": [Command.link(self.bob.id)]})
        self.assertNotIn(self.secret, self._seen_by(self.bob))

    def test_the_creator_of_a_folder_sees_it(self):
        mine = self.Folder.with_user(self.alice).create({"name": "Mine"})
        self.assertIn(mine, self._seen_by(self.alice))
        self.assertNotIn(mine, self._seen_by(self.bob))

    def test_the_creator_keeps_the_folder_when_the_notices_are_stopped(self):
        mine = self.Folder.with_user(self.alice).create({"name": "Mine"})
        self.assertEqual(mine.sudo().access_user_ids, self.alice)
        mine.sudo().message_unsubscribe(partner_ids=[self.alice.partner_id.id])
        self.assertIn(mine, self._seen_by(self.alice))

    def test_a_subfolder_is_listed_by_its_parent_only(self):
        mine = self.Folder.with_user(self.alice).create({"name": "Mine"})
        sub = self.Folder.with_user(self.alice).create({"name": "Sub", "parent_id": mine.id})
        self.assertFalse(sub.sudo().access_user_ids)
        self.assertIn(sub, self._seen_by(self.alice))
        self.assertNotIn(sub, self._seen_by(self.bob))

    def test_what_the_code_makes_as_superuser_lists_nobody(self):
        self.assertFalse(self.secret.access_user_ids)

    def test_a_folder_can_be_made_below_a_folder_the_user_sees(self):
        self._invite(self.secret, self.alice)
        sub = self.Folder.with_user(self.alice).create({"name": "Sub", "parent_id": self.secret.id})
        self.assertIn(sub, self._seen_by(self.alice))
        self.assertIn(sub, self._seen_by(self.boss))

    def test_a_folder_cannot_be_made_below_a_hidden_folder(self):
        with self.assertRaises(AccessError):
            self.Folder.with_user(self.alice).create({"name": "Sneaky", "parent_id": self.secret.id})

    def test_the_search_panel_offers_the_folders_the_user_sees_only(self):
        result = self.Document.with_user(self.alice).search_panel_select_range(
            "folder_id", expand=True, limit=0
        )
        names = {value["display_name"] for value in result["values"]}
        self.assertEqual(names, {"Shared", "Deep"})


@tagged("post_install", "-at_install")
class TestFolderAccessOverHttp(AccessCase, HttpCase):
    """Upload and download follow the same rights."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()

    def _upload(self, folder):
        data = {"csrf_token": http.Request.csrf_token(self), "folder_id": folder.id}
        response = self.url_open(
            "/int_filemanager/upload", data=data, files={"ufile": ("a.txt", io.BytesIO(b"x"))}
        )
        if response.status_code == 200:
            document = self.Document.browse(response.json()["id"])
            self.addCleanup(remove, self.Document._blob_path(document.checksum))
        return response

    def _download(self, document):
        return self.url_open(
            f"/web/content/int.filemanager.document/{document.id}/content?download=true"
        )

    def test_a_user_uploads_into_a_folder_the_user_sees_only(self):
        self.authenticate("access_alice", "access_alice")
        self.assertEqual(self._upload(self.secret).status_code, 404)
        self.assertEqual(self._upload(self.inner).status_code, 404)
        self.assertEqual(self._upload(self.deep).status_code, 200)
        self._invite(self.secret, self.alice)
        self.assertEqual(self._upload(self.inner).status_code, 200)

    def test_a_user_downloads_from_a_folder_the_user_sees_only(self):
        hidden = self._document(self.inner, "hidden.txt")
        shown = self._document(self.deep, "shown.txt")
        self.authenticate("access_alice", "access_alice")
        self.assertEqual(self._download(hidden).status_code, 404)
        self.assertEqual(self._download(shown).status_code, 200)
        self._invite(self.secret, self.alice)
        self.assertEqual(self._download(hidden).status_code, 200)

    def test_the_administrators_reach_everything(self):
        hidden = self._document(self.inner, "hidden.txt")
        self.authenticate("access_boss", "access_boss")
        self.assertEqual(self._download(hidden).status_code, 200)
        self.assertEqual(self._upload(self.secret).status_code, 200)
