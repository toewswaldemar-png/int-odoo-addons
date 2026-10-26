import io
import zipfile

from odoo.tests.common import HttpCase, new_test_user, tagged

from odoo.addons.int_filemanager.tests.test_folder_access import USER_GROUPS, remove

ROUTE = "/int_filemanager/folder_zip/"


@tagged("post_install", "-at_install")
class TestFolderZipOfLinked(HttpCase):
    def test_a_document_that_is_read_through_a_record_stays_in_its_hidden_folder(self):
        Folder = self.env["int.filemanager.folder"]
        Document = self.env["int.filemanager.document"]
        user = new_test_user(self.env, login="record_zip_user", groups=USER_GROUPS)
        club = Folder.create({"name": "Club", "access_mode": "open"})
        secret = Folder.create({"name": "Secret", "parent_id": club.id, "access_mode": "restricted"})
        document = Document._create_from_stream(io.BytesIO(b"classified"), "linked.txt", secret)
        self.addCleanup(remove, Document._blob_path(document.checksum))
        partner = self.env["res.partner"].create({"name": "Linked to"})
        self.env["int.filemanager.link"]._toggle_access_via_record(True)
        self.env["int.filemanager.link"].create(
            {"document_id": document.id, "record_ref": f"res.partner,{partner.id}"}
        )
        self.assertEqual(Document.with_user(user).search([("id", "=", document.id)]), document)
        self.authenticate("record_zip_user", "record_zip_user")
        response = self.url_open(f"{ROUTE}{club.id}")
        self.assertEqual(response.status_code, 200, response.text[:200])
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        self.assertNotIn(b"linked.txt", response.content)
        self.assertFalse([name for name in archive.namelist() if "linked" in name])
