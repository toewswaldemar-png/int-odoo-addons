import io
import os

from psycopg2 import IntegrityError

from odoo import Command, http
from odoo.exceptions import AccessError
from odoo.tests.common import HttpCase, TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger

UPLOAD = "/int_filemanager/upload"


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


@tagged("post_install", "-at_install")
class TestModelFolder(TransactionCase):
    """The folder that the files of a model go to."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Setting = cls.env["int.filemanager.model.folder"]
        cls.company2 = cls.env["res.company"].create({"name": "Second company"})
        cls.all = cls.env["int.filemanager.folder"].create({"name": "For all"})
        cls.own = cls.env["int.filemanager.folder"].create(
            {"name": "Own", "company_id": cls.company2.id}
        )

    def test_the_setting_of_the_company_comes_before_the_one_for_all(self):
        self.Setting.create({"res_model": "res.partner", "folder_id": self.all.id, "company_id": False})
        self.Setting.create(
            {"res_model": "res.partner", "folder_id": self.own.id, "company_id": self.company2.id}
        )
        partner = self.env["res.partner"].create({"name": "P", "company_id": self.company2.id})
        self.assertEqual(self.Setting._folder_for_record(partner), self.own)
        other = self.env["res.partner"].create({"name": "Q", "company_id": self.env.company.id})
        self.assertEqual(self.Setting._folder_for_record(other), self.all)

    def test_without_a_setting_there_is_no_folder(self):
        partner = self.env["res.partner"].create({"name": "P"})
        self.assertFalse(self.Setting._folder_for_record(partner))

    def test_an_archived_folder_does_not_count(self):
        self.Setting.create({"res_model": "res.partner", "folder_id": self.all.id, "company_id": False})
        self.all.active = False
        partner = self.env["res.partner"].create({"name": "P"})
        self.assertFalse(self.Setting._folder_for_record(partner))

    def test_one_setting_per_model_and_company(self):
        self.Setting.create({"res_model": "res.partner", "folder_id": self.all.id, "company_id": False})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.Setting.create(
                {"res_model": "res.partner", "folder_id": self.all.id, "company_id": False}
            )

    def test_the_folder_lists_its_settings_by_the_name_of_the_model(self):
        setting = self.Setting.create(
            {"res_model": "res.partner", "folder_id": self.all.id, "company_id": False}
        )
        self.assertEqual(self.all.model_folder_ids, setting)
        label = dict(self.Setting._selection_res_model())["res.partner"]
        self.assertEqual(setting.display_name, label)

    def test_a_setting_is_added_in_the_folder(self):
        self.all.write(
            {"model_folder_ids": [Command.create({"res_model": "res.partner", "company_id": False})]}
        )
        partner = self.env["res.partner"].create({"name": "P"})
        self.assertEqual(self.Setting._folder_for_record(partner), self.all)

    def test_only_the_administrators_reach_the_settings_through_the_folder(self):
        folder = self.env["int.filemanager.folder"].create({"name": "Open", "access_mode": "open"})
        user = new_test_user(self.env, login="fm_user", groups="base.group_user,int_filemanager.int_filemanager_group_user")
        admin = new_test_user(self.env, login="fm_admin", groups="base.group_user,int_filemanager.int_filemanager_group_admin")
        create = [Command.create({"res_model": "res.partner", "company_id": False})]
        with self.assertRaises(AccessError):
            folder.with_user(user).model_folder_ids  # noqa: B018
        with self.assertRaises(AccessError):
            folder.with_user(user).write({"model_folder_ids": create})
        folder.with_user(admin).write({"model_folder_ids": create})
        self.assertEqual(folder.model_folder_ids.res_model, "res.partner")

    def test_only_models_that_can_be_linked_are_offered(self):
        models = [name for name, __ in self.Setting._selection_res_model()]
        self.assertIn("res.partner", models)
        self.assertNotIn("res.country", models)


@tagged("post_install", "-at_install")
class TestUploadAtRecord(HttpCase):
    """``POST /int_filemanager/upload`` with ``link_model`` and ``link_id``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env["int.filemanager.document"]
        # Nobody but the administrators sees this folder: the uploader never does.
        cls.folder = cls.env["int.filemanager.folder"].create(
            {"name": "Contacts", "access_mode": "restricted"}
        )
        cls.env["int.filemanager.model.folder"].create(
            {"res_model": "res.partner", "folder_id": cls.folder.id, "company_id": False}
        )
        cls.worker = new_test_user(
            cls.env, login="link_worker", groups="base.group_user,base.group_partner_manager"
        )
        cls.reader = new_test_user(cls.env, login="link_reader", groups="base.group_user")
        cls.partner = cls.env["res.partner"].create({"name": "Mueller"})

    def _upload(self, login, content=b"hello", name="a.txt", **fields):
        self.authenticate(login, login)
        data = {"csrf_token": http.Request.csrf_token(self), **fields}
        response = self.url_open(
            UPLOAD, data=data, files={"ufile": (name, io.BytesIO(content), "text/plain")}
        )
        if response.status_code == 200:
            document = self.Document.browse(response.json()["id"])
            self.addCleanup(remove, self.Document._blob_path(document.checksum))
        return response

    def _at(self, record=None, **extra):
        record = record or self.partner
        return {"link_model": record._name, "link_id": record.id, **extra}

    def test_a_file_uploaded_at_a_record_is_linked_to_it(self):
        response = self._upload("link_worker", name="plan.txt", **self._at())
        self.assertEqual(response.status_code, 200)
        document = self.Document.browse(response.json()["id"])
        self.assertEqual((document.folder_id, document.create_uid), (self.folder, self.worker))
        link = document.link_ids
        self.assertEqual((link.res_model, link.res_id), ("res.partner", self.partner.id))
        self.assertEqual(link.create_uid, self.worker)

    def test_the_uploader_sees_the_file_through_the_record_only(self):
        document = self.Document.browse(
            self._upload("link_worker", **self._at()).json()["id"]
        )
        self.env["int.filemanager.link"]._toggle_access_via_record(True)
        found = self.Document.with_user(self.worker).search([])
        self.assertEqual(found, document)
        self.assertFalse(self.env["int.filemanager.folder"].with_user(self.worker).has_access("read"))
        self.assertEqual(self.partner.with_user(self.worker).document_count, 1)
        # the folder is not theirs: they cannot change the document
        self.assertFalse(document.with_user(self.worker).has_access("write"))

    def test_the_note_is_in_the_chatter_of_the_record(self):
        self._upload("link_worker", name="plan.txt", **self._at())
        notes = " ".join(self.partner.message_ids.mapped("body"))
        self.assertIn("A document was linked.", notes)
        self.assertNotIn("plan.txt", notes)

    def test_whoever_may_not_change_the_record_cannot_upload(self):
        response = self._upload("link_reader", **self._at())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.Document.search([("name", "=", "a.txt")]))

    def test_without_a_folder_for_the_model_the_answer_says_so(self):
        self.env["int.filemanager.model.folder"].search([]).unlink()
        response = self._upload("link_worker", **self._at())
        self.assertEqual(response.status_code, 400)
        self.assertIn("upload folder", response.json()["error"]["message"])

    def test_a_model_that_cannot_be_linked_is_refused(self):
        country = self.env.ref("base.de")
        response = self._upload("link_worker", **self._at(country))
        self.assertEqual(response.status_code, 400)

    def test_a_missing_record_is_not_found(self):
        response = self._upload("link_worker", link_model="res.partner", link_id=0)
        self.assertEqual(response.status_code, 404)
        response = self._upload("link_worker", link_model="res.partner", link_id="x")
        self.assertEqual(response.status_code, 404)

    def test_the_upload_into_a_folder_is_as_before(self):
        user = new_test_user(
            self.env,
            login="link_folder_user",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )
        # not invited to the restricted folder: it is not there for the user, as before
        response = self._upload("link_folder_user", folder_id=self.folder.id)
        self.assertEqual(response.status_code, 404)
        self.folder.message_subscribe(partner_ids=user.partner_id.ids)
        response = self._upload("link_folder_user", folder_id=self.folder.id)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.Document.browse(response.json()["id"]).link_ids)
