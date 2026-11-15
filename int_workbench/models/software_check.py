"""Read and judge the program files of the controllers: S-Record images and program texts.

What the files are, and how they are told apart, is measured on the whole stock of the original (micserv-7.1/PROGRAMMIERDATEN.md): the
name and the extension of a file say nothing, so everything here goes by the content. The module is plain Python (no ORM) so that it can
be tested alone and be compared with the reading in the Go service.
"""

import hashlib
import re
from dataclasses import dataclass, field

# What a file is. "text" is a program that is sent as lines through the command line (`dl 1`), not as an image through the bootloader.
KIND_OS = "os"
KIND_APPLICATION = "application"
KIND_COMBINED = "combined"
KIND_BOOTLOADER = "bootloader"
KIND_PARAMETER = "parameter"
KIND_TEXT = "text"
KIND_UNKNOWN = "unknown"

# Which controller the image is for, told by where it sits in the memory.
HARDWARE_HA3X = "ha3x"
HARDWARE_FAMILY_B = "family_b"
HARDWARE_UNKNOWN = "unknown"

# The places in the memory of a controller (measured, PROGRAMMIERDATEN.md section 1).
OS_START = 0x000000
APPLICATION_START = 0x198000
FAMILY_B_START = 0x04D000
BOOTLOADER_STARTS = (0xFF8000, 0xEF8000)
PARAMETER_START = 0x3B385C
PARAMETER_LIMIT = 0x10000  # a block of parameters is small (1 to 2 KB measured)

MAX_FILE_SIZE = 16 * 1024 * 1024
HEADER_WINDOW = 80  # the application header starts within these bytes of the start of its range

# Application header: ... 05 06 (FF FE | FE FF), the name (32 bytes), the resource (32 bytes). Family B has the other byte order.
APPLICATION_MARK = re.compile(rb"\x05\x06(?:\xff\xfe|\xfe\xff)")
# 009880 is the number of the operating system, not of an application
APPLICATION_DOCUMENT = re.compile(rb"3EGM(?!009880)(\d{6})E(\d{4})")
OS_IDENTITY = re.compile(rb"3EGM ?0098 ?80 ?E0(\d)(\d\d)")
OS_EXPECTED = re.compile(rb"3EGM009880E9(\d)(\d\d)")

TEXT_HEADER = re.compile(r"#\s*PLC\s+Applikation:\s*([^,\r\n]*),\s*Resource:\s*([^\r\n,]*?)(?:,\s*Byteanz\.\s*=\s*(\d+))?\s*$", re.M | re.I)
TEXT_DATE = re.compile(r"Erstelldatum Resource[^=]*=\s*(\d\d\.\d\d\.\d{4})\s+(\d\d:\d\d:\d\d)")


class ImageError(ValueError):
    """The file cannot be a program file of the controllers. The reason is a code with its values (the words are the model's, which
    translates them): ``empty``, ``too_large``, ``not_a_program``, ``bad_line``, ``not_hex``, ``bad_length``, ``bad_checksum``,
    ``unknown_record``, ``no_data``, ``text_no_header``, ``text_no_data``."""

    def __init__(self, code, **values):
        super().__init__(code)
        self.code = code
        self.values = values


@dataclass
class Checked:
    """What reading a file found out."""

    kind: str = KIND_UNKNOWN
    hardware: str = HARDWARE_UNKNOWN
    sha256: str = ""
    size: int = 0
    data_size: int = 0
    ranges: list = field(default_factory=list)  # [(first, last)] of the bytes that the image writes
    app_name: str = ""
    resource: str = ""
    document: str = ""  # 3EGM<6 digits>E<4 digits>: the document number of the application
    document_number: str = ""  # the six digits of it
    document_codes: list = field(default_factory=list)  # the E<d><nnn> numbers that the image carries: E2nnn (CAN), E3nnn, E4nnn (diagnosis)
    os_version: str = ""  # the operating system that is in the image: "3.10"
    expected_os: str = ""  # the one the application says it is made for (assumed, not proven): "2.10"
    created: str = ""  # of a program text
    warnings: list = field(default_factory=list)  # [(code, values)]: overlap, no_end, unknown_ranges, no_header, name_differs, text_no_dl


def check_file(filename, content):
    """Read a file and say what it is; raise ImageError if it is neither an image nor a program text."""
    if not content:
        raise ImageError("empty")
    if len(content) > MAX_FILE_SIZE:
        raise ImageError("too_large", megabytes=MAX_FILE_SIZE // 1024 // 1024)
    first = content[:200].lstrip()
    if first[:1] in (b"S", b"s") and re.match(rb"[Ss][0-9]", first):
        result = _check_image(content)
    elif _looks_like_text(content):
        result = _check_text(content)
    else:
        raise ImageError("not_a_program")
    result.sha256 = hashlib.sha256(content).hexdigest()
    result.size = len(content)
    result.warnings += _name_warnings(filename, result)
    return result


def _name_warnings(filename, result):
    """The name of a file is no proof of its content; say so where they differ."""
    stem = re.sub(r"\.[^.]*$", "", filename or "").strip().lower()
    if result.app_name and stem and stem != result.app_name.lower() and result.kind in (KIND_APPLICATION, KIND_COMBINED, KIND_TEXT):
        return [("name_differs", {"filename": filename, "app_name": result.app_name})]
    return []


def _check_image(content):
    segments, ends, bad = [], 0, []
    previous_end = None
    lines = content.split(b"\n")
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        if line[:1] not in (b"S", b"s") or len(line) < 10:
            raise ImageError("bad_line", line=number)
        kind = chr(line[1])
        try:
            record = bytes.fromhex(line[2:].decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            raise ImageError("not_hex", line=number) from None
        if len(record) != record[0] + 1:
            raise ImageError("bad_length", line=number)
        if (sum(record[:-1]) + record[-1]) & 0xFF != 0xFF:
            raise ImageError("bad_checksum", line=number)
        address_length = {"0": 2, "1": 2, "2": 3, "3": 4, "5": 2, "7": 4, "8": 3, "9": 2}.get(kind)
        if address_length is None:
            raise ImageError("unknown_record", line=number, record=kind)
        if kind in "789":
            ends += 1
            continue
        if kind not in "123":
            continue
        address = int.from_bytes(record[1 : 1 + address_length], "big")
        data = record[1 + address_length : -1]
        if previous_end == address and segments:
            segments[-1][1] += data
        else:
            segments.append([address, bytearray(data)])
        previous_end = address + len(data)
    if not segments:
        raise ImageError("no_data")
    # a segment is a stretch without a gap; two stretches that touch are one range
    segments.sort(key=lambda segment: segment[0])
    merged = []
    for start, data in segments:
        if merged and start < merged[-1][0] + len(merged[-1][1]):
            bad.append(("overlap", {"address": "0x%X" % start}))
        if merged and start == merged[-1][0] + len(merged[-1][1]):
            merged[-1][1] += data
        else:
            merged.append([start, bytearray(data)])
    result = Checked()
    result.ranges = [(start, start + len(data) - 1) for start, data in merged]
    result.data_size = sum(len(data) for _start, data in merged)
    result.warnings += bad
    if not ends:
        result.warnings.append(("no_end", {}))
    _classify(result, merged)
    return result


def _classify(result, merged):
    starts = [start for start, _data in merged]
    has_os = OS_START in starts
    application = next(((start, data) for start, data in merged if start == APPLICATION_START), None)
    family_b = next(((start, data) for start, data in merged if start == FAMILY_B_START), None)
    if any(start in BOOTLOADER_STARTS for start in starts):
        result.kind = KIND_BOOTLOADER
        # 0xFF8000 is the bootstrap of the controllers of the original; the other place is not placed yet
        result.hardware = HARDWARE_HA3X if BOOTLOADER_STARTS[0] in starts else HARDWARE_UNKNOWN
    elif family_b:
        result.kind = KIND_COMBINED
        result.hardware = HARDWARE_FAMILY_B
        _read_application(result, family_b[1])
    elif has_os and application:
        result.kind = KIND_COMBINED
        result.hardware = HARDWARE_HA3X
    elif has_os:
        result.kind = KIND_OS
        result.hardware = HARDWARE_HA3X
    elif application:
        result.kind = KIND_APPLICATION
        result.hardware = HARDWARE_HA3X
    elif any(PARAMETER_START <= start < PARAMETER_START + PARAMETER_LIMIT for start in starts) and result.data_size < PARAMETER_LIMIT:
        result.kind = KIND_PARAMETER
        result.hardware = HARDWARE_HA3X
    else:
        result.warnings.append(("unknown_ranges", {"ranges": ", ".join("0x%X" % start for start in starts[:4])}))
        return
    if application:
        _read_application(result, application[1])
    if result.kind in (KIND_APPLICATION, KIND_COMBINED):
        _read_documents(result, merged)
    # the operating system says which version it is (E0310 is 3.10); a block of parameters carries the one it belongs to
    if has_os or result.kind == KIND_PARAMETER:
        for start, data in merged:
            if start == OS_START or result.kind == KIND_PARAMETER:
                match = OS_IDENTITY.search(data)
                if match:
                    result.os_version = "%s.%s" % (match.group(1).decode(), match.group(2).decode())
                    break
    if result.kind == KIND_APPLICATION and not result.app_name:
        result.warnings.append(("no_header", {}))


def _read_application(result, data):
    """Name, resource, document number and the operating system the application is made for, from the start of its range."""
    head = bytes(data[:HEADER_WINDOW])
    mark = APPLICATION_MARK.search(head)
    if mark:
        name_start = mark.end()
        result.app_name = _text(data[name_start : name_start + 32])
        result.resource = _text(data[name_start + 32 : name_start + 64])
    expected = OS_EXPECTED.search(data)
    if expected:
        result.expected_os = "%s.%s" % (expected.group(1).decode(), expected.group(2).decode())


def _read_documents(result, merged):
    """The document numbers an application carries, wherever they sit (for many images in the area of the lists at 0x2B8000, not at the
    start of the application). Measured: an image carries the numbers of the configuration documents it belongs to, E2nnn (the CAN
    configuration, confcan), E3nnn (confpdl) and E4nnn (the diagnosis, confdia, the same number as the error table Ftab); see
    micserv-7.1/PROGRAMMIERDATEN.md, section 7."""
    pairs = []
    for _start, data in merged:
        for match in APPLICATION_DOCUMENT.finditer(data):
            pair = (match.group(1).decode(), "E%s" % match.group(2).decode())
            if pair not in pairs:
                pairs.append(pair)
    result.document_codes = [code for _number, code in pairs]
    # the application's own number is the E2 one (the same as its CAN configuration), if there is one
    chosen = next((pair for pair in pairs if pair[1].startswith("E2")), pairs[0] if pairs else None)
    if chosen and not result.document:
        result.document = "3EGM%s%s" % chosen
        result.document_number = chosen[0]


def _text(raw):
    """A text field of a header: printable characters up to the first filler."""
    out = bytearray()
    for byte in raw:
        if byte < 0x20 or byte > 0x7E:
            break
        out.append(byte)
    return out.decode("ascii").strip()


def _looks_like_text(content):
    head = content[:4000].decode("latin1", "replace")
    return bool(TEXT_HEADER.search(head))


def _check_text(content):
    """A program that is sent as text (`dl 1`, then the lines `*ADDRESS word word ...`)."""
    text = content.decode("latin1", "replace")
    match = TEXT_HEADER.search(text)
    result = Checked(kind=KIND_TEXT, hardware=HARDWARE_UNKNOWN)
    if not match:
        raise ImageError("text_no_header")
    result.app_name = match.group(1).strip()
    result.resource = match.group(2).strip()
    date = TEXT_DATE.search(text)
    if date:
        result.created = "%s %s" % (date.group(1), date.group(2))
    data_lines = [line for line in text.splitlines() if line.startswith("*")]
    if not data_lines:
        raise ImageError("text_no_data")
    result.data_size = sum(len(line.split()) - 1 for line in data_lines) * 2
    if not re.search(r"(?im)^\s*#?\s*dl\s+1\s*$", text):
        result.warnings.append(("text_no_dl", {}))
    return result
