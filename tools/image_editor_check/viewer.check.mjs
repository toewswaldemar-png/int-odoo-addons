import "./env.mjs";
import fs from "node:fs";
import { VIEWER_SRC, odooWeb } from "./paths.mjs";
import { pathToFileURL } from "node:url";

const CORE = odooWeb() + "/src/";
const MOD = VIEWER_SRC + "/";
window.eval(fs.readFileSync(odooWeb() + "/lib/owl/owl.js", "utf8"));
globalThis.owl = window.owl;
for (const name of ["Element", "HTMLElement", "Text", "Comment", "DocumentFragment", "Document", "XPathEvaluator", "Node", "WheelEvent", "DOMMatrixReadOnly", "getComputedStyle", "XPathResult"]) {
    globalThis[name] = window[name];
}
globalThis.odoo = { debug: false };
globalThis.requestAnimationFrame = (f) => setTimeout(f, 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
// jsdom has no layout: the ground is 1000 x 600, the picture 800 x 500 before the zoom
Object.defineProperty(window.HTMLElement.prototype, "offsetWidth", {
    get() { return this.classList.contains("o-FileViewer-zoomer") ? 1000 : this.classList.contains("o-FileViewer-viewImage") ? 800 : 0; },
    configurable: true,
});
Object.defineProperty(window.HTMLElement.prototype, "offsetHeight", {
    get() { return this.classList.contains("o-FileViewer-zoomer") ? 600 : this.classList.contains("o-FileViewer-viewImage") ? 500 : 0; },
    configurable: true,
});

let fails = 0;
const ok = (name, cond, extra = "") => {
    console.log((cond ? "PASS " : "FAIL ") + name + (extra ? "  " + extra : ""));
    if (!cond) fails++;
};
const wait = (ms = 20) => new Promise((r) => setTimeout(r, ms));

// ---- the template: Odoo's own inheritance on the core's template
const { applyInheritance } = await import(pathToFileURL(CORE + "core/template_inheritance.js").href);
const parse = (xml) => new window.DOMParser().parseFromString(xml, "text/xml");
const coreDoc = parse(fs.readFileSync(CORE + "core/file_viewer/file_viewer.xml", "utf8"));
const base = [...coreDoc.querySelectorAll("[t-name]")].find((t) => t.getAttribute("t-name") === "web.FileViewer");
const ours = parse(fs.readFileSync(MOD + "document_file_viewer.xml", "utf8")).querySelector("[t-name]");
const root = base.cloneNode(true);
root.setAttribute("t-name", ours.getAttribute("t-name"));
const built = applyInheritance(root, ours, "/int_filemanager/static/src/int_filemanager/file_viewer/document_file_viewer.xml");
const main = built.querySelector(".o-FileViewer-main");
const img = built.querySelector("img.o-FileViewer-viewImage");
ok("main has the handlers of the surface", ["t-ref", "t-on-click.stop", "t-on-wheel", "t-on-mousedown.stop", "t-on-mouseup.stop"].every((a) => main.hasAttribute(a)) && main.getAttribute("t-on-wheel") === "onWheelImage" && main.getAttribute("t-ref") === "main");
ok("the image has lost the three it had", !img.hasAttribute("t-on-wheel") && !img.hasAttribute("t-on-mousedown.stop") && !img.hasAttribute("t-on-mouseup.stop"));
ok("the image keeps the ones that stay", img.hasAttribute("t-on-click.stop") && img.hasAttribute("t-on-load") && img.hasAttribute("t-ref"));
ok("main keeps the mousemove of the core", main.hasAttribute("t-on-mousemove"));
ok("the edit button is still added", !!built.querySelector("[title='Edit']"));

// ---- the component
globalThis.__services = { ui: { isSmall: false } };
const { DocumentFileViewer } = await import("@int_filemanager/int_filemanager/file_viewer/document_file_viewer");
const templates = `<templates>${new window.XMLSerializer().serializeToString(built)}</templates>`;

async function mountViewer(file, close) {
    const target = document.createElement("div");
    document.body.appendChild(target);
    const app = new owl.App(DocumentFileViewer, { env: { services: {} }, props: { files: [file], startIndex: 0, modal: false, close }, dev: true, warnIfNoStaticProps: false });
    app.addTemplates(templates);
    await app.mount(target);
    await wait();
    return { app, viewer: app.root.component, target };
}
const picture = { name: "p.jpg", isImage: true, isViewable: true, defaultSource: "x", downloadUrl: "#", isEditable: false };
let closed = 0;
const { viewer, target } = await mountViewer(picture, () => closed++);
const ground = target.querySelector(".o-FileViewer-zoomer");     // the dark area around the picture
const mainEl = target.querySelector(".o-FileViewer-main");
const imageEl = target.querySelector("img.o-FileViewer-viewImage");
const wheel = (el, deltaY, x = 10, y = 10) => el.dispatchEvent(new window.WheelEvent("wheel", { deltaY, deltaMode: 0, clientX: x, clientY: y, bubbles: true, cancelable: true }));
const mouse = (el, type, x, y) => el.dispatchEvent(new window.MouseEvent(type, { clientX: x, clientY: y, button: 0, bubbles: true, cancelable: true }));

// wheel
wheel(ground, -100);
const afterGround = viewer.state.scale;
ok("the wheel zooms on the ground around the picture", afterGround > 1, "scale=" + afterGround);
viewer.state.scale = 1; viewer.updateZoomerStyle(); viewer.wheelTicks = 0;
wheel(imageEl, -100);
ok("on the picture it zooms as before, and only once (no double handling)", viewer.state.scale === afterGround, `${viewer.state.scale} vs ${afterGround}`);
viewer.state.scale = 1; viewer.updateZoomerStyle(); viewer.wheelTicks = 0;
wheel(ground, 100);
ok("the wheel out", viewer.state.scale <= 1);
viewer.state.scale = 1; viewer.wheelTicks = 0;

// drag with the mouse
viewer.state.scale = 2; viewer.updateZoomerStyle();      // 1600 px wide: the picture may move 300 px
mouse(ground, "mousedown", 100, 100);
mouse(mainEl, "mousemove", 160, 130);
mouse(ground, "mouseup", 160, 130);
ok("a drag that begins on the ground moves the picture", viewer.translate.x === 60 && viewer.translate.y === 30, JSON.stringify(viewer.translate));
ok("and ends when the mouse is let go on the ground", viewer.isDragging === false);
// the click after that drag does not close the viewer
mouse(ground, "click", 160, 130);
ok("the click that ends the drag does not close the viewer", closed === 0);
// a plain click on the ground closes it (as the core does)
mouse(ground, "mousedown", 300, 300); mouse(ground, "mouseup", 300, 300); mouse(ground, "click", 300, 300);
ok("a plain click on the ground still closes", closed === 1, "closed=" + closed);
// a drag that is too short is a click
mouse(ground, "mousedown", 300, 300); mouse(mainEl, "mousemove", 302, 301); mouse(ground, "mouseup", 302, 301); mouse(ground, "click", 302, 301);
ok("a press that hardly moved is a click", closed === 2, "closed=" + closed);
// a drag that begins on the picture and ends on the ground does not close it either
const before = closed;
mouse(imageEl, "mousedown", 500, 300); mouse(mainEl, "mousemove", 560, 330); mouse(ground, "mouseup", 560, 330); mouse(mainEl, "click", 560, 330);
ok("a drag from the picture to the ground does not close it", closed === before && viewer.translate.x >= 120 && viewer.translate.x <= 124, JSON.stringify(viewer.translate) + " closed=" + closed);
// a click on the picture does not close
mouse(imageEl, "mousedown", 500, 300); mouse(imageEl, "mouseup", 500, 300); mouse(imageEl, "click", 500, 300);
ok("a click on the picture does not close", closed === before);

// touch: two fingers on the ground pinch, one finger moves
const pointer = (el, type, id, x, y) => { const e = new window.Event(type, { bubbles: true, cancelable: true }); for (const [k, v] of Object.entries({ pointerType: "touch", pointerId: id, clientX: x, clientY: y, button: 0, timeStamp: performance.now() })) Object.defineProperty(e, k, { value: v }); el.dispatchEvent(e); };
viewer.state.scale = 1; viewer.updateZoomerStyle(); Object.assign(viewer.translate, { x: 0, y: 0, dx: 0, dy: 0 });
pointer(ground, "pointerdown", 1, 400, 300);
pointer(ground, "pointerdown", 2, 600, 300);
ok("two fingers on the ground make a pinch", !!viewer.pinch);
pointer(ground, "pointermove", 1, 300, 300);
pointer(ground, "pointermove", 2, 700, 300);
ok("moving them apart zooms in", viewer.state.scale > 1.5, "scale=" + viewer.state.scale);
pointer(ground, "pointerup", 1, 300, 300);
pointer(ground, "pointerup", 2, 700, 300);
ok("lifting them ends the pinch", viewer.pinch === null && viewer.touches.size === 0);
viewer.state.scale = 2; viewer.updateZoomerStyle(); Object.assign(viewer.translate, { x: 0, y: 0, dx: 0, dy: 0 });
pointer(ground, "pointerdown", 3, 200, 200);
pointer(ground, "pointermove", 3, 260, 240);
pointer(ground, "pointerup", 3, 260, 240);
ok("one finger that begins on the ground moves the picture", viewer.translate.x === 60 && viewer.translate.y === 40, JSON.stringify(viewer.translate));

// not a picture: nothing of this applies
const pdf = { name: "d.pdf", isPdf: true, isViewable: true, defaultSource: "x", downloadUrl: "#" };
const second = await mountViewer(pdf, () => closed++);
const pdfMain = second.target.querySelector(".o-FileViewer-main");
wheel(pdfMain, -100);
mouse(pdfMain, "mousedown", 10, 10); mouse(pdfMain, "mousemove", 90, 90); mouse(pdfMain, "mouseup", 90, 90);
ok("a PDF is not zoomed or moved by the ground", second.viewer.state.scale === 1 && second.viewer.translate.x === 0 && second.viewer.isDragging === false);
const closedBefore = closed;
mouse(pdfMain, "click", 10, 10);
ok("but a click on its ground still closes", closed === closedBefore + 1);

// the touch listeners are those of the ground, and they go when the file is no picture / on destroy
second.app.destroy();
viewer.state.file = pdf; await wait();
pointer(ground, "pointerdown", 9, 1, 1);
ok("after a picture gives way to a PDF the finger handlers are gone", viewer.touches.size === 0);
console.log(fails ? `\n${fails} FAILED` : "\nALL PASSED");
process.exit(fails ? 1 : 0);
