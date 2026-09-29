"""Compare the scanner's own text layer with --redo-ocr and --force-ocr (numbers only)."""
import os
import re
import subprocess
import sys
import tempfile
import time

import pdfplumber

ROOT = "/docs"
rows = [line.rstrip("\n").split("\t") for line in open("/out/classes.tsv")]
sample = [r for r in rows if r[0] == "scan_with_text"]
# every n-th file, so all producers are represented
step = max(1, len(sample) // int(sys.argv[1]))
sample = sample[::step][: int(sys.argv[1])]

CLEAN = re.compile(
    r"^(?:[A-Za-zÄÖÜäöüß]{2,}(?:-[A-Za-zÄÖÜäöüß]+)*|\d{1,2}\.\d{1,2}\.\d{2,4}|\d{1,3}(?:\.\d{3})*,\d{2}|\d+)[.,:;!?)]?$"
)


def words_of(path):
    with pdfplumber.open(path) as pdf:
        return [w["text"] for p in pdf.pages[:6] for w in p.extract_words()]


def score(words):
    """Share of tokens that look like real words or well-formed numbers."""
    return sum(bool(CLEAN.match(w)) for w in words) / max(len(words), 1)


def ocr(path, mode, workdir):
    out = os.path.join(workdir, mode + ".pdf")
    t = time.monotonic()
    r = subprocess.run(
        ["ocrmypdf", f"--{mode}", "-l", "deu+eng", "--output-type", "pdf", "--jobs", "4",
         "--optimize", "0", "--fast-web-view", "0", "--pages", "1-6", path, out],
        capture_output=True, timeout=900,
    )
    took = time.monotonic() - t
    if r.returncode != 0:
        return None, took, r.stderr.decode()[-120:].replace("\n", " ")
    return words_of(out), took, ""


print(f"{'#':>2} {'Hersteller':22} {'Scanner':>13} {'redo-ocr':>20} {'force-ocr':>20}")
for i, (_k, _pp, _cov, producer, rel) in enumerate(sample, 1):
    path = os.path.join(ROOT, rel)
    base = words_of(path)
    with tempfile.TemporaryDirectory() as wd:
        redo, t_redo, e_redo = ocr(path, "redo-ocr", wd)
        force, t_force, e_force = ocr(path, "force-ocr", wd)

    def cell(ws, t, e):
        if ws is None:
            return f"FEHLER {e[:12]}"
        return f"{score(ws):.2f} {len(ws):5}W {t:4.0f}s"

    print(f"{i:2} {producer[:22]:22} {score(base):.2f} {len(base):5}W "
          f"{cell(redo, t_redo, e_redo):>20} {cell(force, t_force, e_force):>20}", flush=True)
