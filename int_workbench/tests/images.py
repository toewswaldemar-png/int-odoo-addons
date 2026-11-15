"""Program files built in memory, for the tests of the checker (Python here, Go in micserv/go/workbench/softwarelib).

Plain Python without Odoo, so that tools/int_workbench/software_golden.py can use it to write the file of common examples.
"""


def srec(parts, end=True):
    """The text of an S-Record file with the given ``[(address, bytes)]`` (S2 records of 32 bytes, an S0 header and an S8 end record)."""

    def record(kind, address, data):
        body = bytes([len(data) + 4]) + address.to_bytes(3, "big") + data
        return ("S%s%s%02X" % (kind, body.hex().upper(), (sum(body) & 0xFF) ^ 0xFF)).encode()

    lines = [record("0", 0, b"HDR")]
    for address, data in parts:
        for offset in range(0, len(data), 32):
            lines.append(record("2", address + offset, data[offset : offset + 32]))
    if end:
        lines.append(record("8", 0, b""))
    return b"\r\n".join(lines) + b"\r\n"


def field(text, length=32):
    return text.encode().ljust(length, b"\x00")


def application(name="BR186002", resource="R090644", document="3EGM090644E2002", expected="3EGM009880E9210", other_order=False):
    mark = b"\x05\x06\xfe\xff" if other_order else b"\x05\x06\xff\xfe"
    prefix = b"\xb3\x8f\x00\xf0\x00\xf0" if other_order else b"\x00\x04\x8b\xd5\xb3\x8f\x01\x5a\x01\x5a"
    return prefix + mark + field(name) + field(resource) + b"RES-GLOBAL".ljust(40, b"\x00") + document.encode() + b"\x00" + expected.encode() + b"\x00" * 20


def operating_system(identity="3EGM 0098 80 E0310"):
    return b"\x00\x40\x24\x1c" * 8 + identity.encode() + b"\x00" * 30


def lists(first="3EGM090644E2002", second="3EGM090644E4002"):
    """The area of the lists at 0x2B8000, where many images carry the numbers of their configuration documents."""
    return b"\x00" * 32 + first.encode().ljust(72, b"\x00") + second.encode() + b"\x00" * 8


APPLICATION_TEXT = (
    b"\r\n\r\n#dl 1\r\n#PLC  Applikation: CANTAUFE, Resource: 64EX_A00, Byteanz. = 8\r\n"
    b"Erstelldatum Resource (GMT+1) = 21.01.2003  15:34:37  \r\n> \r\n*1A44F0 75B3 8F00\r\n*1A44F8 0001 0002\r\n#PLC  Ende\r\n\r\n> \r\n"
)


def golden_cases():
    """The examples that Python and Go must read the same way: ``[(name, filename, content)]``."""
    bad = bytearray(srec([(0, operating_system())]))
    bad[40] = ord("1") if bad[40] != ord("1") else ord("2")
    return [
        ("os", "v310.bin", srec([(0, operating_system())])),
        ("os_old", "v205.dwn", srec([(0, operating_system("3EGM 0098 80 E0205"))])),
        ("application", "BR186002.dwn", srec([(0x198000, application()), (0x2B8000, b"\x01" * 64)])),
        ("application_lists", "BR186002.dwn", srec([(0x198000, application(document="", expected="")), (0x2B8000, lists())])),
        ("application_lists_reversed", "x.dwn", srec([(0x198000, application(document="", expected="")), (0x2B8000, lists("3EGM090644E4010", "3EGM090644E2010"))])),
        ("name_differs", "B1852010.dwn", srec([(0x198000, application("B1852006", "R090622", "3EGM090622E2004"))])),
        ("combined", "x.m00", srec([(0, operating_system("3EGM 0098 80 E0211")), (0x198000, application("ALP45010", "ALP45010"))])),
        ("family_b", "R2016010.DWN", srec([(0x4D000, application("R2016010", "RS090189", "3EGM090189E2010", other_order=True))])),
        ("bootloader", "b.dwn", srec([(0xFF8000, b"\x01\x02" * 40)])),
        ("bootloader_other", "b.dwn", srec([(0xEF8000, b"\x01\x02" * 40)])),
        ("parameter", "hsi.dwn", srec([(0x3B385C, b"3EGM 0098 80 E0205\x00hsi_frm.c ver: 1.00")])),
        ("unknown_ranges", "x.dwn", srec([(0x500000, b"\x01" * 16)])),
        ("no_end", "x.dwn", srec([(0, operating_system())], end=False)),
        ("text", "CANTAUFE.LAD", APPLICATION_TEXT),
        ("bad_checksum", "x", bytes(bad)),
        ("empty", "x", b""),
        ("not_a_program", "x", b"CONFCAN\r\n# nothing\r\n"),
        ("no_data", "x", b"S0030000FC\r\nS9030000FC\r\n"),
        ("text_no_data", "x", b"#PLC  Applikation: X, Resource: Y\r\n"),
    ]


def describe(check, filename, content):
    """What the checker says about a file, as plain data (the golden file holds it for each example, and the Go checker must say the same)."""
    try:
        result = check.check_file(filename, content)
    except check.ImageError as error:
        return {"ok": False, "error": error.code}
    return {
        "ok": True,
        "kind": result.kind,
        "hardware": result.hardware,
        "app_name": result.app_name,
        "resource": result.resource,
        "document": result.document,
        "document_number": result.document_number,
        "document_codes": list(result.document_codes),
        "os_version": result.os_version,
        "expected_os": result.expected_os,
        "created": result.created,
        "size": result.size,
        "data_size": result.data_size,
        "sha256": result.sha256,
        "ranges": [[first, last] for first, last in result.ranges],
        "warnings": [code for code, _values in result.warnings],
    }


def golden(check):
    """The file of the common examples: ``[{"name", "filename", "hex", "expected"}]``."""
    return [
        {"name": name, "filename": filename, "hex": content.hex(), "expected": describe(check, filename, content)}
        for name, filename, content in golden_cases()
    ]
