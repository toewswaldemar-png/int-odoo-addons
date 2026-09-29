"""Derived files (thumbnails): queue, storing the result, states, cleanup.

The converter is replaced by a fake at the HTTP client; the real service has its own
tests in tools/fmconverter. The last test class proves that Odoo never decodes what
the converter returns.
"""

import contextlib
import hashlib
import importlib
import io
import json
import os
from unittest.mock import patch

import psycopg2

from odoo import fields
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import image as odoo_image

from .. import blobstore, converter_client
from .. import derivative_plan as plan
from ..models import int_filemanager_derivative as derivative_module

# Only the magic bytes matter: nothing in Odoo decodes the file, the fake converter
# never looks at it.
JPEG = b"\xff\xd8\xff\xe0" + b"photo" * 40
OTHER_JPEG = b"\xff\xd8\xff\xe0" + b"other" * 40
TILE = b"\xff\xd8\xff\xe0" + b"tile" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"not really a png" * 4
URL = "http://converter.invalid:8090"


def done(content=TILE):
    return converter_client.ConversionResult(
        "done",
        stream=io.BytesIO(content),
        mime="image/jpeg",
        tool="fake",
        tool_version="1",
    )


def refused(state, error="nope"):
    return converter_client.ConversionResult(state, error=error, tool="fake")


PDF = b"%PDF-1.4 fake"
TEXT = "Hello text \u00e4\u00f6\u00fc"
META = {
    "taken_at": "2019-07-04 12:30:00",
    "camera": "ACME Cam 1",
    "width": 640,
    "height": 480,
    "duration": 12.5,
    "gps_lat": 49.5,
    "gps_lon": 6.25,
    "pages": 3,
}


WORDS = {
    "version": 2,
    "ocr": "none",
    "pages": [{"width": 595.0, "height": 842.0, "rotation": 0}],
    "text": "Hello converter",
    # page, x0, top, x1, bottom, start, end - text[start:end] is the word
    "words": [[1, 10.0, 5.0, 40.0, 15.0, 0, 5], [1, 45.0, 5.0, 110.0, 15.0, 6, 15]],
}


def answer_for(kind):
    """What the converter would send for a kind, if nothing else is arranged."""
    if kind == "preview_pdf":
        return converter_client.ConversionResult(
            "done", stream=io.BytesIO(PDF), mime="application/pdf", tool="fake"
        )
    if kind == "text":
        return converter_client.ConversionResult(
            "done",
            stream=io.BytesIO(TEXT.encode()),
            mime="text/plain",
            tool="fake",
        )
    if kind == "words":
        return converter_client.ConversionResult(
            "done",
            stream=io.BytesIO(json.dumps(WORDS).encode()),
            mime="application/json",
            tool="fake",
        )
    if kind == "meta":
        return converter_client.ConversionResult(
            "done",
            stream=io.BytesIO(json.dumps(META).encode()),
            mime="application/json",
            tool="fake",
        )
    return done()


class FakeConverter:
    """Stands in for converter_client.convert.

    ``answer`` (a function of the blob hash) decides for every kind; ``by_kind`` maps a
    kind to such a function for that kind alone; else the kind's usual answer is given.
    """

    def __init__(self, answer=None, by_kind=None):
        self.answer = answer
        self.by_kind = by_kind or {}
        self.calls = []

    def of_kind(self, kind):
        return [call for call in self.calls if call[2] == kind]

    @contextlib.contextmanager
    def __call__(self, url, sha256, kind, spec, ext, timeout):
        self.calls.append((url, sha256, kind, spec, ext))
        if kind in self.by_kind:
            yield self.by_kind[kind](sha256)
        elif self.answer:
            yield self.answer(sha256)
        else:
            yield answer_for(kind)


class DerivativeCase(TransactionCase):
    def setUp(self):
        super().setUp()
        group = self.env["res.groups"].sudo().create({"name": "Derivative test group"})
        scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Derivative test scope",
                    "read_group_ids": [(4, group.id)],
                    "write_group_ids": [(4, group.id)],
                }
            )
        )
        self.folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "derivs", "scope_id": scope.id, "is_dir": True})
        )
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        Users = self.env["res.users"].sudo()
        self.writer = Users.create(
            {
                "name": "Derivative writer",
                "login": "derivative_writer",
                "group_ids": [(6, 0, [base_group.id, group.id])],
            }
        )
        self.outsider = Users.create(
            {
                "name": "Derivative outsider",
                "login": "derivative_outsider",
                "group_ids": [(6, 0, [base_group.id])],
            }
        )
        self.Derivative = self.env["int_filemanager.derivative"].sudo()
        self.Blob = self.env["int_filemanager.blob"].sudo()
        self.env["ir.config_parameter"].sudo().set_param(
            derivative_module.CONVERTER_URL_PARAM, URL
        )
        self._keys = 0
        # The queue commits between its steps, which a test cursor forbids; the
        # calls are counted instead.
        self.commits = []
        self.enterContext(
            patch.object(
                self.env.registry["ir.cron"],
                "_commit_progress",
                side_effect=lambda *args, **kwargs: self.commits.append(1),
            )
        )

    def _file(self, name, content):
        self._keys += 1
        result = (
            self.env["int_filemanager.node"]
            .with_user(self.writer)
            .create_file(self.folder.id, name, content, f"op-deriv-{self._keys}")
        )
        return self.env["int_filemanager.node"].sudo().browse(result["node_id"])

    def _job_of(self, node, kind="tile"):
        return self.Derivative.search(
            [
                ("source_blob_id", "=", node.current_revision_id.blob_id.id),
                ("kind", "=", kind),
            ]
        )

    def _run(self, converter=None):
        converter = converter or FakeConverter()
        with patch.object(converter_client, "convert", converter):
            self.Derivative._cron_run()
        return converter


@tagged("post_install", "-at_install")
class TestDerivativeQueue(DerivativeCase):
    def test_current_jpeg_gets_one_job_and_others_none(self):
        photo = self._file("a.jpg", JPEG)
        twin = self._file("b.jpg", JPEG)
        self._file("c.xyz", b"plain text")
        self._file("empty.jpg", b"")
        self.Derivative._enqueue_missing()
        self.Derivative._enqueue_missing()
        jobs = self._job_of(photo)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs.kind, "tile")
        self.assertEqual(jobs.spec, plan.TILE_SPEC)
        self.assertEqual(jobs.state, "pending")
        self.assertEqual(self._job_of(twin), jobs, "same content, one job")
        self.assertEqual(
            self.Derivative.search_count(
                [
                    (
                        "source_blob_id.revision_ids.node_id.name",
                        "in",
                        ["c.xyz", "empty.jpg"],
                    )
                ]
            ),
            0,
        )

    def test_without_converter_url_nothing_happens(self):
        photo = self._file("a.jpg", JPEG)
        self.env["ir.config_parameter"].sudo().set_param(
            derivative_module.CONVERTER_URL_PARAM, ""
        )
        converter = self._run()
        self.assertFalse(converter.calls)
        self.assertFalse(self._job_of(photo))

    def test_result_is_stored_as_blob_and_job_is_done(self):
        photo = self._file("a.jpg", JPEG)
        converter = self._run()
        job = self._job_of(photo)
        self.assertEqual(job.state, "done")
        self.assertEqual(job.mime, "image/jpeg")
        self.assertEqual(job.tool, "fake")
        self.assertEqual(len(converter.of_kind("tile")), 1)
        self.assertEqual(
            converter.of_kind("tile")[0][1:],
            (photo.current_revision_id.blob_id.sha256, "tile", "400x300", "jpg"),
        )
        with open(blobstore.blob_path(self.env, job.derived_blob_id.sha256), "rb") as f:
            self.assertEqual(f.read(), TILE)
        self.assertEqual(job.derived_blob_id.size, len(TILE))
        self.assertTrue(job.derived_blob_id.last_used)

    def test_the_converter_is_called_only_after_the_jobs_were_committed(self):
        photo = self._file("a.jpg", JPEG)
        seen = []

        def answer(sha256):
            seen.append(len(self.commits))
            return done()

        self._run(FakeConverter(answer))
        self.assertTrue(seen and seen[0] >= 1, "claimed jobs are committed first")
        self.assertEqual(self._job_of(photo).state, "done")

    def test_converter_unavailable_keeps_the_job_open_without_an_attempt(self):
        photo = self._file("a.jpg", JPEG)

        def answer(sha256):
            raise converter_client.ConverterUnavailable("down")

        self._run(FakeConverter(answer))
        job = self._job_of(photo)
        self.assertEqual(job.state, "pending")
        self.assertEqual(job.attempts, 0)
        self.assertFalse(job.lease_until)

    def test_a_failure_is_retried_and_finally_recorded(self):
        photo = self._file("a.jpg", JPEG)
        converter = FakeConverter(lambda sha256: refused("failed", "bad jpeg"))
        for expected_attempts in (1, 2):
            self._run(converter)
            job = self._job_of(photo)
            self.assertEqual((job.state, job.attempts), ("pending", expected_attempts))
            self.assertGreater(job.next_try_at, fields.Datetime.now())
            # A test transaction's now() stands still: a past time means "later".
            job.next_try_at = "2000-01-01 00:00:00"
        self._run(converter)
        job = self._job_of(photo)
        self.assertEqual((job.state, job.attempts), ("failed", 3))
        self.assertEqual(job.error, "bad jpeg")
        self._run(converter)
        self.assertEqual(len(converter.of_kind("tile")), 3, "failed is not tried again")

    def test_a_job_waits_for_its_retry_time(self):
        photo = self._file("a.jpg", JPEG)
        self.Derivative._enqueue_missing()
        self._job_of(photo).next_try_at = "2999-01-01 00:00:00"
        converter = self._run()
        self.assertFalse(converter.of_kind("tile"))

    def test_not_applicable_is_final(self):
        photo = self._file("a.jpg", JPEG)
        converter = FakeConverter(lambda sha256: refused("not_applicable", "too big"))
        self._run(converter)
        self._run(converter)
        job = self._job_of(photo)
        self.assertEqual(job.state, "not_applicable")
        self.assertEqual(len(converter.of_kind("tile")), 1)

    def test_visible_files_are_converted_first(self):
        first = self._file("a.jpg", JPEG)
        second = self._file("b.jpg", OTHER_JPEG)
        self.Derivative._enqueue_missing()
        with patch.object(derivative_module, "CLAIM_BATCH", 1):
            claimed = self.Derivative._claim_jobs()
        self.assertEqual(claimed, self._job_of(first), "queue order without a request")
        claimed.state = "pending"
        self.env["int_filemanager.node"].with_user(self.writer).request_previews(
            [second.id]
        )
        with patch.object(derivative_module, "CLAIM_BATCH", 1):
            claimed = self.Derivative._claim_jobs()
        self.assertEqual(claimed, self._job_of(second))

    def test_a_claim_conflict_with_another_run_is_retried(self):
        photo = self._file("a.jpg", JPEG)
        real_claim = type(self.Derivative)._claim_jobs
        calls = []

        def claim(model):
            calls.append(1)
            if len(calls) == 1:
                raise psycopg2.errors.SerializationFailure("concurrent update")
            return real_claim(model)

        # A test cursor cannot roll back; the retry itself is what is under test.
        with (
            patch.object(type(self.Derivative), "_claim_jobs", claim),
            patch.object(self.env.cr, "rollback"),
        ):
            self._run()
        self.assertEqual(len(calls) >= 2, True)
        self.assertEqual(self._job_of(photo).state, "done")

    def test_a_job_whose_worker_died_is_taken_again_after_its_lease(self):
        photo = self._file("a.jpg", JPEG)
        self.Derivative._enqueue_missing()
        job = self._job_of(photo)
        job.write({"state": "running", "lease_until": "2999-01-01 00:00:00"})
        self.assertNotIn(job, self.Derivative._claim_jobs(), "lease still valid")
        job.lease_until = "2000-01-01 00:00:00"
        self.assertIn(job, self.Derivative._claim_jobs())

    def test_a_result_for_a_job_that_vanished_is_dropped_quietly(self):
        photo = self._file("a.jpg", JPEG)

        def answer(sha256):
            self._job_of(photo).unlink()
            return done()

        self._run(FakeConverter(answer))
        self.assertFalse(self._job_of(photo))
        orphan = self.Blob.search([("sha256", "=", hashlib.sha256(TILE).hexdigest())])
        self.assertTrue(orphan, "the blob stays for the cleanup job")
        self.assertFalse(orphan.revision_ids)

    def test_a_broken_result_stream_counts_as_converter_unavailable(self):
        photo = self._file("a.jpg", JPEG)

        class Broken(io.BytesIO):
            def read(  # pylint: disable=unknown-option-value,method-required-super
                self, size=-1
            ):
                raise converter_client.ConverterUnavailable("connection reset")

        result = done()
        result.stream = Broken(b"x")
        self._run(FakeConverter(lambda sha256: result))
        job = self._job_of(photo)
        self.assertEqual((job.state, job.attempts), ("pending", 0))


@tagged("post_install", "-at_install")
class TestImageKinds(DerivativeCase):
    def test_the_class_follows_the_extension_only(self):
        for name, expected in (
            ("a.jpg", "browser"),
            ("A.JPEG", "browser"),
            ("b.png", "browser"),
            ("c.webp", "browser"),
            ("d.tif", "converted"),
            ("e.HEIC", "converted"),
            ("f.bmp", "converted"),
            ("g.CR2", "converted"),
            ("h.txt", None),
            ("noextension", None),
            ("photo.jpg.bak", None),
            (".jpg", "browser"),
            ("archive.tar.gz", None),
        ):
            with self.subTest(name=name):
                self.assertEqual(plan.image_class(name), expected)

    def test_a_browser_image_gets_a_tile_job_and_is_its_own_large_preview(self):
        photo = self._file("a.jpg", JPEG)
        self.Derivative._enqueue_missing()
        tile = self._job_of(photo)
        preview = self._job_of(photo, "preview")
        self.assertEqual((tile.state, tile.hint_ext), ("pending", "jpg"))
        self.assertEqual(preview.state, "done")
        self.assertEqual(preview.derived_blob_id, preview.source_blob_id)
        self.assertEqual(preview.mime, "image/jpeg")
        self.assertEqual(preview.spec, plan.PREVIEW_SPEC)

    def test_a_converted_format_gets_two_jobs_and_the_preview_waits(self):
        raw = self._file("IMG_0001.CR2", b"raw sensor data" * 10)
        self.Derivative._enqueue_missing()
        tile, preview = self._job_of(raw), self._job_of(raw, "preview")
        self.assertEqual((tile.state, preview.state), ("pending", "pending"))
        self.assertEqual(tile.hint_ext, "cr2")
        self.assertLess(preview.priority, tile.priority)

    def test_the_converter_is_asked_with_the_extension_hint(self):
        self._file("scan.TIFF", b"tiff-ish" * 20)
        converter = self._run()
        kinds = sorted((call[2], call[3], call[4]) for call in converter.calls)
        self.assertEqual(
            kinds,
            [
                ("meta", "v1", "tiff"),
                ("preview", "1920x1920", "tiff"),
                ("tile", "400x300", "tiff"),
            ],
        )

    def test_other_files_get_no_job(self):
        note = self._file("notes.xyz", b"hello")
        self.Derivative._enqueue_missing()
        self.assertFalse(
            self.Derivative.search(
                [("source_blob_id", "=", note.current_revision_id.blob_id.id)]
            )
        )

    def test_the_large_preview_state_follows_its_job(self):
        raw = self._file("IMG_0002.NEF", b"raw" * 30)
        self.Derivative._enqueue_missing()

        def state():
            raw.invalidate_recordset(["full_preview_state", "preview_state"])
            node = raw.with_user(self.writer)
            return node.preview_state, node.full_preview_state

        self.assertEqual(state(), ("pending", "pending"))
        self._job_of(raw).write({"state": "done"})
        self.assertEqual(state(), ("ready", "pending"))
        self._job_of(raw, "preview").write({"state": "failed"})
        self.assertEqual(state(), ("ready", "failed"))

    def test_a_browser_image_needs_no_large_preview_of_its_own(self):
        """The viewer shows the original; its "preview" job is the original itself."""
        photo = self._file("a.png", PNG)
        self.Derivative._enqueue_missing()
        photo.invalidate_recordset(["full_preview_state"])
        self.assertEqual(photo.with_user(self.writer).full_preview_state, "none")
        self.assertEqual(self._job_of(photo, "preview").state, "done")


@tagged("post_install", "-at_install")
class TestPreviewState(DerivativeCase):
    def _state(self, node):
        # Computed per request in real use; inside one test transaction it is cached.
        node.invalidate_recordset(["preview_state"])
        return node.with_user(self.writer).preview_state

    def test_state_follows_the_job(self):
        photo = self._file("a.jpg", JPEG)
        self.assertEqual(self._state(photo), "pending", "not queued yet, but coming")
        self.Derivative._enqueue_missing()
        self.assertEqual(self._state(photo), "pending")
        self._run()
        self.assertEqual(self._state(photo), "ready")
        self._job_of(photo).write({"state": "failed"})
        self.assertEqual(self._state(photo), "failed")
        self._job_of(photo).write({"state": "not_applicable"})
        self.assertEqual(self._state(photo), "none")

    def test_folders_and_other_types_have_none(self):
        self.assertEqual(self._state(self.folder), "none")
        self.assertEqual(self._state(self._file("c.xyz", b"plain text")), "none")

    def test_request_previews_ignores_what_the_caller_cannot_read(self):
        photo = self._file("a.jpg", JPEG)
        self.Derivative._enqueue_missing()
        count = (
            self.env["int_filemanager.node"]
            .with_user(self.outsider)
            .request_previews([photo.id])
        )
        self.assertEqual(count, 0)
        self.assertEqual(self._job_of(photo).priority, 0)

    def test_request_previews_survives_junk_and_caps_the_list(self):
        Node = self.env["int_filemanager.node"].with_user(self.writer)
        for junk in ("x", None, {"a": 1}, [None, "1", True, 1.5, [1]]):
            with self.subTest(junk=junk):
                self.assertEqual(Node.request_previews(junk), 0)
        with patch.object(
            Node.env.registry["int_filemanager.node"], "search"
        ) as search:
            search.return_value = Node.browse()
            Node.request_previews(list(range(100000)))
        self.assertEqual(
            len(search.call_args.args[0][0][2]), derivative_module.MAX_REQUESTED_NODES
        )


@tagged("post_install", "-at_install")
class TestDerivativeCleanup(DerivativeCase):
    OLD = "2000-01-01 00:00:00"

    def _gc(self):
        return self.Blob._gc_blobs_unsafe()

    def _age(self, *blobs):
        for blob in blobs:
            blob.last_used = self.OLD

    def test_a_derived_blob_is_kept_while_a_job_refers_to_it(self):
        photo = self._file("a.jpg", JPEG)
        self._run()
        job = self._job_of(photo)
        self._age(job.derived_blob_id)
        self._gc()
        self.assertTrue(job.derived_blob_id.exists())
        self.assertTrue(job.exists())

    def test_jobs_of_a_used_blob_are_never_removed(self):
        photo = self._file("a.jpg", JPEG)
        self._run()
        job = self._job_of(photo)
        self._age(photo.current_revision_id.blob_id, job.derived_blob_id)
        self._gc()
        self.assertTrue(job.exists())

    def test_purged_source_takes_job_and_result_with_it(self):
        photo = self._file("a.jpg", JPEG)
        self._run()
        job = self._job_of(photo)
        source, result = job.source_blob_id, job.derived_blob_id
        sha_result = result.sha256
        photo.sudo().write({"current_revision_id": False})
        photo.revision_ids.sudo().unlink()
        self._age(source, result)
        self._gc()
        self.assertFalse(job.exists())
        self.assertFalse(source.exists())
        self.assertFalse(result.exists())
        # The file follows once its marker has aged, like any other blob.
        marker = os.path.join(blobstore.checklist_dir(self.env), sha_result)
        os.utime(marker, (1, 1))
        self._gc()
        self.assertFalse(os.path.exists(blobstore.blob_path(self.env, sha_result)))

    def test_a_result_that_is_its_own_source_goes_with_the_source(self):
        photo = self._file("a.jpg", JPEG)
        self.Derivative._enqueue_missing()
        job = self._job_of(photo)
        blob = job.source_blob_id
        job.write({"state": "done", "derived_blob_id": blob.id, "mime": "image/jpeg"})
        photo.sudo().write({"current_revision_id": False})
        photo.revision_ids.sudo().unlink()
        self._age(blob)
        self._gc()
        self.assertFalse(job.exists())
        self.assertFalse(blob.exists())

    def test_a_result_that_is_its_own_source_survives_while_used(self):
        photo = self._file("a.jpg", JPEG)
        self.Derivative._enqueue_missing()
        job = self._job_of(photo)
        blob = job.source_blob_id
        job.write({"state": "done", "derived_blob_id": blob.id, "mime": "image/jpeg"})
        self._age(blob)
        self._gc()
        self.assertTrue(job.exists() and blob.exists())

    def test_a_blob_no_revision_uses_but_a_job_refers_to_is_kept(self):
        """The result of a live job is not swept although no revision points at it."""
        photo = self._file("a.jpg", JPEG)
        self._run()
        result = self._job_of(photo).derived_blob_id
        self.assertFalse(result.revision_ids)
        self._age(result)
        stale, _removed, _kept = self._gc()
        self.assertTrue(result.exists())
        self.assertEqual(stale, 0)


@tagged("post_install", "-at_install")
class TestOdooNeverDecodesResults(DerivativeCase):
    """Odoo stores and serves what the converter returns; it never opens it."""

    def _watch(self):
        real = odoo_image.ImageProcess
        stack = contextlib.ExitStack()
        watchers = {
            "ImageProcess": stack.enter_context(
                patch.object(odoo_image, "ImageProcess", wraps=real)
            ),
            "image_process": stack.enter_context(
                patch.object(
                    odoo_image, "image_process", wraps=odoo_image.image_process
                )
            ),
            "base64_to_image": stack.enter_context(
                patch.object(
                    odoo_image, "base64_to_image", wraps=odoo_image.base64_to_image
                )
            ),
        }
        # Whichever PDF library this Odoo image carries.
        for name in ("pypdf", "PyPDF2"):
            with contextlib.suppress(ImportError):
                module = importlib.import_module(name)
                watchers[f"{name}.PdfReader"] = stack.enter_context(
                    patch.object(module, "PdfReader", wraps=module.PdfReader)
                )
        with contextlib.suppress(ImportError):
            from pdfminer import high_level

            watchers["pdfminer.extract_text"] = stack.enter_context(
                patch.object(high_level, "extract_text", wraps=high_level.extract_text)
            )
        return stack, watchers

    def test_queue_cleanup_and_states_do_not_decode(self):
        photo = self._file("a.jpg", JPEG)
        stack, watchers = self._watch()
        with stack:
            self._run()
            job = self._job_of(photo)
            self.assertEqual(job.state, "done")
            self.env["int_filemanager.node"].with_user(self.writer).request_previews(
                [photo.id]
            )
            self.assertEqual(photo.with_user(self.writer).preview_state, "ready")
            self.Derivative._result_for_blob(job.source_blob_id, "tile")
            job.derived_blob_id.last_used = "2000-01-01 00:00:00"
            self.Blob._gc_blobs_unsafe()
        for name, watcher in watchers.items():
            with self.subTest(watched=name):
                watcher.assert_not_called()

    def test_every_kind_of_result_is_stored_without_decoding(self):
        made = [
            self._file("letter.docx", b"docx bytes"),
            self._file("paper.pdf", b"pdf bytes"),
            self._file("song.mp3", b"mp3 bytes"),
            self._file("note.txt", b"text bytes"),
            self._file("photo.jpg", JPEG),
        ]
        stack, watchers = self._watch()
        with stack:
            self._run()
            self._run()
        for name, watcher in watchers.items():
            with self.subTest(watched=name):
                watcher.assert_not_called()
        states = {
            (node.name, job.kind): job.state
            for node in made
            for job in self.Derivative.search(
                [("source_blob_id", "=", node.current_revision_id.blob_id.id)]
            )
        }
        self.assertEqual(set(states.values()), {"done"}, states)
        self.assertEqual(len(states), 4 + 4 + 2 + 1 + 3)

    def test_the_watch_would_notice_an_attachment_being_decoded(self):
        """Counter-check: the same watchers do fire for an ordinary attachment."""
        stack, watchers = self._watch()
        buf = io.BytesIO()
        from PIL import Image

        Image.new("RGB", (8, 8)).save(buf, "PNG")
        with stack:
            self.env["ir.attachment"].create({"name": "x.png", "raw": buf.getvalue()})
        self.assertTrue(watchers["ImageProcess"].called)
