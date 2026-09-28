"""One conversion, run in its own process by server.py.

Usage: worker.py <source> <kind> <spec> <ext> <output>

kind   tile / preview   a JPEG picture that fits the box ``spec`` ("<w>x<h>")
       preview_pdf      a PDF made from an office document
       text             the text of a PDF or a text file, UTF-8
       meta             a JSON object with the facts about the file
ext    the lower case file name extension the caller knows: a hint that picks the
       kind of file, not trusted (pictures are recognised by looking into the file);
       camera RAW and office formats are found by it, as there is nothing else to go by.

Exit codes: 0 done, 10 not applicable, 11 failed. One JSON line on stdout says why.
A crash, a decoder bug or a limit hit only kills this process, never the server.
"""

import io
import json
import os
import subprocess
import sys

from PIL import Image, ImageOps

try:
    import pillow_heif

    # One opener for HEIC/HEIF and, in current versions, AVIF as well.
    pillow_heif.register_heif_opener()
except ImportError:  # the tests of a slimmer image still run
    pillow_heif = None

EXIT_DONE, EXIT_NOT_APPLICABLE, EXIT_FAILED = 0, 10, 11
MAX_PIXELS = 64_000_000
MAX_IMAGE_BYTES = int(os.environ.get("CONVERTER_MAX_IMAGE_MB", "512")) * 1024 * 1024
MAX_RAW_BYTES = int(os.environ.get("CONVERTER_MAX_RAW_MB", "200")) * 1024 * 1024
MAX_OFFICE_BYTES = int(os.environ.get("CONVERTER_MAX_OFFICE_MB", "100")) * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000
MAX_PDF_TEXT_PAGES = 400
TOOL_TIMEOUT_S = int(os.environ.get("CONVERTER_TOOL_TIMEOUT_S", "25"))
QUALITY = {"tile": 80, "preview": 85}
# MPO is what Pillow calls a JPEG with extra pictures attached (many cameras and phones).
IMAGE_FORMATS = {"JPEG", "MPO", "PNG", "GIF", "BMP", "WEBP", "TIFF", "HEIF", "AVIF"}
RAW_EXTENSIONS = {
    "cr2", "cr3", "crw", "nef", "nrw", "arw", "srf", "sr2", "dng", "orf", "rw2",
    "raf", "pef", "srw", "3fr", "erf", "kdc", "mrw", "rwl", "x3f", "iiq",
}  # fmt: skip
VIDEO_EXTENSIONS = {
    "mp4", "m4v", "mov", "avi", "mkv", "wmv", "mpg", "mpeg", "mts", "m2ts", "3gp",
    "webm", "flv", "ogv",
}  # fmt: skip
AUDIO_EXTENSIONS = {"mp3", "flac", "m4a", "ogg", "oga", "opus", "wav", "wma", "aac"}
OFFICE_EXTENSIONS = {
    "doc", "docx", "odt", "rtf", "xls", "xlsx", "ods", "ppt", "pptx", "odp",
}  # fmt: skip
TEXT_EXTENSIONS = {
    "txt", "md", "csv", "tsv", "log", "json", "xml", "html", "htm", "ini", "yml", "yaml",
}  # fmt: skip
# libraw's "flip" value -> degrees to turn a PIL image (counter-clockwise) to upright
RAW_FLIP_DEGREES = {3: 180, 5: 90, 6: 270}


class NotApplicable(Exception):
    pass


def say(state, error=""):
    print(
        json.dumps({"state": state, "error": error, "tool_version": Image.__version__})
    )


def run_tool(args, **kwargs):
    """Run an external tool with an argument list (no shell) and a time limit."""
    try:
        return subprocess.run(
            args,
            capture_output=True,
            timeout=TOOL_TIMEOUT_S,
            check=False,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{args[0]} timed out") from None


def check_pixels(width, height):
    if width * height > MAX_PIXELS:
        raise NotApplicable(f"too many pixels ({width}x{height})")


# ---------------------------------------------------------------- pictures


def open_raw(source, box):
    """Return an upright PIL image of a camera RAW file (embedded preview if big enough)."""
    import rawpy

    if os.path.getsize(source) > MAX_RAW_BYTES:
        raise NotApplicable("RAW file too big")
    with rawpy.imread(source) as raw:
        flip = raw.sizes.flip
        image = None
        try:
            thumb = raw.extract_thumb()
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
            thumb = None
        if thumb is not None and thumb.format == rawpy.ThumbFormat.JPEG:
            candidate = Image.open(io.BytesIO(thumb.data))
            # A small embedded preview would be blown up: decode the sensor data then.
            if max(candidate.size) >= 0.9 * min(max(box), max(raw.sizes.width, 1)):
                check_pixels(*candidate.size)
                candidate.load()
                image = candidate
                if not image.getexif().get(0x0112) and flip in RAW_FLIP_DEGREES:
                    image = image.rotate(RAW_FLIP_DEGREES[flip], expand=True)
        if image is None:
            check_pixels(raw.sizes.width, raw.sizes.height)
            rgb = raw.postprocess(half_size=True, use_camera_wb=True, output_bps=8)
            image = Image.fromarray(rgb)
    return image


def to_rgb(image):
    """A JPEG holds no alpha channel and no 16-bit data: flatten to 8-bit RGB."""
    if image.mode in ("I;16", "I;16L", "I;16B", "I"):
        image = image.point(lambda value: value * (1 / 256)).convert("L")
    if image.mode in ("RGBA", "LA", "PA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        image = image.convert("RGBA")
        flat = Image.new("RGB", image.size, "white")
        flat.paste(image, mask=image.getchannel("A"))
        return flat
    return image if image.mode == "RGB" else image.convert("RGB")


def save_jpeg(image, kind, box, output):
    with image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail(box)
        image = to_rgb(image)
        image.save(output, "JPEG", quality=QUALITY[kind], optimize=True)


def open_picture(source, box):
    if os.path.getsize(source) > MAX_IMAGE_BYTES:
        raise NotApplicable("file too big")
    image = Image.open(source)
    if image.format not in IMAGE_FORMATS:
        raise NotApplicable(f"not an image format we convert ({image.format})")
    check_pixels(*image.size)
    if image.format in ("JPEG", "MPO"):
        # Lets the decoder scale down while reading: much faster for big photos.
        image.draft("RGB", (2 * box[0], 2 * box[1]))
    return image


def video_frame(source, workdir):
    """A still picture from the video, taken a tenth into it (the first second at least)."""
    probe = run_tool(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type", "-of", "json", source,
        ]
    )  # fmt: skip
    try:
        info = json.loads(probe.stdout.decode("utf-8", errors="replace"))
    except ValueError:
        info = {}
    if not any(s.get("codec_type") == "video" for s in info.get("streams", [])):
        # Audio in a video container, or something that is no video at all.
        raise NotApplicable("no video stream")
    duration = _float(info.get("format", {}).get("duration")) or 0.0
    frame = os.path.join(workdir, "frame.png")
    for seek in (max(duration * 0.1, 1.0) if duration > 2 else 0.0, 0.0):
        result = run_tool(
            [
                "ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file",
                "-ss", f"{seek:.2f}", "-i", source, "-frames:v", "1", "-y", frame,
            ]
        )  # fmt: skip
        if result.returncode == 0 and os.path.exists(frame):
            return Image.open(frame)
    raise RuntimeError("no picture in the video: " + result.stderr.decode()[-200:])


def pdf_page(source, workdir, dpi):
    """Page 1 of a PDF as a picture, rendered by Ghostscript."""
    page = os.path.join(workdir, "page.png")
    result = run_tool(
        [
            "gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-dFirstPage=1",
            "-dLastPage=1", "-sDEVICE=png16m", f"-r{dpi}", "-dTextAlphaBits=4",
            "-dGraphicsAlphaBits=4", f"-sOutputFile={page}", source,
        ]
    )  # fmt: skip
    if result.returncode != 0 or not os.path.exists(page):
        raise RuntimeError("Ghostscript: " + result.stderr.decode()[-200:])
    return Image.open(page)


def audio_cover(source):
    """The cover picture in the tags of an audio file, as a PIL image."""
    import mutagen

    tags = mutagen.File(source)
    data = None
    if tags is not None:
        pictures = getattr(tags, "pictures", None)  # FLAC
        if pictures:
            data = pictures[0].data
        elif tags.tags is not None:
            for key in tags.tags.keys():
                if str(key).startswith("APIC"):  # MP3
                    data = tags.tags[key].data
                    break
                if str(key) == "covr":  # MP4/M4A
                    data = bytes(tags.tags[key][0])
                    break
                if str(key).lower() == "metadata_block_picture":  # Ogg
                    import base64

                    from mutagen.flac import Picture

                    data = Picture(base64.b64decode(tags.tags[key][0])).data
                    break
    if not data:
        raise NotApplicable("no cover picture in the tags")
    return Image.open(io.BytesIO(data))


def make_picture(source, kind, spec, ext, output, workdir):
    width, height = (int(part) for part in spec.split("x"))
    box = (width, height)
    if ext in RAW_EXTENSIONS:
        image = open_raw(source, box)
    elif ext in VIDEO_EXTENSIONS:
        image = video_frame(source, workdir)
    elif ext == "pdf":
        image = pdf_page(source, workdir, 72 if kind == "tile" else 180)
    elif ext in AUDIO_EXTENSIONS:
        image = audio_cover(source)
    elif ext in OFFICE_EXTENSIONS:
        raise NotApplicable("office documents are converted to PDF first")
    else:
        image = open_picture(source, box)
    check_pixels(*image.size)
    save_jpeg(image, kind, box, output)


# ---------------------------------------------------------------- office, text


def office_to_pdf(source, ext, output, workdir):
    if ext not in OFFICE_EXTENSIONS:
        raise NotApplicable("not an office format")
    if os.path.getsize(source) > MAX_OFFICE_BYTES:
        raise NotApplicable("office file too big")
    # LibreOffice picks the filter by the extension: link the file under its own.
    linked = os.path.join(workdir, f"document.{ext}")
    os.symlink(source, linked)
    result = run_tool(
        [
            "soffice", "--headless", "--norestore", "--nolockcheck", "--nologo",
            f"-env:UserInstallation=file://{workdir}/profile",
            "--convert-to", "pdf", "--outdir", workdir, linked,
        ]
    )  # fmt: skip
    produced = os.path.join(workdir, "document.pdf")
    if result.returncode != 0 or not os.path.exists(produced):
        message = (result.stderr or result.stdout).decode()[-200:]
        raise RuntimeError("LibreOffice: " + message)
    os.replace(produced, output)


def decode_text(data):
    """Text of a file in any usual encoding: UTF-16 by its mark, else UTF-8, else CP1252."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def write_text(text, output):
    text = text.replace("\x00", "")[:MAX_TEXT_CHARS]
    with open(output, "w", encoding="utf-8") as f:
        f.write(text)


def make_text(source, ext, output):
    if ext == "pdf":
        result = run_tool(
            [
                "pdftotext", "-enc", "UTF-8", "-nopgbrk", "-l", str(MAX_PDF_TEXT_PAGES),
                source, "-",
            ]
        )  # fmt: skip
        if result.returncode != 0:
            raise RuntimeError("pdftotext: " + result.stderr.decode()[-200:])
        write_text(result.stdout.decode("utf-8", errors="replace"), output)
    elif ext in TEXT_EXTENSIONS:
        with open(source, "rb") as f:
            write_text(decode_text(f.read(4 * MAX_TEXT_CHARS)), output)
    else:
        raise NotApplicable("no text to take from this kind of file")


# ---------------------------------------------------------------- metadata


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _exif_datetime(value):
    """'2019:07:04 12:30:00' (Exif) or ISO-like -> 'YYYY-MM-DD HH:MM:SS' or None."""
    text = str(value or "")[:19]
    if len(text) == 19 and text[4] in ":-" and text[10] in " T":
        return f"{text[:4]}-{text[5:7]}-{text[8:10]} {text[11:19]}"
    return None


def _text(value):
    return None if value in (None, "") else str(value)


def _integer(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def picture_meta(source):
    """Camera facts of a picture or video by ExifTool (numbers, not print conversions)."""
    result = run_tool(["exiftool", "-j", "-n", "-api", "largefilesupport=1", source])
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError("exiftool: " + result.stderr.decode()[-200:])
    info = json.loads(result.stdout.decode("utf-8", errors="replace"))[0]
    if info.get("Error"):
        # ExifTool exits 0 for a file it cannot read and says so in the result.
        raise RuntimeError(f"exiftool: {info['Error']}")
    camera =" ".join(
        str(part) for part in (info.get("Make"), info.get("Model")) if part
    )
    meta = {
        "taken_at": _exif_datetime(
            info.get("DateTimeOriginal") or info.get("CreateDate")
        ),
        "camera": camera or None,
        "lens": _text(info.get("LensModel") or info.get("LensID")),
        "exposure_time": _float(info.get("ExposureTime")),
        "f_number": _float(info.get("FNumber")),
        "iso": _integer(info.get("ISO")),
        "gps_lat": _float(info.get("GPSLatitude")),
        "gps_lon": _float(info.get("GPSLongitude")),
        "orientation": _integer(info.get("Orientation")),
        "software": _text(info.get("Software")),
        "artist": _text(info.get("Artist") or info.get("Creator")),
        "width": _integer(info.get("ImageWidth")),
        "height": _integer(info.get("ImageHeight")),
    }
    meta = {key: value for key, value in meta.items() if value not in (None, "")}
    if not meta and info.get("Warning"):
        # Nothing readable, and ExifTool complains: junk, not a picture without facts.
        raise RuntimeError(f"exiftool: {info['Warning']}")
    return meta


def picture_meta_safe(source):
    try:
        return picture_meta(source)
    except (RuntimeError, ValueError, IndexError):
        return {}


def media_meta(source):
    """Duration, codecs and tags of audio and video by ffprobe."""
    result = run_tool(
        [
            "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json",
            source,
        ]
    )  # fmt: skip
    if result.returncode != 0:
        raise RuntimeError("ffprobe: " + result.stderr.decode()[-200:])
    info = json.loads(result.stdout.decode("utf-8", errors="replace"))
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    meta = {
        "duration": _float(fmt.get("duration")),
        "bitrate": _float(fmt.get("bit_rate")),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio[0].get("codec_name") if audio else None,
        "audio_tracks": len(audio) or None,
        "width": _integer(video.get("width")),
        "height": _integer(video.get("height")),
        "chapters": len(info.get("chapters", [])) or None,
    }
    num, _, den = video.get("avg_frame_rate", "").partition("/")
    if _float(num) and _float(den):
        meta["frame_rate"] = _float(num) / _float(den)
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
    for key, names in (
        ("title", ("title",)),
        ("artist", ("artist", "album_artist")),
        ("album", ("album",)),
        ("composer", ("composer",)),
        ("genre", ("genre",)),
    ):
        for name in names:
            if tags.get(name):
                meta[key] = tags[name]
                break
    if tags.get("creation_time"):
        meta["taken_at"] = _exif_datetime(tags["creation_time"])
    return {key: value for key, value in meta.items() if value not in (None, "")}


def pdf_meta(source):
    result = run_tool(["pdfinfo", source])
    if result.returncode != 0:
        raise RuntimeError("pdfinfo: " + result.stderr.decode()[-200:])
    meta = {}
    names = {"Title": "title", "Author": "artist", "Producer": "software"}
    for line in result.stdout.decode("utf-8", errors="replace").splitlines():
        key, _, value = line.partition(":")
        if key == "Pages" and value.strip().isdigit():
            meta["pages"] = int(value)
        elif key in names and value.strip():
            meta[names[key]] = value.strip()
    return meta


def make_meta(source, ext, output):
    if ext == "pdf":
        meta = pdf_meta(source)
    elif ext in AUDIO_EXTENSIONS:
        meta = media_meta(source)
    elif ext in VIDEO_EXTENSIONS:
        meta = {**picture_meta_safe(source), **media_meta(source)}
    elif ext in OFFICE_EXTENSIONS or ext in TEXT_EXTENSIONS:
        raise NotApplicable("no metadata taken from this kind of file")
    else:
        meta = picture_meta(source)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(meta, f)


# ---------------------------------------------------------------- main


def main(argv):
    source, kind, spec, ext, output = argv[1:6]
    workdir = os.path.dirname(os.path.abspath(output))
    try:
        if kind in QUALITY:
            make_picture(source, kind, spec, ext, output, workdir)
        elif kind == "preview_pdf":
            office_to_pdf(source, ext, output, workdir)
        elif kind == "text":
            make_text(source, ext, output)
        elif kind == "meta":
            make_meta(source, ext, output)
        else:
            raise NotApplicable(f"unknown kind {kind}")
    except NotApplicable as exc:
        say("not_applicable", str(exc))
        return EXIT_NOT_APPLICABLE
    except Image.DecompressionBombError as exc:
        # Pillow's own guard fires while opening, before our pixel check gets to run.
        say("not_applicable", f"too many pixels ({exc})"[:300])
        return EXIT_NOT_APPLICABLE
    except Exception as exc:  # noqa: BLE001 - every decoder has its own error types
        # A broken, truncated or unreadable file; the process ends here either way.
        say("failed", f"{type(exc).__name__}: {exc}"[:300])
        return EXIT_FAILED
    say("done")
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main(sys.argv))
