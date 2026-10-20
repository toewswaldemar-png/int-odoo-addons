// The file the editor makes: the visible part of the scene (the crop, or all of it) at a scale,
// as a PNG, a JPEG or a WebP; or as SVG, with the marks as vectors and the picture inside.
import { FORMATS } from "./constants";

/**
 * Draws `source` onto a canvas of the size asked, if it has not that size already. A JPEG has no
 * transparency: it gets a white ground.
 */
function sized(source, width, height, opaque) {
    if (source.width === width && source.height === height && !opaque) {
        return source;
    }
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (opaque) {
        context.fillStyle = "#fff";
        context.fillRect(0, 0, width, height);
    }
    context.imageSmoothingQuality = "high";
    context.drawImage(source, 0, 0, width, height);
    return canvas;
}

/**
 * Runs `work` with the view of the canvas reset (no zoom, no move): Fabric reads the part that it
 * draws in the space of the view, and the file is made of the scene, not of what is on the screen.
 */
async function withPlainView(canvas, work) {
    const view = [...canvas.viewportTransform];
    canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
    try {
        return await work();
    } finally {
        canvas.setViewportTransform(view);
        canvas.requestRenderAll();
    }
}

function toBlob(canvas, mimetype, quality) {
    return new Promise((resolve, reject) => {
        canvas.toBlob(
            (blob) => (blob ? resolve(blob) : reject(new Error("The browser made no file."))),
            mimetype,
            quality
        );
    });
}

/**
 * @param {Object} parts
 * @param {Object} parts.canvas the Fabric canvas, with nothing selected
 * @param {Object} parts.picture the `Picture`; it is shown in full while the file is made
 * @param {{left: number, top: number, width: number, height: number}} parts.region
 * @param {number} parts.scale 1 is the size of the picture
 * @param {string} parts.mimetype a key of `FORMATS`
 * @param {number} parts.quality 0 to 1, for the lossy formats
 * @returns {Promise<Blob>}
 */
export async function renderBlob({ canvas, picture, region, scale, mimetype, quality }) {
    const { left, top, width, height } = region;
    const outWidth = Math.max(1, Math.round(width * scale));
    const outHeight = Math.max(1, Math.round(height * scale));
    picture.show(true);
    try {
        return await withPlainView(canvas, () => {
            // The size is checked: a screen with a higher pixel ratio may have made it larger.
            const drawn = canvas.toCanvasElement(scale, { left, top, width, height });
            const opaque = mimetype === "image/jpeg";
            const final = sized(drawn, outWidth, outHeight, opaque);
            return toBlob(final, mimetype, FORMATS[mimetype].lossy ? quality : undefined);
        });
    } finally {
        picture.show(false);
        canvas.requestRenderAll();
    }
}

/**
 * The marks as vectors, the picture as data inside. The picture is the size of the file, so a
 * big one is made smaller by `scale`.
 * @returns {Promise<Blob>}
 */
export async function renderSvg({ canvas, picture, region, scale }) {
    const { left, top, width, height } = region;
    const copy = sized(picture.full, Math.max(1, Math.round(picture.size.width * scale)), Math.max(1, Math.round(picture.size.height * scale)), false);
    picture.showElement(copy, scale);
    try {
        const svg = await withPlainView(canvas, () =>
            canvas.toSVG({
                width: Math.round(width * scale),
                height: Math.round(height * scale),
                viewBox: { x: left, y: top, width, height },
            })
        );
        return new Blob([svg], { type: "image/svg+xml" });
    } finally {
        picture.show(false);
        canvas.requestRenderAll();
    }
}
