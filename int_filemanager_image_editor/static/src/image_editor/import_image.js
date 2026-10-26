// A picture or a vector drawing that the user puts onto the picture (a stamp, a logo, a mark of
// the water). It is made small first and carried inside the state as data, so that a later edit
// finds it again without the file.
import { EMBED_EDGE, MARK_PROPS } from "./constants";
import { limitEdge } from "./geometry";
import { reviveObjects } from "./edit_state";

const { FabricImage, loadSVGFromString, util } = window.fabric;

export const IMPORT_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml"];
// A drawing is text that is parsed; a bigger one is more than a mark needs.
const SVG_MAX_SIZE = 2 * 1024 ** 2;
// A `url(...)` that is neither a link to a part of the drawing (`#id`) nor data.
const EXTERNAL_URL = /url\(\s*['"]?\s*(?!#|data:)/i;
const EXTERNAL_URL_GLOBAL = /url\(\s*['"]?\s*(?!#|data:)[^)]*\)/gi;

/** @returns {boolean} whether the editor can put this file onto a picture */
export function isImportable(file) {
    return IMPORT_TYPES.includes(file?.type);
}

/**
 * @param {File|Blob} file
 * @returns {Promise<Object>} a Fabric object, not yet on the canvas
 */
export async function importFile(file) {
    if (file.type === "image/svg+xml") {
        return importDrawing(file);
    }
    return importRaster(file);
}

async function importRaster(file) {
    const url = URL.createObjectURL(file);
    try {
        const picture = await util.loadImage(url);
        const { width, height } = limitEdge(
            { width: picture.naturalWidth, height: picture.naturalHeight },
            EMBED_EDGE
        );
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext("2d");
        context.imageSmoothingQuality = "high";
        context.drawImage(picture, 0, 0, width, height);
        // A photograph stays a JPEG, everything else keeps its transparency.
        const data = file.type === "image/jpeg" ? canvas.toDataURL("image/jpeg", 0.9) : canvas.toDataURL("image/png");
        const image = await FabricImage.fromURL(data);
        image.set({ mark: "stamp" });
        return image;
    } finally {
        URL.revokeObjectURL(url);
    }
}

/**
 * The drawing without what reaches out of it. Fabric loads every picture that a drawing names
 * while it reads the text, so a drawing from somebody else would make the browser ask a server
 * of theirs: pictures and links that do not carry their data, scripts and handlers go first.
 * @param {string} text
 * @returns {string}
 */
export function sanitizeSvg(text) {
    const document = new DOMParser().parseFromString(text, "image/svg+xml");
    if (document.querySelector("parsererror")) {
        throw new Error("The drawing cannot be read.");
    }
    for (const element of [...document.querySelectorAll("script, foreignObject, iframe, object, embed")]) {
        element.remove();
    }
    for (const element of [...document.querySelectorAll("*")]) {
        for (const attribute of [...element.attributes]) {
            const name = attribute.name.toLowerCase();
            const value = attribute.value.trim();
            if (name.startsWith("on")) {
                element.removeAttribute(attribute.name);
            } else if (name === "href" || name === "xlink:href") {
                if (!value.startsWith("#") && !/^data:image\//i.test(value)) {
                    element.removeAttribute(attribute.name);
                    if (["image", "feImage"].includes(element.localName)) {
                        element.remove();
                    }
                }
            } else if (EXTERNAL_URL.test(value)) {
                element.removeAttribute(attribute.name);
            }
        }
    }
    for (const style of document.querySelectorAll("style")) {
        style.textContent = style.textContent.replace(/@import[^;]*;?/gi, "").replace(EXTERNAL_URL_GLOBAL, "none");
    }
    return new XMLSerializer().serializeToString(document);
}

async function importDrawing(file) {
    if (file.size > SVG_MAX_SIZE) {
        throw new Error("The drawing is too large.");
    }
    const { objects, options } = await loadSVGFromString(sanitizeSvg(await file.text()));
    const parts = objects.filter(Boolean);
    if (!parts.length) {
        throw new Error("The drawing has nothing to show.");
    }
    const drawing = parts.length === 1 ? parts[0] : util.groupSVGElements(parts, options);
    // Through the same filter as a stored state: no picture that points to somewhere else.
    const [safe] = await reviveObjects([drawing.toObject(MARK_PROPS)]);
    if (!safe) {
        throw new Error("The drawing has nothing to show.");
    }
    safe.set({ mark: "stamp" });
    return safe;
}

/** Scales a stamp to `share` of the width of `region` and puts it in the middle. */
export function placeInMiddle(object, region, share = 0.4) {
    const scale = Math.min((region.width * share) / object.width, (region.height * share) / object.height);
    object.set({
        originX: "center",
        originY: "center",
        left: region.left + region.width / 2,
        top: region.top + region.height / 2,
        scaleX: scale,
        scaleY: scale,
    });
    object.setCoords();
}
