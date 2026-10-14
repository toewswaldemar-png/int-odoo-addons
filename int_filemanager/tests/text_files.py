"""Small files of every type the text reader knows, made by hand (no libraries)."""

import io
import zipfile

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
ODT = "application/vnd.oasis.opendocument.text"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
T = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"


def escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pdf(pages):
    """A PDF with the text of each entry of ``pages`` on its own page (Helvetica, WinAnsi)."""
    count = len(pages)
    kids = " ".join(f"{4 + 2 * index} 0 R" for index in range(count))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for index, text in enumerate(pages):
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("cp1252")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {5 + 2 * index} 0 R"
            " /Resources << /Font << /F1 3 0 R >> >> >>".encode()
        )
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
        )
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def _zip(parts):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return stream.getvalue()


def docx(paragraphs, footer=None):
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>' for text in paragraphs)
    parts = {"word/document.xml": f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'}
    if footer:
        parts["word/footer1.xml"] = (
            f'<w:ftr xmlns:w="{W}"><w:p><w:r><w:t>{escape(footer)}</w:t></w:r></w:p></w:ftr>'
        )
    return _zip(parts)


def xlsx(rows, shared=True):
    """``rows``: lists of cells (text or numbers); text goes to the shared strings or inline."""
    strings = []
    sheet_rows = []
    for number, row in enumerate(rows, 1):
        cells = []
        for column, value in enumerate(row):
            reference = f"{chr(65 + column)}{number}"
            if isinstance(value, str) and shared:
                strings.append(value)
                cells.append(f'<c r="{reference}" t="s"><v>{len(strings) - 1}</v></c>')
            elif isinstance(value, str):
                cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
            else:
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
        sheet_rows.append(f'<row r="{number}">{"".join(cells)}</row>')
    parts = {
        "xl/worksheets/sheet1.xml": (
            f'<worksheet xmlns="{S}"><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
        )
    }
    if strings:
        items = "".join(f"<si><t>{escape(text)}</t></si>" for text in strings)
        parts["xl/sharedStrings.xml"] = f'<sst xmlns="{S}">{items}</sst>'
    return _zip(parts)


def pptx(slides):
    parts = {}
    for number, paragraphs in enumerate(slides, 1):
        body = "".join(f"<a:p><a:r><a:t>{escape(text)}</a:t></a:r></a:p>" for text in paragraphs)
        parts[f"ppt/slides/slide{number}.xml"] = (
            f'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="{A}">'
            f"<p:cSld><p:spTree><p:sp><p:txBody>{body}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
        )
    return _zip(parts)


def odt(paragraphs):
    body = "".join(f"<text:p>{escape(text)}</text:p>" for text in paragraphs)
    return _zip(
        {
            "content.xml": (
                f'<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
                f' xmlns:text="{T}"><office:body><office:text>{body}</office:text></office:body>'
                "</office:document-content>"
            )
        }
    )
