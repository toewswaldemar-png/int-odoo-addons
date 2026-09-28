"""The content type of a file comes from its content, when a revision is attached:
by upload, direct creation, new revision or restore."""

from unittest.mock import patch

from odoo.tests.common import HttpCase, TransactionCase, tagged
from odoo.tools import config
from odoo.tools.mimetypes import guess_mimetype

from .. import blobstore

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 30
PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n"
HTML = b"<!DOCTYPE html><html><body><script>alert(1)</script></body></html>"
BINARY = bytes(range(0, 200)) * 3


class MimeCase:
    def setUp(self):
        super().setUp()
        group = self.env["res.groups"].sudo().create({"name": "Mime test group"})
        scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Mime test scope",
                    "read_group_ids": [(4, group.id)],
                    "write_group_ids": [(4, group.id)],
                }
            )
        )
        self.folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "mime", "scope_id": scope.id, "is_dir": True})
        )
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.writer = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Mime writer",
                    "login": "mime_writer",
                    "group_ids": [(6, 0, [base_group.id, group.id])],
                }
            )
        )
        self._keys = 0

    def _node(self):
        return self.env["int_filemanager.node"].with_user(self.writer)

    def _upload(self, name, content):
        """A file in through the chunked upload, the way the browser does it."""
        self._keys += 1
        Upload = self.env["int_filemanager.upload"].with_user(self.writer)
        init = Upload.init_upload(
            self.folder.id, name, False, False, len(content), f"op-mime-i{self._keys}"
        )
        Upload.upload_chunk(init["upload_id"], 0, content)
        result = Upload.finish_upload(init["upload_id"], f"op-mime-f{self._keys}")
        return self.env["int_filemanager.node"].sudo().browse(result["node_id"])

    def _create(self, name, content):
        self._keys += 1
        result = self._node().create_file(
            self.folder.id, name, content, f"op-mime-{self._keys}"
        )
        return self.env["int_filemanager.node"].sudo().browse(result["node_id"])


@tagged("post_install", "-at_install")
class TestNodeMime(MimeCase, TransactionCase):
    def test_the_type_comes_from_the_content_not_the_name(self):
        node = self._create("picture.dat", PNG)
        self.assertEqual(node.mime, "image/png")
        self.assertEqual(node.current_revision_id.blob_id.mime, "image/png")

    def test_an_upload_in_chunks_sets_it_too(self):
        node = self._upload("scan.dat", PDF)
        self.assertEqual(node.mime, "application/pdf")
        self.assertEqual(node.current_revision_id.blob_id.mime, "application/pdf")

    def test_a_new_revision_of_another_kind_changes_the_type(self):
        node = self._create("thing.dat", PNG)
        self._node().create_new_revision(
            node.id, node.current_revision_id.id, PDF, "op-mime-newrev"
        )
        self.assertEqual(node.mime, "application/pdf")

    def test_restoring_an_old_revision_restores_its_type(self):
        node = self._create("thing.dat", PNG)
        first = node.current_revision_id
        self._node().create_new_revision(node.id, first.id, PDF, "op-mime-newrev")
        second = node.current_revision_id
        self._node().restore_version(node.id, first.id, second.id, "op-mime-restore")
        self.assertEqual(node.mime, "image/png")

    def test_unknown_content_gets_what_the_check_says_and_empty_content_no_type(self):
        self.assertEqual(self._create("data.bin", BINARY).mime, guess_mimetype(BINARY))
        self.assertEqual(self._upload("data2.bin", BINARY).mime, guess_mimetype(BINARY))
        empty = self._create("nothing.jpg", b"")
        self.assertFalse(empty.mime)
        self.assertFalse(empty.current_revision_id.blob_id.mime)

    def test_the_same_content_is_looked_at_once(self):
        with patch.object(blobstore, "read_head", wraps=blobstore.read_head) as spy:
            first = self._upload("a.dat", PDF)
            second = self._upload("b.dat", PDF)
        self.assertEqual((first.mime, second.mime), ("application/pdf",) * 2)
        self.assertEqual(spy.call_count, 1)

    def test_a_copy_needs_no_new_look(self):
        original = self._create("a.dat", PNG)
        with patch.object(blobstore, "read_head") as spy:
            self._keys += 1
            copy = self._node().copy_node(
                original.id, self.folder.id, "copy.dat", f"op-mime-copy-{self._keys}"
            )
        spy.assert_not_called()
        copied = self.env["int_filemanager.node"].sudo().browse(copy["node_id"])
        self.assertEqual(copied.mime, "image/png")


@tagged("post_install", "-at_install")
class TestNodeMimeServed(MimeCase, HttpCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.dict(config.options, {"x_sendfile": False}))

    def _served_type(self, node, disposition="inline"):
        self.authenticate("mime_writer", "irrelevant")
        response = self.url_open(
            f"/int_filemanager/v2/download/{node.id}?disposition={disposition}"
        )
        self.assertEqual(response.status_code, 200)
        return response.headers["Content-Type"].split(";")[0]

    def test_a_page_hidden_in_a_text_file_is_served_as_text(self):
        node = self._create("notes.txt", HTML)
        self.assertEqual(node.mime, "text/html")
        self.assertEqual(self._served_type(node), "text/plain")

    def test_a_page_is_served_as_text_whatever_its_name(self):
        node = self._create("page.html", HTML)
        self.assertEqual(self._served_type(node), "text/plain")
        self.assertEqual(self._served_type(node, "attachment"), "text/plain")

    def test_other_types_are_served_as_what_they_are(self):
        self.assertEqual(self._served_type(self._create("p.dat", PNG)), "image/png")
        self.assertEqual(
            self._served_type(self._create("d.dat", PDF)), "application/pdf"
        )
