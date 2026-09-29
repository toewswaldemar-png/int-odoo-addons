"""W-6: sender groups, practice/check split, sample, and the suggestions of the sample.

Writes /out/w6_sample.json (private: values of the user's documents; stays on Tower
and on the user's PC, never in the repository). Prints numbers only.
"""
import collections
import json
import os
import random
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date

sys.path.insert(0, "/m")
import odoo.init  # noqa: F401  Odoo's import hook, as in the server
from fm import value_suggest as vs
from fm import value_types as vt

TODAY = date(2026, 9, 29)
PRACTICE_SHARE = 0.6
SAMPLE = {"practice": 24, "check": 16}
SEED = 20260929

root = ET.parse("/m/int_filemanager_extraction_field.xml").getroot()
fields, rules = {}, {}
for rec in root.iter("record"):
    vals = {f.get("name"): (f.text or f.get("ref")) for f in rec.iter("field")}
    if rec.get("model") == "int_filemanager.extraction_field":
        fields[rec.get("id")] = vals
    else:
        rules[vals["field_id"]] = vals
specs, names, types = [], {}, {}
for i, (fid, f) in enumerate(fields.items(), 1):
    r = rules[fid]
    names[i], types[i] = f["name"], f["value_type"]
    if r.get("mode") == "regex":
        specs.append(vs.FieldSpec(i, f["value_type"], unit=f.get("unit"),
                                  patterns=[(i, re.compile(r["pattern"], re.I), 0)]))
    else:
        specs.append(vs.FieldSpec(i, f["value_type"], r["keywords"].splitlines(),
                                  f.get("unit"), rule_id=i))

index = json.load(open("/w/index.json", encoding="utf-8"))


# An IBAN printed on many documents is the owner's own account (direct debits),
# not a sender; it would put unrelated senders into one group.
iban_docs = collections.Counter()
for entry in index:
    text = json.load(open(f"/w/{entry['n']:04d}.json", encoding="utf-8"))["text"]
    iban_docs.update({c.value["value_text"] for c in vt.find("iban", text, today=TODAY)})
OWN_IBANS = {iban for iban, n in iban_docs.items() if n >= 20}


def sender_key(text, path):
    """Who sent a document: VAT number, else IBAN, else mail domain, else its folder."""
    for c in vt.find("vat", text, today=TODAY):
        return f"vat:{c.value['value_text']}"
    for c in vt.find("iban", text, today=TODAY):
        if c.value["value_text"] not in OWN_IBANS:
            return f"iban:{c.value['value_text']}"
    for c in vt.find("email", text, today=TODAY):
        return "mail:" + c.value["value_text"].rsplit("@", 1)[1]
    return "folder:" + os.path.dirname(path)


docs = []
for entry in index:
    data = json.load(open(f"/w/{entry['n']:04d}.json", encoding="utf-8"))
    docs.append({"n": entry["n"], "path": entry["path"], "ocr": entry["ocr"],
                 "sender": sender_key(data["text"], entry["path"]), "data": data})

groups = sorted({d["sender"] for d in docs})
rng = random.Random(SEED)
rng.shuffle(groups)
cut = round(len(groups) * PRACTICE_SHARE)
part_of = {g: ("practice" if i < cut else "check") for i, g in enumerate(groups)}

for d in docs:
    page = vs.Page(d["data"]["text"], d["data"]["words"])
    found, unassigned = vs.suggest(page, specs, today=TODAY)
    d["suggestions"] = {
        names[fid]: [
            {"text": s.source_text, "value": s.value["value_text"], "label": s.label,
             "direction": s.direction, "tier": s.tier, "page": s.box[0] if s.box else 0}
            for s in sug
        ]
        for fid, sug in found.items()
    }
    d["unassigned"] = unassigned
    del d["data"]

# Once drawn, the sample and the split stay as they are: new fields or rules must not
# swap the documents under review.
frozen = None
if os.path.exists("/out/w6_sample.json"):
    frozen = json.load(open("/out/w6_sample.json", encoding="utf-8"))
if frozen:
    part_of = frozen["split"]
    by_n = {d["n"]: d for d in docs}
    sample = []
    for old in frozen["documents"]:
        d = by_n[old["n"]]
        d["part"] = old["part"]
        sample.append(d)
    eligible = sample
    groups = sorted(part_of)
else:
    sample = None

# Documents worth checking: at least two fields besides the mail address.
if sample is None:
    eligible = [d for d in docs if len([f for f in d["suggestions"] if f != "Email"]) >= 2]
    sample = []
for part, size in (SAMPLE.items() if not frozen else ()):
    by_group = collections.defaultdict(list)
    for d in eligible:
        if part_of[d["sender"]] == part:
            by_group[d["sender"]].append(d)
    order = sorted(by_group)
    rng.shuffle(order)
    taken = []
    # One document per sender first, then a second one, until the part is full.
    for round_ in range(3):
        for g in order:
            if len(taken) < size and len(by_group[g]) > round_:
                taken.append(by_group[g][round_])
    for d in taken:
        d["part"] = part
    sample += taken

out = {"fields": [{"name": names[i], "type": types[i]} for i in names],
       "documents": sample,
       "split": {g: part_of[g] for g in groups}}
json.dump(out, open("/out/w6_sample.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1,
          default=str)
parts = collections.Counter(part_of.values())
print(f"{len(docs)} Dokumente, {len(groups)} Absender-Gruppen: Übung {parts['practice']}, Prüf {parts['check']}")
kinds = collections.Counter(g.split(":")[0] for g in groups)
print("Absender erkannt über:", dict(kinds), "- übergangene häufige IBANs:", len(OWN_IBANS))
print(f"geeignet (>= 2 Felder): {len(eligible)}; Stichprobe: "
      + ", ".join(f"{p} {sum(d['part'] == p for d in sample)}" for p in SAMPLE))
print("Absender in der Stichprobe:", len({d['sender'] for d in sample}))
