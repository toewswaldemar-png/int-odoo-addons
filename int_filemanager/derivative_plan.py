"""What is derived from which kind of file.

Chosen by the extension of the file name, not by ``node.mime``: the mime type is not set
for files that came in as chunked uploads or as new revisions, and the converter looks
into the file anyway. A lying extension ends as "not applicable" or "failed", never as a
wrong result.
"""

import dataclasses

TILE_SPEC = "400x300"
PREVIEW_SPEC = "1920x1920"
PDF_SPEC = "pdf"
TEXT_SPEC = "embedded"
# v2: lines, column gaps, each word's place in the text, page sizes; scans OCR'd anew.
# v3: text drawn twice for bold is read once.
# v4: the values of filled-in PDF form fields are part of the text and the words.
# v5: text printed in white on white (machine tags) is not part of the text.
# v6: the box of a word follows the glyph box of its font when the font declares no
# ascent and no descent (it stood on the baseline and stuck out above the text).
WORDS_SPEC = "v6"
META_SPEC = "v1"

# Order in the queue: what is seen first, then what is only looked up. "words" can mean
# OCR on a scan, which is slow - it waits behind everything else, including "text".
PRIORITY = {
    "tile": 0,
    "preview_pdf": 0,
    "text": -5,
    "preview": -10,
    "meta": -20,
    "words": -25,
}

# A browser shows these itself: their large preview is the original.
BROWSER_IMAGE_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "avif": "image/avif",
}
# These need converting for the large preview as well.
CONVERTED_IMAGE_EXTENSIONS = frozenset({"bmp", "tif", "tiff", "heic", "heif"})
RAW_EXTENSIONS = frozenset(
    (
        "cr2 cr3 crw nef nrw arw srf sr2 dng orf rw2 raf pef srw 3fr erf kdc mrw rwl"
        " x3f iiq"
    ).split()
)
VIDEO_EXTENSIONS = frozenset(
    "mp4 m4v mov avi mkv wmv mpg mpeg mts m2ts 3gp webm flv ogv".split()
)
AUDIO_EXTENSIONS = frozenset("mp3 flac m4a ogg oga opus wav wma aac".split())
OFFICE_EXTENSIONS = frozenset("doc docx odt rtf xls xlsx ods ppt pptx odp".split())
TEXT_EXTENSIONS = frozenset("txt md csv tsv log json xml html htm ini yml yaml".split())
PDF_EXTENSIONS = frozenset({"pdf"})
# Pictures whose text can be read, but only when someone asks for it: most of them are
# photos, not documents. The converter takes the same ones (PICTURE_WORD_EXTENSIONS).
READABLE_PICTURE_EXTENSIONS = frozenset({"jpg", "jpeg", "png"})


@dataclasses.dataclass(frozen=True)
class JobPlan:
    kind: str
    spec: str
    # The kind of the job whose result this one is made from (an office document
    # becomes a PDF first; picture and text are taken from the PDF).
    after: str | None = None
    # The mime type, when the original file itself is the result (nothing to convert).
    original_mime: str | None = None

    @property
    def priority(self):
        return PRIORITY[self.kind]


def file_extension(name):
    """The lower case extension of a file name if it looks like one, else ""."""
    ext = (name or "").rpartition(".")[2].lower() if "." in (name or "") else ""
    return ext if 0 < len(ext) <= 8 and ext.isalnum() else ""


def file_class(name):
    """What kind of file the name says it is, or None if nothing is derived from it."""
    ext = file_extension(name)
    if ext in BROWSER_IMAGE_TYPES:
        return "browser_image"
    if ext in CONVERTED_IMAGE_EXTENSIONS or ext in RAW_EXTENSIONS:
        return "converted_image"
    for label, extensions in (
        ("video", VIDEO_EXTENSIONS),
        ("pdf", PDF_EXTENSIONS),
        ("office", OFFICE_EXTENSIONS),
        ("audio", AUDIO_EXTENSIONS),
        ("text", TEXT_EXTENSIONS),
    ):
        if ext in extensions:
            return label
    return None


def image_class(name):
    """ "browser", "converted" or None: what to derive images from this name."""
    return {"browser_image": "browser", "converted_image": "converted"}.get(
        file_class(name)
    )


def job_plan(name):
    """The jobs of a file of this name, in an order in which dependencies come first."""
    klass = file_class(name)
    tile = JobPlan("tile", TILE_SPEC)
    preview = JobPlan("preview", PREVIEW_SPEC)
    meta = JobPlan("meta", META_SPEC)
    if klass == "browser_image":
        original = BROWSER_IMAGE_TYPES[file_extension(name)]
        return [tile, dataclasses.replace(preview, original_mime=original), meta]
    if klass in ("converted_image", "video"):
        return [tile, preview, meta]
    if klass == "pdf":
        return [tile, preview, JobPlan("words", WORDS_SPEC), meta]
    if klass == "office":
        return [
            JobPlan("preview_pdf", PDF_SPEC),
            dataclasses.replace(tile, after="preview_pdf"),
            dataclasses.replace(preview, after="preview_pdf"),
            JobPlan("words", WORDS_SPEC, after="preview_pdf"),
        ]
    if klass == "audio":
        return [tile, meta]
    if klass == "text":
        return [JobPlan("text", TEXT_SPEC)]
    return []


def can_read_text(name):
    """Whether the text of a picture of this name can be asked for."""
    return file_extension(name) in READABLE_PICTURE_EXTENSIONS


def has_tile(name):
    return any(item.kind == "tile" for item in job_plan(name))


def full_preview_kind(name):
    """The kind of large result the explorer's viewer needs when the browser cannot
    show the original itself: a picture for converted formats, a PDF for office."""
    kinds = {"converted_image": "preview", "office": "preview_pdf"}
    return kinds.get(file_class(name))


ALL_EXTENSIONS = sorted(
    set(BROWSER_IMAGE_TYPES)
    | CONVERTED_IMAGE_EXTENSIONS
    | RAW_EXTENSIONS
    | VIDEO_EXTENSIONS
    | AUDIO_EXTENSIONS
    | OFFICE_EXTENSIONS
    | TEXT_EXTENSIONS
    | PDF_EXTENSIONS
)

# Every (kind, spec) some file would get today. A row with any other pair was made by
# an older version of this plan (a changed size, a new word list format).
CURRENT_JOBS = sorted(
    {(item.kind, item.spec) for ext in ALL_EXTENSIONS for item in job_plan(f"x.{ext}")}
)
