import "./env.mjs";
import { OUT } from "./paths.mjs";
import fs from "node:fs";
const IE = "@int_filemanager_image_editor/image_editor/";
const { Picture, canvasFits } = await import(IE + "picture");
const marks = await import(IE + "marks");
const { RedactMark } = await import(IE + "redact_mark");
const state = await import(IE + "edit_state");
const arrange = await import(IE + "arrange");
const ops = await import(IE + "scene_ops");
const exp = await import(IE + "export");
const { Viewport } = await import(IE + "viewport");
const flt = await import(IE + "filters");
const f = fabric;
let fails = 0;
const ok = (name, cond, extra = "") => {
    console.log((cond ? "PASS " : "FAIL ") + name + (extra ? "  " + extra : ""));
    if (!cond) fails++;
};
const near = (a, b, eps = 1e-6) => Math.abs(a - b) < eps;

// a picture 1000x600 with a checker and colours
const el = napi.createCanvas(1000, 600);
const c = el.getContext("2d");
c.fillStyle = "#3366cc";
c.fillRect(0, 0, 1000, 600);
for (let y = 0; y < 600; y += 20)
    for (let x = 0; x < 1000; x += 20) {
        if (((x + y) / 20) % 2) {
            c.fillStyle = "#ffffff";
            c.fillRect(x, y, 20, 20);
        }
    }
c.fillStyle = "#cc3333";
c.fillRect(0, 0, 100, 100);
const picture = new Picture(el, 500);
ok("working copy scale", picture.scale === 0.5, "scale=" + picture.scale);
ok("scene size", picture.sceneSize.width === 1000 && picture.sceneSize.height === 600);
picture.resetPlacement();

const canvasEl = document.createElement("canvas");
const canvas = new f.Canvas(canvasEl, { width: 800, height: 500, renderOnAddRemove: false });
canvas.backgroundImage = picture.image;
const stage = { clientWidth: 800, clientHeight: 500 };
const vp = new Viewport(canvas, stage);
vp.setRegion({ left: 0, top: 0, width: 1000, height: 600 });
ok("viewport fit zoom", near(vp.zoom, 768 / 1000), "zoom=" + vp.zoom);
const sceneBefore = { x: (400 - canvas.viewportTransform[4]) / vp.zoom, y: (250 - canvas.viewportTransform[5]) / vp.zoom };
vp.zoomBy(2, { x: 400, y: 250 });
const sceneAfter = { x: (400 - canvas.viewportTransform[4]) / vp.zoom, y: (250 - canvas.viewportTransform[5]) / vp.zoom };
ok("zoom keeps the point under the pointer", near(sceneBefore.x, sceneAfter.x, 1e-6) && near(sceneBefore.y, sceneAfter.y, 1e-6), JSON.stringify([sceneBefore, sceneAfter]));
vp.fit();

const unit = 1;
const style = { ...marks.DEFAULT_STYLE };
const draft = marks.createDraft("rect", { x: 200, y: 200 }, { ...style, fillMode: "gradient" }, unit);
marks.updateDraft("rect", draft, { x: 200, y: 200 }, { x: 400, y: 320 }, false);
canvas.add(draft);
const arrow = marks.createArrow({ x: 100, y: 500 }, { x: 400, y: 450 }, style, unit);
canvas.add(arrow);
const text = marks.createText("textbox", { x: 500, y: 100 }, "Hello", { ...style, bold: true, textSize: 40 }, unit, 1000);
canvas.add(text);
const red = marks.createDraft("redact", { x: 0, y: 0 }, style, unit);
marks.updateDraft("redact", red, { x: 0, y: 0 }, { x: 140, y: 140 }, false);
canvas.add(red);
const poly = marks.createPolyMark("polygon", [{ x: 600, y: 300 }, { x: 700, y: 300 }, { x: 650, y: 400 }], { ...style, fillMode: "solid" }, unit);
canvas.add(poly);
const kinds = [draft, arrow, text, red, poly].map(marks.kindOf).join();
ok("kinds", kinds === "rect,arrow,text,redact,polygon", kinds);

const strokeStyle = { ...style, stroke: "#00AA00", width: 10, dash: "dashed", radius: 8 };
marks.applyStyle(draft, { stroke: "#00AA00", width: 10, dash: "dashed", radius: 8 }, strokeStyle, unit);
const read = marks.readStyle(draft, unit);
ok("readStyle after apply", read.stroke === "#00AA00" && read.width === 10 && read.dash === "dashed" && read.radius === 8 && read.fillMode === "gradient", JSON.stringify(read).slice(0, 200));
marks.applyStyle(arrow, { stroke: "#112233", width: 8 }, { ...style, stroke: "#112233", width: 8 }, unit);
ok("arrow restyle", marks.readStyle(arrow, unit).stroke === "#112233" && arrow.getObjects()[1].fill === "#112233");
marks.applyStyle(text, { font: "serif", textSize: 60, italic: true }, { ...style, font: "serif", textSize: 60, italic: true }, unit);
const tr = marks.readStyle(text, unit);
ok("text restyle", tr.font === "serif" && tr.textSize === 60 && tr.italic === true && tr.bold === true, JSON.stringify(tr).slice(0, 160));
const shadowStyle = { ...style, opacity: 0.5, shadow: { on: true, color: "#000000", blur: 6, offset: 3 } };
marks.applyStyle(poly, { opacity: 0.5, shadow: shadowStyle.shadow }, shadowStyle, unit);
ok("opacity+shadow", poly.opacity === 0.5 && poly.shadow && poly.shadow.blur === 6);

let filters = flt.withSetting({}, "brightness", 0.2);
filters = flt.withSetting(filters, "sepia", true);
picture.setFilters(filters);
ok("filters built", picture.image.filters.length === 2, String(picture.image.filters.length));
const crop = { left: 10, top: 20, width: 800, height: 400 };
const built = state.buildState({ picture, canvas, filters, crop });
const json = JSON.stringify(built);
ok("state size reasonable", json.length < 40000, "bytes=" + json.length);
const parsed = state.readState(JSON.parse(json), picture.size);
ok("readState ok", parsed && parsed.objects.length === 5 && parsed.filters.sepia === true && parsed.crop.width === 800);
ok("readState wrong size -> null", state.readState(JSON.parse(json), { width: 1, height: 1 }) === null);
const revived = await state.reviveObjects(parsed.objects);
ok("revive count/types", revived.length === 5 && revived[3] instanceof RedactMark && revived[1].type === "group", revived.map((o) => o.type).join());
ok("arrow mark survives", revived[1].mark === "arrow" && revived[1].getObjects()[1].mark === "arrowhead");
ok("gradient survives", revived[0].fill instanceof f.Gradient);
const evil = [
    { type: "Image", src: "http://evil.example/x.png" },
    { type: "Rect", clipPath: { type: "Image", src: "http://x" }, width: 5, height: 5 },
    { type: "Bogus" },
    { type: "Image", src: "data:image/png;base64,iVBORw0KGgo=" },
];
const cleaned = state.cleanObjects(evil);
ok("untrusted objects filtered", cleaned.length === 2 && !("clipPath" in cleaned[0]), JSON.stringify(cleaned.map((o) => o.type)));

const before = text.getCenterPoint();
const crop1 = ops.turnScene(canvas, picture, crop);
ok("turn: scene size swapped", picture.sceneSize.width === 600 && picture.sceneSize.height === 1000, JSON.stringify(picture.sceneSize));
const after = text.getCenterPoint();
ok("turn: text center moved (H - y, x)", near(after.x, 600 - before.y) && near(after.y, before.x), `${before.x},${before.y} -> ${after.x},${after.y}`);
ok("turn: crop turned", near(crop1.width, 400) && near(crop1.height, 800), JSON.stringify(crop1));
const bc = picture.image.getCenterPoint();
ok("turn: picture center", near(bc.x, 300) && near(bc.y, 500), `${bc.x},${bc.y}`);
for (let i = 0; i < 3; i++) ops.turnScene(canvas, picture, null);
ok("4 turns = identity", near(text.getCenterPoint().x, before.x) && near(text.getCenterPoint().y, before.y) && picture.sceneSize.width === 1000);
const rc = red.getCenterPoint();
ops.flipScene(canvas, picture, null, true);
ok("flip: redact center mirrored", near(red.getCenterPoint().x, 1000 - rc.x) && red.flipX === true);
ok("flip: text not mirrored", text.flipX === false);
ops.flipScene(canvas, picture, null, true);
ok("flip twice = identity", near(red.getCenterPoint().x, rc.x) && red.flipX === false);

arrange.select(canvas, [draft, poly]);
arrange.group(canvas);
ok("group created", canvas.getActiveObject()?.type === "group" && canvas.getObjects().length === 4, "objs=" + canvas.getObjects().length);
arrange.ungroup(canvas); canvas.discardActiveObject();
ok("ungroup restores", canvas.getObjects().length === 5 && near(draft.left, 200) && near(poly.getBoundingRect().left, 600 - 0.5 * 0 - poly.strokeWidth / 2 * 0, 6), `draft.left=${draft.left} poly.left=${poly.getBoundingRect().left}`);
arrange.select(canvas, [draft]);
arrange.align(canvas, "left", { left: 0, top: 0, width: 1000, height: 600 });
ok("align left", near(draft.getBoundingRect().left, 0), "left=" + draft.getBoundingRect().left);
arrange.select(canvas, [draft]);
arrange.order(canvas, "back");
ok("order back", canvas.getObjects()[0] === draft);
const before2 = draft.left;
const copies = await arrange.duplicate(canvas, 20);
ok("duplicate", copies.length === 1 && canvas.getObjects().length === 6 && near(copies[0].left, before2 + 20), `n=${canvas.getObjects().length}`);
arrange.setLocked(draft, true);
ok("lock", draft.lockMovementX && arrange.isLocked(draft));

canvas.discardActiveObject();
canvas.getObjects().forEach((o) => { o.objectCaching = false; o.getObjects?.().forEach((q) => (q.objectCaching = false)); });
const blob = await exp.renderBlob({ canvas, picture, region: { left: 0, top: 0, width: 1000, height: 600 }, scale: 1, mimetype: "image/png", quality: 1 });
const buf = Buffer.from(await blob.arrayBuffer());
fs.writeFileSync(OUT + "/full.png", buf);
const im = await createImg(buf);
ok("export png size", im.width === 1000 && im.height === 600, `${im.width}x${im.height}`);
const blob2 = await exp.renderBlob({ canvas, picture, region: { left: 100, top: 100, width: 400, height: 300 }, scale: 0.5, mimetype: "image/jpeg", quality: 0.8 });
const im2 = await createImg(Buffer.from(await blob2.arrayBuffer()));
ok("export cropped+scaled jpeg size", im2.width === 200 && im2.height === 150, `${im2.width}x${im2.height}`);
ok("picture back to copy after export", picture.shown.element === picture.work);
const svg = await exp.renderSvg({ canvas, picture, region: { left: 0, top: 0, width: 1000, height: 600 }, scale: 0.5 });
const svgText = await svg.text();
ok("svg export", svgText.startsWith("<?xml") && svgText.includes("<image") && svgText.includes('viewBox="0 0 1000 600"'), svgText.slice(0, 160).replace(/\n/g, " "));
ok("picture back to copy after svg", picture.shown.element === picture.work && near(picture.image.scaleX, 2));
ok("canvasFits small", canvasFits(100, 100) === true);
console.log(fails ? `\n${fails} FAILED` : "\nALL PASSED");
