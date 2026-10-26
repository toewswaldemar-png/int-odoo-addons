import "./env.mjs";
const IE = "@int_filemanager_image_editor/image_editor/";
const { importFile, placeInMiddle, isImportable } = await import(IE + "import_image");
const { reviveObjects, cleanObjects } = await import(IE + "edit_state");
const { MARK_PROPS } = await import(IE + "constants");
let fails = 0;
const ok = (n, c, x = "") => { console.log((c ? "PASS " : "FAIL ") + n + (x ? "  " + x : "")); if (!c) fails++; };
ok("importable types", isImportable({ type: "image/svg+xml" }) && isImportable({ type: "image/png" }) && !isImportable({ type: "text/html" }));
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100"><rect x="0" y="0" width="100" height="100" fill="#ff0000"/><circle cx="150" cy="50" r="40" fill="#00ff00"/></svg>`;
const file = new File([svg], "logo.svg", { type: "image/svg+xml" });
const stamp = await importFile(file);
ok("svg becomes one object with the mark 'stamp'", stamp.mark === "stamp" && ["group", "rect", "circle", "path"].includes(stamp.type), stamp.type + " " + stamp.width + "x" + stamp.height);
placeInMiddle(stamp, { left: 0, top: 0, width: 1000, height: 600 }, 0.4);
const c = stamp.getCenterPoint();
ok("placed in the middle, scaled to 40%", Math.abs(c.x - 500) < 1e-6 && Math.abs(c.y - 300) < 1e-6 && Math.abs(stamp.getScaledWidth() - 400) < 1 || Math.abs(stamp.getScaledHeight() - 240) < 1, `${c.x},${c.y} ${stamp.getScaledWidth()}x${stamp.getScaledHeight()}`);
const plain = JSON.parse(JSON.stringify(stamp.toObject(MARK_PROPS)));
const [back] = await reviveObjects([plain]);
ok("stamp survives the state filter", !!back && back.mark === "stamp", back && back.type);
// an svg with external references is cleaned before Fabric reads it
const { sanitizeSvg } = await import(IE + "import_image");
const evil = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="50" height="50" onload="alert(1)"><script>alert(1)</script><image xlink:href="http://evil.example/x.png" width="50" height="50"/><image href="data:image/png;base64,AAAA" width="5" height="5"/><use xlink:href="#a"/><rect id="a" width="10" height="10" fill="url(http://evil.example/g.svg#x)" stroke="url(#local)" onclick="x()"/><style>@import url(http://evil.example/s.css); .a{fill:url(http://evil.example/p.png)} .b{fill:url(#ok)}</style></svg>`;
const cleaned = sanitizeSvg(evil);
ok("no external address left", !cleaned.includes("evil.example"), cleaned.slice(0, 200));
ok("scripts and handlers gone", !cleaned.includes("<script") && !cleaned.includes("onload") && !cleaned.includes("onclick"));
ok("data pictures and local links kept", cleaned.includes("data:image/png") && cleaned.includes('xlink:href="#a"') && cleaned.includes("url(#local)") && cleaned.includes("url(#ok)"));
let threw = false; try { sanitizeSvg("<svg><not closed"); } catch { threw = true; }
ok("a broken drawing is refused", threw);
const evil2 = evil.replace(/<image[^>]*data:image[^>]*\/>/, "");
const s2 = await Promise.race([importFile(new File([evil2], "e.svg", { type: "image/svg+xml" })), new Promise((_, r) => setTimeout(() => r(new Error("timeout")), 3000))]);
ok("the cleaned drawing imports without waiting for a server", !!s2 && s2.mark === "stamp");
try { await importFile(new File(["x".repeat(3 * 1024 * 1024)], "big.svg", { type: "image/svg+xml" })); ok("big drawing refused", false); } catch { ok("big drawing refused", true); }
try { await importFile(new File(["<svg xmlns='http://www.w3.org/2000/svg'/>"], "empty.svg", { type: "image/svg+xml" })); ok("empty drawing refused", false); } catch { ok("empty drawing refused", true); }
console.log(fails ? `${fails} FAILED` : "ALL PASSED");
process.exit(fails ? 1 : 0);
