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
import tempfile
import threading
import unittest
from unittest import mock

from PIL import Image

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

    def tile(self, sha256, spec="400x300"):
        return self.post({"sha256": sha256, "kind": "tile", "spec": spec})

    def assert_refused(self, sha256, state, contains=""):
        status, _headers, data = self.tile(sha256)
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

    def test_png_is_not_applicable(self):
        buf = io.BytesIO()
        Image.new("RGB", (10, 10)).save(buf, "PNG")
        self.assert_refused(store(buf.getvalue()), "not_applicable", "not a JPEG")

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
