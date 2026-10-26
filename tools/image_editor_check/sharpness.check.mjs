import "./env.mjs";
import fs from "node:fs";
const f = fabric;
// A big mark on a big picture, saved at full size: does the cache cap the quality of the file?
function render(caching) {
  const canvas = new f.Canvas(document.createElement("canvas"), { width: 3000, height: 1400 });
  const t = new f.IText("Hy", { left: 100, top: 50, fontSize: 1100, fontFamily: "sans-serif", fontWeight: "bold", fill: "#d00000", objectCaching: caching });
  canvas.add(t); t.setCoords();
  const raw = t._getCacheCanvasDimensions();
  const lim = t._limitCacheSize({ ...raw });
  const out = canvas.toCanvasElement(1, { left: 0, top: 0, width: 3000, height: 1400 });
  return { out, info: { caching, needed: `${raw.width}x${raw.height}`, cacheWould: `${lim.width}x${lim.height}`, resolution: (lim.zoomX / raw.zoomX * 100).toFixed(0) + "%", capped: !!lim.capped } };
}
const a = render(true), b = render(false);
console.log(JSON.stringify(a.info)); console.log(JSON.stringify(b.info));

const { drawDirectly } = await import("@int_filemanager_image_editor/image_editor/marks");
function renderEditorWay() {
  const canvas = new f.Canvas(document.createElement("canvas"), { width: 3000, height: 1400 });
  const t = new f.IText("Hy", { left: 100, top: 50, fontSize: 1100, fontFamily: "sans-serif", fontWeight: "bold", fill: "#d00000" });
  canvas.add(t); drawDirectly(t); t.setCoords();
  return canvas.toCanvasElement(1, { left: 0, top: 0, width: 3000, height: 1400 });
}
function stats(cv) {
  const d = cv.getContext("2d").getImageData(0, 0, 3000, 1400).data; let solid = 0, partial = 0;
  for (let i = 3; i < d.length; i += 4) { if (d[i] > 250) solid++; else if (d[i] > 5) partial++; }
  return { solid, partial };
}
const sa = stats(a.out), sb = stats(renderEditorWay());
console.log("cached      ", JSON.stringify(sa), (sa.partial / (sa.solid + sa.partial) * 100).toFixed(2) + " % edge pixels");
console.log("editor (drawDirectly)", JSON.stringify(sb), (sb.partial / (sb.solid + sb.partial) * 100).toFixed(2) + " % edge pixels");
let fails = 0;
const ok = (n, c, x = "") => { console.log((c ? "PASS " : "FAIL ") + n + (x ? "  " + x : "")); if (!c) fails++; };
ok("a large mark of the editor is sharper in the file than a cached one", sb.partial < sa.partial * 0.6, `${sb.partial} vs ${sa.partial}`);
process.exit(fails ? 1 : 0);
