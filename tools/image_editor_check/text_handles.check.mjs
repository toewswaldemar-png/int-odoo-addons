import "./env.mjs";
globalThis.ResizeObserver = class { observe() {} disconnect() {} };
globalThis.requestAnimationFrame = (f) => setTimeout(f, 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
const W = 3000, H = 4000;
globalThis.__loadPicture = async () => { const c = napi.createCanvas(W, H); c.naturalWidth = W; c.naturalHeight = H; return c; };
globalThis.__services = { dialog: {}, notification: { add() {} }, action: {}, orm: { call: async () => ({}) }, ui: { isSmall: false }, file_upload: {} };
const { DocumentImageEditor } = await import("@int_filemanager_image_editor/image_editor/document_image_editor");
const stage = document.createElement("div");
Object.defineProperty(stage, "clientWidth", { value: 1000 }); Object.defineProperty(stage, "clientHeight", { value: 700 });
const cv = document.createElement("canvas"); stage.appendChild(cv); document.body.appendChild(stage);
globalThis.__refs = { root: { el: { focus() {} } }, canvas: { el: cv }, stage: { el: stage }, import: { el: {} } };
const ed = new DocumentImageEditor({ file: { id: 1, name: "p.jpg", mimetype: "image/jpeg", folder_id: 1, defaultSource: "x" }, close() {} });
await ed.start();
const { canvas } = ed;
let fails = 0;
const ok = (n, c, x = "") => { console.log((c ? "PASS " : "FAIL ") + n + (x ? "  " + x : "")); if (!c) fails++; };
const Wd = window;
const mouse = (type, target, x, y, extra = {}) => target.dispatchEvent(new Wd.MouseEvent(type, { clientX: x, clientY: y, button: 0, bubbles: true, cancelable: true, view: Wd, ...extra }));
function drag(t, handle, dx, dy, extra = {}) {
  t.setCoords();
  const p = t.oCoords[handle];
  mouse("mousedown", canvas.upperCanvasEl, p.x, p.y, extra);
  mouse("mousemove", Wd.document, p.x + dx / 2, p.y + dy / 2, extra);
  mouse("mousemove", Wd.document, p.x + dx, p.y + dy, extra);
  mouse("mouseup", Wd.document, p.x + dx, p.y + dy, extra);
}
const sp = (x, y) => { const [z, , , , e, f] = canvas.viewportTransform; return { x: x * z + e, y: y * z + f }; };
function addText(kind, x, y) {
  ed.setTool(kind);
  const p = sp(x, y);
  ed.drawing.onMouseDown({ e: { clientX: p.x, clientY: p.y, shiftKey: false }, target: undefined });
  const t = canvas.getObjects().at(-1);
  t.exitEditing?.();
  canvas.setActiveObject(t); t.setCoords();
  return t;
}
console.log("canvas uniScaleKey:", canvas.uniScaleKey, "| uniformScaling:", canvas.uniformScaling);

// ---- a line of text
const it = addText("text", 1000, 1500);
ok("IText: side handles are hidden, corners and the turning handle stay", ["ml", "mr", "mt", "mb"].every((k) => !it.isControlVisible(k)) && ["tl", "tr", "bl", "br", "mtr"].every((k) => it.isControlVisible(k)));
const fs0 = it.fontSize;
drag(it, "br", 40, 15);
ok("a corner scales it alike and the scale becomes the font size", it.scaleX === 1 && it.scaleY === 1 && it.fontSize > fs0, `fontSize ${fs0} -> ${it.fontSize.toFixed(1)} scale ${it.scaleX}x${it.scaleY}`);
canvas.setActiveObject(it); ed.syncSelection();
ok("the panel's size is the size the text has (in units)", ed.state.style.textSize === Math.round(it.fontSize / ed.unit), `${ed.state.style.textSize} vs ${Math.round(it.fontSize / ed.unit)}`);
const fs1 = it.fontSize;
drag(it, "br", 40, 5, { shiftKey: true });
ok("Shift on a corner does not stretch it either", it.scaleX === 1 && it.scaleY === 1 && it.fontSize > fs1, `fontSize ${fs1.toFixed(1)} -> ${it.fontSize.toFixed(1)}`);
const before = { left: it.left, top: it.top, w: it.width, sx: it.scaleX };
drag(it, "mr", 60, 0);
ok("where the side handle was nothing is stretched", it.scaleX === 1 && it.scaleY === 1, `scale ${it.scaleX}x${it.scaleY}`);
ok("glyph aspect stays as the font has it", it.scaleX === it.scaleY);

// ---- a text box
const tb = addText("textbox", 1000, 2200);
ok("Textbox: top and bottom handles are hidden, left and right stay", ["mt", "mb"].every((k) => !tb.isControlVisible(k)) && ["ml", "mr", "tl", "tr", "bl", "br", "mtr"].every((k) => tb.isControlVisible(k)));
const w0 = tb.width, f0 = tb.fontSize;
drag(tb, "mr", 60, 0);
ok("the right handle makes it wider, the letters stay", tb.width > w0 && tb.scaleX === 1 && tb.scaleY === 1 && tb.fontSize === f0, `width ${Math.round(w0)} -> ${Math.round(tb.width)} fontSize ${tb.fontSize}`);
const w1 = tb.width;
drag(tb, "br", 80, 40);
ok("a corner: the font size and the width grow together, the scale is 1", tb.scaleX === 1 && tb.scaleY === 1 && tb.fontSize > f0 && tb.width > w1, `fontSize ${f0} -> ${tb.fontSize.toFixed(1)}, width ${Math.round(w1)} -> ${Math.round(tb.width)}`);
const ratio = tb.fontSize / f0, widthRatio = tb.width / w1;
ok("wrapping stays as it was: both grew by the same factor", Math.abs(ratio - widthRatio) < 0.02, `${ratio.toFixed(3)} vs ${widthRatio.toFixed(3)}`);
// text the panel reads
canvas.setActiveObject(tb); ed.syncSelection();
ok("the controls of the panel show the size it has", ed.state.style.textSize === Math.round(tb.fontSize / ed.unit), `${ed.state.style.textSize}`);

// ---- shapes are not changed by this
ed.setTool("rect");
const p1 = sp(1000, 2900), p2 = sp(1400, 3100);
ed.drawing.onMouseDown({ e: { clientX: p1.x, clientY: p1.y, shiftKey: false }, target: undefined });
ed.drawing.onMouseMove({ e: { clientX: p2.x, clientY: p2.y, shiftKey: false } });
ed.drawing.onMouseUp();
ed.setTool("select");
const rect = canvas.getObjects().at(-1); canvas.setActiveObject(rect); rect.setCoords();
ok("a rectangle keeps all its handles", ["ml", "mr", "mt", "mb", "tl", "br"].every((k) => rect.isControlVisible(k)));
drag(rect, "mr", 50, 0);
ok("and its side handle still stretches it", rect.scaleX > 1 && rect.scaleY === 1, `scale ${rect.scaleX.toFixed(2)}x${rect.scaleY}`);
// undo brings a text back with the handles chosen and the size baked
const before2 = canvas.getObjects().length;
await ed.undo(); await ed.redo();
const back = canvas.getObjects().find((o) => o.type === "textbox");
ok("a text brought back by undo has the same handles and size", back && !back.isControlVisible('mt') && back.isControlVisible('mr') && Math.abs(back.fontSize - tb.fontSize) < 1e-6, back && String(back.fontSize));
console.log(fails ? `${fails} FAILED` : "ALL PASSED");
process.exit(fails ? 1 : 0);
