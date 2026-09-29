import json, re, sys, stdnum.eu.vat, stdnum.iban, stdnum.eu.at_02

NUM = r"(?=[A-Za-z0-9\-/.]*\d)[A-Za-z0-9][A-Za-z0-9\-/.]*[A-Za-z0-9]"
# numbers printed in groups: "6 357 507 591", "44 450 7-5 148 621"
SPACED = r"\d{1,4}(?:-\d{1,4})?(?:\s\d{1,4}(?:-\d{1,4})?){1,6}(?![\d,])"
DATE = r"\d{1,2}\.\d{1,2}\.\d{2,4}"
EUR = r"(?:€|EUR)(?:/Monat)?"
CT = r"(?:ct|Cent)/kWh"
TYPES = {
    "Nummer": rf"{SPACED}|{NUM}",
    "Datum": DATE,
    # unit before or after the number
    "Betrag": rf"(?:{EUR}\s+)?-?\d{{1,3}}(?:\.\d{{3}})*,\d{{2}}(?:\s?{EUR})?",
    "ct/kWh": rf"(?:{CT}\s+)?\d+,\d+(?:\s?{CT})?",
    "kWh": r"\d[\d.]*(?:,\d+)?\s?kWh",
    "Zeitraum": rf"{DATE}\s?(?:bis|-|–)\s?{DATE}",
    "Dauer": r"\d+\s(?:Monate|Monaten|Tage|Tagen|Wochen|Jahre|Jahren)",
}
TYPES["ZeitraumOderDauer"] = TYPES["Zeitraum"] + "|" + TYPES["Dauer"]

FIELDS = [
    ("Rechnungsnummer", "Nummer", ["Rechnungsnummer", "Rechnungsnr.", "Rechnungs-Nr.", "Belegnummer", "Beleg-Nr."]),
    ("Kundennummer", "Nummer", ["Kundennummer", "Geschäftspartnernummer", "Kunden-Nr.", "Kundennr.", "Kund*innennummer", "Kd.-Nr."]),
    ("Vertragsnummer", "Nummer", ["Vertragsnummer", "Vertragskonto", "Vertrags-Nr.", "Vertragskontonummer"]),
    ("Dokumentdatum", "Datum", ["Rechnungsdatum", "Datum", "Bescheiddatum"]),
    ("Gesamtbetrag", "Betrag", ["Gesamtbetrag", "Rechnungsbetrag", "Einzugsbetrag", "zu zahlender Betrag", "Endbetrag"]),
    ("Fällig am", "Datum", ["fällig am", "Fälligkeit", "zahlbar bis", "buchen wir am"]),
    ("Mandatsreferenz", "Nummer", ["Mandatsreferenz", "Mandats-ID", "Mandatsnummer"]),
    ("Zählernummer", "Nummer", ["Zählernummer", "Zähler-Nr.", "Zählernr."]),
    ("Zählerstand", "kWh", ["Zählerstand"]),
    ("Abschlag", "Betrag", ["Abschlagshöhe", "Abschlag", "Abschlagsbetrag"]),
    ("Grundpreis", "Betrag", ["Grundpreis"]),
    ("Arbeitspreis", "ct/kWh", ["Arbeitspreis", "Verbrauchspreis"]),
    ("Jahresverbrauch", "kWh", ["Jahresverbrauch", "Verbrauch"]),
    ("Lieferbeginn", "Datum", ["Lieferbeginn", "Belieferungsstart", "Lieferstart", "Vertragsbeginn"]),
    ("Preisgarantie", "ZeitraumOderDauer", ["Preisgarantie"]),
    ("Abrechnungszeitraum", "Zeitraum", ["Abrechnungszeitraum", "Leistungszeitraum", "Zeitraum"]),
    ("Mindestlaufzeit", "Dauer", ["Mindestvertragslaufzeit", "Mindestlaufzeit", "Laufzeit"]),
    ("Kündigungsfrist", "Dauer", ["Kündigungsfrist"]),
]

d = json.load(open(sys.argv[1]))
words, text = d["words"], d["text"]


def norm(s):
    return s.lower().rstrip(":")


def mode_a(kind, kws):
    for kw in kws:
        k = r"\s+".join(re.escape(p) for p in kw.split())
        for m in re.finditer(rf"(?<!\w){k}:?((?:\s+\S+){{0,6}})", text, re.I):
            v = re.search(TYPES[kind], m.group(1))
            if v:
                return v.group(0)
    return None


def find_kw(kw):
    parts = [norm(p) for p in kw.split()]
    for i in range(len(words) - len(parts) + 1):
        if all(norm(words[i + j]["text"]) == parts[j] for j in range(len(parts))):
            ws = words[i:i + len(parts)]
            yield {"page": ws[0]["page"], "x0": ws[0]["x0"], "x1": ws[-1]["x1"],
                   "top": ws[0]["top"], "bottom": ws[-1]["bottom"]}


def line_text(ws):
    """Words of one line; a wide gap (a column boundary) becomes a separator a value cannot cross."""
    out, prev = [], None
    for w in sorted(ws, key=lambda w: w["x0"]):
        if prev is not None:
            out.append(" | " if w["x0"] - prev["x1"] > 12 else " ")
        out.append(w["text"])
        prev = w
    return "".join(out)


def mode_b(kind, kws):
    for kw in kws:
        for k in find_kw(kw):
            same = sorted([w for w in words if w["page"] == k["page"] and abs(w["top"] - k["top"]) < 3
                           and w["x0"] > k["x1"]], key=lambda w: w["x0"])
            m = re.search(TYPES[kind], line_text(same[:5])) if same else None
            if m:
                return m.group(0)
            below = [w for w in words if w["page"] == k["page"] and k["bottom"] < w["top"] < k["bottom"] + 22
                     and w["x0"] < k["x1"] + 5 and w["x1"] > k["x0"] - 5]
            if below:
                top = min(w["top"] for w in below)
                row = [w for w in words if w["page"] == k["page"] and abs(w["top"] - top) < 3
                       and k["x0"] - 5 <= w["x0"] < k["x0"] + 170]
                m = re.match(TYPES[kind], line_text(row))
                if m:
                    return m.group(0)
    return None


for name, kind, kws in FIELDS:
    b = mode_b(kind, kws)
    a = mode_a(kind, kws)
    print(f"{name:20} {str(b or a):28} (B={b} | A={a})")
print("-- Prüfziffern")
for m in re.finditer(r"(?:U[Ss]t|Umsatzsteuer)[-.\s]?I[Dd][-.\w]*\s*(?:Nr\.?|Nummer)?:?\s*([A-Z]{2}\s?[\d\s]{9,12})", text):
    c = m.group(1).replace(" ", "")
    print("USt-IdNr.", c, "gültig" if stdnum.eu.vat.is_valid(c) else "ungültig")
for m in re.finditer(r"Gläubiger-?I[Dd]:?\s*(\S+)", text):
    print("Gläubiger-ID", m.group(1), "gültig" if stdnum.eu.at_02.is_valid(m.group(1)) else "Prüfziffer falsch")
