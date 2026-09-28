"""Derived files beyond thumbnails: the plan per kind of file, the chain from an office
document through its PDF, and the text and facts kept in the job rows."""

import datetime
import hashlib
import io
from unittest.mock import patch

from odoo.tests.common import BaseCase, tagged

from .. import converter_client
from .. import derivative_plan as plan
from ..models import int_filemanager_derivative as derivative_module
from .test_v2_derivative import (
    JPEG,
    META,
    PDF,
    TEXT,
    DerivativeCase,
    FakeConverter,
    refused,
)


def text_result(data, mime="text/plain"):
    return converter_client.ConversionResult(
        "done", stream=io.BytesIO(data), mime=mime, tool="fake"
    )


@tagged("post_install", "-at_install")
class TestJobPlan(BaseCase):
    def kinds(self, name):
        return [item.kind for item in plan.job_plan(name)]

    def test_what_is_derived_from_which_kind_of_file(self):
        for name, expected in (
            ("a.JPG", ["tile", "preview", "meta"]),
            ("a.heic", ["tile", "preview", "meta"]),
            ("a.CR2", ["tile", "preview", "meta"]),
            ("a.mp4", ["tile", "preview", "meta"]),
            ("a.pdf", ["tile", "preview", "text", "meta"]),
            ("a.docx", ["preview_pdf", "tile", "preview", "text"]),
            ("a.xlsx", ["preview_pdf", "tile", "preview", "text"]),
            ("a.mp3", ["tile", "meta"]),
            ("a.flac", ["tile", "meta"]),
            ("a.txt", ["text"]),
            ("a.json", ["text"]),
            ("a.exe", []),
            ("noextension", []),
        ):
            with self.subTest(name=name):
                self.assertEqual(self.kinds(name), expected)

    def test_a_job_made_from_another_comes_after_it(self):
        for ext in plan.ALL_EXTENSIONS:
            seen = set()
            for item in plan.job_plan(f"x.{ext}"):
                if item.after:
                    self.assertIn(item.after, seen, ext)
                seen.add(item.kind)

    def test_only_browser_images_are_their_own_large_preview(self):
        originals = [
            (ext, item.original_mime)
            for ext in plan.ALL_EXTENSIONS
            for item in plan.job_plan(f"x.{ext}")
            if item.original_mime
        ]
        self.assertEqual(
            sorted(ext for ext, _mime in originals), sorted(plan.BROWSER_IMAGE_TYPES)
        )
        self.assertTrue(all(mime.startswith("image/") for _e, mime in originals))

    def test_the_large_preview_the_viewer_needs(self):
        self.assertEqual(plan.full_preview_kind("a.tif"), "preview")
        self.assertEqual(plan.full_preview_kind("a.docx"), "preview_pdf")
        for name in ("a.jpg", "a.pdf", "a.mp4", "a.mp3", "a.txt", "a.exe"):
            self.assertIsNone(plan.full_preview_kind(name), name)

    def test_the_thumbnail_kinds(self):
        self.assertTrue(plan.has_tile("a.docx") and plan.has_tile("a.mp3"))
        self.assertFalse(plan.has_tile("a.txt") or plan.has_tile("a.exe"))

    def test_extension_handling(self):
        self.assertEqual(plan.file_extension("a.b.TIFF"), "tiff")
        for name in ("", None, "noext", "trailingdot.", "x.toolongextension", "x.a-b"):
            self.assertEqual(plan.file_extension(name), "", name)


@tagged("post_install", "-at_install")
class TestKindsQueue(DerivativeCase):
    def _rows(self, node):
        return {
            job.kind: job
            for job in self.Derivative.search(
                [("source_blob_id", "=", node.current_revision_id.blob_id.id)]
            )
        }

    def test_each_kind_of_file_gets_its_rows(self):
        made = {
            "a.jpg": self._file("a.jpg", JPEG),
            "d.docx": self._file("d.docx", b"docx bytes"),
            "s.mp3": self._file("s.mp3", b"mp3 bytes"),
            "v.mp4": self._file("v.mp4", b"mp4 bytes"),
            "p.pdf": self._file("p.pdf", b"pdf bytes"),
            "t.txt": self._file("t.txt", b"text bytes"),
        }
        self.Derivative._enqueue_missing()
        got = {name: sorted(self._rows(node)) for name, node in made.items()}
        self.assertEqual(
            got,
            {
                "a.jpg": ["meta", "preview", "tile"],
                "d.docx": ["preview", "preview_pdf", "text", "tile"],
                "s.mp3": ["meta", "tile"],
                "v.mp4": ["meta", "preview", "tile"],
                "p.pdf": ["meta", "preview", "text", "tile"],
                "t.txt": ["text"],
            },
        )

    def test_queueing_again_adds_nothing_and_a_missing_row_is_caught_up(self):
        photo = self._file("a.jpg", JPEG)
        self.Derivative._enqueue_missing()
        first = self._rows(photo)
        self.Derivative._enqueue_missing()
        self.assertEqual(self._rows(photo), first)
        first["meta"].unlink()
        self.Derivative._enqueue_missing()
        self.assertEqual(sorted(self._rows(photo)), ["meta", "preview", "tile"])

    def test_an_office_document_waits_for_its_pdf_and_then_uses_it(self):
        doc = self._file("letter.docx", b"docx bytes")
        self.Derivative._enqueue_missing()
        rows = self._rows(doc)
        self.assertFalse(rows["preview_pdf"].depends_on_id)
        for kind in ("tile", "preview", "text"):
            self.assertEqual(rows[kind].depends_on_id, rows["preview_pdf"])
        with self.subTest("only the PDF can be taken at first"):
            self.assertEqual(self.Derivative._claim_jobs(), rows["preview_pdf"])
        rows["preview_pdf"].state = "pending"
        converter = self._run()
        self.assertEqual(
            {row.state for row in self._rows(doc).values()}, {"done"}, converter.calls
        )
        pdf_sha = hashlib.sha256(PDF).hexdigest()
        self.assertEqual(rows["preview_pdf"].derived_blob_id.sha256, pdf_sha)
        by_kind = {call[2]: call for call in converter.calls}
        self.assertEqual(
            by_kind["preview_pdf"][1:],
            (doc.current_revision_id.blob_id.sha256, "preview_pdf", "pdf", "docx"),
        )
        for kind in ("tile", "preview", "text"):
            self.assertEqual(by_kind[kind][1], pdf_sha, kind)
            self.assertEqual(by_kind[kind][4], "pdf", kind)

    def test_jobs_made_from_a_missing_pdf_are_dropped(self):
        doc = self._file("letter.docx", b"docx bytes")
        converter = FakeConverter(
            by_kind={"preview_pdf": lambda sha256: refused("not_applicable")}
        )
        self._run(converter)
        self._run(converter)
        rows = self._rows(doc)
        self.assertEqual(
            {kind: row.state for kind, row in rows.items()},
            {
                "preview_pdf": "not_applicable",
                "tile": "not_applicable",
                "preview": "not_applicable",
                "text": "not_applicable",
            },
        )
        self.assertEqual([call[2] for call in converter.calls], ["preview_pdf"])

    def test_text_is_kept_in_the_row_and_no_blob_is_made_for_it(self):
        note = self._file("note.txt", b"some text")
        blobs_before = self.Blob.search_count([])
        self._run()
        job = self._rows(note)["text"]
        self.assertEqual((job.state, job.text), ("done", TEXT))
        self.assertFalse(job.derived_blob_id)
        self.assertEqual(self.Blob.search_count([]), blobs_before)

    def test_text_loses_nul_bytes(self):
        note = self._file("note.txt", b"some text")
        self._run(
            FakeConverter(by_kind={"text": lambda sha256: text_result(b"a\x00b")})
        )
        self.assertEqual(self._rows(note)["text"].text, "ab")

    def test_no_text_found_is_a_result_too(self):
        scan = self._file("scan.pdf", b"pdf bytes")
        self._run(FakeConverter(by_kind={"text": lambda sha256: text_result(b"")}))
        job = self._rows(scan)["text"]
        self.assertEqual(job.state, "done")
        self.assertFalse(job.text)

    def test_an_answer_longer_than_allowed_is_not_taken(self):
        note = self._file("note.txt", b"some text")
        converter = FakeConverter(
            by_kind={"text": lambda sha256: text_result(b"x" * 100)}
        )
        with patch.object(derivative_module, "MAX_TEXT_BYTES", 50):
            self._run(converter)
        self.assertEqual(self._rows(note)["text"].state, "pending")

    def test_the_facts_go_into_columns_and_the_whole_object_is_kept(self):
        photo = self._file("a.jpg", JPEG)
        self._run()
        job = self._rows(photo)["meta"]
        self.assertEqual(job.state, "done")
        self.assertEqual(job.taken_at, datetime.datetime(2019, 7, 4, 12, 30))
        self.assertEqual(
            (job.camera, job.width, job.height, job.pages),
            ("ACME Cam 1", 640, 480, 3),
        )
        self.assertEqual((job.duration, job.gps_lat, job.gps_lon), (12.5, 49.5, 6.25))
        self.assertEqual(job.meta, META)

    def test_junk_in_the_facts_is_dropped_not_stored(self):
        photo = self._file("a.jpg", JPEG)
        junk = (
            b'{"width": "abc", "height": -5, "duration": "x", "taken_at": "garbage",'
            b' "camera": 5, "list": [1, 2], "nested": {"a": 1}, "flag": true,'
            b' "big": 1099511627776, "ok": "fine"}'
        )
        self._run(
            FakeConverter(
                by_kind={
                    "meta": lambda sha256: text_result(junk, "application/json"),
                }
            )
        )
        job = self._rows(photo)["meta"]
        self.assertEqual(job.state, "done")
        self.assertFalse(job.width or job.height or job.duration or job.taken_at)
        self.assertFalse(job.camera)
        self.assertEqual(
            job.meta,
            {
                "width": "abc",
                "height": -5,
                "duration": "x",
                "taken_at": "garbage",
                "camera": 5,
                "big": 1099511627776,
                "ok": "fine",
            },
        )

    def test_facts_that_are_no_json_object_leave_the_columns_empty(self):
        photo = self._file("a.jpg", JPEG)
        for answer in (b"not json", b"[1, 2, 3]", b'"text"'):
            job = self._rows(photo).get("meta")
            if job:
                job.unlink()
            self._run(
                FakeConverter(
                    by_kind={
                        "meta": lambda sha256, data=answer: text_result(
                            data, "application/json"
                        )
                    }
                )
            )
            job = self._rows(photo)["meta"]
            with self.subTest(answer=answer):
                self.assertEqual(job.state, "done")
                self.assertFalse(job.meta)

    def test_the_states_for_an_office_file_and_for_audio_and_text(self):
        doc = self._file("letter.docx", b"docx bytes")
        song = self._file("song.mp3", b"mp3 bytes")
        note = self._file("note.txt", b"text bytes")
        self.Derivative._enqueue_missing()

        def states(node):
            node.invalidate_recordset(["preview_state", "full_preview_state"])
            node = node.with_user(self.writer)
            return node.preview_state, node.full_preview_state

        self.assertEqual(states(doc), ("pending", "pending"))
        self.assertEqual(states(song), ("pending", "none"))
        self.assertEqual(states(note), ("none", "none"))
        self._run()
        self.assertEqual(states(doc), ("ready", "ready"))
        self.assertEqual(states(song), ("ready", "none"))
        self._rows(song)["tile"].state = "not_applicable"
        self.assertEqual(states(song), ("none", "none"))

    def test_purging_the_source_removes_the_chain_in_one_go(self):
        doc = self._file("letter.docx", b"docx bytes")
        self._run()
        rows = list(self._rows(doc).values())
        blobs = (
            doc.current_revision_id.blob_id
            | self.Derivative.browse([r.id for r in rows]).derived_blob_id
        )
        doc.sudo().write({"current_revision_id": False})
        doc.revision_ids.sudo().unlink()
        blobs.write({"last_used": "2000-01-01 00:00:00"})
        self.Blob._gc_blobs_unsafe()
        self.assertFalse(self.Derivative.browse([r.id for r in rows]).exists())
        self.assertFalse(blobs.exists())
