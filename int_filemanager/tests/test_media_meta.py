import base64
import io
import os
import shutil
import tempfile
import wave
from unittest.mock import patch

from PIL import Image

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMediaMeta(TransactionCase):
    """Phase 4: Vorschau & Metadaten (Bild-Thumbnail+EXIF, PDF-Seitenzahl,
    Audio-Tags), asynchron per Cron extrahiert - analog zum Hash-Cron aus
    Phase 1."""

    def setUp(self):
        super().setUp()
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="int_filemanager_test_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.root_path", self.root)
        self.Model = self.env["int_filemanager.file"].sudo()
        # Wie test_scan_identity.py: Batch-Commits im Cron-Code fuer die
        # Testdauer neutralisieren (TransactionCase erlaubt keinen echten
        # Zwischen-Commit).
        self.env.cr.commit = lambda: None

    def _write_bytes(self, rel_path, content=b"hello"):
        abs_path = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(content)
        return abs_path

    def _write_image(self, rel_path, size=(40, 30), color=(200, 50, 50)):
        abs_path = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        Image.new("RGB", size, color).save(abs_path, "JPEG")
        return abs_path

    def _write_pdf(self, rel_path, pages=1):
        abs_path = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        img = Image.new("RGB", (50, 50), (0, 0, 0))
        if pages == 1:
            img.save(abs_path, "PDF")
        else:
            img.save(abs_path, "PDF", save_all=True, append_images=[img] * (pages - 1))
        return abs_path

    def _write_wav(self, rel_path, seconds=1.0, framerate=8000):
        abs_path = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        n_frames = int(seconds * framerate)
        with wave.open(abs_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(framerate)
            w.writeframes(b"\x00\x00" * n_frames)
        return abs_path

    def _scan(self):
        self.Model._scan_and_reconcile()

    def _extract_pending(self):
        while self.Model.search_count([("meta_state", "=", "pending"), ("is_dir", "=", False)]):
            self.Model._cron_extract_media_meta()

    # ------------------------------------------------------------------
    # Vorfilterung: nur unterstützte Medientypen laufen überhaupt pending
    # ------------------------------------------------------------------

    def test_unsupported_file_never_becomes_pending(self):
        self._write_bytes("notes.txt", b"plain text")
        self._scan()
        rec = self.Model.search([("path", "=", "notes.txt")])
        self.assertFalse(rec.meta_state)
        self._extract_pending()  # darf nichts tun / nicht crashen
        self.assertFalse(self.Model.browse(rec.id).meta_state)

    def test_folder_never_becomes_pending(self):
        os.makedirs(os.path.join(self.root, "Ordner"))
        self._scan()
        rec = self.Model.search([("path", "=", "Ordner")])
        self.assertFalse(rec.meta_state)

    # ------------------------------------------------------------------
    # Bild: Thumbnail, Abmessungen
    # ------------------------------------------------------------------

    def test_image_extraction_sets_thumbnail_and_dimensions(self):
        self._write_image("foto.jpg", size=(400, 300))
        self._scan()
        rec = self.Model.search([("path", "=", "foto.jpg")])
        self.assertEqual(rec.meta_state, "pending")
        self._extract_pending()
        rec = self.Model.browse(rec.id)
        self.assertEqual(rec.meta_state, "done")
        self.assertTrue(rec.thumbnail)
        self.assertEqual(rec.media_width, 400)
        self.assertEqual(rec.media_height, 300)
        # Thumbnail wurde auf das konfigurierte Maximum verkleinert.
        thumb = Image.open(io.BytesIO(base64.b64decode(rec.thumbnail)))
        self.assertLessEqual(thumb.width, 320)
        self.assertLessEqual(thumb.height, 320)

    # ------------------------------------------------------------------
    # PDF: Seitenzahl
    # ------------------------------------------------------------------

    def test_pdf_extraction_sets_page_count(self):
        self._write_pdf("dokument.pdf", pages=3)
        self._scan()
        self._extract_pending()
        rec = self.Model.search([("path", "=", "dokument.pdf")])
        self.assertEqual(rec.meta_state, "done")
        self.assertEqual(rec.page_count, 3)

    # ------------------------------------------------------------------
    # Audio: Dauer
    # ------------------------------------------------------------------

    def test_audio_extraction_sets_duration(self):
        self._write_wav("ton.wav", seconds=2.0)
        self._scan()
        self._extract_pending()
        rec = self.Model.search([("path", "=", "ton.wav")])
        self.assertEqual(rec.meta_state, "done")
        self.assertAlmostEqual(rec.audio_duration, 2.0, delta=0.05)

    # ------------------------------------------------------------------
    # Fehlerfälle: definitiv (zu groß) und transient (kaputt/nicht lesbar)
    # ------------------------------------------------------------------

    def test_oversized_file_rejected_as_error(self):
        self._write_image("gross.jpg", size=(100, 100))
        self._scan()
        with patch.dict(
            "odoo.addons.int_filemanager.models.filemanager_file.DEFAULT_META_MAX_BYTES", {"image": 10}
        ):
            self._extract_pending()
        rec = self.Model.search([("path", "=", "gross.jpg")])
        self.assertEqual(rec.meta_state, "error")
        self.assertIn("zu groß", rec.meta_error)
        self.assertEqual(rec.meta_attempts, 1)
        self.assertFalse(rec.thumbnail)

    def test_size_limit_overridable_via_config_parameter(self):
        self._write_image("gross2.jpg", size=(100, 100))
        self._scan()
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.meta_max_bytes_image", "10")
        self._extract_pending()
        rec = self.Model.search([("path", "=", "gross2.jpg")])
        self.assertEqual(rec.meta_state, "error")

    def test_corrupt_image_marks_error_not_pending_forever(self):
        self._write_bytes("kaputt.jpg", b"das ist kein jpeg")
        self._scan()
        self._extract_pending()
        rec = self.Model.search([("path", "=", "kaputt.jpg")])
        self.assertEqual(rec.meta_state, "error")
        self.assertTrue(rec.meta_error)
        self.assertEqual(rec.meta_attempts, 1)

    def test_extraction_discarded_on_concurrent_modification(self):
        from ..mediameta import extract_metadata

        abs_path = self._write_image("aendert_sich.jpg")
        real_stat = os.stat
        call_count = {"n": 0}

        class _FakeStat:
            def __init__(self, size, mtime_ns):
                self.st_size = size
                self.st_mtime_ns = mtime_ns

        def flaky_stat(path, *args, **kwargs):
            result = real_stat(path, *args, **kwargs)
            call_count["n"] += 1
            if call_count["n"] == 2:
                return _FakeStat(result.st_size + 1, result.st_mtime_ns)
            return result

        with patch("odoo.addons.int_filemanager.mediameta.os.stat", side_effect=flaky_stat):
            result = extract_metadata(abs_path, "image", max_bytes=None)
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # Watcher-Pfad: unbedingtes pending, alte Werte bleiben bis dahin stehen
    # ------------------------------------------------------------------

    def test_index_upsert_marks_supported_media_pending(self):
        from ..index_utils import index_upsert

        img_path = self._write_image("watched.jpg")
        txt_path = self._write_bytes("watched.txt", b"content")

        img_rec = index_upsert(self.env, img_path)
        txt_rec = index_upsert(self.env, txt_path)

        self.assertEqual(img_rec.meta_state, "pending")
        self.assertFalse(txt_rec.meta_state)

    def test_modify_resets_meta_state_but_keeps_old_thumbnail_until_recomputed(self):
        from ..index_utils import index_upsert

        img_path = self._write_image("stabil.jpg", size=(10, 10))
        rec = index_upsert(self.env, img_path)
        self._extract_pending()
        rec = self.Model.browse(rec.id)
        old_thumbnail = rec.thumbnail
        self.assertEqual(rec.meta_state, "done")
        self.assertTrue(old_thumbnail)

        # Datei aendert sich (z.B. neuer Inhalt) - Watcher-Pfad feuert erneut.
        Image.new("RGB", (500, 500), (1, 2, 3)).save(img_path, "JPEG")
        rec2 = index_upsert(self.env, img_path)

        self.assertEqual(rec2.id, rec.id)
        self.assertEqual(rec2.meta_state, "pending")
        # Alter Thumbnail bleibt sichtbar stehen, bis der Cron neu extrahiert
        # hat (write() im Watcher-Pfad aendert nur die uebergebenen Felder).
        self.assertEqual(rec2.thumbnail, old_thumbnail)

        self._extract_pending()
        rec3 = self.Model.browse(rec.id)
        self.assertEqual(rec3.meta_state, "done")
        self.assertEqual(rec3.media_width, 500)
