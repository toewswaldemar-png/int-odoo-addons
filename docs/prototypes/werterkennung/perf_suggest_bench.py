import json, random, sys, time, tracemalloc
sys.path.insert(0, "/tmp/pkg")
from fmv import value_suggest as vs

random.seed(1)
LABELS = ["Rechnungsnummer", "Rechnungsdatum", "Gesamtbetrag", "Fälligkeit", "IBAN", "USt-IdNr.", "Kundennummer", "Leistungszeitraum", "Verbrauch"]
FILL = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore".split()

def make(pages, lines=45):
    text, words = [], []
    pos = 0
    for p in range(1, pages + 1):
        for ln in range(lines):
            top = 60 + ln * 14
            parts = []
            r = random.random()
            if r < 0.08:
                lab = random.choice(LABELS)
                val = random.choice(["%05d/%d" % (random.randint(1, 99999), 2025), "%02d.%02d.2025" % (random.randint(1, 28), random.randint(1, 12)), "%d,%02d EUR" % (random.randint(1, 9999), random.randint(0, 99)), "DE89370400440532013000", "DE123456789", "%d kWh" % random.randint(10, 9000)])
                parts = [lab + ":", "\t", val]
            else:
                parts = [random.choice(FILL) for _ in range(random.randint(6, 12))]
            x = 50.0
            line = []
            for w in parts:
                if w == "\t":
                    line.append(w); x += 60; continue
                line.append(w)
            # build text with positions
            buf = ""
            first = True
            for w in line:
                if w == "\t":
                    buf += "\t"; first = True; continue
                if not first:
                    buf += " "
                start = pos + len(buf)
                buf += w
                words.append([p, x, float(top), x + 6 * len(w), float(top + 10), start, start + len(w)])
                x += 6 * len(w) + 4
                first = False
            text.append(buf)
            pos += len(buf) + 1
            text.append("\n")
            pos += 0
        # replace last newline of page by form feed
        text[-1] = "\f"
    return "".join(text), words

def specs():
    S = vs.FieldSpec
    return [
        S(1, "number", keywords=["Rechnungsnummer", "Kundennummer"]),
        S(2, "date", keywords=["Rechnungsdatum", "Fälligkeit"]),
        S(3, "amount", keywords=["Gesamtbetrag", "Betrag"]),
        S(4, "iban", keywords=["IBAN"]),
        S(5, "vat", keywords=["USt-IdNr."]),
        S(6, "period", keywords=["Leistungszeitraum"]),
        S(7, "quantity", keywords=["Verbrauch"], unit="kWh"),
        S(8, "email", keywords=["E-Mail"]),
    ]

for pages in [int(a) for a in sys.argv[1:]]:
    text, words = make(pages)
    blob = json.dumps({"version": 2, "pages": [{"width": 595, "height": 842, "rotation": 0}] * pages, "text": text, "words": words})
    tracemalloc.start()
    t0 = time.perf_counter()
    d = json.loads(blob)
    t1 = time.perf_counter()
    page = vs.Page(d["text"], d["words"], d["pages"])
    t2 = time.perf_counter()
    sug, un = vs.suggest(page, specs(), currencies=None) if False else (None, None)
    try:
        sug, un = vs.suggest(page, specs())
    except TypeError as e:
        print("suggest error", e); raise
    t3 = time.perf_counter()
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    found = sum(len(v) for v in sug.values())
    print(f"pages={pages:5d} words={len(words):7d} json={len(blob)/1e6:6.2f}MB load={t1-t0:6.3f}s Page={t2-t1:6.3f}s suggest={t3-t2:7.3f}s peak={peak/1e6:7.1f}MB found={found} unassigned={len(un)}", flush=True)
