"""W-6: checks the current suggestions of the sample against the user's answers of a round.

    python3 /m/w6_recheck.py <round> [<round> ...]

Reads /out/w6_sample.json (suggestions as w6_sample.py last computed them) and
/out/runde<N>.json (what the user marked). A field counts as right when the new best
suggestion reads as the value the user confirmed, corrected or added, and when nothing
is suggested for a value marked "not in the document". Fields the user left open are
not counted. Prints the numbers and every field whose result changed since the round;
the values appear only in that list (private: run on Tower, keep the output out of the
repository).
"""
import json
import sys
import xml.etree.ElementTree as ET
from datetime import date

sys.path.insert(0, "/m")
import odoo.init  # noqa: F401  Odoo's import hook, as in the server
from fm import value_types as vt

TODAY = date(2026, 9, 29)

units = {}
for rec in ET.parse("/m/int_filemanager_extraction_field.xml").getroot().iter("record"):
    if rec.get("model") == "int_filemanager.extraction_field":
        vals = {f.get("name"): f.text for f in rec.iter("field")}
        units[vals["name"]] = vals.get("unit")

sample = json.load(open("/out/w6_sample.json", encoding="utf-8"))
types = {f["name"]: f["type"] for f in sample["fields"]}
by_n = {d["n"]: d for d in sample["documents"]}


def read(field, text):
    """value_text of a printed or typed value, as the server would read it."""
    value_type, unit = types[field], units.get(field)
    attempts = [text]
    if value_type == "amount":
        attempts.append(f"{text} EUR")
    elif value_type == "quantity":
        attempts.append(f"{text} {unit}")
    for attempt in attempts:
        parsed = vt.parse(value_type, attempt, unit=unit, today=TODAY)
        if parsed:
            return parsed["value_text"]
    return text.strip()


totals = {"found": 0, "wrong": 0, "absent_suggested": 0, "missing": 0, "present": 0}
changes = []
for rnd in sys.argv[1:]:
    answers = json.load(open(f"/out/runde{rnd}.json", encoding="utf-8"))
    for doc in answers["documents"]:
        if doc.get("skip"):
            continue
        new = {f: s[0]["value"] for f, s in by_n[doc["n"]]["suggestions"].items()}
        truth, was_right = {}, {}
        for field, mark in doc["fields"].items():
            status = mark.get("status")
            if status == "ok":
                truth[field] = {mark["suggested"]}
                was_right[field] = True
            elif status == "wrong" and (mark.get("correct") or "").strip():
                truth[field] = {read(field, mark["correct"])}
                was_right[field] = False
            elif status == "absent":
                truth[field] = set()
                was_right[field] = False
        for added in doc["added"]:
            # A second value of a field (another mail address) is no error.
            truth.setdefault(added["field"], set()).add(read(added["field"], added["value"]))
            was_right.setdefault(added["field"], False)
        for field, values in truth.items():
            got = new.get(field)
            if values:
                totals["present"] += 1
            if got is None:
                result = "missing" if values else "right"
            elif not values:
                result = "absent_suggested"
            else:
                result = "right" if got in values else "wrong"
            if result == "right":
                totals["found"] += bool(values)
            else:
                totals[result] += 1
            if (result == "right") != was_right[field]:
                changes.append((doc["n"], field, result, got, sorted(values)))

hits = totals["found"]
suggested = hits + totals["wrong"] + totals["absent_suggested"]
print(f"Vorschläge richtig: {hits} / {suggested} = {hits / max(suggested, 1):.0%}")
print(f"Vorhandene Werte gefunden: {hits} / {totals['present']} = "
      f"{hits / max(totals['present'], 1):.0%}")
print("  falsch:", totals["wrong"], " vorgeschlagen obwohl nicht drin:",
      totals["absent_suggested"], " fehlt:", totals["missing"])
print("Geändert gegenüber der Runde (richtig <-> nicht richtig):")
for n, field, result, got, values in changes:
    print(f"  Dok {n} {field}: jetzt {result}  vorgeschlagen={got!r}  soll={values}")
