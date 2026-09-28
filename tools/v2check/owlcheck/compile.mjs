// Compiles every template of merged.xml with the real OWL (the one Odoo ships) inside jsdom,
// so a bad directive, an invalid JS expression in an attribute, or a broken structure is
// found here and not in a user's browser. Compiling only: nothing is rendered.
//   node compile.mjs merged.xml
import {readFileSync} from "node:fs";
import {JSDOM} from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {pretendToBeVisual: true});
// owl.js reaches for many browser globals (DOMTokenList, Node, ...): lend it all of them.
for (const name of Object.getOwnPropertyNames(dom.window)) {
  if (!(name in globalThis)) {
    Object.defineProperty(globalThis, name, {
      get: () => dom.window[name],
      configurable: true,
    });
  }
}
// owl.js is an IIFE that attaches itself to `this.owl` (globalThis when called this way).
new Function(readFileSync(new URL("./owl.js", import.meta.url), "utf8")).call(globalThis);
const owl = globalThis.owl;

const xml = readFileSync(process.argv[2], "utf8");
// Only the module's own templates are judged; the core ones are just there to be called.
const names = readFileSync(`${process.argv[2]}.own`, "utf8")
  .split(/\r?\n/)
  .filter(Boolean);

class Root extends owl.Component {}
Root.template = names[0];
const app = new owl.App(Root, {templates: xml, dev: true});

let failures = 0;
for (const name of names) {
  try {
    app.getTemplate(name);
  } catch (error) {
    failures++;
    console.log(`PROBLEM: ${name}: ${String(error.message).split("\n")[0]}`);
  }
}
console.log(`${names.length} template(s) compiled, ${failures} problem(s)`);
process.exit(failures ? 1 : 0);
