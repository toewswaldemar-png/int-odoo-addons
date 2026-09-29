"""W-4 over the collection: errors, time, and how often each field gets a suggestion.

Numbers only - no values, labels or file names are printed.
"""
import collections
import glob
import json
import re
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import date

sys.path.insert(0, "/m")
import odoo.init  # noqa: F401  Odoo's import hook, as in the server
from fm import value_suggest as vs

root = ET.parse("/m/int_filemanager_extraction_field.xml").getroot()
fields, rules = {}, {}
for rec in root.iter("record"):
    vals = {f.get("name"): (f.text or f.get("ref")) for f in rec.iter("field")}
    if rec.get("model") == "int_filemanager.extraction_field":
        fields[rec.get("id")] = vals
    else:
        rules[vals["field_id"]] = vals
specs, names = [], {}
for i, (fid, f) in enumerate(fields.items(), 1):
    r = rules[fid]
    names[i] = f["name"]
    if r.get("mode") == "regex":
        specs.append(vs.FieldSpec(i, f["value_type"], unit=f.get("unit"),
                                  patterns=[(i, re.compile(r["pattern"], re.I), 0)]))
    else:
        specs.append(vs.FieldSpec(i, f["value_type"], r["keywords"].splitlines(),
                                  f.get("unit"), rule_id=i))

per_field = collections.Counter()
tiers = collections.defaultdict(collections.Counter)
directions = collections.defaultdict(collections.Counter)
times, errors, docs, unassigned = [], 0, 0, 0
for path in sorted(glob.glob("/w/[0-9]*.json")):
    data = json.load(open(path, encoding="utf-8"))
    docs += 1
    started = time.perf_counter()
    try:
        page = vs.Page(data["text"], data["words"])
        found, free = vs.suggest(page, specs, today=date(2026, 9, 29))
    except Exception:
        errors += 1
        traceback.print_exc(limit=3)
        continue
    times.append((time.perf_counter() - started, len(data["words"])))
    unassigned += len(free)
    for field_id, suggestions in found.items():
        per_field[field_id] += 1
        tiers[field_id][suggestions[0].tier] += 1
        directions[field_id][suggestions[0].direction] += 1

times.sort()
print(f"{docs} Dokumente, Fehler {errors}")
print(f"Zeit: Median {times[len(times) // 2][0]:.3f} s, max {times[-1][0]:.2f} s "
      f"({times[-1][1]} Wörter)")
print(f"nicht zugeordnete Paare im Schnitt: {unassigned / max(docs, 1):.1f}")
tier_names = {0: "gelernt", 1: "exakt", 2: "enthalten", 3: "unscharf", 4: "ohne Beschriftung"}
for i, name in names.items():
    t = ", ".join(f"{tier_names[k]} {v}" for k, v in sorted(tiers[i].items()))
    d = ", ".join(f"{k} {v}" for k, v in directions[i].most_common())
    print(f"{name:22} {per_field[i]:4} Dok.  [{t}]  [{d}]")
