"""A ZIP of files, written as a stream.

Pure Python, no Odoo: it knows files and names, not records or rights. The caller makes the list
of entries (name in the archive, path of the file, size, date) and passes it on. An entry whose
name ends with a slash is a folder: it has no file (``path`` is ``None``) and no bytes, and shows
a folder that has nothing in it.

The archive is stored (``ZIP_STORED``): the files of the filemanager are mostly PDF, pictures and
Office files, which do not shrink. So its length is known before the first byte: ``zip_length``
gives it exactly (checked against the real writer, also above 2 GiB and with more than 65535
entries), and the answer can carry a ``Content-Length``. Without it a stream that breaks off
cannot be told from one that is complete, if the server closes the connection to end it.
"""

import datetime
import os
import re
import unicodedata
import zipfile
from typing import NamedTuple

# Bytes read from a file and handed on at a time.
CHUNK_SIZE = 1024 * 1024
# The longest name of one file in the archive (Windows allows 255 characters per name).
NAME_MAX_LENGTH = 255
# Python's limit: a file above this size (or a bit less, the writer plans 5% for what a stream
# cannot know) needs the ZIP64 fields, and so does an archive that grows beyond it.
ZIP64_LIMIT = (1 << 31) - 1
ZIP64_ENTRIES = 0xFFFF
# A ZIP knows no date before 1980.
EARLIEST_DATE = (1980, 1, 1, 0, 0, 0)
# Characters that Windows does not allow in a name (the slashes and control characters are
# dropped), and the names that it reserves for devices, with or without an extension.
WINDOWS_CHARACTERS = re.compile(r'[:?*"<>|]')
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
EMPTY_NAME = "file"


class ZipEntry(NamedTuple):
    """A file in the archive: its name there, where it is, how big, and its date.

    A folder is an entry with a name that ends with ``/``, no path and the size 0.
    """

    name: str
    path: str | None
    size: int
    date: datetime.date


def folder_entry(name, date):
    return ZipEntry(f"{name}/", None, 0, date)


def export_name(name):
    """Return the name of a file as it goes into the archive: one that opens everywhere.

    The name is in the composed Unicode form (a ZIP made on a Mac holds the decomposed one),
    without slash and control character, with the characters of Windows made ``_``, without
    space or dot at the end, without device name, and no longer than Windows allows with the
    extension kept. The stored name of the document does not change.
    """
    name = unicodedata.normalize("NFC", name)
    name = "".join(char for char in name if unicodedata.category(char) != "Cc" and char not in "/\\")
    name = WINDOWS_CHARACTERS.sub("_", name).strip().rstrip(" .")
    if not name:
        return EMPTY_NAME
    if name.split(".")[0].upper() in RESERVED_NAMES:
        name = f"_{name}"
    return _shortened(name, NAME_MAX_LENGTH)


def _shortened(name, length):
    if len(name) <= length:
        return name
    stem, extension = os.path.splitext(name)
    if len(extension) > length // 2:  # not an extension but a long tail
        stem, extension = name, ""
    return stem[: length - len(extension)] + extension


def export_names(items, taken=(), folders=False):
    """Return ``{key: name in the archive}`` for ``(key, name)`` pairs, all names different.

    Names that are equal after the cleaning (case aside, as Windows and macOS see them) get a
    number: ``a.txt``, ``a (2).txt``. The pairs are taken in the order of their keys, so the
    same files always give the same names. ``taken`` are names (in lower case) that are in use
    already, in the same folder of the archive. The name of a folder has no extension to keep:
    ``v1.2`` becomes ``v1.2 (2)``, not ``v1 (2).2``.
    """
    taken = set(taken)
    result = {}
    for key, name in sorted(items, key=lambda item: item[0]):
        clean = export_name(name)
        stem, extension = (clean, "") if folders else os.path.splitext(clean)
        candidate, number = clean, 1
        while candidate.lower() in taken:
            number += 1
            suffix = f" ({number})"
            candidate = _shortened(stem, NAME_MAX_LENGTH - len(extension) - len(suffix)) + suffix + extension
        taken.add(candidate.lower())
        result[key] = candidate
    return result


def date_time(date):
    """Return the date of a ZIP entry (a tuple) from a ``datetime`` or a ``date``, not before 1980.
    """
    if not isinstance(date, datetime.datetime):
        date = datetime.datetime.combine(date, datetime.time())
    return max(date.timetuple()[:6], EARLIEST_DATE)


def zip_length(entries):
    """Return the exact number of bytes of the archive that ``zip_chunks`` writes for these entries.
    """
    total = central = 0
    for name, _path, size, _date in entries:
        name_length = len(name.encode())
        if name.endswith("/"):  # a folder: the header and the data descriptor of an empty file
            extra = [total] if total > ZIP64_LIMIT else []
            central += 46 + name_length + (4 + 8 * len(extra) if extra else 0)
            total += 30 + name_length + 16
            continue
        # The writer cannot go back in a stream: the sizes follow the data (a data descriptor).
        zip64_file = size * 1.05 > ZIP64_LIMIT
        record = 30 + name_length + (20 if zip64_file else 0) + size + (24 if zip64_file else 16)
        extra = []
        if size > ZIP64_LIMIT:
            extra += [size, size]
        if total > ZIP64_LIMIT:
            extra.append(total)
        central += 46 + name_length + (4 + 8 * len(extra) if extra else 0)
        total += record
    end = 22
    if len(entries) > ZIP64_ENTRIES or total > ZIP64_LIMIT or central > ZIP64_LIMIT:
        end += 56 + 20
    return total + central + end


class _Sink:
    """What the ZIP writer writes to: it cannot seek, so it writes forward only."""

    def __init__(self):
        self.chunks = []

    def write(self, data):
        self.chunks.append(bytes(data))
        return len(data)

    def flush(self):
        pass

    def take(self):
        chunks, self.chunks = self.chunks, []
        return chunks


def zip_chunks(entries):
    """Yield the bytes of the archive, a piece at a time.

    A file that is not as big as its entry says (it changed, or it is gone) breaks the stream:
    an archive that does not fit the length that was announced must not look complete.
    """
    sink = _Sink()
    archive = zipfile.ZipFile(sink, "w", zipfile.ZIP_STORED, allowZip64=True)
    for name, path, size, date in entries:
        info = zipfile.ZipInfo(name, date_time(date))
        info.compress_type = zipfile.ZIP_STORED
        if path is None:
            # An empty file with a name that ends with a slash. ``ZipFile.mkdir`` would do the same
            # without the data descriptor, but it is new in Python 3.11 and Odoo 19 runs on 3.10.
            info.external_attr = (0o40755 << 16) | 0x10  # a folder, for Unix and for DOS
            with archive.open(info, "w"):
                pass
            yield from sink.take()
            continue
        info.file_size = size  # the writer decides on ZIP64 from it, in a stream it cannot wait
        done = 0
        with open(path, "rb") as source, archive.open(info, "w") as target:
            while block := source.read(CHUNK_SIZE):
                done += len(block)
                if done > size:
                    break
                target.write(block)
                yield from sink.take()
        if done != size:
            raise OSError(f"{path} has {done} bytes, the entry {name} was made for {size}")
        yield from sink.take()
    archive.close()
    yield from sink.take()
