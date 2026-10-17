import errno
import json
import os
import time
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import HttpCase, tagged
from odoo.tools.misc import verify_limited_field_access_token

from ..models.int_filemanager_document import THUMBNAIL_CRON_XMLID
from .test_folder_access import AccessCase

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n" + b"x" * 100
PASSWORD = "a long password"
MEBIBYTE = 1024 * 1024


@tagged("post_install", "-at_install")
class TestShareUpload(AccessCase, HttpCase):
    """What a guest may put into a folder through a share, and what is kept of a refused file."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Share = cls.env["int.filemanager.share"]

    def setUp(self):
        super().setUp()
        self.env.registry._int_filemanager_share_brake = None
        self.env["ir.config_parameter"].set_param("int_filemanager.share_brake", "0")
        self.folder = self.Folder.create({"name": "Mailbox", "access_mode": "open"})
        self.share = self.Share.create(
            {
                "folder_id": self.folder.id,
                "can_upload": True,
                "upload_max_file_mb": 1,
                "upload_max_total_mb": 3,
                "upload_max_files": 3,
            }
        )
        self.upload_folder = self.share.upload_folder_id

    # --- helpers ------------------------------------------------------------------------------

    def _url(self, share=None, tail="upload", key=None):
        share = share or self.share
        url = f"/int_filemanager/share/{share.token}/{tail}"
        return f"{url}?k={key}" if key else url

    def _send(self, name, data, share=None, key=None, mimetype="application/octet-stream", **kwargs):
        return self.url_open(
            self._url(share, key=key), files={"ufile": (name, data, mimetype)}, **kwargs
        )

    def _post_json(self, tail, body, share=None):
        # ``url_open`` sends a body that is false (``[]``, ``{}``, ``null``) as a GET: pass text
        return self.url_open(
            self._url(share, tail),
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )

    def _kept(self):
        """What is on the disk for the uploads now: the blobs and the temporary files."""
        found = set()
        root = self.Document._blob_path("0" * 64).rsplit(os.sep, 2)[0]
        for folder, _subfolders, names in os.walk(root):
            found.update(os.path.join(folder, name) for name in names)
        return found

    def _count(self):
        self.share.invalidate_recordset()
        return self.share.upload_count, self.share.upload_size

    def _documents(self):
        return self.Document.with_context(active_test=False).search([("share_id", "=", self.share.id)])

    def _assert_refused(self, response, status):
        self.assertEqual(response.status_code, status, response.text[:200])
        self.assertEqual(self._count(), (0, 0))
        self.assertFalse(self._documents())

    def _upload_ok(self, name="a.pdf", data=PDF, **kwargs):
        response = self._send(name, data, **kwargs)
        self.assertEqual(response.status_code, 200, response.text[:200])
        return response.json()

    # --- a file that is taken --------------------------------------------------------------

    def test_a_file_is_kept_in_the_folder_of_the_uploads_and_a_receipt_is_given(self):
        answer = self._upload_ok(mimetype="text/html")
        self.assertEqual(set(answer), {"id", "name", "size", "receipt"})
        document = self.Document.browse(answer["id"])
        self.addCleanup(os.remove, self.Document._blob_path(document.checksum))
        self.assertEqual(document.folder_id, self.upload_folder)
        self.assertEqual(document.share_id, self.share)
        self.assertEqual(document.name, "a.pdf")
        # the type is made from the name and the start of the file, not from what the browser said
        self.assertEqual(document.mimetype, "application/pdf")
        self.assertEqual(document.create_uid, self.env.ref("base.public_user"))
        self.assertEqual(self._count(), (1, len(PDF)))
        self.assertTrue(
            verify_limited_field_access_token(
                document, "id", answer["receipt"], scope="int_filemanager.share_receipt"
            )
        )

    def test_the_type_the_browser_gives_does_not_change_what_the_file_is(self):
        answer = self._upload_ok("note.txt", b"just text", mimetype="application/x-msdownload")
        document = self.Document.browse(answer["id"])
        self.addCleanup(os.remove, self.Document._blob_path(document.checksum))
        self.assertEqual(document.mimetype, "text/plain")

    def test_a_name_that_is_taken_is_numbered_and_a_direction_mark_goes(self):
        first = self._upload_ok("same.pdf")
        second = self._upload_ok("sa\u202eme.pdf", PDF + b"2")
        self.addCleanup(os.remove, self.Document._blob_path(self.Document.browse(first["id"]).checksum))
        self.addCleanup(os.remove, self.Document._blob_path(self.Document.browse(second["id"]).checksum))
        self.assertEqual((first["name"], second["name"]), ("same.pdf", "same (2).pdf"))

    def test_a_signed_in_user_is_a_guest_at_the_address(self):
        self.authenticate("access_alice", "access_alice")
        answer = self._upload_ok()
        document = self.Document.browse(answer["id"])
        self.addCleanup(os.remove, self.Document._blob_path(document.checksum))
        self.assertEqual(document.create_uid, self.env.ref("base.public_user"))

    def test_a_share_with_a_password_wants_the_key_in_the_address(self):
        self.share.password = PASSWORD
        self.assertEqual(self._send("a.pdf", PDF).status_code, 403)
        self.assertEqual(self._send("a.pdf", PDF, key="wrong").status_code, 403)
        answer = self._upload_ok(key=self.share._unlock_key())
        self.addCleanup(os.remove, self.Document._blob_path(self.Document.browse(answer["id"]).checksum))

    def test_the_page_tells_the_app_how_large_a_file_may_be(self):
        self.share.upload_extensions = "pdf, JPG"
        text = self.url_open(f"/int_filemanager/share/{self.share.token}").text
        self.assertIn(f'"max_file_upload_size": {MEBIBYTE}', text)
        self.assertIn(f'"upload_max_file": {MEBIBYTE}', text)
        self.assertIn('"upload_extensions": ["jpg", "pdf"]', text)
        looking = self.Share.create({"folder_id": self.folder.id})
        text = self.url_open(f"/int_filemanager/share/{looking.token}").text
        self.assertIn('"max_file_upload_size": 0', text)

    # --- the limits ----------------------------------------------------------------------

    def test_a_file_over_the_limit_of_the_share_leaves_nothing(self):
        before = self._kept()
        response = self._send("big.txt", b"a" * (MEBIBYTE + 1))
        self._assert_refused(response, 413)
        self.assertEqual(self._kept(), before)
        self.assertIn("error", response.json())

    def test_the_total_and_the_number_are_kept_by_the_share(self):
        self.share.write({"upload_max_total_mb": 1, "upload_max_files": 2})
        first = self._upload_ok("a.txt", b"a" * 600_000)
        before = self._kept()
        response = self._send("b.txt", b"b" * 600_000)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self._kept(), before)
        self.assertEqual(self._count(), (1, 600_000))
        second = self._upload_ok("c.txt", b"c" * 10)
        response = self._send("d.txt", b"d" * 10)  # two files: the number is reached
        self.assertEqual(response.status_code, 413)
        for answer in (first, second):
            self.addCleanup(os.remove, self.Document._blob_path(self.Document.browse(answer["id"]).checksum))

    def test_an_empty_file_and_a_wrong_number_of_files_are_a_bad_request(self):
        self._assert_refused(self._send("empty.txt", b""), 400)
        response = self.url_open(self._url(), files=[("ufile", ("a.txt", b"a")), ("ufile", ("b.txt", b"b"))])
        self._assert_refused(response, 400)
        response = self.url_open(self._url(), files={"other": ("a.txt", b"a")})
        self._assert_refused(response, 400)

    def test_the_body_is_limited_before_it_is_read(self):
        """A body over the largest file and the frame is turned away by Odoo: the handler does not
        run, and the brake does not count it."""
        document = type(self.Document)
        with patch.object(document, "_create_from_stream") as store:
            response = self._send("big.txt", b"a" * (MEBIBYTE + 100_000))
            self.assertEqual(response.status_code, 413)
            store.assert_not_called()
        self.assertEqual(self._count(), (0, 0))

    def test_a_share_that_takes_no_files_takes_no_body_over_the_frame(self):
        """Blocked, expired, full, locked by a password, folder gone: all the same 413 for a big
        body, a refusal with the reason for a small one."""
        big = b"a" * 100_000

        def make(**values):
            return self.Share.create({"folder_id": self.folder.id, "can_upload": True, **values})

        cases = {
            "blocked": make(),
            "expired": make(),
            "full": make(upload_max_files=1),
            "password": make(),
            "no folder": make(),
            "no upload": self.Share.create({"folder_id": self.folder.id, "can_view": True}),
        }
        cases["blocked"].active = False
        cases["full"].upload_count = 1
        cases["password"].password = PASSWORD
        # the ORM would repair these two (a date in the past is refused, a missing folder is made)
        self.env.flush_all()  # what the ORM has not written yet would come after the SQL
        self.env.cr.execute(
            "UPDATE int_filemanager_share SET expiration_date = now() - interval '1 day' WHERE id = %s",
            [cases["expired"].id],
        )
        self.env.cr.execute(
            "UPDATE int_filemanager_share SET upload_folder_id = NULL WHERE id = %s", [cases["no folder"].id]
        )
        self.env.invalidate_all()
        self.assertEqual(cases["expired"].state, "expired")
        for name, share in cases.items():
            with self.subTest(name):
                self.assertEqual(self._send("a.txt", big, share=share).status_code, 413)
        self.assertEqual(self._send("a.txt", b"small", share=cases["blocked"]).status_code, 410)
        self.assertEqual(self._send("a.txt", b"small", share=cases["expired"]).status_code, 410)
        self.assertEqual(self._send("a.txt", b"small", share=cases["password"]).status_code, 403)
        self.assertEqual(self._send("a.txt", b"small", share=cases["no upload"]).status_code, 403)
        self.assertEqual(self._send("a.txt", b"small", share=cases["no folder"]).status_code, 410)

    def test_the_largest_body_follows_the_state_of_the_share(self):
        limit = self.Share._upload_body_limit
        frame = 64 * 1024
        token = self.share.token
        self.assertEqual(limit(token, None), MEBIBYTE + frame)
        self.assertEqual(limit("not a token", None), frame)
        self.assertEqual(limit(None, None), frame)
        self.assertEqual(limit(self.Share.create({"folder_id": self.folder.id}).token, None), frame)
        # what is left of the total is less than the largest file
        self.share.write({"upload_max_total_mb": 2, "upload_size": 2 * MEBIBYTE - 1000})
        self.assertEqual(limit(token, None), 1000 + frame)
        self.share.upload_size = 2 * MEBIBYTE
        self.assertEqual(limit(token, None), frame)
        self.share.write({"upload_size": 0, "active": False})
        self.assertEqual(limit(token, None), frame)

    # --- what a name and a start of a file say --------------------------------------------

    def test_the_endings_that_run_are_never_taken(self):
        names = ("a.exe", "a.html", "a.svg", "a.php", "a.js", "a.bat", "a.lnk", "a.docm", "a.EXE")
        # a dot or a space at the end is not seen by Windows; a direction mark hides the ending
        for name in names + ("a.exe.", "a.exe ", "a.\u202eexe", "a.ex\u200be"):
            with self.subTest(name):
                self.assertEqual(self._send(name, PDF).status_code, 415)
        self.assertFalse(self._documents())

    def test_only_the_endings_that_the_maker_named_are_taken(self):
        self.share.upload_extensions = "pdf, .JPG"
        self.assertEqual(self._send("a.txt", b"text").status_code, 415)
        self.assertEqual(self._send("noending", b"text").status_code, 415)
        answer = self._upload_ok("a.pdf")
        self.addCleanup(os.remove, self.Document._blob_path(self.Document.browse(answer["id"]).checksum))

    def test_the_start_of_a_file_has_to_say_what_its_ending_says(self):
        html = b"<!DOCTYPE html><html><body><script>alert(1)</script></body></html>"
        program = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 200
        elf = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 200
        cases = {
            "page.pdf": html,
            "picture.png": PDF,
            "program.pdf": program,
            "program.dat": program,
            "program.txt": program,
            "elf.dat": elf,
            "binary.txt": b"text\x00more",
            "word.docx": PDF,
        }
        for name, data in cases.items():
            with self.subTest(name):
                self.assertEqual(self._send(name, data).status_code, 415, name)
        self._assert_refused(self._send("again.pdf", html), 415)

    def test_files_that_are_what_they_say_are_taken(self):
        self.share.upload_max_files = 10
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 30
        for name, data in (("a.png", png), ("a.pdf", PDF), ("a.csv", b"a,b\n1,2\n"), ("a.dat", b"\x01\x02\x03 data")):
            with self.subTest(name):
                answer = self._upload_ok(name, data)
                self.addCleanup(os.remove, self.Document._blob_path(self.Document.browse(answer["id"]).checksum))

    def test_a_failure_after_the_limits_were_taken_gives_them_back(self):
        document = type(self.Document)
        before = self._kept()
        with patch.object(document, "_create_numbered", side_effect=ValueError("no document")):
            response = self.url_open(self._url(), files={"ufile": ("a.pdf", PDF)})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self._count(), (0, 0))
        self.assertEqual(self._kept(), before)

    def test_a_disk_that_is_full_answers_507(self):
        document = type(self.Document)
        with patch.object(document, "_store_stream", side_effect=OSError(errno.ENOSPC, "full")):
            response = self.url_open(self._url(), files={"ufile": ("a.pdf", PDF)})
        self._assert_refused(response, 507)

    # --- the brake -----------------------------------------------------------------------

    def test_the_brake_stops_an_address_that_sends_too_often(self):
        self.env["ir.config_parameter"].set_param("int_filemanager.share_brake", "1")
        self.env["ir.config_parameter"].set_param("int_filemanager.share_uploads_per_minute", "2")
        self.assertEqual(self._send("a.txt", b"1").status_code, 200)
        self.assertEqual(self._send("b.txt", b"2").status_code, 200)
        self.assertEqual(self._send("c.txt", b"3").status_code, 429)
        for document in self._documents():
            self.addCleanup(os.remove, self.Document._blob_path(document.checksum))

    def test_without_the_brake_nothing_stops_the_address(self):
        self.env["ir.config_parameter"].set_param("int_filemanager.share_uploads_per_minute", "1")
        self.env["ir.config_parameter"].set_param("int_filemanager.share_brake", "0")
        self.share.upload_max_files = 3
        for number in range(3):
            answer = self._upload_ok(f"{number}.txt", b"x" * (number + 1))
            self.addCleanup(os.remove, self.Document._blob_path(self.Document.browse(answer["id"]).checksum))

    # --- the folder of the uploads ----------------------------------------------------------

    def test_the_folder_must_be_there_active_and_below_the_target(self):
        self.upload_folder.active = False
        self._assert_refused(self._send("a.txt", b"x"), 410)
        self.upload_folder.active = True
        other = self.Folder.create({"name": "Elsewhere", "access_mode": "open"})
        self.upload_folder.parent_id = other
        self._assert_refused(self._send("a.txt", b"x"), 410)
        self.upload_folder.parent_id = self.folder
        answer = self._upload_ok("a.pdf")
        self.addCleanup(os.remove, self.Document._blob_path(self.Document.browse(answer["id"]).checksum))

    def test_switching_the_upload_off_closes_the_routes_and_keeps_the_files(self):
        answer = self._upload_ok()
        self.addCleanup(os.remove, self.Document._blob_path(self.Document.browse(answer["id"]).checksum))
        body = {"receipts": [{"id": answer["id"], "receipt": answer["receipt"]}]}
        self.share.write({"can_upload": False, "can_view": True})
        self.assertEqual(self._send("b.pdf", PDF + b"2").status_code, 403)
        self.assertEqual(self._post_json("uploads", body).status_code, 403)
        delete = {"id": answer["id"], "receipt": answer["receipt"]}
        self.assertEqual(self._post_json("uploads/delete", delete).status_code, 403)
        self.assertTrue(self.Document.browse(answer["id"]).exists())
        self.assertEqual(self.share.upload_folder_id, self.upload_folder)
        self.share.can_upload = True
        self.assertEqual(self.share.upload_folder_id, self.upload_folder)
        self.assertEqual(self._post_json("uploads", body).status_code, 200)

    # --- the uploads of the guest ------------------------------------------------------------

    def _own(self, name="a.pdf", data=PDF, share=None):
        answer = self._send(name, data, share=share).json()
        self.addCleanup(self._remove_blob, answer["id"])
        return answer

    def _remove_blob(self, document_id):
        document = self.Document.with_context(active_test=False).browse(document_id).exists()
        if document:
            path = self.Document._blob_path(document.checksum)
            if os.path.exists(path):
                os.remove(path)

    def test_the_list_shows_the_files_that_a_receipt_proves(self):
        mine = self._own()
        other_share = self.Share.create({"folder_id": self.folder.id, "can_upload": True})
        foreign = self._own("b.pdf", PDF + b"2", share=other_share)
        body = {
            "receipts": [
                {"id": mine["id"], "receipt": mine["receipt"]},
                {"id": foreign["id"], "receipt": foreign["receipt"]},  # a file of another share
                {"id": mine["id"] + 1000, "receipt": mine["receipt"]},  # the receipt of another file
            ]
        }
        response = self._post_json("uploads", body)
        self.assertEqual(response.status_code, 200)
        shown = response.json()
        self.assertEqual([item["id"] for item in shown], [mine["id"]])
        self.assertEqual(set(shown[0]), {"id", "name", "size", "time", "removable"})
        self.assertTrue(shown[0]["removable"])

    def test_receipts_in_a_wrong_form_are_dropped_without_an_error(self):
        mine = self._own()
        good = {"id": mine["id"], "receipt": mine["receipt"]}
        digest = mine["receipt"].split("o")[0]
        junk = [
            1,
            None,
            "text",
            [],
            {},
            {"id": mine["id"]},
            {"id": mine["id"], "receipt": None},
            {"id": mine["id"], "receipt": 12345},
            {"id": mine["id"], "receipt": ["x"]},
            {"id": mine["id"], "receipt": {"a": 1}},
            {"id": mine["id"], "receipt": digest + "o0xzz"},
            {"id": mine["id"], "receipt": digest + "o0x" + "f" * 12},  # the time is too far away
            {"id": mine["id"], "receipt": "a" * 500},
            {"id": True, "receipt": mine["receipt"]},
            {"id": "1", "receipt": mine["receipt"]},
            {"id": 2**40, "receipt": mine["receipt"]},
            {"id": -1, "receipt": mine["receipt"]},
            {"id": 1.5, "receipt": mine["receipt"]},
        ]
        response = self._post_json("uploads", {"receipts": junk + [good]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [mine["id"]])

    def test_a_call_that_is_not_in_the_form_is_a_bad_request(self):
        for body in ([], "text", {"receipts": "x"}, {"receipts": {}}, {}, None):
            with self.subTest(body=body):
                self.assertEqual(self._post_json("uploads", body).status_code, 400)
        self.assertEqual(self.url_open(self._url(tail="uploads"), data="not json").status_code, 400)

    def test_a_guest_takes_away_what_he_uploaded_and_the_limits_are_free_again(self):
        mine = self._own()
        self.assertEqual(self._count(), (1, len(PDF)))
        body = {"id": mine["id"], "receipt": mine["receipt"]}
        response = self._post_json("uploads/delete", body)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.Document.browse(mine["id"]).exists())
        self.assertEqual(self._count(), (0, 0))
        # a second time: nothing is there
        self.assertEqual(self._post_json("uploads/delete", body).status_code, 404)

    def test_a_wrong_receipt_removes_nothing_and_says_nothing(self):
        mine = self._own()
        other = self._own("b.pdf", PDF + b"2")
        for body in (
            {"id": mine["id"], "receipt": other["receipt"]},
            {"id": mine["id"], "receipt": "x"},
            {"id": mine["id"]},
            {"id": "x", "receipt": mine["receipt"]},
            {},
        ):
            with self.subTest(body=body):
                self.assertEqual(self._post_json("uploads/delete", body).status_code, 404)
        self.assertEqual(len(self._documents()), 2)

    def test_a_file_that_a_user_took_over_cannot_be_taken_away(self):
        moved, linked, archived = self._own("a.pdf"), self._own("b.pdf", PDF + b"2"), self._own("c.pdf", PDF + b"3")
        self.Document.browse(moved["id"]).folder_id = self.folder
        partner = self.env["res.partner"].create({"name": "Somebody"})
        self.env["int.filemanager.link"].create(
            {
                "document_id": linked["id"],
                "res_model_id": self.env["ir.model"]._get_id("res.partner"),
                "res_id": partner.id,
            }
        )
        self.Document.browse(archived["id"]).active = False
        for answer in (moved, linked, archived):
            with self.subTest(answer["name"]):
                body = {"id": answer["id"], "receipt": answer["receipt"]}
                self.assertEqual(self._post_json("uploads/delete", body).status_code, 403)
                self.assertTrue(self.Document.with_context(active_test=False).browse(answer["id"]).exists())
        listed = self._post_json(
            "uploads", {"receipts": [{"id": a["id"], "receipt": a["receipt"]} for a in (moved, linked, archived)]}
        ).json()
        self.assertEqual([item["removable"] for item in listed], [False, False, False])

    def test_an_ended_share_does_not_remove_or_list(self):
        mine = self._own()
        body = {"id": mine["id"], "receipt": mine["receipt"]}
        self.share.active = False
        self.assertEqual(self._post_json("uploads/delete", body).status_code, 410)
        self.assertEqual(self._post_json("uploads", {"receipts": [body]}).status_code, 410)
        self.assertTrue(self.Document.browse(mine["id"]).exists())

    def test_a_receipt_does_not_outlive_the_share_or_ninety_days(self):
        mine = self._own()
        document = self.Document.browse(mine["id"])
        self.assertIsNotNone(document)
        end = int(mine["receipt"].rsplit("o", 1)[1], 16)
        self.assertLessEqual(end, time.time() + 90 * 86400 + 5)
        self.share.expiration_date = fields.Datetime.now() + timedelta(hours=1)
        again = self.share._receipt(document)
        self.assertLessEqual(int(again.rsplit("o", 1)[1], 16), time.time() + 3600 + 5)

    def test_a_broken_pdf_is_a_file_that_the_cron_gives_up_on_without_an_error(self):
        mine = self._own("broken.pdf", b"%PDF-1.4 this is not a pdf at all")
        document = self.Document.browse(mine["id"])
        cron = self.env.ref(THUMBNAIL_CRON_XMLID)
        with patch.object(self.env.cr, "commit"):  # a test must not commit
            self.Document.with_context(cron_id=cron.id)._cron_thumbnails()
        self.assertEqual(document.thumbnail_state, "failed")
