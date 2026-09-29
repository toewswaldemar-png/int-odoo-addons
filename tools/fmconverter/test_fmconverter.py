"""Tests of the converter service: run with ``python3 -m unittest`` in this folder.

They start the real server on a free port with a temporary blob store, so the worker
process, its limits and the HTTP answers are exercised together. POSIX only (resource
limits), like the container it runs in.
"""

import hashlib
import http.client
import http.server
import io
import json
import os
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

from PIL import Image

import worker

BLOB_ROOT = tempfile.mkdtemp(prefix="fmconv_blobs_")
os.environ["CONVERTER_BLOB_ROOT"] = BLOB_ROOT

import server  # noqa: E402  (needs CONVERTER_BLOB_ROOT first)


def store(content):
    sha256 = hashlib.sha256(content).hexdigest()
    path = server.blob_path(sha256)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)
    return sha256


def jpeg(width, height, orientation=None, color="red"):
    buf = io.BytesIO()
    image = Image.new("RGB", (width, height), color)
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    image.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


class ConverterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def post(self, body, path="/convert"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        conn.request("POST", path, raw, {"Content-Type": "application/json"})
        response = conn.getresponse()
        data = response.read()
        headers = dict(response.getheaders())
        conn.close()
        return response.status, headers, data

    def get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        conn.request("GET", path)
        response = conn.getresponse()
        data = response.read()
        headers = dict(response.getheaders())
        conn.close()
        return response.status, headers, data

    def tile(self, sha256, spec="400x300", kind="tile", ext=""):
        return self.post({"sha256": sha256, "kind": kind, "spec": spec, "ext": ext})

    def converted(self, content, spec="400x300", kind="tile", ext=""):
        """Convert ``content``; return the result image after checking it is a JPEG."""
        status, headers, data = self.tile(store(content), spec, kind, ext)
        self.assertEqual(status, 200, data)
        self.assertEqual(headers["Content-Type"], "image/jpeg")
        image = Image.open(io.BytesIO(data))
        self.assertEqual((image.format, image.mode), ("JPEG", "RGB"))
        return image

    def meta(self, content, ext):
        status, headers, data = self.tile(store(content), "v1", "meta", ext)
        self.assertEqual(status, 200, data)
        self.assertEqual(headers["Content-Type"], "application/json")
        return json.loads(data)

    def text(self, content, ext):
        status, headers, data = self.tile(store(content), "embedded", "text", ext)
        self.assertEqual(status, 200, data)
        self.assertTrue(headers["Content-Type"].startswith("text/plain"))
        return data.decode("utf-8")

    def words(self, content, wait=True):
        """Convert a PDF's text and word positions; waits out an async job if given one."""
        status, headers, data = self.tile(store(content), "v2", "words", "pdf")
        if status == 202:
            if not wait:
                return json.loads(data)["job_id"]
            status, headers, data = self.poll_until_done(json.loads(data)["job_id"])
        self.assertEqual(status, 200, data)
        self.assertEqual(headers["Content-Type"], "application/json")
        return json.loads(data)

    def poll(self, job_id):
        return self.get(f"/convert/{job_id}")

    def poll_until_done(self, job_id, deadline=30):
        import time as _time

        end = _time.monotonic() + deadline
        while _time.monotonic() < end:
            status, headers, data = self.poll(job_id)
            if status != 202:
                return status, headers, data
            _time.sleep(0.05)
        raise AssertionError(f"job {job_id} did not finish within {deadline}s")

    def make_video(self, ext):
        path = os.path.join(BLOB_ROOT, f"make_video.{ext}")
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
             "testsrc=duration=2:size=320x240:rate=10", "-pix_fmt", "yuv420p", "-y", path],
            check=True,
        )  # fmt: skip
        with open(path, "rb") as f:
            return f.read()

    def make_audio(self, ext, cover=False):
        path = os.path.join(BLOB_ROOT, f"make_audio.{ext}")
        cover_path = os.path.join(BLOB_ROOT, "cover.jpg")
        Image.new("RGB", (120, 90), "purple").save(cover_path, "JPEG")
        args = ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=duration=1"]
        if cover:
            args += ["-i", cover_path, "-map", "0:a", "-map", "1:v", "-c:v", "copy"]
        args += ["-metadata", "title=Test Title", "-metadata", "artist=Test Artist",
                 "-id3v2_version", "3", "-y", path]  # fmt: skip
        subprocess.run(args, check=True)
        with open(path, "rb") as f:
            return f.read()

    def make_pdf(self, text, *more):
        """A digital PDF; ``more`` are further (x, y, text) placed on the same page."""
        source = os.path.join(BLOB_ROOT, "make.ps")
        placed = "".join(f"{x} {y} moveto ({t}) show " for x, y, t in more)
        with open(source, "w") as f:
            f.write(
                "/Helvetica findfont 24 scalefont setfont 72 700 moveto "
                f"({text}) show {placed}showpage\n"
            )
        path = os.path.join(BLOB_ROOT, "make.pdf")
        subprocess.run(
            ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pdfwrite",
             f"-sOutputFile={path}", source],
            check=True,
        )  # fmt: skip
        with open(path, "rb") as f:
            return f.read()

    def make_scanned_pdf(self, text, size=(1000, 300)):
        """A PDF with no text layer, only a picture of ``text`` - what a scan looks like."""
        from PIL import ImageDraw, ImageFont

        image = Image.new("RGB", size, "white")
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48
        )
        ImageDraw.Draw(image).text((20, 100), text, fill="black", font=font)
        buf = io.BytesIO()
        image.save(buf, "PDF", resolution=150.0)
        return buf.getvalue()

    def make_scan_with_scanner_text(self, picture_text, hidden_text):
        """A scan whose scanner already added (wrong) invisible text, like many do."""
        import pikepdf

        pdf = pikepdf.open(io.BytesIO(self.make_scanned_pdf(picture_text)))
        page = pdf.pages[0]
        font = pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name.Font,
                Subtype=pikepdf.Name.Type1,
                BaseFont=pikepdf.Name.Helvetica,
            )
        )
        page.add_resource(font, pikepdf.Name.Font, name=pikepdf.Name("/FHidden"))
        # Text render mode 3: invisible, exactly how OCR text layers are drawn.
        page.contents_add(
            pdf.make_stream(f"BT /FHidden 24 Tf 3 Tr 20 60 Td ({hidden_text}) Tj ET".encode()),
            prepend=False,
        )
        buf = io.BytesIO()
        pdf.save(buf)
        return buf.getvalue()

    def make_docx(self, text):
        source = os.path.join(BLOB_ROOT, "make_docx.txt")
        with open(source, "w") as f:
            f.write(text)
        subprocess.run(
            ["soffice", "--headless", "-env:UserInstallation=file:///tmp/lo_test_profile",
             "--convert-to", "docx", "--outdir", BLOB_ROOT, source],
            check=True, capture_output=True,
        )  # fmt: skip
        with open(os.path.join(BLOB_ROOT, "make_docx.docx"), "rb") as f:
            return f.read()

    def assert_refused(self, sha256, state, contains="", **kwargs):
        status, _headers, data = self.tile(sha256, **kwargs)
        self.assertEqual(status, 422, data)
        body = json.loads(data)
        self.assertEqual(body["state"], state)
        self.assertIn(contains, body["error"])

    def test_tile_fits_the_box_and_is_a_jpeg(self):
        sha256 = store(jpeg(2000, 1500))
        status, headers, data = self.tile(sha256)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/jpeg")
        self.assertEqual(headers["X-Converter-Tool"], "pillow")
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertLessEqual(image.width, 400)
            self.assertLessEqual(image.height, 300)

    def test_exif_orientation_is_applied(self):
        # Stored 600x300 with "rotate 90": shown as 300x600, so the tile is portrait.
        sha256 = store(jpeg(600, 300, orientation=6, color="blue"))
        _status, _headers, data = self.tile(sha256, "400x400")
        with Image.open(io.BytesIO(data)) as image:
            self.assertGreater(image.height, image.width)

    def test_a_format_we_do_not_convert_is_not_applicable(self):
        buf = io.BytesIO()
        Image.new("RGB", (16, 16)).save(buf, "ICO")
        self.assert_refused(store(buf.getvalue()), "not_applicable", "ICO")

    def test_unknown_kind_is_not_applicable(self):
        self.assert_refused(
            store(jpeg(50, 50)), "not_applicable", kind="text", spec="embedded"
        )

    def test_png_with_transparency_is_flattened_on_white(self):
        buf = io.BytesIO()
        Image.new("RGBA", (100, 100), (255, 0, 0, 0)).save(buf, "PNG")
        image = self.converted(buf.getvalue())
        self.assertGreater(min(image.getpixel((50, 50))), 240)

    def test_palette_png_with_transparency(self):
        buf = io.BytesIO()
        palette = Image.new("P", (40, 40), 0)
        palette.info["transparency"] = 0
        palette.save(buf, "PNG", transparency=0)
        self.converted(buf.getvalue())

    def test_sixteen_bit_tiff(self):
        buf = io.BytesIO()
        Image.new("I;16", (300, 200), 40000).save(buf, "TIFF")
        image = self.converted(buf.getvalue())
        self.assertGreater(image.getpixel((10, 10))[0], 100)

    def test_mpo_jpeg_with_extra_pictures_is_converted(self):
        buf = io.BytesIO()
        first = Image.new("RGB", (400, 300), "red")
        second = Image.new("RGB", (400, 300), "blue")
        first.save(buf, "MPO", save_all=True, append_images=[second])
        self.assertEqual(Image.open(io.BytesIO(buf.getvalue())).format, "MPO")
        self.converted(buf.getvalue())

    def test_a_png_over_pillows_own_limit_is_not_applicable(self):
        buf = io.BytesIO()
        Image.new("1", (20000, 20000), 1).save(buf, "PNG", optimize=True)
        self.assert_refused(store(buf.getvalue()), "not_applicable", "too many pixels")

    def test_cmyk_jpeg(self):
        buf = io.BytesIO()
        Image.new("CMYK", (300, 200), (0, 100, 200, 0)).save(buf, "JPEG")
        self.converted(buf.getvalue())

    def test_animated_gif_gives_its_first_frame(self):
        buf = io.BytesIO()
        frames = [Image.new("RGB", (60, 40), c) for c in ("red", "blue")]
        frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:])
        image = self.converted(buf.getvalue())
        self.assertGreater(image.getpixel((5, 5))[0], 150)

    def test_webp_and_bmp(self):
        for fmt in ("WEBP", "BMP"):
            with self.subTest(format=fmt):
                buf = io.BytesIO()
                Image.new("RGB", (120, 80), "green").save(buf, fmt)
                self.converted(buf.getvalue())

    @unittest.skipUnless(worker.pillow_heif, "pillow-heif is not installed")
    def test_heic_and_avif(self):
        for fmt in ("HEIF", "AVIF"):
            with self.subTest(format=fmt):
                buf = io.BytesIO()
                Image.new("RGB", (200, 120), "orange").save(buf, fmt)
                image = self.converted(buf.getvalue())
                self.assertEqual(image.size, (200, 120))

    def test_preview_is_bigger_than_tile_and_never_enlarges(self):
        content = jpeg(3000, 2000)
        tile = self.converted(content, "400x300", "tile")
        preview = self.converted(content, "1920x1920", "preview")
        self.assertLessEqual(tile.width, 400)
        self.assertEqual(preview.width, 1920)
        small = self.converted(jpeg(100, 80), "1920x1920", "preview")
        self.assertEqual(small.size, (100, 80))

    def test_the_first_picture_of_a_video_and_its_facts(self):
        video = self.make_video("mp4")
        image = self.converted(video, ext="mp4")
        self.assertLessEqual(image.width, 400)
        meta = self.meta(video, "mp4")
        self.assertEqual((meta["width"], meta["height"]), (320, 240))
        self.assertAlmostEqual(meta["duration"], 2.0, delta=0.3)
        self.assertEqual(meta["video_codec"], "h264")

    def test_audio_in_a_video_extension_is_not_applicable(self):
        audio = self.make_audio("mp3")
        self.assert_refused(
            store(audio), "not_applicable", "no video stream", ext="mpeg"
        )

    def test_an_mp3_cover_becomes_a_tile_and_no_cover_is_not_applicable(self):
        image = self.converted(self.make_audio("mp3", cover=True), ext="mp3")
        self.assertEqual(image.size, (120, 90))
        self.assert_refused(
            store(self.make_audio("mp3")), "not_applicable", "no cover", ext="mp3"
        )

    def test_audio_tags_and_duration(self):
        meta = self.meta(self.make_audio("mp3", cover=True), "mp3")
        self.assertEqual(meta["title"], "Test Title")
        self.assertEqual(meta["artist"], "Test Artist")
        self.assertAlmostEqual(meta["duration"], 1.0, delta=0.3)

    def test_pdf_page_text_and_word_positions(self):
        # Long enough (20 characters a page) to count as a page with its own text.
        pdf = self.make_pdf("Hello converter, digital page")
        image = self.converted(pdf, ext="pdf")
        self.assertLessEqual(image.width, 400)
        result = self.words(pdf)
        self.assertEqual(result["version"], 2)
        self.assertEqual(result["ocr"], "none")
        self.assertIn("Hello converter, digital page", result["text"])
        self.assertEqual(len(result["pages"]), 1)
        self.assertEqual(result["pages"][0], {"width": 595.0, "height": 842.0, "rotation": 0})
        page, x0, top, x1, bottom, start, end = self.word(result, "Hello")
        self.assertEqual(page, 1)
        self.assertLess(x0, x1)
        self.assertLess(top, bottom)
        self.assertEqual(self.meta(pdf, "pdf")["pages"], 1)

    def word(self, result, text):
        """The entry of the first word that is ``text``, found through its own range."""
        return next(w for w in result["words"] if result["text"][w[5] : w[6]] == text)

    def assert_ranges_match_the_text(self, result):
        """Every word's range points at a non-empty piece of the text with no gap in it."""
        for entry in result["words"]:
            piece = result["text"][entry[5] : entry[6]]
            self.assertTrue(piece)
            self.assertFalse(any(c in piece for c in " \t\n\f"), repr(piece))

    def test_lines_columns_and_word_ranges(self):
        # Two words on one line far apart (two columns) and one on the next line.
        pdf = self.make_pdf("Kundennummer", (400, 700, "12345"), (72, 650, "Datum"))
        result = self.words(pdf)
        self.assert_ranges_match_the_text(result)
        self.assertIn("Kundennummer\t12345\nDatum", result["text"])

    def test_close_words_stay_on_one_line_with_a_space(self):
        result = self.words(self.make_pdf("Zaehlernummer 44 450 7-5 148 621"))
        self.assertEqual(result["ocr"], "none")
        self.assertIn("Zaehlernummer 44 450 7-5 148 621", result["text"])
        self.assert_ranges_match_the_text(result)

    def test_pages_are_separated_by_a_form_feed(self):
        source = os.path.join(BLOB_ROOT, "two_pages.ps")
        with open(source, "w") as f:
            f.write(
                "/Helvetica findfont 24 scalefont setfont "
                "72 700 moveto (First page of the letter) show showpage "
                "72 700 moveto (Second page of the letter) show showpage\n"
            )
        path = os.path.join(BLOB_ROOT, "two_pages.pdf")
        subprocess.run(
            ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pdfwrite",
             f"-sOutputFile={path}", source],
            check=True,
        )  # fmt: skip
        with open(path, "rb") as f:
            result = self.words(f.read())
        self.assertEqual(
            result["text"], "First page of the letter\fSecond page of the letter"
        )
        self.assertEqual(self.word(result, "Second")[0], 2)
        self.assertEqual(len(result["pages"]), 2)

    def test_a_blank_scan_is_ocrd_and_has_no_text(self):
        buf = io.BytesIO()
        Image.new("RGB", (200, 300), "white").save(buf, "PDF")
        result = self.words(buf.getvalue())
        self.assertEqual(result["text"].strip(), "")
        self.assertEqual(result["words"], [])

    def test_a_real_scan_is_ocrd_with_word_positions(self):
        pdf = self.make_scanned_pdf("SCANNEDTEXT")
        result = self.words(pdf)
        self.assertEqual(result["ocr"], "force-ocr")
        self.assertIn("SCANNEDTEXT", result["text"].upper())
        found = next(
            w for w in result["words"] if result["text"][w[5] : w[6]].upper() == "SCANNEDTEXT"
        )
        self.assertEqual(found[0], 1)
        self.assertGreater(found[3], found[1])
        self.assert_ranges_match_the_text(result)

    def test_the_scanners_own_text_is_replaced_by_ours(self):
        pdf = self.make_scan_with_scanner_text(
            "SCANNEDTEXT", "GARBLEDWORD from the scanners own layer"
        )
        # The scanner's text is there and long enough to be trusted by length alone.
        pages, text, _words, scanned = worker._read_pdf(self.save(pdf))
        self.assertIn("GARBLEDWORD", text)
        self.assertEqual((len(pages), scanned), (1, 1))
        status, headers, data = self.tile(store(pdf), "v2", "words", "pdf")
        if status == 202:
            status, headers, data = self.poll_until_done(json.loads(data)["job_id"])
        self.assertEqual(status, 200, data)
        self.assertEqual(headers["X-Converter-Tool"], "ocrmypdf-redo+pdfplumber")
        result = json.loads(data)
        self.assertEqual(result["ocr"], "redo-ocr")
        self.assertIn("SCANNEDTEXT", result["text"].upper())
        self.assertNotIn("GARBLEDWORD", result["text"])

    def test_a_scan_redo_can_not_handle_is_read_anew(self):
        pdf = self.make_scan_with_scanner_text(
            "FALLBACKTEXT", "GARBLEDWORD from the scanners own layer"
        )
        real_run_ocr = worker._run_ocr
        modes = []

        def run_ocr(source, workdir, mode):
            modes.append(mode)
            if mode == "redo-ocr":
                raise RuntimeError("ocrmypdf: cannot redo this one")
            return real_run_ocr(source, workdir, mode)

        output = os.path.join(BLOB_ROOT, "fallback.json")
        with mock.patch.object(worker, "_run_ocr", run_ocr):
            tool = worker.make_words(self.save(pdf), "pdf", output)
        with open(output) as f:
            result = json.load(f)
        self.assertEqual(modes, ["redo-ocr", "force-ocr"])
        self.assertEqual((tool, result["ocr"]), ("ocrmypdf+pdfplumber", "force-ocr"))
        self.assertIn("FALLBACKTEXT", result["text"].upper())

    def save(self, content, name="saved.pdf"):
        path = os.path.join(BLOB_ROOT, name)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_a_digital_pdf_is_not_ocrd(self):
        pdf = self.make_pdf("No OCR needed on this digital page")
        status, headers, data = self.tile(store(pdf), "v2", "words", "pdf")
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Converter-Tool"], "pdfplumber")

    def test_a_scan_is_ocrd_with_the_ocr_tool(self):
        pdf = self.make_scanned_pdf("OCRTOOLCHECK")
        status, headers, data = self.tile(store(pdf), "v2", "words", "pdf")
        if status == 202:
            status, headers, data = self.poll_until_done(json.loads(data)["job_id"])
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Converter-Tool"], "ocrmypdf+pdfplumber")

    def test_a_document_over_the_page_ceiling_is_refused(self):
        # worker.py reads its limits from the environment at each (subprocess) start,
        # so the override has to travel that way, not as a patch on the imported module.
        pdf = self.make_scanned_pdf("TOOLONG")
        with mock.patch.dict(os.environ, {"CONVERTER_MAX_OCR_PAGES": "0"}):
            self.assert_refused(
                store(pdf),
                "not_applicable",
                "too many pages",
                kind="words",
                spec="v2",
                ext="pdf",
            )

    def test_words_is_only_for_pdf_bytes(self):
        self.assert_refused(
            store(b"not a pdf"), "not_applicable", "PDF", kind="words", spec="v2", ext="txt"
        )

    def test_an_office_document_becomes_a_pdf_with_its_text(self):
        docx = self.make_docx("Office says hello")
        status, headers, data = self.tile(
            store(docx), "pdf", kind="preview_pdf", ext="docx"
        )
        self.assertEqual((status, headers["Content-Type"]), (200, "application/pdf"))
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertIn("Office says hello", self.words(data)["text"])
        self.assertLessEqual(self.converted(data, ext="pdf").width, 400)

    def test_office_kinds_other_than_the_pdf_are_not_applicable(self):
        self.assert_refused(store(self.make_docx("x")), "not_applicable", ext="docx")

    def test_plain_text_in_several_encodings(self):
        for label, data in (
            ("utf-8", "Grüße".encode()),
            ("utf-8 with mark", b"\xef\xbb\xbf" + "Grüße".encode()),
            ("utf-16", "Grüße".encode("utf-16")),
            ("cp1252", "Grüße".encode("cp1252")),
        ):
            with self.subTest(encoding=label):
                self.assertEqual(self.text(data, "txt"), "Grüße")

    def test_text_is_capped_and_has_no_nul(self):
        text = self.text(b"a\x00b" * 3_000_000, "txt")
        self.assertEqual(len(text), worker.MAX_TEXT_CHARS)
        self.assertNotIn("\x00", text)

    def test_picture_facts_from_exif(self):
        buf = io.BytesIO()
        exif = Image.Exif()
        exif[0x010F], exif[0x0110] = "ACME", "Cam 1"
        exif.get_ifd(0x8769)[0x9003] = "2019:07:04 12:30:00"
        exif[0x0112] = 6
        Image.new("RGB", (640, 480), "red").save(buf, "JPEG", exif=exif)
        meta = self.meta(buf.getvalue(), "jpg")
        self.assertEqual(meta["camera"], "ACME Cam 1")
        self.assertEqual(meta["taken_at"], "2019-07-04 12:30:00")
        self.assertEqual(
            (meta["width"], meta["height"], meta["orientation"]), (640, 480, 6)
        )

    def test_meta_of_a_broken_picture_fails_and_of_text_is_not_applicable(self):
        self.assert_refused(
            store(b"junk" * 100), "failed", ext="jpg", kind="meta", spec="v1"
        )
        self.assert_refused(
            store(b"hello"), "not_applicable", ext="txt", kind="meta", spec="v1"
        )

    def test_unknown_kind_and_bad_labels_are_400(self):
        for body in (
            {"sha256": "a" * 64, "kind": "shell", "spec": "v1", "ext": ""},
            {"sha256": "a" * 64, "kind": "meta", "spec": "../x", "ext": ""},
        ):
            with self.subTest(body=body):
                self.assertEqual(self.post(body)[0], 400)

    def test_raw_extension_with_other_content_fails_cleanly(self):
        self.assert_refused(store(b"not a raw file" * 100), "failed", ext="cr2")

    def test_bad_extension_hint_is_400(self):
        status = self.post(
            {"sha256": "a" * 64, "kind": "tile", "spec": "400x300", "ext": "../x"}
        )[0]
        self.assertEqual(status, 400)

    def test_garbage_fails(self):
        self.assert_refused(store(b"this is not an image" * 50), "failed")

    def test_truncated_jpeg_fails(self):
        content = jpeg(1600, 1200)
        self.assert_refused(store(content[: len(content) // 2]), "failed")

    def test_empty_file_fails(self):
        self.assert_refused(store(b""), "failed")

    def test_image_bomb_is_refused_before_it_is_decoded(self):
        # 8001 x 8001 = 64.02 MP: over the limit, and tiny as a JPEG of one colour.
        sha256 = store(jpeg(8001, 8001))
        self.assert_refused(sha256, "not_applicable", "too many pixels")

    def test_missing_blob_fails(self):
        self.assert_refused("a" * 64, "failed", "source blob not found")

    def test_bad_requests_are_400(self):
        for body in (
            {"sha256": "../../etc/passwd", "kind": "tile", "spec": "400x300"},
            {"sha256": "a" * 64, "kind": "tile", "spec": "99999x1"},
            {"sha256": "a" * 64, "kind": "tile"},
            b"not json",
        ):
            with self.subTest(body=body):
                self.assertEqual(self.post(body)[0], 400)

    def test_unknown_path_is_404(self):
        self.assertEqual(self.post({}, path="/elsewhere")[0], 404)

    def test_a_crashing_worker_does_not_take_the_server_down(self):
        crash = os.path.join(BLOB_ROOT, "crash.py")
        with open(crash, "w") as f:
            f.write("import os, signal\nos.kill(os.getpid(), signal.SIGSEGV)\n")
        sha256 = store(jpeg(100, 100))
        with mock.patch.object(server, "WORKER", crash):
            self.assert_refused(sha256, "failed", "worker exited with")
        self.assertEqual(self.tile(sha256)[0], 200)

    def test_a_slow_worker_is_stopped_at_the_timeout(self):
        slow = os.path.join(BLOB_ROOT, "slow.py")
        with open(slow, "w") as f:
            f.write("import time\ntime.sleep(60)\n")
        sha256 = store(jpeg(100, 100))
        with (
            mock.patch.object(server, "WORKER", slow),
            mock.patch.object(server, "JOB_TIMEOUT_S", 1),
        ):
            self.assert_refused(sha256, "failed", "timeout")

    def test_too_many_jobs_at_once_answer_503(self):
        sha256 = store(jpeg(100, 100))
        with mock.patch.object(server, "slots", threading.BoundedSemaphore(0)):
            self.assertEqual(self.tile(sha256)[0], 503)

    def test_a_job_whose_whole_timeout_is_short_fails_synchronously_not_as_a_job(self):
        """A patched-down timeout must not eat the whole wait budget and then still
        hand the job to the background - there is nothing left to give it."""
        slow = os.path.join(BLOB_ROOT, "slow_short.py")
        with open(slow, "w") as f:
            f.write("import time\ntime.sleep(60)\n")
        sha256 = store(jpeg(100, 100))
        with (
            mock.patch.object(server, "WORKER", slow),
            mock.patch.object(server, "JOB_TIMEOUT_S", 1),
        ):
            status, _headers, _data = self.tile(sha256)
        self.assertEqual(status, 422)

    def _slow_worker_script(self, name, seconds, tool="slowtool"):
        """A stand-in worker.py: sleeps, then writes its result like the real one does."""
        script = os.path.join(BLOB_ROOT, name)
        with open(script, "w") as f:
            f.write(
                "import json, sys, time\n"
                f"time.sleep({seconds})\n"
                "with open(sys.argv[5], 'w') as out:\n"
                "    out.write('ok')\n"
                f'print(json.dumps({{"state": "done", "tool": "{tool}", '
                '"tool_version": "1"}))\n'
            )
        return script

    def test_a_slow_job_is_answered_with_a_job_id_and_can_be_polled(self):
        sha256 = store(jpeg(100, 100))
        # A tiny wait budget makes even a quick script exceed it, without having to
        # wait out a real multi-minute OCR run in the test.
        with (
            mock.patch.object(server, "WORKER", self._slow_worker_script("slow1.py", 0.3)),
            mock.patch.object(server, "WAIT_BUDGET_S", 0.05),
        ):
            status, _headers, data = self.tile(sha256)
            self.assertEqual(status, 202, data)
            job_id = json.loads(data)["job_id"]
            self.assertEqual(self.poll(job_id)[0], 202)
            status, headers, data = self.poll_until_done(job_id)
        self.assertEqual((status, data), (200, b"ok"))
        self.assertEqual(headers["X-Converter-Tool"], "slowtool")

    def test_polling_an_unknown_job_id_is_404(self):
        self.assertEqual(self.poll("0" * 32)[0], 404)
        self.assertEqual(self.poll("not-a-valid-id")[0], 404)

    def test_a_job_is_only_delivered_once(self):
        with (
            mock.patch.object(server, "WORKER", self._slow_worker_script("slow2.py", 0.2)),
            mock.patch.object(server, "WAIT_BUDGET_S", 0.05),
        ):
            _status, _headers, data = self.tile(store(jpeg(100, 100)))
            job_id = json.loads(data)["job_id"]
            self.poll_until_done(job_id)
        self.assertEqual(self.poll(job_id)[0], 404)

    def test_health(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/health")
        self.assertEqual(conn.getresponse().status, 200)

    def test_blob_store_is_only_read(self):
        sha256 = store(jpeg(300, 300))
        before = sorted(os.listdir(BLOB_ROOT))
        self.tile(sha256)
        self.assertEqual(sorted(os.listdir(BLOB_ROOT)), before)


if __name__ == "__main__":
    unittest.main()
