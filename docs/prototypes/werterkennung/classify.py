"""Classify the PDFs of the test collection: digital, scan with text layer, scan without."""
import collections
import os
import sys

import pdfplumber

ROOT = sys.argv[1]
rows = []
for dirpath, _dirs, files in os.walk(ROOT):
    for name in files:
        if not name.lower().endswith(".pdf"):
            continue
        path = os.path.join(dirpath, name)
        try:
            with pdfplumber.open(path) as pdf:
                pages = pdf.pages[:5]
                chars = sum(len(p.chars) for p in pages)
                cover = []
                for p in pages:
                    area = float(p.width * p.height) or 1.0
                    best = 0.0
                    for im in p.images:
                        w = max(0.0, min(im["x1"], p.width) - max(im["x0"], 0))
                        h = max(0.0, min(im["bottom"], p.height) - max(im["top"], 0))
                        best = max(best, w * h / area)
                    cover.append(best)
                producer = (pdf.metadata.get("Producer") or "")[:30]
                n = len(pages)
        except Exception as exc:  # noqa: BLE001
            rows.append(("error", 0, 0, type(exc).__name__, os.path.relpath(path, ROOT)))
            continue
        per_page = chars / max(n, 1)
        scanned = sum(c >= 0.5 for c in cover) / max(n, 1)
        if scanned >= 0.5:
            kind = "scan_with_text" if per_page >= 20 else "scan_no_text"
        else:
            kind = "digital" if per_page >= 20 else "digital_little_text"
        rows.append((kind, round(per_page), round(max(cover), 2), producer, os.path.relpath(path, ROOT)))

count = collections.Counter(r[0] for r in rows)
print("total", len(rows), dict(count))
prod = collections.Counter((r[0], r[3]) for r in rows)
for (kind, producer), n in prod.most_common(25):
    print(f"{n:4} {kind:20} {producer}")
with open("/out/classes.tsv", "w") as f:
    for r in rows:
        f.write("\t".join(map(str, r)) + "\n")
