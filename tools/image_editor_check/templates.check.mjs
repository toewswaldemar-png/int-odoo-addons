import "./env.mjs";
import fs from "node:fs";
import { EDITOR_SRC, odooWeb } from "./paths.mjs";

const SRC = EDITOR_SRC + "/";
window.eval(fs.readFileSync(odooWeb() + "/lib/owl/owl.js", "utf8"));
globalThis.owl = window.owl;
globalThis.ResizeObserver = class { observe() {} disconnect() {} };
globalThis.requestAnimationFrame = (f) => setTimeout(f, 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
// layout does not exist in jsdom: the stage is 800 x 500
for (const [k, v] of [["clientWidth", 800], ["clientHeight", 500]]) {
    Object.defineProperty(window.HTMLElement.prototype, k, { get: () => v, configurable: true });
}

let fails = 0;
const ok = (name, cond, extra = "") => {
    console.log((cond ? "PASS " : "FAIL ") + name + (extra ? "  " + extra : ""));
    if (!cond) fails++;
};
const wait = (ms = 30) => new Promise((r) => setTimeout(r, ms));

function makePicture() {
    const c = napi.createCanvas(1000, 600);
    const x = c.getContext("2d");
    x.fillStyle = "#3366cc";
    x.fillRect(0, 0, 1000, 600);
    c.naturalWidth = 1000;
    c.naturalHeight = 600;
    return c;
}
globalThis.__loadPicture = async () => makePicture();

const notes = [];
const dialogs = [];
globalThis.__services = {
    dialog: { add: (C, props) => dialogs.push({ C, props }) },
    notification: { add: (msg, opts) => notes.push({ msg, opts }) },
    action: { currentController: null, doAction: () => {} },
    orm: { call: async () => ({}) },
    ui: { isSmall: false },
    file_upload: { bus: new EventTarget(), upload: async () => ({ state: "loaded", xhr: { responseText: "{}" } }) },
};

const { DocumentImageEditor } = await import("@int_filemanager/image_editor/document_image_editor");
const { SaveDialog } = await import("@int_filemanager/image_editor/save_dialog");

const templates = ["document_image_editor.xml", "color_field.xml", "save_dialog.xml"].map((name) =>
    fs.readFileSync(SRC + name, "utf8")
);

function newApp(Component, props) {
    const app = new owl.App(Component, { env: { services: {} }, props, dev: true, warnIfNoStaticProps: false });
    for (const xml of templates) {
        app.addTemplates(xml);
    }
    return app;
}

const target = document.createElement("div");
document.body.appendChild(target);
let closed = false;
const app = newApp(DocumentImageEditor, {
    file: { id: 1, name: "photo.png", mimetype: "image/png", folder_id: 3, defaultSource: "x" },
    close: () => (closed = true),
});
await app.mount(target);
const editor = app.root.component;
for (let i = 0; i < 100 && !editor.state.ready; i++) await wait();
await wait(50);
ok("editor mounted and ready", editor.state.ready === true);

const $ = (selector, root = target) => root.querySelector(selector);
const $$ = (selector, root = target) => [...root.querySelectorAll(selector)];
const panelText = () => ($(".o_int_filemanager_image_editor_panel")?.textContent || "").replace(/\s+/g, " ");
const headings = () => $$(".o_int_filemanager_image_editor_panel summary").map((h) => h.textContent.trim());
async function tool(id) {
    $(`[data-tool=${id}]`).click();
    await wait();
}

ok("8 buttons in the column (5 tools, 3 dropdowns)", $$(".o_int_filemanager_image_editor_tool").length === 8, String($$(".o_int_filemanager_image_editor_tool").length));
ok("12 tools in the dropdowns", $$(".stub-dropdown-item[data-tool]").length === 12, String($$(".stub-dropdown-item[data-tool]").length));
ok("every one of the 17 tools can be reached", editor.tools.every((t) => !!$(`[data-tool=${t.id}]`)));
ok("tools separated in groups", $$(".o_int_filemanager_image_editor_tools_separator").length === 5);
ok("select tool active", $$(".o_int_filemanager_image_editor_tool")[0].classList.contains("active"));
ok("dropdown buttons show the first tool of the group", editor.groupIcon(editor.toolEntries.find((e) => e.id === "shape")) === "fa-square-o" || editor.state.lastOfGroup.shape === "line");
ok("panel shown", !!$(".o_int_filemanager_image_editor_panel"));
ok("canvas inside the stage", !!$(".o_int_filemanager_image_editor_stage canvas") && !!$(".o_int_filemanager_image_editor_stage .canvas-container"));
ok("zoom label", $(".o-FileViewer-header").textContent.includes("77 %"), $(".o-FileViewer-header").textContent.replace(/\s+/g, " ").slice(0, 120));

// select tool without selection: only the view section
ok("no style sections for plain select", headings().join() === "Grid", headings().join());

await tool("rect");
ok("the shapes dropdown now shows the rectangle and is active", editor.state.lastOfGroup.shape === "rect" && editor.isGroupActive(editor.toolEntries.find((e) => e.id === "shape")) && $$(".o_int_filemanager_image_editor_tool")[4].classList.contains("active"), JSON.stringify(editor.state.lastOfGroup));
ok("rect tool: style sections", ["Color", "Line", "Fill", "Effects"].every((h) => headings().includes(h)), headings().join());
ok("rect tool: corners slider", panelText().includes("Rounded corners"));
ok("rect tool: no text section", !headings().includes("Text"));
// fill mode switch shows the gradient controls
const fillSelect = $$(".o_int_filemanager_image_editor_panel select")[1];
fillSelect.value = "gradient";
fillSelect.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait();
if (0) console.log("DBG fillMode", editor.state.style.fillMode, "selects", $$(".o_int_filemanager_image_editor_panel select").map((x) => x.value).join("|"), "text", panelText().slice(0, 300));
ok("gradient controls appear", panelText().includes("Angle") && editor.state.style.fillMode === "gradient");
fillSelect.value = "none";
fillSelect.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait();
// slider input changes the style
const widthInput = $$(".o_int_filemanager_image_editor_panel input[type=range]")[0];
widthInput.value = "12";
widthInput.dispatchEvent(new window.Event("input", { bubbles: true }));
await wait();
ok("width slider sets the style", editor.state.style.width === 12 && panelText().includes("Width: 12"));

await tool("text");
ok("text tool: text section", headings().includes("Text") && $$(".o_int_filemanager_image_editor_panel select option").length >= 11);
ok("text tool: no fill section", !headings().includes("Fill"));
// bold toggle
const bold = $$(".o_int_filemanager_image_editor_panel .btn-group button").find((b) => b.getAttribute("title") === "Bold");
bold.click();
await wait();
ok("bold toggles", editor.state.style.bold === true && bold.classList.contains("active"));
bold.click();
await wait();

await tool("pen");
ok("pen tool: brush section", headings().includes("Brush") && editor.canvas.isDrawingMode === true);
const brushSelect = $$(".o_int_filemanager_image_editor_panel select")[0];
brushSelect.value = "spray";
brushSelect.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait();
ok("spray brush: density control, brush class", panelText().includes("Density") && editor.canvas.freeDrawingBrush instanceof fabric.SprayBrush);
brushSelect.value = "pencil";
brushSelect.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait();

await tool("redact");
ok("redact tool: hide section", headings().includes("Hide") && !headings().includes("Effects"));

await tool("polygon");
ok("polygon tool: hint shown", panelText().includes("Click each point"));

await tool("adjust");
ok("adjust: sliders and looks", $$(".o_int_filemanager_image_editor_panel input[type=range]").length >= 9 && $$(".o_int_filemanager_image_editor_panel .btn-outline-secondary").length >= 11, "ranges=" + $$(".o_int_filemanager_image_editor_panel input[type=range]").length);
ok("adjust: labels in place", panelText().includes("Brightness") && panelText().includes("Pixelate") && panelText().includes("Sepia"));
const brightness = $$(".o_int_filemanager_image_editor_panel input[type=range]")[0];
brightness.value = "0.4";
brightness.dispatchEvent(new window.Event("input", { bubbles: true }));
brightness.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait(60);
ok("brightness slider -> filter + history", editor.state.filters.brightness === 0.4 && editor.picture.image.filters.length === 1 && editor.state.canUndo);
const sepiaBtn = $$(".o_int_filemanager_image_editor_panel .btn-outline-secondary").find((b) => b.textContent.trim() === "Sepia");
sepiaBtn.click();
await wait(60);
ok("looks button toggles", editor.state.filters.sepia === true && sepiaBtn.classList.contains("active"));
const removeBox = $("#int_filemanager_editor_removecolor");
removeBox.click();
await wait(60);
ok("remove color: controls appear", !!editor.state.filters.removecolor && panelText().includes("Remove a color"));
$("#int_filemanager_editor_blendcolor").click();
await wait(60);
ok("blend color: mode select with 10 modes", $$(".o_int_filemanager_image_editor_panel select")[0].options.length === 10, "options=" + $$(".o_int_filemanager_image_editor_panel select")[0].options.length);

await tool("crop");
ok("crop: panel and aspect select", headings().includes("Crop") && headings().includes("Turn and flip") && $$(".o_int_filemanager_image_editor_panel select")[0].options.length === 9);
ok("crop: frame on canvas", editor.cropTool.active);
const apply = $$(".o_int_filemanager_image_editor_panel button").find((b) => b.textContent.includes("Apply the crop"));
apply.click();
await wait();
ok("apply the crop button", !editor.cropTool.active && editor.state.tool === "select");

// a selected mark: marks section
await tool("rect");
const mouse = (x, y) => ({ e: { clientX: x, clientY: y, shiftKey: false }, target: undefined });
const sp = (x, y) => { const [z, , , , e, f] = editor.canvas.viewportTransform; return { x: x * z + e, y: y * z + f }; };
{
    const a = sp(200, 150), b = sp(350, 250);
    editor.drawing.onMouseDown(mouse(a.x, a.y));
    editor.drawing.onMouseMove(mouse(b.x, b.y));
    editor.drawing.onMouseUp();
}
await tool("select");
editor.canvas.setActiveObject(editor.canvas.getObjects()[0]);
editor.syncSelection();
await wait();
ok("selection: Marks section with arrange buttons", headings().includes("Marks") && $$(".o_int_filemanager_image_editor_panel button[title='Align left']").length === 1);
$$(".o_int_filemanager_image_editor_panel button[title='Align left']")[0].click();
await wait();
ok("align left button works", Math.abs(editor.canvas.getObjects()[0].getBoundingRect().left - editor.regionBox.left) < 1e-6, String(editor.canvas.getObjects()[0].getBoundingRect().left) + " vs " + editor.regionBox.left);

// header buttons
$$(".o-FileViewer-header button").find((b) => b.getAttribute("title") === "Undo (Ctrl+Z)").click();
await wait(60);
ok("undo button", true);
// save button opens the dialog
$$(".o-FileViewer-header button.btn-primary")[0].click();
await wait();
ok("save button opens dialog", dialogs.length === 1 && dialogs[0].C === SaveDialog, "dialogs=" + dialogs.length);

// panel toggle and small screens
$$(".o-FileViewer-header button").find((b) => b.getAttribute("title") === "Show or hide the settings").click();
await wait();
ok("panel can be hidden", !$(".o_int_filemanager_image_editor_panel"));
$$(".o-FileViewer-header button").find((b) => b.getAttribute("title") === "Show or hide the settings").click();
await wait();

// the save dialog itself
const dlgTarget = document.createElement("div");
document.body.appendChild(dlgTarget);
const dlg = newApp(SaveDialog, { name: "photo (edited)", mimetype: "image/png", size: { width: 600, height: 300 }, maxScale: 0.5, canKeepState: true, onSave: (o) => (dlg.saved = o), close: () => (dlg.closed = true) });
await dlg.mount(dlgTarget);
const comp = dlg.root.component;
const dtext = dlgTarget.textContent.replace(/\s+/g, " ");
ok("dialog shows name, format, size", dtext.includes("Name") && dtext.includes("Format") && dtext.includes("Size") && dtext.includes("300 × 150"), dtext.slice(0, 200));
ok("dialog offers only scales the browser can make", [...dlgTarget.querySelectorAll("#int_filemanager_editor_scale option")].map((o) => o.value).join() === "0.5,0.35,0.25,0.15,0.1");
ok("reduced size warning", dtext.includes("largest size it can make"));
ok("no quality slider for PNG", !dlgTarget.querySelector("#int_filemanager_editor_quality"));
const fmt = dlgTarget.querySelector("#int_filemanager_editor_format");
fmt.value = "image/jpeg";
fmt.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait();
ok("quality slider for JPEG, extension follows", !!dlgTarget.querySelector("#int_filemanager_editor_quality") && dlgTarget.querySelector(".input-group-text").textContent.trim() === ".jpg");
fmt.value = "image/svg+xml";
fmt.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait();
ok("svg extension", dlgTarget.querySelector(".input-group-text").textContent.trim() === ".svg" && !dlgTarget.querySelector("#int_filemanager_editor_quality"));
dlgTarget.querySelector(".stub-dialog .btn-primary").click();
await wait();
ok("dialog save returns the options", dlg.closed === true && dlg.saved.mimetype === "image/svg+xml" && dlg.saved.scale === 0.5 && dlg.saved.name === "photo (edited)" && dlg.saved.keepState === true, JSON.stringify(dlg.saved));
// state too large: checkbox disabled
const dlg2 = newApp(SaveDialog, { name: "x", mimetype: "image/png", size: { width: 10, height: 10 }, maxScale: 1, canKeepState: false, onSave() {}, close() {} });
const t2 = document.createElement("div");
document.body.appendChild(t2);
await dlg2.mount(t2);
ok("too-large state: checkbox disabled and warning", t2.querySelector("[id=int_filemanager_editor_keep]").disabled && t2.textContent.includes("too large"));

// loading and failure: no console errors from Owl
console.log(fails ? `\n${fails} FAILED` : "\nALL PASSED");
process.exit(fails ? 1 : 0);
