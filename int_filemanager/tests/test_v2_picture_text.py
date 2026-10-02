"""The text of a JPEG or PNG is read on request, never by the queue on its own."""

import json

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .. import derivative_plan as plan
from ..models import int_filemanager_derivative as derivative_module
from .test_v2_derivative import JPEG, PNG, FakeConverter
from .test_v2_derivative_kinds import text_result
from .test_v2_field_value_suggest import FieldValueCase, words_of
from .test_v2_value_suggest import layout


@tagged("post_install", "-at_install")
class TestV2PictureText(FieldValueCase):
    def _words_job(self, node):
        return self._job_of(node, "words")

    def _read_text(self, node, page):
        """Ask for the text and let the converter answer with the words of ``page``."""
        self.Node.with_user(self.writer).request_text(node.id)
        data = json.dumps(words_of(page)).encode()
        return self._run(
            FakeConverter(
                by_kind={"words": lambda sha256: text_result(data, "application/json")}
            )
        )

    def test_only_jpeg_and_png_can_be_read(self):
        for name, readable in (
            ("a.jpg", True),
            ("a.JPEG", True),
            ("a.png", True),
            ("a.gif", False),
            ("a.webp", False),
            ("a.tif", False),
            ("a.heic", False),
            ("a.pdf", False),
        ):
            with self.subTest(name=name):
                self.assertEqual(plan.can_read_text(name), readable)

    def test_the_queue_does_not_read_pictures_on_its_own(self):
        node = self._file("foto.jpg", JPEG)
        converter = self._run()
        self.assertFalse(converter.of_kind("words"))
        self.assertFalse(self._words_job(node))
        self.assertEqual(
            [item.kind for item in plan.job_plan("foto.jpg")],
            ["tile", "preview", "meta"],
        )

    def test_a_picture_offers_to_read_its_text(self):
        node = self._file("foto.jpg", JPEG)
        self._run()
        answer = self._suggest(node)
        self.assertEqual(answer["state"], "none")
        self.assertTrue(answer["can_read_text"])

    def test_nothing_is_offered_for_other_files(self):
        for name, content in (
            ("foto.gif", b"GIF89a-photo"),
            ("zahlen.txt", b"no values here"),
        ):
            with self.subTest(name=name):
                node = self._file(name, content)
                self._run()
                self.assertFalse(self._suggest(node).get("can_read_text"))

    def test_asking_queues_one_job_in_front_of_the_rest(self):
        node = self._file("foto.png", PNG)
        self.Node.with_user(self.writer).request_text(node.id)
        self.Node.with_user(self.writer).request_text(node.id)
        job = self._words_job(node)
        self.assertEqual(len(job), 1)
        self.assertEqual(
            (job.state, job.spec, job.hint_ext, job.priority),
            ("pending", plan.WORDS_SPEC, "png", derivative_module.VISIBLE_PRIORITY),
        )
        answer = self._suggest(node)
        self.assertEqual(answer["state"], "pending")
        self.assertFalse(answer["can_read_text"])

    def test_the_words_of_the_picture_are_there_when_the_converter_is_done(self):
        node = self._file("beleg.jpg", JPEG)
        page = layout((100, [(50, "Rechnungsnummer"), (200, "R-2024-001")]))
        converter = self._read_text(node, page)
        self.assertEqual(
            [call[2:] for call in converter.of_kind("words")],
            [("words", plan.WORDS_SPEC, "jpg")],
        )
        answer = self._suggest(node)
        self.assertEqual(answer["state"], "ready")
        best = self._best(answer, self.invoice)
        self.assertEqual(best["value"]["value_text"], "R-2024-001")
        self.assertEqual(best["page"], 1)
        words = self.Node.with_user(self.writer).page_words(
            node.id, node.current_revision_id.id, 1
        )
        self.assertEqual(words["state"], "ready")
        self.assertEqual(len(words["words"]), len(page.words))

    def test_the_text_of_a_picture_is_found_by_the_content_search(self):
        node = self._file("beleg.jpg", JPEG)
        self._read_text(node, layout((100, [(50, "Zahnarztrechnung")])))
        found = self.Node.with_user(self.writer).search(
            [("id", "=", node.id), ("content", "ilike", "Zahnarztrechnung")]
        )
        self.assertEqual(found, node)

    def test_a_job_that_gave_up_is_started_again(self):
        node = self._file("beleg.jpg", JPEG)
        self.Node.with_user(self.writer).request_text(node.id)
        job = self._words_job(node)
        job.write({"state": "failed", "attempts": 3, "error": "boom"})
        self.assertEqual(self._suggest(node)["state"], "none")
        self.assertTrue(self._suggest(node)["can_read_text"])
        self.Node.with_user(self.writer).request_text(node.id)
        self.assertEqual((job.state, job.attempts, job.error), ("pending", 0, False))

    def test_a_finished_job_is_not_run_twice(self):
        node = self._file("beleg.jpg", JPEG)
        self._read_text(node, layout((100, [(50, "Rechnungsnummer 1")])))
        self.Node.with_user(self.writer).request_text(node.id)
        self.assertEqual(self._words_job(node).state, "done")

    def test_files_that_cannot_be_read_are_refused(self):
        for name, content in (("foto.gif", b"GIF89a"), ("doc.pdf", b"%PDF-1.4 x")):
            with self.subTest(name=name):
                node = self._file(name, content)
                with self.assertRaises(UserError):
                    self.Node.with_user(self.writer).request_text(node.id)
        with self.assertRaises(UserError):
            self.Node.with_user(self.writer).request_text(self.folder.id)

    def test_asking_needs_the_right_to_write(self):
        node = self._file("beleg.jpg", JPEG)
        with self.assertRaises(AccessError):
            self.Node.with_user(self.outsider).request_text(node.id)
        self.assertFalse(self._words_job(node))
