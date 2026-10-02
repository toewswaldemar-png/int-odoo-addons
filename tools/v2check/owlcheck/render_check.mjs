// Renders the templates of the properties form (picture layer, values widget) with the
// real OWL in jsdom, with stand-ins for what Odoo supplies. compile.mjs only compiles: an
// expression OWL does not know in a template (Boolean(...)) fails first when it is rendered.
//   node render_check.mjs
import {mkdtempSync, readFileSync, writeFileSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {pathToFileURL} from "node:url";
import assert from "node:assert/strict";
import {JSDOM} from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {pretendToBeVisual: true});
for (const name of Object.getOwnPropertyNames(dom.window)) {
  if (!(name in globalThis)) Object.defineProperty(globalThis, name, {get: () => dom.window[name], configurable: true});
}
new Function(readFileSync(new URL("./owl.js", import.meta.url), "utf8")).call(globalThis);
const owl = globalThis.owl;
const dir = new URL("../../../int_filemanager/static/src/int_filemanager/v2/properties/", import.meta.url);
const templates = ["image_words.xml", "preview_field.xml", "values_field.xml"]
  .map((f) => readFileSync(new URL(f, dir), "utf8").replace(/<\?xml[^>]*\?>/, "").replace(/<\/?templates[^>]*>/g, ""))
  .join("\n");
const xml = `<templates>${templates}</templates>`;
const tick = () => new Promise((r) => setTimeout(r, 60));

// --- the image layer in the preview, as the real component's getters give it
// The layer component and its helpers, with the Odoo import of OWL pointed at the global.
const scratch = mkdtempSync(join(tmpdir(), "owlcheck_"));
const source = (name) => readFileSync(new URL(name, dir), "utf8");
writeFileSync(join(scratch, "value_geometry.mjs"), source("value_geometry.js"));
writeFileSync(
  join(scratch, "image_words.mjs"),
  source("image_words.js")
    .replace(/import \{([^}]*)\} from "@odoo\/owl";/, "const {$1} = globalThis.owl;")
    .replace('"./value_geometry.js"', '"./value_geometry.mjs"')
);
const {IntFilemanagerV2ImageWords} = await import(pathToFileURL(join(scratch, "image_words.mjs")));

class Preview extends owl.Component {
  static template = "int_filemanager.v2.PreviewField";
  static components = {IntFilemanagerV2ImageWords};
  setup() {
    this.state = owl.useState({picking: null, markers: [], activeFieldId: null, sizes: null, ratio: 0, words: null});
    host = this;
  }
  file = {isImage: true, defaultSource: "data:image/gif;base64,R0lGODlhAQABAAAAACw="};
  pictureSize = [240, 72];
  get pictureMarkers() { return this.state.markers.filter((m) => m.box.page === 1); }
  get isPicking() { return Boolean(this.state.picking); }
  onPictureLoad() {}
  onOpenWindow() {}
  onCancelPick() {}
  onPickWords() {}
}
let host;
const app = new owl.App(Preview, {templates: xml, dev: true});
await app.mount(document.body);
await tick();
assert.ok(document.querySelector("img"));
assert.equal(document.querySelector(".o_int_filemanager_image_words"), null, "no layer before the picture is loaded");
host.state.ratio = 3.3; host.state.picking = {fieldId: 1, name: "Invoice"};
host.state.words = [[10, 20, 50, 30, 0, 5]];
await tick();
const layer = document.querySelector(".o_int_filemanager_image_words");
assert.ok(layer.classList.contains("o_word_mode"));
assert.equal(document.querySelectorAll(".o_int_filemanager_word").length, 1);
assert.ok(document.querySelector(".o_int_filemanager_picture_frame").classList.contains("o_loaded"));
assert.match(document.querySelector(".o_int_filemanager_picture_frame").getAttribute("style"), /--ratio: 3\.3/);
assert.ok(document.querySelector(".o_int_filemanager_preview_hint"));
host.state.picking = null; await tick();
assert.equal(layer.classList.contains("o_word_mode"), false);
console.log("preview (picture): ok");
app.destroy();
document.body.innerHTML = "";

// --- the values widget in its states
const cases = {
  none_readable: {status: "none", canReadText: true},
  none_plain: {status: "none", canReadText: false},
  pending: {status: "pending", canReadText: false},
  ready_empty: {status: "ready", canReadText: false, hasRows: false, hasForm: false},
};
for (const [name, props] of Object.entries(cases)) {
  class Values extends owl.Component {
    static template = "int_filemanager.v2.ValuesField";
    static components = {Record: class extends owl.Component {static template = owl.xml`<t t-slot="default" record="{}"/>`}, FormRenderer: class extends owl.Component {static template = owl.xml`<div/>`}};
    props = {readonly: false};
    status = props.status; canReadText = props.canReadText; hasRows = props.hasRows ?? false; hasForm = props.hasForm ?? false;
    hasUnconfirmed = false; partner = false; warnings = []; state = {rev: 0};
    fields = {}; values = {}; hooks = {}; archInfo = {};
    onReadText() { clicked = true; }
    onAcceptAll() {} onUsePartner() {}
  }
  var clicked = false;
  const a = new owl.App(Values, {templates: xml, dev: true});
  await a.mount(document.body);
  await tick();
  const text = document.body.textContent.replace(/\s+/g, " ");
  if (name === "none_readable") {
    assert.match(text, /No text has been read from this picture yet\./);
    document.querySelector("button").click();
    assert.equal(clicked, true);
  } else if (name === "none_plain") {
    assert.match(text, /no text to look for values in/);
    assert.equal(document.querySelector("button"), null);
  } else if (name === "pending") {
    assert.match(text, /being read/);
  }
  a.destroy(); document.body.innerHTML = "";
}
console.log("values widget states: ok");
process.exit(0);
