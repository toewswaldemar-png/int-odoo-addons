"""One conversion, run in its own process by server.py.

Usage: worker.py <source> <kind> <width> <height> <output>

Exit codes: 0 done, 10 not applicable, 11 failed. One JSON line on stdout says why.
A crash, a decoder bug or a limit hit only kills this process, never the server.
"""

import json
import sys

from PIL import Image, ImageOps

EXIT_DONE, EXIT_NOT_APPLICABLE, EXIT_FAILED = 0, 10, 11
MAX_PIXELS = 64_000_000
TILE_QUALITY = 80


def say(state, error=""):
    print(
        json.dumps({"state": state, "error": error, "tool_version": Image.__version__})
    )


def make_tile(source, width, height, output):
    with Image.open(source) as image:
        if image.format != "JPEG":
            say("not_applicable", f"not a JPEG ({image.format})")
            return EXIT_NOT_APPLICABLE
        if image.width * image.height > MAX_PIXELS:
            say("not_applicable", f"too many pixels ({image.width}x{image.height})")
            return EXIT_NOT_APPLICABLE
        # Lets the JPEG decoder scale down while reading: much faster for big photos.
        image.draft("RGB", (2 * width, 2 * height))
        image = ImageOps.exif_transpose(image)
        image.thumbnail((width, height))
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(output, "JPEG", quality=TILE_QUALITY, optimize=True)
    return EXIT_DONE


def main(argv):
    source, kind, width, height, output = argv[1:6]
    if kind != "tile":
        say("not_applicable", f"unknown kind {kind}")
        return EXIT_NOT_APPLICABLE
    try:
        code = make_tile(source, int(width), int(height), output)
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        # Pillow reports broken, truncated or unknown files as one of these.
        say("failed", f"{type(exc).__name__}: {exc}"[:300])
        return EXIT_FAILED
    if code == EXIT_DONE:
        say("done")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
