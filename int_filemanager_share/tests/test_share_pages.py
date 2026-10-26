import io

from PIL import Image

from odoo.tests.common import HttpCase, tagged

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase


PASSWORD = "a long password"


def png():
    stream = io.BytesIO()
    Image.new("RGB", (40, 30)).save(stream, "PNG")
    return stream.getvalue()


@tagged("post_install", "-at_install")
class TestSharePages(AccessCase, HttpCase):
    """The pages of a share: what a guest sees first, and what it must not see before the password."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Share = cls.env["int.filemanager.share"]

    def setUp(self):
        super().setUp()
        self.env.registry._int_filemanager_share_brake = None
        self.parent = self.Folder.create({"name": "Secret parent name", "access_mode": "open"})
        self.folder = self.Folder.create({"name": "Shared <b>folder</b>", "parent_id": self.parent.id})
        self.pdf = self._document(self.folder, "a.pdf", b"%PDF-1.4 hello")
        self.picture = self._document(self.folder, "p.png", png())
        self.binary = self._document(self.folder, "x.bin", b"\x00\x01\x02\x03 binary")

    def _page(self, share, **kwargs):
        return self.url_open(f"/int_filemanager/share/{share.token}", **kwargs)

    def _page_with_key(self, share, key):
        return self.url_open(f"/int_filemanager/share/{share.token}/page", data={"k": key})

    # --- the page of a file -------------------------------------------------------------------

    def test_the_page_of_a_file_shows_what_the_rights_allow(self):
        share = self.Share.create({"document_id": self.picture.id})
        text = self._page(share).text
        self.assertIn("p.png", text)
        self.assertIn(f"/int_filemanager/share/{share.token}/image/{self.picture.id}/512", text)
        self.assertIn(f"/int_filemanager/share/{share.token}/download/{self.picture.id}", text)
        self.assertIn(f"/int_filemanager/share/{share.token}/content/{self.picture.id}", text)  # show
        share.write({"can_view": False})
        text = self._page(share).text
        self.assertNotIn("/image/", text)
        self.assertNotIn("/content/", text)
        self.assertIn("/download/", text)
        share.write({"can_view": True, "can_download": False})
        text = self._page(share).text
        self.assertNotIn("/download/", text)
        self.assertIn("/image/", text)

    def test_a_file_that_a_browser_does_not_show_has_no_show_link(self):
        share = self.Share.create({"document_id": self.binary.id})
        self.assertNotIn("/content/", self._page(share).text)

    def test_the_page_of_a_file_tells_the_downloads_left_and_escapes_the_name(self):
        document = self._document(self.folder, "<i>x.txt", b"text")
        share = self.Share.create({"document_id": document.id, "max_downloads": 3})
        text = self._page(share).text
        self.assertIn("&lt;i&gt;x.txt", text)
        self.assertNotIn("<i>x.txt", text)
        self.assertIn("Downloads left", text)
        share.sudo().download_count = 1
        self.assertRegex(self._page(share).text, r"Downloads left:\s*<span>2</span>")

    def test_the_page_counts_a_visit_once_a_minute_and_a_head_request_not_at_all(self):
        share = self.Share.create({"document_id": self.pdf.id})
        self.opener.head(self.base_url() + f"/int_filemanager/share/{share.token}")
        self.assertEqual(share.view_count, 0)
        self._page(share)
        self._page(share)
        self.assertEqual(share.view_count, 1)
        self.assertTrue(share.last_access)

    def test_headers_and_no_cookie(self):
        response = self._page(self.Share.create({"document_id": self.pdf.id}))
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(response.headers["Cache-Control"], "private, no-cache")
        self.assertNotIn("Set-Cookie", response.headers)

    def test_a_share_that_is_not_valid_has_no_page(self):
        share = self.Share.create({"document_id": self.pdf.id})
        self.assertEqual(self.url_open("/int_filemanager/share/unknown").status_code, 404)
        share.action_archive()
        self.assertEqual(self._page(share).status_code, 410)

    # --- the page of a folder -------------------------------------------------------------------

    def test_the_page_of_a_folder_starts_the_app_and_says_nothing_of_what_lies_above(self):
        share = self.Share.create({"folder_id": self.folder.id, "can_download": False})
        response = self._page(share)
        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertIn(f'odoo.int_filemanager_token = "{share.token}"', text)
        self.assertIn('"can_view": true', text)
        self.assertIn('"can_download": false', text)
        self.assertIn("/web/assets/", text)
        self.assertIn("assets_guest", text)
        self.assertNotIn("Secret parent name", text)
        self.assertEqual(share.view_count, 1)

    def test_the_name_of_the_folder_cannot_break_out_of_the_script(self):
        folder = self.Folder.create({"name": "</script><script>alert(1)</script>", "access_mode": "open"})
        text = self._page(self.Share.create({"folder_id": folder.id})).text
        self.assertNotIn("</script><script>alert(1)", text)

    # --- the password ---------------------------------------------------------------------------

    def test_the_shell_that_asks_for_the_password_shows_nothing_of_the_share(self):
        share = self.Share.create({"document_id": self.pdf.id, "password": PASSWORD, "max_downloads": 4})
        response = self._page(share)
        self.assertEqual(response.status_code, 200)
        text = response.text
        for secret in ("a.pdf", "application/pdf", "Downloads left", "/download/", "/content/"):
            self.assertNotIn(secret, text)
        self.assertIn('id="o_share_password"', text)
        self.assertIn(f'data-token="{share.token}"', text)
        self.assertIn("assets_guest_password", text)
        self.assertEqual(share.view_count, 0)  # asking for the password is not a visit

    def test_the_shell_of_a_folder_says_nothing_either(self):
        share = self.Share.create({"folder_id": self.folder.id, "password": PASSWORD})
        text = self._page(share).text
        self.assertNotIn("Shared", text)
        self.assertNotIn("int_filemanager_token", text)

    def test_the_page_comes_with_the_key_in_the_body(self):
        share = self.Share.create({"document_id": self.pdf.id, "password": PASSWORD})
        for key in (None, "", "wrong", "x" * 600):
            with self.subTest(key=key):
                data = {"k": key} if key is not None else {"x": "y"}
                response = self.url_open(f"/int_filemanager/share/{share.token}/page", data=data)
                self.assertEqual(response.status_code, 403)
                self.assertNotIn("a.pdf", response.text)
        key = share._unlock_key()
        response = self._page_with_key(share, key)
        self.assertEqual(response.status_code, 200)
        self.assertIn("a.pdf", response.text)
        self.assertIn(f'name="k" value="{key}"', response.text)  # the download form carries it
        self.assertIn(f"/content/{self.pdf.id}?k={key}", response.text)
        self.assertEqual(share.view_count, 1)
        self.assertNotIn("Set-Cookie", response.headers)

    def test_the_page_of_a_folder_comes_with_the_key_too(self):
        share = self.Share.create({"folder_id": self.folder.id, "password": PASSWORD})
        self.assertEqual(self._page_with_key(share, "wrong").status_code, 403)
        response = self._page_with_key(share, share._unlock_key())
        self.assertEqual(response.status_code, 200)
        self.assertIn("int_filemanager_token", response.text)

    def test_a_key_of_another_share_does_not_open_the_page(self):
        first = self.Share.create({"document_id": self.pdf.id, "password": PASSWORD})
        second = self.Share.create({"document_id": self.picture.id, "password": PASSWORD})
        self.assertEqual(self._page_with_key(second, first._unlock_key()).status_code, 403)
