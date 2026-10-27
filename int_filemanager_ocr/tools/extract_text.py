"""Read the text of a file, page by page. Runs as a child process of the scheduled action.

    python extract_text.py <path> <mimetype> <first page> <block size> <cut size> <memory MiB> [<pages>]

It does not import Odoo (standard library, ``lxml`` and ``pdfminer`` only), so the parent can
bound it in time and memory and kill it: one page of a PDF can take minutes, and in the Odoo
process that would hold up the other users (threaded) or get the worker killed (prefork).

The answer is one JSON object per line on stdout:

- ``{"pages": n}``: the number of pages (PDF only), first
- ``{"page": n, "text": "..."}``: one page, as soon as it is done; ``"cut": true`` if the text
  was cut at the size limit; a PDF page also says ``"image": true`` if it has a picture or a
  form in its resources (a scan has one, an empty sheet has none)
- ``{"done": true}``: the end
- ``{"error": "<kind>", "message": "..."}``: kind is ``corrupt``, ``encrypted`` or ``memory``

Office and text files have no pages: their text is cut into blocks of at most ``block size``
bytes, numbered like pages. A page or block starts at ``first page``; earlier ones are skipped
(the parent has them from a run that was stopped). ``cut size`` is the most bytes of UTF-8 one
PDF page may have; ``memory MiB`` is how much the process may grow. ``pages`` (PDF only) is a
list of page numbers, ``3,7,12``: only these are read (``first page`` is then ignored). The text
recognition reads the pages of the section it just made.
"""

import codecs
import io
import json
import logging
import sys
import zipfile
from lxml import etree

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
ODF = (
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
)
PDF = "application/pdf"

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
S_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
ODF_NS = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
ODF_SPACES = (ODF_NS + "s", ODF_NS + "tab", ODF_NS + "line-break")

# Bytes of a text file that are read at a time to find out whether it is UTF-8.
READ_SIZE = 1024 * 1024
# Parts of a Word file besides the body that carry text.
DOCX_EXTRA_PARTS = ("header", "footer", "footnotes", "endnotes", "comments")


class Corrupt(Exception):
    """The file is not what its type says."""


class Encrypted(Exception):
    """The file needs a password."""


def clean(text):
    """Return what a database text column takes: no NUL, no lone surrogates."""
    return text.replace("\x00", "").encode("utf-8", "ignore").decode("utf-8")


def cut(text, size):
    """Cut ``text`` to at most ``size`` bytes of UTF-8, at a character, and return ``(text, was_cut)``.
    """
    data = text.encode("utf-8")
    if len(data) <= size:
        return text, False
    return data[:size].decode("utf-8", "ignore"), True


def blocks(pieces, size):
    """Join the pieces of text (paragraphs, lines) to blocks of at most ``size`` bytes of UTF-8.

    A block ends where a piece ends if the next one does not fit; a piece above the size is
    cut up at a character.
    """
    size = max(size, 16)
    parts, used = [], 0
    for piece in pieces:
        data = clean(piece).encode("utf-8")
        if not data:
            continue
        if len(data) > size:
            if parts:
                yield "\n".join(parts)
                parts, used = [], 0
            while len(data) > size:
                head = data[:size].decode("utf-8", "ignore")
                yield head
                data = data[len(head.encode("utf-8")) :]
            if not data:
                continue
        extra = len(data) + (1 if parts else 0)
        if parts and used + extra > size:
            yield "\n".join(parts)
            parts, used, extra = [], 0, len(data)
        parts.append(data.decode("utf-8"))
        used += extra
    if parts:
        yield "\n".join(parts)


def elements(stream, tags):
    """Iterate over the elements ``tags`` of an XML file, each when it ends; no entities, no network.
    """
    return etree.iterparse(
        stream, events=("end",), tag=tags, resolve_entities=False, no_network=True
    )


def discard(element):
    """Free an element that is done (and the ones before it) so the tree stays small."""
    element.clear()
    parent = element.getparent()
    while parent is not None and element.getprevious() is not None:
        del parent[0]


def open_part(archive, name):
    try:
        return archive.open(name)
    except KeyError:
        raise Corrupt(f"The file has no part {name}.") from None


def paragraphs(stream, paragraph_tag, text_tag, space_tags):
    """Yield the text of each paragraph: its ``text_tag`` elements, a blank for the ``space_tags``.
    """
    for _event, paragraph in elements(stream, paragraph_tag):
        parts = []
        for node in paragraph.iter(text_tag, *space_tags):
            parts.append((node.text or "") if node.tag == text_tag else " ")
        yield "".join(parts)
        discard(paragraph)


def iter_docx(archive):
    def is_extra(name):
        stem = name.rsplit("/", 1)[-1].split(".")[0].rstrip("0123456789")
        return name.startswith("word/") and name.endswith(".xml") and stem in DOCX_EXTRA_PARTS

    names = ["word/document.xml"] + sorted(name for name in archive.namelist() if is_extra(name))
    for name in names:
        with open_part(archive, name) as stream:
            yield from paragraphs(stream, W_NS + "p", W_NS + "t", (W_NS + "tab", W_NS + "br"))


def iter_pptx(archive):
    def number(name):
        digits = "".join(char for char in name if char.isdigit())
        return int(digits) if digits else 0

    slides = sorted(
        (
            name
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        ),
        key=number,
    )
    for name in slides:
        with open_part(archive, name) as stream:
            yield from paragraphs(stream, A_NS + "p", A_NS + "t", (A_NS + "br",))


def iter_odf(archive):
    # A paragraph may hold a frame with paragraphs of its own: the inner one ends first and is
    # cleared, the outer one then has the rest.
    with open_part(archive, "content.xml") as stream:
        for _event, paragraph in elements(stream, (ODF_NS + "p", ODF_NS + "h")):
            for node in paragraph.iter(*ODF_SPACES):
                node.text = " "
            yield "".join(paragraph.itertext())
            discard(paragraph)


def shared_strings(archive):
    try:
        stream = archive.open("xl/sharedStrings.xml")
    except KeyError:
        return []
    with stream:
        strings = []
        for _event, item in elements(stream, S_NS + "si"):
            strings.append("".join(node.text or "" for node in item.iter(S_NS + "t")))
            discard(item)
        return strings


def iter_xlsx(archive):
    strings = shared_strings(archive)
    sheets = sorted(
        name
        for name in archive.namelist()
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
    )
    for name in sheets:
        with open_part(archive, name) as stream:
            cells = []
            for _event, element in elements(stream, (S_NS + "c", S_NS + "row")):
                if element.tag == S_NS + "row":
                    yield " ".join(cells)
                    cells = []
                    discard(element)
                    continue
                kind = element.get("t")
                if kind == "inlineStr":
                    value = "".join(node.text or "" for node in element.iter(S_NS + "t"))
                else:
                    node = element.find(S_NS + "v")
                    value = node.text if node is not None and node.text else ""
                    if kind == "s":
                        value = strings[int(value)] if value.isdigit() and int(value) < len(strings) else ""
                if value:
                    cells.append(value)
            if cells:
                yield " ".join(cells)


def iter_zip(path, reader):
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise Corrupt("The file is not a valid archive.") from None
    with archive:
        try:
            yield from reader(archive)
        except (etree.XMLSyntaxError, zipfile.BadZipFile) as error:
            raise Corrupt(f"The file is broken: {error}") from None


def text_encoding(path):
    """Return ``utf-8-sig`` if the whole file is UTF-8, else ``latin-1`` (it takes every byte)."""
    decoder = codecs.getincrementaldecoder("utf-8-sig")(errors="strict")
    try:
        with open(path, "rb") as stream:
            while chunk := stream.read(READ_SIZE):
                decoder.decode(chunk)
        decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return "latin-1"
    return "utf-8-sig"


def iter_plain(path):
    with open(path, encoding=text_encoding(path), newline="") as stream:
        for line in stream:
            yield line.rstrip("\r\n")


def has_picture(page, resolve1):
    """Return whether the resources of a page name a picture or a form (``XObject``)."""
    try:
        return bool(resolve1(resolve1(page.resources).get("XObject")))
    except Exception:  # noqa: BLE001 (a broken page: it is no scan we know of)
        return False


def iter_pdf(path, first_page, report_pages, pages=None):
    """Yield ``(page number, text, has a picture)`` from ``first_page`` to the end.

    ``pages`` (a set of numbers) limits it to these pages. ``report_pages(n)`` gets the number
    of pages of the file.
    """
    from pdfminer.converter import TextConverter  # noqa: PLC0415
    from pdfminer.layout import LAParams  # noqa: PLC0415
    from pdfminer.pdfdocument import PDFDocument, PDFPasswordIncorrect  # noqa: PLC0415
    from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager  # noqa: PLC0415
    from pdfminer.pdfpage import PDFPage  # noqa: PLC0415
    from pdfminer.pdfparser import PDFParser  # noqa: PLC0415
    from pdfminer.pdftypes import resolve1  # noqa: PLC0415

    logging.getLogger("pdfminer").setLevel(logging.CRITICAL)
    with open(path, "rb") as stream:
        try:
            document = PDFDocument(PDFParser(stream))
            count = resolve1(resolve1(document.catalog["Pages"])["Count"])
        except PDFPasswordIncorrect:
            raise Encrypted("The file needs a password.") from None
        except Exception as error:  # noqa: BLE001 (pdfminer raises whatever the file breaks)
            raise Corrupt(f"The PDF cannot be read: {error}") from None
        if isinstance(count, int):
            report_pages(count)
        manager = PDFResourceManager()
        # As the core's attachment_indexation does: no grouping of text boxes (it costs memory).
        # ``extract_pages`` would give no text for the invisible text a scan has after OCR.
        laparams = LAParams(detect_vertical=True, boxes_flow=None)
        for number, page in enumerate(PDFPage.create_pages(document), 1):
            if pages is not None:
                if number > max(pages, default=0):
                    break
                if number not in pages:
                    continue
            elif number < first_page:
                continue
            with io.StringIO() as content, TextConverter(
                manager, content, laparams=laparams
            ) as device:
                try:
                    PDFPageInterpreter(manager, device).process_page(page)
                except Exception:  # noqa: BLE001 (a broken page: the others may be fine)
                    content.seek(0)
                    content.truncate()
                yield number, content.getvalue(), has_picture(page, resolve1)


def limit_memory(budget_mib):
    """Let the process grow by ``budget_mib`` at most (where the system allows it)."""
    try:
        import resource  # noqa: PLC0415
    except ImportError:
        return
    try:
        with open("/proc/self/statm", encoding="ascii") as statm:
            current = int(statm.read().split()[0]) * resource.getpagesize()
    except (OSError, ValueError):
        current = 512 * 1024 * 1024
    _soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    wanted = current + budget_mib * 1024 * 1024
    if hard != resource.RLIM_INFINITY:
        wanted = min(wanted, hard)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (wanted, hard))
    except (ValueError, OSError):
        pass


def emit(**message):
    sys.stdout.write(json.dumps(message, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def run(path, mimetype, first_page, block_size, cut_size, pages=None):
    if mimetype == PDF:
        for number, text, picture in iter_pdf(path, first_page, lambda count: emit(pages=count), pages):
            text, was_cut = cut(clean(text), cut_size)
            emit(page=number, text=text, image=picture, **({"cut": True} if was_cut else {}))
        return
    if mimetype == DOCX:
        pieces = iter_zip(path, iter_docx)
    elif mimetype == XLSX:
        pieces = iter_zip(path, iter_xlsx)
    elif mimetype == PPTX:
        pieces = iter_zip(path, iter_pptx)
    elif mimetype in ODF:
        pieces = iter_zip(path, iter_odf)
    elif mimetype.startswith("text/"):
        pieces = iter_plain(path)
    else:
        raise Corrupt(f"The type {mimetype} has no reader.")
    for number, block in enumerate(blocks(pieces, block_size), 1):
        if number >= first_page:
            emit(page=number, text=block)


def main(argv):
    path, mimetype = argv[1], argv[2]
    first_page, block_size, cut_size, memory_mib = (int(value) for value in argv[3:7])
    pages = {int(number) for number in argv[7].split(",")} if len(argv) > 7 and argv[7] else None
    limit_memory(memory_mib)
    try:
        run(path, mimetype, first_page, block_size, cut_size, pages)
    except MemoryError:
        emit(error="memory", message="The file needs more memory than the budget.")
        return 0
    except Corrupt as error:
        emit(error="corrupt", message=str(error))
        return 0
    except Encrypted as error:
        emit(error="encrypted", message=str(error))
        return 0
    except Exception as error:  # noqa: BLE001 (what the file breaks, told to the parent)
        emit(error="corrupt", message=f"{type(error).__name__}: {error}")
        return 0
    emit(done=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
