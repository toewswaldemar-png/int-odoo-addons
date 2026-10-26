"""The programs of the text recognition that the scheduled action starts."""

import json
import os
import subprocess
import sys

from odoo.addons.int_filemanager.tools.programs import PROBE_SECONDS

IMAGE_INFO = os.path.join(os.path.dirname(__file__), "image_info.py")


def image_info(path):
    """``(number of pictures, width in pixels)`` of an image file, from its header; ``None`` if it is none.

    A child process answers (``tools/image_info.py``): the Odoo process loads only some of the
    formats of Pillow, and TIFF and WebP are not among them.
    """
    try:
        done = subprocess.run(  # noqa: S603 (own script, own interpreter, no shell)
            [sys.executable, "-I", IMAGE_INFO, path],
            capture_output=True,
            check=False,
            timeout=PROBE_SECONDS,
        )
        answer = json.loads(done.stdout.decode().splitlines()[-1])
        return int(answer["frames"]), int(answer["width"])
    except (OSError, subprocess.TimeoutExpired, IndexError, ValueError, KeyError):
        return None
