"""Run the new word extraction over the whole test collection (numbers only on stdout)."""
import collections
import json
import os
import re
import time

import worker

ROOT, OUT = "/docs", "/out"
CLEAN = re.compile(
    r"^(?:[A-Za-zÄÖÜäöüß]{2,}(?:-[A-Za-zÄÖÜäöüß]+)*|\d{1,2}\.\d{1,2}\.\d{2,4}"
    r"|\d{1,3}(?:\.\d{3})*,\d{2}|\d+)[.,:;!?)]?$"
)


def score(text):
    tokens = text.split()
    return sum(bool(CLEAN.match(t)) for t in tokens) / max(len(tokens), 1), len(tokens)


paths = []
for dirpath, _dirs, files in os.walk(ROOT):
    paths += [os.path.join(dirpath, f) for f in files if f.lower().endswith(".pdf")]
paths.sort()
index, modes, errors, bad_ranges = [], collections.Counter(), 0, 0
before_after = collections.defaultdict(list)
started = time.monotonic()
for n, path in enumerate(paths, 1):
    out = os.path.join(OUT, f"{n:04d}.json")
    t = time.monotonic()
    try:
        _pages, own_text, _w, _s = worker._read_pdf(path)
        tool = worker.make_words(path, "pdf", out)
        with open(out) as f:
            result = json.load(f)
    except Exception as exc:  # noqa: BLE001
        errors += 1
        index.append({"n": n, "path": os.path.relpath(path, ROOT), "error": f"{type(exc).__name__}: {exc}"[:200]})
        print(f"{n:4} FEHLER {type(exc).__name__}", flush=True)
        continue
    took = time.monotonic() - t
    text = result["text"]
    for entry in result["words"]:
        piece = text[entry[5]:entry[6]]
        if not piece or any(c in piece for c in " \t\n\f"):
            bad_ranges += 1
    modes[result["ocr"]] += 1
    if result["ocr"] == "redo-ocr" or tool == "ocrmypdf+pdfplumber" and own_text.strip():
        before_after[result["ocr"]].append((score(own_text)[0], score(text)[0]))
    index.append({"n": n, "path": os.path.relpath(path, ROOT), "ocr": result["ocr"],
                  "tool": tool, "seconds": round(took, 1), "pages": len(result["pages"]),
                  "words": len(result["words"])})
    if n % 25 == 0:
        print(f"{n:4}/{len(paths)} {time.monotonic() - started:6.0f}s {dict(modes)}", flush=True)

with open(os.path.join(OUT, "index.json"), "w") as f:
    json.dump(index, f, ensure_ascii=False, indent=0)
print("fertig", len(paths), "Dateien in", round(time.monotonic() - started), "s")
print("Modus", dict(modes), "Fehler", errors, "kaputte Zeichenbereiche", bad_ranges)
for mode, pairs in before_after.items():
    better = sum(a > b + 0.02 for b, a in pairs)
    worse = sum(a < b - 0.02 for b, a in pairs)
    avg_b = sum(b for b, _ in pairs) / len(pairs)
    avg_a = sum(a for _, a in pairs) / len(pairs)
    print(f"{mode}: {len(pairs)} Dokumente, sauber vorher {avg_b:.2f} -> nachher {avg_a:.2f}, besser {better}, schlechter {worse}")
slow = sorted((e for e in index if "seconds" in e), key=lambda e: -e["seconds"])[:5]
print("langsamste:", [(e["seconds"], e["pages"], e["ocr"]) for e in slow])
