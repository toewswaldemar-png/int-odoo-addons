import io
import re

from PIL import Image

from odoo.tests.common import HttpCase, tagged

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase

from ..controllers.int_filemanager import PAGE_SIZE
from .common import NoSessionMixin, guest_key

PASSWORD = "a long password"


def png():
    stream = io.BytesIO()
    Image.new("RGB", (40, 30)).save(stream, "PNG")
    return stream.getvalue()


@tagged("post_install", "-at_install")
class TestSharePages(NoSessionMixin, AccessCase, HttpCase):
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

    def _address(self, share, tail=""):
        return f"/int_filemanager/share/{share.token}{tail}"

    def _page(self, share, tail="", key=False, **kwargs):
        """The page; ``key``: True for the key of the share, a text for another one (in the cookie)."""
        if key is False:
            return self.url_open(self._address(share, tail), **kwargs)
        with guest_key(self.opener, share, None if key is True else key):
            return self.url_open(self._address(share, tail), **kwargs)

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
        self.opener.head(self.base_url() + self._address(share))
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
        self.assertNoSession(response)

    def test_a_share_that_is_not_valid_has_no_page(self):
        share = self.Share.create({"document_id": self.pdf.id})
        self.assertEqual(self.url_open("/int_filemanager/share/unknown").status_code, 404)
        share.action_archive()
        self.assertEqual(self._page(share).status_code, 410)

    def test_the_share_of_a_file_has_no_folders(self):
        share = self.Share.create({"document_id": self.pdf.id})
        self.assertEqual(self._page(share, f"/folder/{self.folder.id}").status_code, 404)

    # --- the page of a folder -------------------------------------------------------------------

    def test_the_page_of_a_folder_is_a_page_of_the_portal_with_its_files_and_folders(self):
        sub = self.Folder.create({"name": "Sub <i>folder</i>", "parent_id": self.folder.id})
        share = self.Share.create({"folder_id": self.folder.id})
        response = self._page(share)
        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertIn("o_portal_wrap", text)
        self.assertIn("o_portal_search_panel", text)
        for name in ("a.pdf", "p.png", "x.bin"):
            self.assertIn(name, text)
        self.assertIn(self._address(share, f"/folder/{sub.id}"), text)
        self.assertIn("Sub &lt;i&gt;folder&lt;/i&gt;", text)  # escaped
        self.assertNotIn("<i>folder</i>", text)
        self.assertIn(self._address(share, f"/content/{self.pdf.id}"), text)  # shown in the browser
        self.assertIn(self._address(share, f"/content/{self.pdf.id}?download=1"), text)
        self.assertNotIn(self._address(share, f"/content/{self.binary.id}") + '"', text)  # not shown
        self.assertEqual(share.view_count, 1)

    def test_the_page_says_nothing_of_what_lies_above_the_shared_folder(self):
        share = self.Share.create({"folder_id": self.folder.id})
        for tail in ("", f"/folder/{self.folder.id}"):
            with self.subTest(tail=tail):
                text = self._page(share, tail).text
                self.assertNotIn("Secret parent name", text)
                self.assertNotIn(self._address(share, f"/folder/{self.parent.id}"), text)

    def test_the_way_down_is_on_the_page_as_far_as_the_shared_folder(self):
        sub = self.Folder.create({"name": "Down one", "parent_id": self.folder.id})
        deeper = self.Folder.create({"name": "Down two", "parent_id": sub.id})
        share = self.Share.create({"folder_id": self.folder.id})
        text = self._page(share, f"/folder/{deeper.id}").text
        crumbs = re.search(r'<ol class="breadcrumb">(.*?)</ol>', text, re.S).group(1)
        self.assertEqual(crumbs.count("<li"), 3)
        self.assertIn(self._address(share, f"/folder/{self.folder.id}"), crumbs)
        self.assertIn(self._address(share, f"/folder/{sub.id}"), crumbs)
        self.assertNotIn(self._address(share, f"/folder/{deeper.id}"), crumbs)  # the last one is no link
        self.assertNotIn("Secret parent name", crumbs)

    def test_a_folder_that_the_share_does_not_reach_is_not_there(self):
        hidden = self.Folder.create({"name": "Hidden", "parent_id": self.folder.id, "access_mode": "restricted"})
        below = self.Folder.create({"name": "Below hidden", "parent_id": hidden.id})
        archived = self.Folder.create({"name": "Archived", "parent_id": self.folder.id})
        archived.action_archive()
        share = self.Share.create({"folder_id": self.folder.id})
        text = self._page(share).text
        self.assertNotIn("Hidden", text)
        self.assertNotIn("Archived", text)
        for folder in (hidden, below, archived, self.parent, self.shared):
            with self.subTest(folder.name):
                self.assertEqual(self._page(share, f"/folder/{folder.id}").status_code, 404)
        self.assertEqual(self._page(share, "/folder/2147483647").status_code, 404)

    def test_the_folder_for_the_uploads_is_not_listed(self):
        share = self.Share.create({"folder_id": self.folder.id, "can_upload": True})
        self.assertNotIn("Uploads", self._page(share).text)
        self.assertEqual(self._page(share, f"/folder/{share.upload_folder_id.id}").status_code, 404)

    def test_the_search_looks_below_the_folder_and_nowhere_else(self):
        sub = self.Folder.create({"name": "Sub", "parent_id": self.folder.id})
        self._document(sub, "needle-in-sub.txt", b"x")
        hidden = self.Folder.create({"name": "needle-hidden", "parent_id": self.folder.id, "access_mode": "restricted"})
        self._document(hidden, "needle-secret.txt", b"x")
        self._document(self.shared, "needle-outside.txt", b"x")
        share = self.Share.create({"folder_id": self.folder.id})
        text = self._page(share, params={"search": "needle"}).text
        self.assertIn("needle-in-sub.txt", text)
        self.assertNotIn("needle-secret", text)
        self.assertNotIn("needle-hidden", text)
        self.assertNotIn("needle-outside", text)
        self.assertNotIn("a.pdf", text)
        self.assertIn("<th>Folder</th>", text)
        self.assertIn("No file or folder has this name.", self._page(share, params={"search": "nothing like it"}).text)

    def test_a_search_text_is_text_and_not_a_pattern(self):
        share = self.Share.create({"folder_id": self.folder.id})
        for search in ("%", "_", "\\", "' OR 1=1 --", "x" * 500):
            with self.subTest(search=search[:10]):
                response = self._page(share, params={"search": search})
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("a.pdf", response.text)

    def test_the_sortings_are_those_of_the_list_and_nothing_else(self):
        small = self._document(self.folder, "aa-small.txt", b"1")
        share = self.Share.create({"folder_id": self.folder.id})

        def order(sortby):
            text = self._page(share, params={"sortby": sortby}).text
            names = ("aa-small.txt", "a.pdf", "p.png", "x.bin")
            return sorted(names, key=text.index)

        self.assertEqual(order("name"), ["a.pdf", "aa-small.txt", "p.png", "x.bin"])
        self.assertEqual(order("size")[-1], "aa-small.txt")  # the smallest file is the last
        self.assertEqual(order("name; DROP TABLE x"), order("name"))
        self.assertEqual(order("write_date desc, id"), order("name"))
        self.assertTrue(small)

    def test_a_long_list_comes_in_pages_with_the_folders_first(self):
        for number in range(PAGE_SIZE + 5):
            self._document(self.folder, f"file-{number:03d}.txt", b"x")
        self.Folder.create({"name": "A folder", "parent_id": self.folder.id})
        share = self.Share.create({"folder_id": self.folder.id})
        first = self._page(share).text
        self.assertIn("A folder", first)
        self.assertIn(f"/folder/{self.folder.id}/page/2", first)
        second = self._page(share, f"/folder/{self.folder.id}/page/2").text
        self.assertNotIn("A folder", second)
        total = len(re.findall(r"file-\d{3}\.txt|a\.pdf|p\.png|x\.bin", first + second))
        self.assertEqual(total, PAGE_SIZE + 5 + 3)
        self.assertEqual(self._page(share, f"/folder/{self.folder.id}/page/99").status_code, 200)

    def test_the_rights_decide_what_the_rows_offer(self):
        share = self.Share.create({"folder_id": self.folder.id, "can_view": False})
        text = self._page(share).text
        self.assertIn("?download=1", text)
        self.assertNotIn("fa-eye", text)
        share.write({"can_view": True, "can_download": False})
        text = self._page(share).text
        self.assertNotIn("?download=1", text)
        self.assertIn("fa-eye", text)

    def test_a_share_that_only_takes_files_lists_nothing(self):
        share = self.Share.create(
            {"folder_id": self.folder.id, "can_view": False, "can_download": False, "can_upload": True}
        )
        response = self._page(share)
        self.assertEqual(response.status_code, 200)
        for name in ("a.pdf", "p.png", "x.bin", "breadcrumb"):
            self.assertNotIn(name, response.text)
        self.assertIn("o_if_share_upload", response.text)
        self.assertEqual(self._page(share, f"/folder/{self.folder.id}").status_code, 200)

    def test_the_upload_area_is_there_for_a_share_that_takes_files(self):
        share = self.Share.create({"folder_id": self.folder.id, "can_upload": True})
        text = self._page(share).text
        self.assertIn("o_if_share_upload", text)
        self.assertIn(f'data-token="{share.token}"', text)
        share.upload_folder_id.active = False  # the folder of the uploads is gone
        text = self._page(share).text
        self.assertNotIn("o_if_share_upload", text)
        self.assertIn("This link does not take files any more.", text)

    # --- the password ---------------------------------------------------------------------------

    def test_the_page_that_asks_for_the_password_shows_nothing_of_the_share(self):
        share = self.Share.create({"document_id": self.pdf.id, "password": PASSWORD, "max_downloads": 4})
        response = self._page(share)
        self.assertEqual(response.status_code, 200)
        text = response.text
        for secret in ("a.pdf", "application/pdf", "Downloads left", "/download/", "/content/"):
            self.assertNotIn(secret, text)
        self.assertIn(f'action="{self._address(share, "/unlock")}"', text)
        self.assertIn('type="password"', text)
        self.assertEqual(share.view_count, 0)  # asking for the password is not a visit

    def test_the_page_of_a_folder_with_a_password_says_nothing_either(self):
        share = self.Share.create({"folder_id": self.folder.id, "password": PASSWORD})
        for tail in ("", f"/folder/{self.folder.id}", f"/folder/{self.folder.id}/page/2"):
            with self.subTest(tail=tail):
                text = self._page(share, tail).text
                self.assertNotIn("Shared", text)
                self.assertNotIn("a.pdf", text)
                self.assertIn('type="password"', text)

    def test_a_wrong_or_a_broken_key_is_the_same_as_none(self):
        share = self.Share.create({"document_id": self.pdf.id, "password": PASSWORD})
        for key in ("", "wrong", "x" * 600):
            with self.subTest(key=key[:5]):
                response = self._page(share, key=key)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("a.pdf", response.text)
        response = self._page(share, key=True)
        self.assertIn("a.pdf", response.text)
        self.assertNotIn('type="password"', response.text)
        self.assertEqual(share.view_count, 1)
        self.assertNoSession(response)

    def test_the_key_opens_the_pages_and_the_files_of_a_folder(self):
        share = self.Share.create({"folder_id": self.folder.id, "password": PASSWORD})
        sub = self.Folder.create({"name": "Sub", "parent_id": self.folder.id})
        self._document(sub, "in-sub.txt", b"x")
        self.assertIn("a.pdf", self._page(share, key=True).text)
        self.assertIn("in-sub.txt", self._page(share, f"/folder/{sub.id}", key=True).text)
        self.assertEqual(self._page(share, f"/content/{self.pdf.id}", key=True).status_code, 200)
        self.assertEqual(self._page(share, f"/content/{self.pdf.id}").status_code, 403)

    def test_a_key_of_another_share_does_not_open_the_page(self):
        first = self.Share.create({"document_id": self.pdf.id, "password": PASSWORD})
        second = self.Share.create({"document_id": self.picture.id, "password": PASSWORD})
        response = self._page(second, key=first._unlock_key())
        self.assertNotIn("p.png", response.text)
        self.assertIn('type="password"', response.text)
