import base64
import io
import os
from datetime import timedelta
from unittest.mock import patch

from PIL import Image

from odoo import fields
from odoo.tests.common import HttpCase, TransactionCase, tagged
from odoo.tools import image as image_tools

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase


PASSWORD = "a long password"


def png(size=(40, 30), mode="RGB"):
    stream = io.BytesIO()
    Image.new(mode, size).save(stream, "PNG")
    return stream.getvalue()


@tagged("post_install", "-at_install")
class TestShareCounters(AccessCase, TransactionCase):
    """The counters are changed by SQL: once a minute for the visits, exact for the downloads."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Share = cls.env["int.filemanager.share"]

    def test_a_visit_is_counted_once_a_minute(self):
        share = self.Share.create({"folder_id": self.shared.id})
        now = fields.Datetime.now()
        with patch.object(fields.Datetime, "now", return_value=now):
            self.assertTrue(share._count_visit())
            self.assertFalse(share._count_visit())
        self.assertEqual((share.view_count, share.last_access), (1, now))
        later = now + timedelta(seconds=61)
        with patch.object(fields.Datetime, "now", return_value=later):
            self.assertTrue(share._count_visit())
        self.assertEqual(share.view_count, 2)

    def test_a_download_is_counted_up_to_the_limit_and_the_state_follows(self):
        document = self._document(self.shared)
        share = self.Share.create({"document_id": document.id, "max_downloads": 2})
        self.assertEqual(share.state, "valid")
        self.assertTrue(share._count_download())
        self.assertEqual((share.download_count, share.state), (1, "valid"))
        self.assertTrue(share._count_download())
        self.assertEqual((share.download_count, share.state), (2, "limit"))
        self.assertFalse(share._count_download())
        self.assertEqual(share.download_count, 2)

    def test_without_a_limit_every_download_is_counted(self):
        share = self.Share.create({"document_id": self._document(self.shared).id})
        for __ in range(3):
            self.assertTrue(share._count_download())
        self.assertEqual(share.download_count, 3)


@tagged("post_install", "-at_install")
class TestShareFiles(AccessCase, HttpCase):
    """The routes of the files: what is shown, what is downloaded, what is counted."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Share = cls.env["int.filemanager.share"]

    def setUp(self):
        super().setUp()
        self.env.registry._int_filemanager_share_brake = None
        self.folder = self.Folder.create({"name": "Files", "access_mode": "open"})
        self.hidden = self.Folder.create({"name": "Hidden", "parent_id": self.folder.id, "access_mode": "restricted"})
        self.pdf = self._document(self.folder, "a.pdf", b"%PDF-1.4 hello")
        self.text = self._document(self.folder, "n.txt", b"plain text")
        self.binary = self._document(self.folder, "x.bin", b"\x00\x01\x02\x03 binary")
        self.picture = self._document(self.folder, "p.png", png())
        self.in_hidden = self._document(self.hidden, "h.txt", b"hidden")
        self.outside = self._document(self.shared, "o.txt", b"outside")
        self.archived = self._document(self.folder, "z.txt", b"archived")
        self.archived.active = False
        self.share = self.Share.create({"folder_id": self.folder.id})

    def _url(self, kind, document, share=None, tail=""):
        share = share or self.share
        return f"/int_filemanager/share/{share.token}/{kind}/{document.id}{tail}"

    def _open(self, document, share=None, **kwargs):
        return self.url_open(self._url("content", document, share), **kwargs)

    # --- showing and downloading --------------------------------------------------------------

    def test_a_file_that_a_browser_shows_is_shown_inline(self):
        for document, mimetype in ((self.pdf, "application/pdf"), (self.text, "text/plain"), (self.picture, "image/png")):
            with self.subTest(document.name):
                response = self._open(document)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.headers["Content-Type"].startswith(mimetype))
                self.assertNotIn("attachment", response.headers.get("Content-Disposition", ""))

    def test_the_other_types_are_not_shown_to_those_who_may_only_see(self):
        self.assertEqual(self._open(self.binary).status_code, 403)
        self.share.can_download = True
        self.assertEqual(self._open(self.binary, params={"download": "1"}).status_code, 200)

    def test_download_needs_the_right_and_gives_an_attachment(self):
        self.share.can_download = False
        self.assertEqual(self._open(self.pdf, params={"download": "1"}).status_code, 403)
        self.share.can_download = True
        response = self._open(self.pdf, params={"download": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(response.content, b"%PDF-1.4 hello")
        self.share.write({"can_view": False})
        self.assertEqual(self._open(self.pdf).status_code, 403)  # not shown without the right to see

    def test_headers_and_no_cookie(self):
        response = self._open(self.pdf)
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(response.headers["Cache-Control"], "private, no-cache")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertNotIn("Set-Cookie", response.headers)

    def test_a_file_outside_the_scope_is_not_there(self):
        for document in (self.in_hidden, self.outside, self.archived):
            with self.subTest(document.name):
                self.assertEqual(self._open(document).status_code, 404)
                self.assertEqual(self.url_open(self._url("thumbnail", document)).status_code, 404)
                self.assertEqual(self.url_open(self._url("image", document, tail="/256")).status_code, 404)
                self.assertEqual(self.url_open(self._url("download", document), data={"x": "y"}).status_code, 404)

    def test_the_share_of_a_file_gives_that_file_only(self):
        share = self.Share.create({"document_id": self.pdf.id})
        self.assertEqual(self._open(self.pdf, share).status_code, 200)
        self.assertEqual(self._open(self.text, share).status_code, 404)

    def test_a_missing_blob_is_404_for_the_file_and_the_placeholder_for_the_picture(self):
        os.unlink(self.Document._blob_path(self.picture.checksum))
        self.assertEqual(self._open(self.picture).status_code, 404)
        response = self.url_open(self._url("image", self.picture, tail="/256"))
        self.assertEqual(response.status_code, 200)

    def test_a_blocked_share_and_a_password_stop_the_files(self):
        share = self.Share.create({"folder_id": self.folder.id, "password": PASSWORD})
        self.assertEqual(self._open(self.pdf, share).status_code, 403)
        self.assertEqual(self._open(self.pdf, share, params={"k": share._unlock_key()}).status_code, 200)
        self.share.action_archive()
        self.assertEqual(self._open(self.pdf).status_code, 410)

    def test_a_logged_in_user_gets_what_a_guest_gets(self):
        self.authenticate("access_alice", "access_alice")
        self.assertEqual(self._open(self.in_hidden).status_code, 404)
        self.assertEqual(self._open(self.pdf).status_code, 200)

    # --- the ETag -------------------------------------------------------------------------------

    def test_the_etag_is_not_the_checksum_and_is_one_per_share(self):
        first = self._open(self.pdf).headers["ETag"]
        again = self._open(self.pdf).headers["ETag"]
        other = self._open(self.pdf, self.Share.create({"folder_id": self.folder.id})).headers["ETag"]
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)
        for etag in (first, other):
            self.assertNotIn(self.pdf.checksum[:16], etag)
        self.assertNotEqual(first, self._open(self.text).headers["ETag"])
        revalidated = self._open(self.pdf, headers={"If-None-Match": first})
        self.assertEqual(revalidated.status_code, 304)

    def test_a_blocked_share_answers_a_revalidation_with_410(self):
        etag = self._open(self.pdf).headers["ETag"]
        self.share.action_archive()
        self.assertEqual(self._open(self.pdf, headers={"If-None-Match": etag}).status_code, 410)

    # --- counting and the limit -------------------------------------------------------------------

    def _file_share(self, **values):
        return self.Share.create({"document_id": self.pdf.id, **values})

    def test_a_download_without_a_limit_is_counted_unless_it_asks_for_a_part(self):
        share = self._file_share()
        self._open(self.pdf, share, params={"download": "1"})
        self._open(self.pdf, share, params={"download": "1"}, headers={"Range": "bytes=0-"})
        self._open(self.pdf, share)  # shown, not downloaded
        self.assertEqual(share.download_count, 1)
        self.assertEqual(self._open(self.pdf, share, headers={"Range": "bytes=0-4"}).status_code, 206)

    def test_with_a_limit_the_download_is_a_post_that_counts_every_time(self):
        share = self._file_share(max_downloads=2)
        url = self._url("download", self.pdf, share)
        self.assertEqual(self._open(self.pdf, share, params={"download": "1"}).status_code, 405)
        self.assertEqual(share.download_count, 0)
        first = self.url_open(url, data={"x": "y"})
        self.assertEqual((first.status_code, first.content), (200, b"%PDF-1.4 hello"))
        self.assertIn("attachment", first.headers["Content-Disposition"])
        self.assertEqual(self.url_open(url, data={"x": "y"}, headers={"Range": "bytes=0-1"}).status_code, 200)
        self.assertEqual(share.download_count, 2)
        self.assertEqual(self.url_open(url, data={"x": "y"}).status_code, 410)
        self.assertEqual(share.download_count, 2)
        self.assertEqual(self._open(self.pdf, share).status_code, 410)

    def test_what_is_refused_does_not_use_up_a_download(self):
        share = self._file_share(max_downloads=1)
        self.assertEqual(self.url_open(self._url("download", self.text, share), data={"x": "y"}).status_code, 404)
        share.can_download = False
        share.can_view = True
        self.assertEqual(self.url_open(self._url("download", self.pdf, share), data={"x": "y"}).status_code, 403)
        self.assertEqual(self.url_open(self._url("download", self.pdf, share)).status_code, 405)  # a GET
        os.unlink(self.Document._blob_path(self.pdf.checksum))
        share.can_download = True
        self.assertEqual(self.url_open(self._url("download", self.pdf, share), data={"x": "y"}).status_code, 404)
        self.assertEqual(share.download_count, 0)

    def test_a_head_request_is_not_a_download(self):
        share = self._file_share()
        response = self.opener.head(self.base_url() + self._url("content", self.pdf, share) + "?download=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(share.download_count, 0)

    # --- the pictures ---------------------------------------------------------------------------------

    def test_a_picture_comes_in_the_sizes_of_the_list_only(self):
        response = self.url_open(self._url("image", self.picture, tail="/64"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("image/"))
        self.assertEqual(self.url_open(self._url("image", self.picture, tail="/100")).status_code, 404)
        self.assertEqual(self.url_open(self._url("image", self.picture, tail="/99999")).status_code, 404)

    def test_a_picture_needs_the_right_to_see(self):
        self.share.write({"can_view": False})
        self.assertEqual(self.url_open(self._url("image", self.picture, tail="/64")).status_code, 403)
        self.assertEqual(self.url_open(self._url("thumbnail", self.pdf)).status_code, 403)

    def test_a_picture_of_too_many_pixels_and_a_file_that_is_no_picture_get_the_placeholder(self):
        placeholder = self.url_open(self._url("image", self.pdf, tail="/64")).content
        self.assertTrue(placeholder)
        with patch.object(image_tools, "IMAGE_MAX_RESOLUTION", 100):
            big = self.url_open(self._url("image", self.picture, tail="/64"))
        self.assertEqual(big.status_code, 200)
        self.assertEqual(big.content, placeholder)
        self.assertNotEqual(self.url_open(self._url("image", self.picture, tail="/64")).content, placeholder)

    def test_the_thumbnail_of_a_pdf_is_served_and_the_checksum_is_not_a_field_of_it(self):
        self.pdf.thumbnail = base64.b64encode(png((50, 50)))
        response = self.url_open(self._url("thumbnail", self.pdf))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("image/"))
        self.assertNotIn(self.pdf.checksum[:16], response.headers.get("ETag", ""))
