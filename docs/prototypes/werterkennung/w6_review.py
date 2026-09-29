"""Builds a local review page (never published) for one round of W-6.

    py w6_review.py <w6_sample.json> <round> <first> <count> [practice|check]
    e.g. py w6_review.py %TEMP%/w6_sample.json 2 10 10

The sample (and every result) holds values of private documents: fetch it from
Tower (/mnt/user/test/werterkennung_w6/w6_sample.json) into a temporary folder, not
into the repository. The page is written next to the sample and shows the originals
from BASE; "Ergebnis speichern" downloads werterkennung_runde<round>.json, which goes
back to Tower as runde<round>.json.
"""
import json
import os
import sys
import urllib.parse

BASE = "G:/Meine Ablage/Privat"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

sample_path = sys.argv[1]
rnd, first, count = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
part = sys.argv[5] if len(sys.argv) > 5 else "practice"
HERE = os.path.dirname(os.path.abspath(sample_path))
sample = json.load(open(sample_path, encoding="utf-8"))
german = json.load(open(f"{REPO}/tools/v2check/i18n_de.json", encoding="utf-8"))
docs = [d for d in sample["documents"] if d["part"] == part][first : first + count]
fields = [
    {"name": f["name"], "label": german.get(f["name"], f["name"]), "type": f["type"]}
    for f in sample["fields"]
]
for d in docs:
    d["url"] = "file:///" + urllib.parse.quote(f"{BASE}/{d['path']}")
    d.pop("sender", None)

page = """<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Werterkennung – Runde @@NUM@@</title>
<style>
:root{--bg:#f6f6f4;--card:#fff;--ink:#1d1d1b;--muted:#6b6b66;--line:#ddd;--ok:#1f7a3a;--bad:#b3261e;--no:#7a5b00;--sel:#e8f0fe}
*{box-sizing:border-box}body{margin:0;font:14px/1.4 system-ui,sans-serif;background:var(--bg);color:var(--ink)}
.wrap{display:grid;grid-template-columns:1fr 520px;height:100vh}
iframe{width:100%;height:100%;border:0;background:#888}
.side{overflow:auto;padding:14px 16px;border-left:1px solid var(--line);background:var(--card)}
h1{font-size:16px;margin:0 0 4px}.path{color:var(--muted);font-size:12px;word-break:break-all}
.nav{display:flex;gap:8px;align-items:center;margin:10px 0}
button{font:inherit;padding:5px 10px;border:1px solid var(--line);border-radius:6px;background:#fff;cursor:pointer}
button.on.ok{background:var(--ok);color:#fff;border-color:var(--ok)}button.on.bad{background:var(--bad);color:#fff;border-color:var(--bad)}
button.on.no{background:var(--no);color:#fff;border-color:var(--no)}
.field{border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin:8px 0}
.field .name{font-weight:600}.val{font-size:15px;margin:3px 0}.small{color:var(--muted);font-size:12px}
.row{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}input,select{font:inherit;padding:4px 6px;border:1px solid var(--line);border-radius:6px}
input.correct{width:100%;margin-top:6px}.hint{background:#fffbe6;border:1px solid #f1e3a6;border-radius:8px;padding:8px 10px;font-size:13px}
.done{color:var(--ok);font-weight:600}.todo{color:var(--bad)}
</style></head><body>
<div class="wrap"><iframe id="pdf"></iframe><div class="side">
<div class="hint">Links das Dokument. Rechts je Feld: <b>✓</b> Vorschlag stimmt, <b>✗</b> falsch (dann den richtigen Wert so eintragen, wie er im Dokument steht), <b>steht nicht drin</b> wenn das Dokument diesen Wert gar nicht enthält. Unten fehlende Werte ergänzen. Zum Schluss <b>Ergebnis speichern</b> – die Datei landet in „Downloads“.</div>
<div class="nav"><button id="prev">◀ Zurück</button><span id="pos"></span><button id="next">Weiter ▶</button>
<span style="flex:1"></span><button id="save">Ergebnis speichern</button></div>
<h1 id="title"></h1><div class="path" id="path"></div>
<div class="small"><a id="open" target="_blank">PDF in neuem Tab öffnen</a> · <label><input type="checkbox" id="skip"> Dokument überspringen (ungeeignet)</label></div>
<div id="fields"></div>
<h1 style="margin-top:16px">Fehlt ein Wert?</h1>
<div class="small">Ein Wert, der im Dokument steht, aber oben nicht vorgeschlagen wurde – auch ein zweiter Wert zu einem Feld oben (z. B. eine weitere E-Mail-Adresse).</div>
<div id="added"></div>
<div class="row"><select id="addField"></select><input id="addValue" placeholder="Wert wie im Dokument"><button id="add">Hinzufügen</button></div>
<div class="small" style="margin-top:12px">Notiz zum Dokument (optional)</div><input id="note" style="width:100%">
<p id="status" class="small"></p>
</div></div>
<script>
const ROUND = @@NUM@@, DOCS = @@DOCS@@, FIELDS = @@FIELDS@@;
const KEY = "w6_round_" + ROUND;
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
let i = 0;
const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const label = n => esc((FIELDS.find(f => f.name === n) || {label: n}).label);
const ds = d => state[d.n] || (state[d.n] = {path: d.path, part: d.part, fields: {}, added: [], note: "", skip: false});
function persist() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} progress(); }
function progress() {
  const open = DOCS.filter(d => { const s = ds(d); return !s.skip && Object.keys(d.suggestions).some(f => !(s.fields[f] || {}).status); }).length;
  document.getElementById("status").innerHTML = open ? `<span class="todo">Noch ${open} Dokument(e) mit offenen Feldern.</span>` : `<span class="done">Alle Dokumente dieser Runde bearbeitet – bitte „Ergebnis speichern“.</span>`;
}
function show() {
  const d = DOCS[i], s = ds(d);
  document.getElementById("pdf").src = d.url;
  document.getElementById("open").href = d.url;
  document.getElementById("title").textContent = `Dokument ${i + 1} von ${DOCS.length}`;
  document.getElementById("path").textContent = d.path;
  document.getElementById("pos").textContent = `${i + 1} / ${DOCS.length}`;
  document.getElementById("skip").checked = s.skip;
  document.getElementById("note").value = s.note;
  const box = document.getElementById("fields"); box.innerHTML = "";
  for (const [name, sug] of Object.entries(d.suggestions)) {
    const f = s.fields[name] || (s.fields[name] = {suggested: sug[0].value, printed: sug[0].text});
    const el = document.createElement("div"); el.className = "field";
    const alts = sug.slice(1).map(a => `<option value="${esc(a.text)}">${esc(a.text)}</option>`).join("");
    el.innerHTML = `<div class="name">${label(name)}</div>
      <div class="val">${esc(sug[0].text)}</div>
      <div class="small">gelesen als ${esc(sug[0].value)} · Beschriftung „${esc(sug[0].label) || "–"}“ (${esc(sug[0].direction)}) · Seite ${sug[0].page}</div>
      <div class="row"><button class="ok">✓ stimmt</button><button class="bad">✗ falsch</button><button class="no">steht nicht drin</button></div>
      <input class="correct" placeholder="richtiger Wert, wie im Dokument" style="display:none">
      ${alts ? `<div class="row small" style="display:none" data-alt>Oder eine Alternative: <select><option value="">–</option>${alts}</select></div>` : ""}`;
    const [ok, bad, no] = el.querySelectorAll("button"), inp = el.querySelector("input"), alt = el.querySelector("[data-alt]");
    const paint = () => {
      ok.className = "ok" + (f.status === "ok" ? " on" : ""); bad.className = "bad" + (f.status === "wrong" ? " on" : ""); no.className = "no" + (f.status === "absent" ? " on" : "");
      inp.style.display = f.status === "wrong" ? "" : "none"; if (alt) alt.style.display = f.status === "wrong" ? "" : "none";
      inp.value = f.correct || "";
    };
    ok.onclick = () => { f.status = "ok"; f.correct = ""; paint(); persist(); };
    bad.onclick = () => { f.status = "wrong"; paint(); persist(); inp.focus(); };
    no.onclick = () => { f.status = "absent"; f.correct = ""; paint(); persist(); };
    inp.oninput = () => { f.correct = inp.value; persist(); };
    if (alt) alt.querySelector("select").onchange = e => { f.correct = e.target.value; paint(); persist(); };
    paint(); box.appendChild(el);
  }
  const added = document.getElementById("added"); added.innerHTML = "";
  s.added.forEach((a, k) => {
    const row = document.createElement("div"); row.className = "row small";
    row.innerHTML = `<span><b>${label(a.field)}</b>: ${esc(a.value)}</span><button>entfernen</button>`;
    row.querySelector("button").onclick = () => { s.added.splice(k, 1); persist(); show(); };
    added.appendChild(row);
  });
  const sel = document.getElementById("addField");
  sel.innerHTML = FIELDS.map(f => `<option value="${esc(f.name)}">${esc(f.label)}</option>`).join("");
  progress();
}
document.getElementById("prev").onclick = () => { i = Math.max(0, i - 1); show(); };
document.getElementById("next").onclick = () => { i = Math.min(DOCS.length - 1, i + 1); show(); };
document.getElementById("skip").onchange = e => { ds(DOCS[i]).skip = e.target.checked; persist(); };
document.getElementById("note").oninput = e => { ds(DOCS[i]).note = e.target.value; persist(); };
document.getElementById("add").onclick = () => {
  const v = document.getElementById("addValue").value.trim(); if (!v) return;
  ds(DOCS[i]).added.push({field: document.getElementById("addField").value, value: v});
  document.getElementById("addValue").value = ""; persist(); show();
};
document.getElementById("save").onclick = () => {
  const out = {round: ROUND, saved: new Date().toISOString(), documents: DOCS.map(d => ({n: d.n, ...ds(d)}))};
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {type: "application/json"}));
  a.download = `werterkennung_runde${ROUND}.json`; a.click();
};
show();
</script></body></html>"""
page = (
    page.replace("@@NUM@@", str(rnd))
    .replace("@@FIELDS@@", json.dumps(fields, ensure_ascii=False))
    .replace("@@DOCS@@", json.dumps(docs, ensure_ascii=False).replace("</", "<\\/"))
)
out = os.path.join(HERE, f"werterkennung_runde{rnd}.html")
open(out, "w", encoding="utf-8").write(page)
print(out)
