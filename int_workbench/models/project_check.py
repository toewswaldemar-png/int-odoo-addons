"""Read and judge the definition files of a controller project (a "version" of the project library).

The rule of what belongs to a version and of its checksum is the one of the project library of the service (go/workbench/projectlib):
the same files give the same checksum in Python and in Go, and the value for a fixed example is the same in both tests. Plain Python
(no ORM), so that it can be tested alone and used by the tool that brings the stock of the original in.
"""

import hashlib
import io
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field

try:
    from . import software_check
except ImportError:  # used alone (the tool that brings the stock in): the modules lie side by side
    import software_check

# Files that the original or the user make, but that are no definition; they are no part of a version (they would change it each time
# the original runs). The rule of the service (projectlib.DefaultOptions).
EXCLUDED_EXTENSIONS = frozenset({"fs2", "rpt", "tmp", "bak", "exe", "zip", "rar", "pdf", "gif", "bmp"})
MAX_FILE_BYTES = 32 << 20
MAX_TOTAL_BYTES = 64 << 20
SETTINGS_FILE = "def.bin"  # the settings file of a project: a folder without it is no project
MAX_ARCHIVE_FILES = 2000

# What a file of a project is.
KIND_SETTINGS = "settings"
KIND_TABLE = "table"
KIND_SCRIPT = "script"
KIND_PROGRAM = "program"
KIND_OTHER = "other"

TABLE_NAMES = ("ftab.txt", "ptab.txt", "fptab.txt", "signadr.lst", "kstab.txt", "kstab2.txt", "diagnose.txt")
SCRIPT_COMMANDS = ("confcan", "confdia", "confpdl", "confpro", "confpdm", "clr")

# NAME Vnn.n DD.MM.YYYY HH:MM 3EGM<6 digits><letter><4 digits> AUTHOR    (the line that a table or a script carries as its version)
VERSION_LINE = re.compile(
    r"^\W*([A-Za-z0-9_]{3,12})\s+V(\d+\.\d+)\s+(\d\d\.\d\d\.\d{4})\s+(\d\d:\d\d)\s+3EGM(\d{6})([A-Z])(\d{4})\s*(.*?)\s*#?\s*$", re.M
)


class VersionError(ValueError):
    """The files cannot be a version. The reason is a code with its values (the model translates it): ``no_files``, ``no_settings``,
    ``too_big``, ``file_too_big``, ``name_clash``, ``bad_name``, ``bad_archive``, ``too_many_files``."""

    def __init__(self, code, **values):
        super().__init__(code)
        self.code = code
        self.values = values


@dataclass
class FileInfo:
    """What is known about one file of a version."""

    name: str
    size: int
    sha256: str
    kind: str = KIND_OTHER
    command: str = ""  # of a script: confcan, confdia ...
    line_name: str = ""  # the version line of a table or a script
    line_version: str = ""
    line_date: str = ""
    line_document: str = ""  # the six digits
    line_letter: str = ""
    line_author: str = ""
    content: bytes = field(default=b"", repr=False)


@dataclass
class VersionInfo:
    checksum: str
    files: list
    size: int
    expected_document: str = ""
    expected_names: str = ""


def is_excluded(name):
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return bool(extension) and extension in EXCLUDED_EXTENSIONS


def checksum(files):
    """The name of a version: SHA-256 over the files sorted by lower-case name, for each its lower-case name, a zero byte and the 32 bytes
    of the SHA-256 of its content. ``files`` is ``[(name, sha256_hex)]``."""
    digest = hashlib.sha256()
    for name, sha in sorted(files, key=lambda item: item[0].lower()):
        digest.update(name.lower().encode("utf-8"))
        digest.update(b"\x00")
        digest.update(bytes.fromhex(sha))
    return digest.hexdigest()


def parse_version_line(text):
    """The version line in the first lines of a text, as a dict, or ``None``."""
    match = VERSION_LINE.search(text[:4000])
    if not match:
        return None
    name, version, date, _time, document, letter, _number, author = match.groups()
    return {"name": name, "version": version, "date": date, "document": document, "letter": letter, "author": author.strip()}


def analyse(name, content):
    """A file of a project: its kind and, where it has one, its version line."""
    info = FileInfo(name=name, size=len(content), sha256=hashlib.sha256(content).hexdigest(), content=content)
    lower = name.lower()
    text = content[:4000].decode("latin1", "replace")
    first = text.split("\n", 1)[0].strip().lower()
    if lower == SETTINGS_FILE:
        info.kind = KIND_SETTINGS
        return info
    if content[:1] in (b"S", b"s") and re.match(rb"[Ss][0-9][0-9A-Fa-f]{2}", content[:4]):
        info.kind = KIND_PROGRAM
        return info
    if software_check.TEXT_HEADER.search(text):
        info.kind = KIND_PROGRAM
        return info
    word = first.split(" ")[0] if first else ""
    if word in SCRIPT_COMMANDS and len(first) < 40:
        info.kind = KIND_SCRIPT
        info.command = word
    elif lower in TABLE_NAMES:
        info.kind = KIND_TABLE
    line = parse_version_line(text) if info.kind in (KIND_SCRIPT, KIND_TABLE) else None
    if line:
        info.line_name, info.line_version, info.line_date = line["name"], line["version"], line["date"]
        info.line_document, info.line_letter, info.line_author = line["document"], line["letter"], line["author"]
    return info


def read_archive(content):
    """The files of a ZIP archive, ``[(name, bytes)]``: the files directly in it or in the one folder that holds all of them. Nothing is
    written anywhere; a name with a path that leaves the archive is refused."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise VersionError("bad_archive") from None
    entries = [item for item in archive.infolist() if not item.is_dir()]
    if len(entries) > MAX_ARCHIVE_FILES:
        raise VersionError("too_many_files", count=len(entries))
    paths = []
    for item in entries:
        parts = [part for part in item.filename.replace("\\", "/").split("/") if part]
        if any(part == ".." for part in parts):
            raise VersionError("bad_name", name=item.filename)
        paths.append((parts, item))
    # a folder that holds everything (the archive of a project folder) is taken away; deeper folders are not part of a version
    top = {parts[0] for parts, _item in paths if len(parts) > 1}
    strip = 1 if paths and all(len(parts) > 1 for parts, _item in paths) and len(top) == 1 else 0
    files = []
    for parts, item in paths:
        if len(parts) - strip != 1:
            continue
        if item.file_size > MAX_FILE_BYTES:
            raise VersionError("file_too_big", name=parts[-1], megabytes=MAX_FILE_BYTES >> 20)
        files.append((parts[-1], archive.read(item)))
    return files


def build(files):
    """Judge the files of a project folder and make a version of them; raise VersionError if they are none.

    ``files`` is ``[(name, bytes)]``. Files that are no definition (error data, reports ...) are left out, as the service leaves them out.
    """
    infos = []
    seen = {}
    total = 0
    for name, content in files:
        if not name or "/" in name or "\\" in name or name in (".", ".."):
            raise VersionError("bad_name", name=name)
        if is_excluded(name):
            continue
        low = name.lower()
        if low in seen:
            raise VersionError("name_clash", first=seen[low], second=name)
        seen[low] = name
        if len(content) > MAX_FILE_BYTES:
            raise VersionError("file_too_big", name=name, megabytes=MAX_FILE_BYTES >> 20)
        total += len(content)
        if total > MAX_TOTAL_BYTES:
            raise VersionError("too_big", megabytes=MAX_TOTAL_BYTES >> 20)
        infos.append(analyse(name, content))
    if not infos:
        raise VersionError("no_files")
    if SETTINGS_FILE not in seen:
        raise VersionError("no_settings")
    infos.sort(key=lambda info: info.name.lower())
    version = VersionInfo(checksum=checksum([(info.name, info.sha256) for info in infos]), files=infos, size=total)
    # the application that the tables are made for: the six digits that most of the version lines of the tables carry
    lines = [info for info in infos if info.line_document and info.line_letter == "M"]
    if lines:
        document, _count = Counter(info.line_document for info in lines).most_common(1)[0]
        names = sorted({info.line_name for info in lines if info.line_document == document})
        version.expected_document = document
        version.expected_names = ", ".join(names)
    return version
