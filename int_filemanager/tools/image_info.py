"""Say how many pictures an image file has and how wide the first one is.

    python image_info.py <path>

Answers one JSON line: ``{"frames": n, "width": w}``, or ``{"error": "..."}`` for a file that is
no image. Only the header is read. Only a TIFF has several pages: the other formats count as one
picture although Pillow reports more frames for some (a JPEG of a phone with a second, smaller
picture inside, "MPO", shows two), and ``ocrmypdf`` makes one page of them. It runs as a child process of the scheduled action because
the Odoo process knows only the formats PNG, JPEG, GIF and BMP (``odoo.tools.image`` loads no
other plug-ins of Pillow), and TIFF and WebP are among those that the recognition reads.
"""

import json
import sys

from PIL import Image


def main(argv):
    # Only the header is read, so a very large picture does no harm here; ``ocrmypdf`` has its
    # own limit for the pictures it decodes.
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(argv[1]) as image:
            frames = getattr(image, "n_frames", 1) if image.format == "TIFF" else 1
            answer = {"frames": frames, "width": image.size[0]}
    except Exception as error:  # noqa: BLE001 (whatever a broken file makes Pillow raise)
        answer = {"error": f"{type(error).__name__}: {error}"}
    sys.stdout.write(json.dumps(answer) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
