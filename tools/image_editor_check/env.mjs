// The browser the checks run in: jsdom, the real Fabric, and a canvas that draws (jsdom has none; the
// canvas of @napi-rs/canvas is put behind every canvas element). Every check starts with
// `import "./env.mjs"`.
import fs from "node:fs";
import { FABRIC, requireModule } from "./paths.mjs";

const { JSDOM } = requireModule("jsdom");
const napi = requireModule("@napi-rs/canvas");
const dom = new JSDOM("<!doctype html><body><div id='stage'></div></body>", {
    pretendToBeVisual: true,
    runScripts: "outside-only",
});
const w = dom.window;

const backing = new WeakMap();
function napiFor(el) {
    let c = backing.get(el);
    if (!c) {
        c = napi.createCanvas(el.width || 300, el.height || 150);
        backing.set(el, c);
    }
    if (c.width !== el.width || c.height !== el.height) {
        c.width = el.width;
        c.height = el.height;
    }
    return c;
}

// like a browser: setting the size of a canvas element resizes (and clears) it at once
for (const dim of ["width", "height"]) {
    const desc = Object.getOwnPropertyDescriptor(w.HTMLCanvasElement.prototype, dim);
    Object.defineProperty(w.HTMLCanvasElement.prototype, dim, {
        get() {
            return desc.get.call(this);
        },
        set(value) {
            desc.set.call(this, value);
            const c = backing.get(this);
            if (c) {
                c[dim] = Math.max(0, Math.round(Number(value) || 0)) || 0;
            }
        },
        configurable: true,
    });
}

const contexts = new WeakMap();
w.HTMLCanvasElement.prototype.getContext = function (type) {
    if (type !== "2d") {
        return null;
    }
    const c = napiFor(this);
    let ctx = contexts.get(this);
    if (!ctx) {
        const raw = c.getContext(type);
        const draw = raw.drawImage.bind(raw);
        const element = this;
        ctx = new Proxy(raw, {
            get(target, key) {
                if (key === "drawImage") {
                    return (img, ...args) => draw(img instanceof w.HTMLCanvasElement ? napiFor(img) : img, ...args);
                }
                if (key === "canvas") {
                    return element;
                }
                const value = target[key];
                return typeof value === "function" ? value.bind(target) : value;
            },
            set(target, key, value) {
                try {
                    target[key] = value;
                } catch {
                    // a browser ignores values it cannot parse
                }
                return true;
            },
        });
        contexts.set(this, ctx);
    }
    return ctx;
};
w.HTMLCanvasElement.prototype.toDataURL = function (type, quality) {
    return napiFor(this).toDataURL(type || "image/png", quality);
};
w.HTMLCanvasElement.prototype.toBlob = function (callback, type) {
    const buffer = napiFor(this).toBuffer(type || "image/png");
    callback(new Blob([buffer], { type: type || "image/png" }));
};

w.eval(fs.readFileSync(FABRIC, "utf8"));
globalThis.window = w;
globalThis.document = w.document;
globalThis.fabric = w.fabric;
globalThis.napi = napi;
globalThis.dom = dom;
globalThis.DOMParser = w.DOMParser;
globalThis.XMLSerializer = w.XMLSerializer;
globalThis.createImg = (buffer) =>
    new Promise((resolve) => {
        const img = new napi.Image();
        img.src = buffer;
        resolve(img);
    });
