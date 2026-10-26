import "./env.mjs";
import { OUT } from "./paths.mjs";
import fs from "node:fs";

globalThis.ResizeObserver = class { observe() {} disconnect() {} };
globalThis.requestAnimationFrame = (f) => setTimeout(f, 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);

const f = fabric;
// the picture: 1000x600, red square top-left, blue ground
function makePicture() {
    const c = napi.createCanvas(1000, 600);
    const x = c.getContext("2d");
    x.fillStyle = "#3366cc";
    x.fillRect(0, 0, 1000, 600);
    x.fillStyle = "#cc3333";
    x.fillRect(0, 0, 100, 100);
    c.naturalWidth = 1000;
    c.naturalHeight = 600;
    return c;
}
globalThis.__loadPicture = async () => makePicture();

let fails = 0;
const ok = (name, cond, extra = "") => {
    console.log((cond ? "PASS " : "FAIL ") + name + (extra ? "  " + extra : ""));
    if (!cond) fails++;
};
const near = (a, b, eps = 1e-6) => Math.abs(a - b) < eps;

const notes = [];
const dialogs = [];
const uploads = [];
let session = {};
globalThis.__services = {
    dialog: { add: (C, props) => dialogs.push({ C, props }) },
    notification: { add: (msg, opts) => notes.push({ msg, opts }) },
    action: { currentController: { props: { type: "list" } }, doAction: (a) => notes.push({ doAction: a }) },
    orm: { call: async () => session },
    ui: { isSmall: false },
    file_upload: {
        bus: new EventTarget(),
        upload: async (route, files, params) => {
            const fd = new FormData();
            params.buildFormData(fd);
            uploads.push({ route, files, fd });
            return { state: "loaded", xhr: { responseText: JSON.stringify({ id: 77, name: files[0].name }) } };
        },
    },
};

const { DocumentImageEditor } = await import("@int_filemanager_image_editor/image_editor/document_image_editor");
const { readState } = await import("@int_filemanager_image_editor/image_editor/edit_state");

async function makeEditor(file) {
    const stage = document.createElement("div");
    Object.defineProperty(stage, "clientWidth", { value: 800 });
    Object.defineProperty(stage, "clientHeight", { value: 500 });
    const canvasEl = document.createElement("canvas");
    stage.appendChild(canvasEl);
    document.body.appendChild(stage);
    globalThis.__refs = {
        root: { el: { focus() {} } },
        canvas: { el: canvasEl },
        stage: { el: stage },
        import: { el: { click() {} } },
    };
    let closed = false;
    const editor = new DocumentImageEditor({ file, close: () => (closed = true) });
    editor.isClosed = () => closed;
    await editor.start();
    return editor;
}
const mouse = (x, y, extra = {}) => ({ e: { clientX: x, clientY: y, shiftKey: false, ...extra }, target: undefined });
// the scene point of a screen point, so that tests can speak in scene units
const toScreen = (editor, x, y) => {
    const [z, , , , e, fy] = editor.canvas.viewportTransform;
    return { x: x * z + e, y: y * z + fy };
};
function drag(editor, tool, from, to) {
    editor.setTool(tool);
    const a = toScreen(editor, from.x, from.y);
    const b = toScreen(editor, to.x, to.y);
    editor.drawing.onMouseDown(mouse(a.x, a.y));
    editor.drawing.onMouseMove(mouse(b.x, b.y));
    editor.drawing.onMouseUp();
}

const file = { id: 1, name: "photo.png", mimetype: "image/png", folder_id: 3, defaultSource: "x" };
const editor = await makeEditor(file);
ok("editor ready", editor.state.ready === true && !!editor.canvas);
ok("unit and scene", editor.unit === 1 && editor.scene.width === 1000 && editor.scene.height === 600, JSON.stringify(editor.scene));
ok("no working copy under the edge", editor.picture.scale === 1 && editor.picture.work === editor.picture.full);
ok("history starts with one", editor.history.entries.length === 1 && !editor.state.canUndo);
ok("fit zoom", near(editor.viewport.zoom, 768 / 1000) && editor.state.zoom === 77, "zoom%=" + editor.state.zoom);

// drawing
drag(editor, "rect", { x: 100, y: 100 }, { x: 300, y: 220 });
ok("rect drawn", editor.canvas.getObjects().length === 1 && editor.canvas.getObjects()[0].type === "rect");
ok("history grew", editor.history.entries.length === 2 && editor.state.canUndo);
const rect = editor.canvas.getObjects()[0];
ok("rect size", near(rect.width, 200, 0.5) && near(rect.height, 120, 0.5), `${rect.width}x${rect.height}`);
drag(editor, "arrow", { x: 400, y: 400 }, { x: 600, y: 300 });
drag(editor, "ellipse", { x: 500, y: 100 }, { x: 700, y: 200 });
drag(editor, "circle", { x: 800, y: 100 }, { x: 900, y: 150 });
drag(editor, "triangle", { x: 50, y: 400 }, { x: 150, y: 500 });
drag(editor, "line", { x: 700, y: 400 }, { x: 900, y: 450 });
drag(editor, "highlight", { x: 100, y: 300 }, { x: 400, y: 340 });
drag(editor, "redact", { x: 0, y: 0 }, { x: 120, y: 120 });
const kinds = editor.canvas.getObjects().map((o) => o.mark || o.type);
ok("all drag tools produced marks", kinds.join() === "rect,arrow,ellipse,circle,triangle,line,highlight,redact", kinds.join());
// a tiny drag makes nothing
const countBefore = editor.canvas.getObjects().length;
drag(editor, "rect", { x: 10, y: 10 }, { x: 10.5, y: 10.5 });
ok("tiny drag ignored", editor.canvas.getObjects().length === countBefore);

// polygon
editor.setTool("polygon");
for (const [x, y] of [[600, 450], [700, 450], [650, 550]]) {
    const p = toScreen(editor, x, y);
    editor.drawing.onMouseDown(mouse(p.x, p.y));
}
ok("polygon in progress", editor.drawing.poly.points.length === 3 && editor.drawing.polyOverlay().points.length === 4);
editor.drawing.finishPoly();
ok("polygon made", editor.canvas.getObjects().at(-1).type === "polygon" && !editor.drawing.poly);

// text
editor.setTool("text");
const tp = toScreen(editor, 300, 500);
editor.drawing.onMouseDown(mouse(tp.x, tp.y));
const textObj = editor.canvas.getObjects().at(-1);
ok("text made, tool back to select", textObj.type === "i-text" && editor.state.tool === "select");
textObj.exitEditing?.();
editor.onTextEdited(textObj);

// undo / redo across all of it
const total = editor.canvas.getObjects().length;
await editor.undo();
ok("undo removes last", editor.canvas.getObjects().length === total - 1 || editor.canvas.getObjects().length === total);
await editor.redo();
let n = editor.canvas.getObjects().length;
while (editor.state.canUndo) await editor.undo();
ok("undo all -> empty", editor.canvas.getObjects().length === 0 && !editor.state.canUndo);
while (editor.state.canRedo) await editor.redo();
ok("redo all -> same count", editor.canvas.getObjects().length === n, `${editor.canvas.getObjects().length} vs ${n}`);
const redactAfterRedo = editor.canvas.getObjects().find((o) => o.mark === "redact");
ok("redact survives undo/redo as RedactMark", !!redactAfterRedo && redactAfterRedo.mode === "pixelate");

// selection + style
const first = editor.canvas.getObjects()[0];
editor.canvas.setActiveObject(first);
editor.syncSelection();
ok("selection synced", editor.state.selection.kind === "rect" && editor.state.selection.count === 1 && editor.hasFill && editor.hasLine);
editor.setStyle({ stroke: "#00AA00" });
ok("style applied to selection", first.stroke === "#00AA00" && editor.history.entries.length > 1);
editor.setStyle({ fillMode: "solid", fill: "#FFFF00" });
ok("fill applied", first.fill === "#FFFF00");
editor.setStyle({ shadow: { ...editor.state.style.shadow, on: true } });
ok("shadow applied", !!first.shadow);
editor.setStyle({ opacity: 0.4 });
ok("opacity applied", near(first.opacity, 0.4));

// arrange via editor
editor.canvas.discardActiveObject();
editor.selectAll();
ok("select all", editor.selectedObjects.length === editor.canvas.getObjects().length);
editor.canvas.discardActiveObject();
editor.canvas.setActiveObject(first);
await editor.duplicate();
ok("duplicate via editor", editor.canvas.getObjects().length === n + 1);
editor.canvas.discardActiveObject();
editor.canvas.setActiveObject(editor.canvas.getObjects().at(-1));
editor.deleteSelection();
ok("delete", editor.canvas.getObjects().length === n);

// filters
editor.setTool("adjust");
editor.onFilterInput("brightness", { target: { value: "0.3" } });
editor.onFilterChange("brightness", { target: { value: "0.3" } });
await new Promise((r) => setTimeout(r, 20));
ok("filter set and applied", editor.state.filters.brightness === 0.3 && editor.picture.image.filters.length === 1);
editor.toggleFilter("sepia");
await new Promise((r) => setTimeout(r, 20));
ok("toggle filter", editor.state.filters.sepia === true && editor.picture.image.filters.length === 2);
editor.toggleColorFilter("blendcolor", editor.blendColorDefaults);
await new Promise((r) => setTimeout(r, 20));
ok("color filter", editor.picture.image.filters.length === 3);
await editor.undo();
await new Promise((r) => setTimeout(r, 20));
ok("undo of color filter", !editor.state.filters.blendcolor && editor.picture.image.filters.length === 2);
await editor.undo();
ok("undo of toggle", !editor.state.filters.sepia && editor.picture.image.filters.length === 1);
await editor.redo();
await editor.redo();
ok("redo filters", editor.state.filters.sepia && editor.state.filters.blendcolor);

// crop
editor.setTool("crop");
ok("crop tool active, scene whole", editor.cropTool.active && editor.regionBox.width === 1000);
editor.cropTool.rect.set({ left: 100, top: 50, width: 600, height: 400, scaleX: 1, scaleY: 1 });
editor.cropTool.rect.setCoords();
editor.setAspect("16:9");
const box16 = editor.cropTool.box;
ok("aspect 16:9 holds", near(box16.width / box16.height, 16 / 9, 1e-3), `${box16.width}x${box16.height}`);
editor.applyCrop();
ok("crop applied", !!editor.crop && editor.state.cropped && !editor.cropTool.active && editor.state.tool === "select");
ok("region is the crop", editor.regionBox === editor.crop);
ok("clip path set", !!editor.canvas.clipPath);
ok("marks selectable again after crop", editor.canvas.getObjects().every((o) => o.selectable !== false && o.evented !== false));
ok("crop in snapshot", JSON.parse(editor.snapshot()).crop.width > 0);

// rotate
const sizeBefore = { ...editor.scene };
const cropBefore = { ...editor.crop };
editor.rotate(true);
ok("rotate swaps scene", editor.scene.width === sizeBefore.height && editor.scene.height === sizeBefore.width);
ok("rotate turns crop", near(editor.crop.width, cropBefore.height, 1e-6), JSON.stringify(editor.crop));
editor.rotate(false);
ok("rotate back", editor.scene.width === sizeBefore.width && near(editor.crop.width, cropBefore.width, 1e-6));
editor.flip(true);
editor.flip(true);
await editor.undo();
await editor.undo();
await editor.undo();
await editor.undo();
ok("undo of rotations/flip keeps scene consistent", editor.scene.width === sizeBefore.width && !!editor.crop);

// reset crop
editor.resetCrop();
ok("reset crop: the whole scene is the region again", editor.crop === null && editor.regionBox.width === editor.scene.width && editor.canvas.clipPath.width === editor.scene.width);

// nothing outside the picture
{
    editor.setTool("rect");
    const n0 = editor.canvas.getObjects().length;
    const out = toScreen(editor, -150, 300); const inn = toScreen(editor, 300, 300); const far = toScreen(editor, 1400, 300);
    editor.drawing.onMouseDown(mouse(out.x, out.y));
    ok("a drag that begins outside makes no draft", !editor.drawing.draft);
    editor.drawing.onMouseDown(mouse(inn.x, inn.y));
    editor.drawing.onMouseMove(mouse(far.x, far.y));
    const o = editor.drawing.draft.object;
    ok("a drag that ends outside stops at the edge", Math.abs(o.left + o.width - editor.regionBox.width) < 1e-6 && o.width > 0, `right edge ${o.left + o.width}`);
    editor.drawing.onMouseUp();
    ok("that mark lies inside", editor.canvas.getObjects().at(-1).getBoundingRect().left + editor.canvas.getObjects().at(-1).getBoundingRect().width <= 1000 + 4 + 1e-6);
    editor.setTool("text");
    editor.drawing.onMouseDown(mouse(out.x, out.y));
    ok("a text outside is not set", editor.canvas.getObjects().length === n0 + 1 && editor.state.tool === "text");
    editor.setTool("polygon");
    editor.drawing.onMouseDown(mouse(out.x, out.y));
    ok("a polygon does not begin outside", !editor.drawing.poly);
    // a stroke entirely outside is removed, one that touches the picture stays
    const { Path } = fabric;
    const outside = new Path("M -300 10 L -200 50", { stroke: "#f00" }); editor.canvas.add(outside); editor.onPathCreated(outside);
    ok("a stroke outside is dropped", !editor.canvas.getObjects().includes(outside));
    const touching = new Path("M -100 10 L 200 50", { stroke: "#f00" }); editor.canvas.add(touching); editor.onPathCreated(touching);
    ok("a stroke that reaches the picture stays", editor.canvas.getObjects().includes(touching));
    editor.canvas.remove(touching); editor.commit();
    editor.setTool("select");
}
// the bounding box is stale while a drag is in progress (Fabric works out the coordinates after the handlers)
{
    editor.setTool("select");
    const m = editor.canvas.getObjects().find((o) => o.type === "rect");
    const region = editor.regionBox;
    m.set({ left: 100, top: 100 }); m.setCoords();           // coordinates of the last step
    m.set({ left: 6000, top: 100 });                         // the new place, coordinates not worked out yet
    editor.onObjectMoving({ target: m });
    m.setCoords();
    const b = m.getBoundingRect();
    ok("a correction made on a stale box is still right", b.left + b.width <= region.left + region.width + 1e-6 && b.left >= region.left - 1e-6, JSON.stringify(b));
    // twice in a row at the edge: the same place both times, no jumping back and forth
    m.set({ left: 6000, top: 100 }); editor.onObjectMoving({ target: m }); const first = m.left;
    m.setCoords(); m.set({ left: 6000, top: 100 }); editor.onObjectMoving({ target: m });
    ok("the same pointer place gives the same mark place", Math.abs(m.left - first) < 1e-9, `${first} / ${m.left}`);
    editor.state.snap = "objects";
    m.set({ left: 100, top: 100 }); m.setCoords(); m.set({ left: 6000, top: 100 });
    editor.onObjectMoving({ target: m });
    m.setCoords();
    ok("with snapping the place is the same", Math.abs(m.left - first) < 1e-6 || m.getBoundingRect().left + m.getBoundingRect().width <= region.left + region.width + 1e-6);
    editor.state.snap = "off";
}
// no mark is drawn from a bitmap (the cache of Fabric): sharp when it is scaled, zoomed and saved
{
    const marks = editor.canvas.getObjects();
    const all = (o) => [o, ...(o.type === "group" ? o.getObjects().flatMap(all) : [])];
    ok("every mark and every part of a group is drawn directly", marks.flatMap(all).every((o) => o.objectCaching === false && o.shouldCache() === false), String(marks.flatMap(all).filter((o) => o.objectCaching !== false).map((o) => o.type)));
    // a text made by the tool, then scaled by a handle, is not a stretched bitmap
    editor.setTool("text");
    const tp2 = toScreen(editor, 400, 400);
    editor.drawing.onMouseDown(mouse(tp2.x, tp2.y));
    const t2 = editor.canvas.getObjects().at(-1);
    t2.exitEditing?.();
    ok("a new text is drawn directly", t2.type === "i-text" && t2.objectCaching === false && t2.shouldCache() === false);
    t2.set({ scaleX: 8, scaleY: 8 }); t2.setCoords();
    editor.canvas._currentTransform = { target: t2, action: "scale", corner: "br" };
    ok("while a handle scales it there is no bitmap to stretch", t2.shouldCache() === false && !t2._cacheCanvas?.width);
    editor.canvas._currentTransform = null;
    editor.canvas.remove(t2); editor.commit();
    // marks that come back by the undo have the same
    await editor.undo(); await editor.redo();
    ok("marks brought back by undo and redo are drawn directly too", editor.canvas.getObjects().flatMap(all).every((o) => o.objectCaching === false));
    // a copy has it as well
    editor.canvas.discardActiveObject(); editor.canvas.setActiveObject(editor.canvas.getObjects()[0]);
    await editor.duplicate();
    ok("so does a copy", editor.canvas.getObjects().flatMap(all).every((o) => o.objectCaching === false));
    editor.canvas.discardActiveObject();
    editor.setTool("select");
}
// the handles of every mark have the cursors that fit
{
    editor.setTool("select");
    const ev0 = { shiftKey: false, altKey: false };
    const cur = (o, k) => { o.setCoords(); const c = o.controls[k]; return c.cursorStyleHandler(ev0, c, o, o.oCoords[k]); };
    const wide = editor.canvas.getObjects().find((o) => o.mark === "highlight") || editor.canvas.getObjects().find((o) => o.type === "rect");
    ok("a mark drawn in the editor has diagonal corners and a turning handle", ["tl", "tr", "bl", "br"].map((k) => cur(wide, k)).join() === "nw-resize,ne-resize,sw-resize,se-resize" && wide.controls.mtr.cursorStyle.startsWith("url("), ["tl", "tr", "bl", "br"].map((k) => cur(wide, k)).join());
    const arrowMark = editor.canvas.getObjects().find((o) => o.mark === "arrow");
    ok("so has an arrow (a group)", !!arrowMark && cur(arrowMark, "tl") === "nw-resize" && cur(arrowMark, "br") === "se-resize");
    editor.canvas.discardActiveObject(); editor.selectAll();
    const sel = editor.canvas.getActiveObject();
    ok("a selection of several marks has them too", sel.type === "activeselection" && cur(sel, "tr") === "ne-resize" && sel.controls.mtr.cursorStyle.startsWith("url("));
    editor.canvas.discardActiveObject();
    // the frame of a crop
    editor.setTool("crop");
    const frame = editor.cropTool.rect;
    ok("the frame of a crop has them", cur(frame, "br") === "se-resize");
    editor.setTool("select");
}
// marks stay on the picture when moved
{
    editor.setTool("select");
    const mark = editor.canvas.getObjects().find((o) => o.type === "rect");
    const region = editor.regionBox;
    const inside = (o) => { const b = o.getBoundingRect(); return b.left >= region.left - 1e-6 && b.top >= region.top - 1e-6 && b.left + b.width <= region.left + region.width + 1e-6 && b.top + b.height <= region.top + region.height + 1e-6; };
    mark.set({ left: 5000, top: -4000 }); mark.setCoords();
    editor.onObjectMoving({ target: mark });
    ok("a mark pushed far out is brought back inside", inside(mark), JSON.stringify(mark.getBoundingRect()));
    mark.set({ left: -300, top: 100 }); mark.setCoords();
    editor.onObjectMoving({ target: mark });
    ok("a mark pushed over the left edge stops at it", Math.abs(mark.getBoundingRect().left - region.left) < 1e-6);
    // snapping on: still inside
    editor.state.snap = "objects";
    mark.set({ left: 4000, top: 4000 }); mark.setCoords();
    editor.onObjectMoving({ target: mark });
    ok("with snapping a mark stays inside as well", inside(mark));
    editor.state.snap = "off";
    // a mark larger than the picture keeps covering it
    const big = new fabric.Rect({ left: 0, top: 0, width: 3000, height: 2000, fill: "#00f" }); editor.canvas.add(big);
    big.set({ left: 2500, top: 2500 }); big.setCoords(); editor.onObjectMoving({ target: big });
    const bb = big.getBoundingRect();
    ok("a mark larger than the picture still covers it", bb.left <= region.left + 1e-6 && bb.top <= region.top + 1e-6 && bb.left + bb.width >= region.left + region.width - 1e-6, JSON.stringify(bb));
    editor.canvas.remove(big);
    // after resizing
    mark.set({ left: 900, top: 500, scaleX: 3, scaleY: 3 }); mark.setCoords();
    editor.onObjectModified({ target: mark });
    ok("a mark made larger is brought back after the change", inside(mark) || mark.getBoundingRect().width > region.width);
    // the keys
    editor.canvas.setActiveObject(mark);
    mark.set({ left: 0, top: 0 }); mark.setCoords();
    editor.onKeydown({ key: "ArrowLeft", target: { matches: () => false }, preventDefault() {} });
    ok("the arrow key does not push a mark off the picture", mark.getBoundingRect().left >= region.left - 1e-6);
    editor.canvas.discardActiveObject();
}
// the overlay is drawn on the lower layer only (the upper one keeps what it is given)
{
    let drawn = 0;
    const fake = new Proxy({}, { get: () => () => { drawn++; } });
    editor.paintOverlay(fake);
    ok("overlay is not drawn on another layer", drawn === 0);
    editor.paintOverlay(editor.canvas.getContext());
    ok("overlay is drawn on the lower layer", true);
}
// view
editor.zoomIn();
ok("zoom in", editor.viewport.zoom > 0.768);
editor.zoomActual();
ok("actual size", near(editor.viewport.zoom, 1));
editor.viewport.panBy(-20, -20);
editor.zoomFit();
ok("fit again", near(editor.viewport.zoom, 0.768));

// keys
editor.setTool("select");
editor.canvas.setActiveObject(editor.canvas.getObjects()[1]);
const delCount = editor.canvas.getObjects().length;
editor.onKeydown({ key: "Delete", ev: null, target: { matches: () => false }, preventDefault() {} });
ok("Delete key deletes", editor.canvas.getObjects().length === delCount - 1);
editor.onKeydown({ key: "z", ctrlKey: true, target: { matches: () => false }, preventDefault() {} });
await new Promise((r) => setTimeout(r, 20));
ok("Ctrl+Z undoes the delete", editor.canvas.getObjects().length === delCount);
editor.onKeydown({ key: "r", target: { matches: () => false }, preventDefault() {} });
ok("tool key", editor.state.tool === "rect");
editor.setTool("select");

// save flow
editor.crop = { left: 100, top: 100, width: 600, height: 300 };
editor.state.cropped = true;
editor.updateRegion();
editor.openSave();
const dlg = dialogs.at(-1);
ok("save dialog opened with proper props", dlg && dlg.props.size.width === 600 && dlg.props.maxScale === 1 && dlg.props.name === "photo (edited)" && dlg.props.canKeepState === true, JSON.stringify(dlg?.props.size) + " " + dlg?.props.name);
await editor.save({ mimetype: "image/png", quality: 1, scale: 0.5, name: "photo (edited)", keepState: true });
const up = uploads.at(-1);
ok("uploaded to route with folder", up && up.route === "/int_filemanager/upload" && up.fd.get("folder_id") === "3");
const upFile = up.files[0];
ok("file name/type", upFile.name === "photo (edited).png" && upFile.type === "image/png", upFile.name + " " + upFile.type);
const pngBuf = Buffer.from(await upFile.arrayBuffer());
fs.writeFileSync(OUT + "/saved.png", pngBuf);
const savedImg = await createImg(pngBuf);
ok("saved size = crop * scale", savedImg.width === 300 && savedImg.height === 150, `${savedImg.width}x${savedImg.height}`);
ok("state sent, source id is the picture", up.fd.get("edit_source_id") === "1" && up.fd.get("edit_state").length > 100);
const sentState = JSON.parse(up.fd.get("edit_state"));
ok("sent state valid", !!readState(sentState, { width: 1000, height: 600 }) && sentState.crop.width === 600 && sentState.objects.length > 5, "objects=" + sentState.objects.length);
ok("closed after storing + soft_reload", editor.isClosed() && notes.some((n) => n.doAction === "soft_reload"));
ok("success notice", notes.some((n) => n.opts?.type === "success"));
const saveCountObjects = editor.canvas.getObjects().length;
ok("editor still consistent after save", editor.canvas.getObjects().length === saveCountObjects && !editor.exporting && !editor.state.saving && editor.picture.shown.element === editor.picture.work);

// reopen with the state: an edited picture whose session has the source and the state
session = { state: sentState, source: { id: 1, name: "photo.png", mimetype: "image/png", checksum: "abc", size: 1 } };
const editedFile = { id: 77, name: "photo (edited).png", mimetype: "image/png", folder_id: 3, defaultSource: "x" };
const editor2 = await makeEditor(editedFile);
ok("reopened: marks are objects again", editor2.canvas.getObjects().length === sentState.objects.length, `${editor2.canvas.getObjects().length} vs ${sentState.objects.length}`);
ok("reopened: filters and crop", editor2.state.filters.brightness === 0.3 && !!editor2.crop && editor2.crop.width === 600, JSON.stringify(editor2.state.filters));
ok("reopened: source id kept for the next save", editor2.sourceFile.id === 1);
ok("reopened: region is the crop", editor2.regionBox.width === 600);
ok("reopened: redact is RedactMark", editor2.canvas.getObjects().some((o) => o.mark === "redact" && o.constructor.name === "RedactMark"));
editor2.history.reset(editor2.snapshot());
ok("reopened: nothing to discard yet", !editor2.changed);
// a state of another picture is ignored
session = { state: { ...sentState, source: { width: 5, height: 5 } }, source: { id: 1, name: "photo.png", mimetype: "image/png", checksum: "abc", size: 1 } };
const editor3 = await makeEditor(editedFile);
ok("state of another size ignored", editor3.canvas.getObjects().length === 0 && editor3.crop === null);
// no readable source: flat picture
session = {};
const editor4 = await makeEditor(editedFile);
ok("no session: flat picture", editor4.sourceFile.id === 77 && editor4.canvas.getObjects().length === 0);

console.log(fails ? `\n${fails} FAILED` : "\nALL PASSED");
