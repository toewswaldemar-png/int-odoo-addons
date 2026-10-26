import "./env.mjs";
import { OUT } from "./paths.mjs";
import fs from "node:fs";
const f = fabric;
const { styleHandles, cornerCursor, ROTATE_CURSOR } = await import("@int_filemanager_image_editor/image_editor/controls");
const canvas = new f.Canvas(document.createElement("canvas"), { width: 800, height: 600 });
const ev = { shiftKey: false, altKey: false };
let fails = 0;
const ok = (n, c, x = "") => { console.log((c ? "PASS " : "FAIL ") + n + (x ? "  " + x : "")); if (!c) fails++; };
function cursors(obj) {
  canvas.add(obj); styleHandles(obj); obj.setCoords();
  const out = {};
  for (const k of ["tl", "tr", "bl", "br"]) { const c = obj.controls[k]; out[k] = c.cursorStyleHandler(ev, c, obj, obj.oCoords[k]); }
  return out;
}
const diag = { tl: "nw-resize", tr: "ne-resize", bl: "sw-resize", br: "se-resize" };
for (const [name, o] of [
  ["square", new f.Rect({ left: 300, top: 200, width: 100, height: 100 })],
  ["wide rect", new f.Rect({ left: 200, top: 200, width: 400, height: 20 })],
  ["tall rect", new f.Rect({ left: 100, top: 100, width: 20, height: 300 })],
  ["line", new f.Line([100, 100, 400, 120])],
  ["flipped wide rect", new f.Rect({ left: 200, top: 200, width: 400, height: 20, flipX: true })],
  ["wide text", new f.IText("A long line of text here", { left: 50, top: 50 })],
  ["textbox", new f.Textbox("Box", { left: 50, top: 400, width: 300 })],
  ["ellipse", new f.Ellipse({ left: 400, top: 400, rx: 200, ry: 10 })],
]) {
  const c = cursors(o);
  ok(name + ": the corners are diagonal whatever the shape", JSON.stringify(c) === JSON.stringify(diag), JSON.stringify(c));
}
// turned objects: the corner cursor follows the angle (quantized to 45 degrees)
const expected = { 0: diag, 45: { tl: "n-resize", tr: "e-resize", bl: "w-resize", br: "s-resize" }, 90: { tl: "ne-resize", tr: "se-resize", bl: "nw-resize", br: "sw-resize" }, 180: { tl: "se-resize", tr: "sw-resize", bl: "ne-resize", br: "nw-resize" } };
for (const [angle, want] of Object.entries(expected)) {
  const o = new f.Rect({ left: 400, top: 300, width: 400, height: 20, angle: Number(angle) });
  const c = cursors(o);
  ok(`wide rect at ${angle} degrees`, JSON.stringify(c) === JSON.stringify(want), JSON.stringify(c));
}
// the pure function
ok("cornerCursor is independent of the size", cornerCursor({ x: -0.5, y: -0.5 }, 0) === "nw-resize" && cornerCursor({ x: 0.5, y: 0.5 }, 90) === "sw-resize" && cornerCursor({ x: -0.5, y: 0.5 }, -90) === "se-resize");
// the rotation handle
const o2 = new f.Rect({ left: 10, top: 10, width: 50, height: 50 }); canvas.add(o2); styleHandles(o2); o2.setCoords();
const m = o2.controls.mtr;
ok("the rotation handle has a turning cursor", m.cursorStyleHandler(ev, m, o2, o2.oCoords.mtr) === ROTATE_CURSOR && ROTATE_CURSOR.startsWith('url("data:image/svg+xml,') && ROTATE_CURSOR.endsWith(") 12 12, crosshair"));
// locked scaling stays not allowed
const locked = new f.Rect({ left: 10, top: 10, width: 50, height: 50, lockScalingX: true, lockScalingY: true }); canvas.add(locked); styleHandles(locked); locked.setCoords();
const tl = locked.controls.tl;
ok("a mark that cannot be scaled keeps Fabric's 'not allowed'", tl.cursorStyleHandler(ev, tl, locked, locked.oCoords.tl) === "not-allowed");
const lockedRot = new f.Rect({ left: 10, top: 10, width: 50, height: 50, lockRotation: true }); canvas.add(lockedRot); styleHandles(lockedRot); lockedRot.setCoords();
ok("a mark that cannot be turned: 'not allowed' on the turning handle", (() => { const h = lockedRot.controls.mtr; return h.cursorStyleHandler(ev, h, lockedRot, lockedRot.oCoords.mtr) === "not-allowed"; })());
// styling twice does not wrap twice
const again = new f.Rect({ left: 0, top: 0, width: 300, height: 10 }); canvas.add(again); styleHandles(again); styleHandles(again); again.setCoords();
const c1 = again.controls.tr;
ok("styling twice gives the same answer", c1.cursorStyleHandler(ev, c1, again, again.oCoords.tr) === "ne-resize");
// draw the cursor so that it can be looked at
const img = await createImg(Buffer.from(decodeURIComponent(ROTATE_CURSOR.match(/svg\+xml,([^"]*)"/)[1])));
const cv = napi.createCanvas(96, 96); const cx = cv.getContext("2d"); cx.fillStyle = "#c8a46e"; cx.fillRect(0, 0, 96, 96); cx.fillStyle = "#222"; cx.fillRect(48, 0, 48, 96); cx.drawImage(img, 0, 0, 96, 96);
fs.writeFileSync(OUT + "/rotate_cursor.png", cv.toBuffer("image/png"));
console.log(fails ? `${fails} FAILED` : "ALL PASSED");
process.exit(fails ? 1 : 0);
