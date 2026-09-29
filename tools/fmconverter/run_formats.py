"""Run the converter over a folder of real test files and print what happens.

Usage (in the converter image, test folder mounted read-only):
    python run_formats.py /testdata [category ...]

The folder is the one collected from the real stock (one sub folder per category, see
its MANIFEST.tsv). Every file gets the conversions its kind of file gets in the
system (pictures: thumbnail, large preview, metadata; video the same from a frame; PDF
also text; office documents a PDF first, then the PDF's picture and text; audio the
cover and metadata; text files their text), through the same code path the service
uses (a resource-limited worker process). A table shows state, time and result size;
the exit code is 1 if a file ended differently than its category and name say it should.
"""

import os
import shutil
import sys
import time

import server
import worker

TILE = ("tile", "400x300")
PREVIEW = ("preview", "1920x1920")
TEXT = ("text", "embedded")
WORDS = ("words", "v2")
META = ("meta", "v1")
PDF = ("preview_pdf", "pdf")

# Categories whose files must all convert (unless a name says otherwise, see EXPECTED).
MUST_CONVERT = {"jpeg", "image_other", "tiff", "raw", "video", "office", "text"}
# name fragment -> expected state ("*" = anything; a set = one of these); first match wins
EXPECTED = {
    "over64mp": {"not_applicable"},
    "v1_unreadable": "*",  # v1 could not read them: whatever we do is news
    "truncated": {"failed"},
    "garbage_named": {"failed"},
    "text_named": {"failed", "not_applicable"},
    "bomb": {"not_applicable"},
    "largest__banner": "*",  # a TIFF above the size limit: refusing it is the point
    "zero_": "*",  # the system never sends an empty blob
    "encrypted": "*",
    "unreadable": "*",
    "_largest": "*",  # too big to have been copied or too big for the limits
}
# (name fragment, kind) -> expected states, checked before EXPECTED
EXPECTED_KIND = {("nocover", "tile"): {"not_applicable"}}
# Audio that lives in a "video" extension: no picture, and that is not an error.
NO_PICTURE = {"Lied f"}


def kinds_for(ext):
    """What the system asks the converter for, by the extension of the file name."""
    if ext == "pdf":
        return [TILE, PREVIEW, WORDS, META]
    if ext in worker.OFFICE_EXTENSIONS:
        return [PDF]  # the rest is taken from the PDF, see main()
    if ext in worker.AUDIO_EXTENSIONS:
        return [TILE, META]
    if ext in worker.TEXT_EXTENSIONS:
        return [TEXT]
    return [TILE, PREVIEW, META]


# Files meant to be refused as pictures: their facts (a header is enough) may still be read.
PICTURE_ONLY = ("over64mp", "truncated", "garbage_named", "bomb")


def expected(category, name, kind):
    if kind not in ("tile", "preview") and any(part in name for part in PICTURE_ONLY):
        return "*"
    for (fragment, of_kind), states in EXPECTED_KIND.items():
        if fragment in name and kind == of_kind:
            return states
    if kind in ("tile", "preview") and any(part in name for part in NO_PICTURE):
        return {"not_applicable"}
    for fragment, states in EXPECTED.items():
        if fragment in name:
            return states
    return {"done"} if category in MUST_CONVERT else "*"


def convert(path, kind, spec, ext):
    started = time.monotonic()
    state, error, _version, tool, result, workdir = server.run_worker(
        path, kind, spec, ext
    )
    size = os.path.getsize(result) if result else 0
    return state, error, tool, size, time.monotonic() - started, result, workdir


def main(root, categories):
    unexpected = 0
    tally = {}
    for category in sorted(os.listdir(root)):
        folder = os.path.join(root, category)
        if not os.path.isdir(folder) or (categories and category not in categories):
            continue
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            ext = name.rpartition(".")[2].lower() if "." in name else ""
            todo = [(path, ext, kind, spec) for kind, spec in kinds_for(ext)]
            kept = []
            while todo:
                source, source_ext, kind, spec = todo.pop(0)
                state, error, tool, size, seconds, result, workdir = convert(
                    source, kind, spec, source_ext
                )
                if kind == "preview_pdf" and state == "done":
                    # The chain: what is made from the office document is made from
                    # its PDF, which has to outlive this conversion.
                    kept.append(workdir)
                    todo += [(result, "pdf", k, s) for k, s in (TILE, PREVIEW, WORDS)]
                else:
                    shutil.rmtree(workdir, ignore_errors=True)
                want = expected(category, name, kind)
                bad = want != "*" and state not in want
                unexpected += bad
                tally[state] = tally.get(state, 0) + 1
                note = "  <-- expected " + "/".join(sorted(want)) if bad else ""
                print(
                    f"{category:11} {kind:11} {state:14} {seconds:5.1f}s {size:8} "
                    f"{(tool or ''):18} {name[:40]:40} {error[:50]}{note}",
                    flush=True,
                )
            for workdir in kept:
                shutil.rmtree(workdir, ignore_errors=True)
    print("summary:", tally, "unexpected:", unexpected)
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], set(sys.argv[2:])))
