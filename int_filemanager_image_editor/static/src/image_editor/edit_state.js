// The state of an edit as plain data: where the picture lies, its filters, the crop and the marks.
// It is the unit of the undo history and what is stored with an edited picture (as JSON), so that
// the next edit finds the marks as objects again.
//
// A state that comes from outside (it was stored by a user) is not trusted: only the kinds of
// marks that the editor makes are revived, and a picture inside a state has to carry its data.
import { MARK_PROPS, STATE_VERSION } from "./constants";
import { cleanSettings } from "./filters";

const { util } = window.fabric;

const ALLOWED_TYPES = new Set([
    "Rect",
    "Ellipse",
    "Circle",
    "Triangle",
    "Line",
    "Polygon",
    "Polyline",
    "Path",
    "IText",
    "Textbox",
    "Group",
    "RedactMark",
    "Image",
]);
const INLINE_PICTURE = /^data:image\/(png|jpeg|webp|gif|svg\+xml)[;,]/;
const MAX_DEPTH = 6;
const MAX_OBJECTS = 5000;
// Keys of a stored object that would reach out of the state (a clip path holds more objects).
const DROPPED_KEYS = ["clipPath", "filters", "crossOrigin"];
// The keys that hold a colour, a gradient or a pattern.
const PAINT_KEYS = ["fill", "stroke", "backgroundColor", "textBackgroundColor"];

/**
 * The state of the edit now.
 * @param {{picture: Object, canvas: Object, filters: Object, crop: Object|null}} parts
 */
export function captureModel({ picture, canvas, filters, crop }) {
    return {
        base: picture.placement(),
        filters: { ...filters },
        crop: crop ? { ...crop } : null,
        // The helpers of the editor (the frame of a crop that is being chosen) are no marks.
        objects: canvas
            .getObjects()
            .filter((object) => !object.helper)
            .map((object) => object.toObject(MARK_PROPS)),
    };
}

/** @returns {Object} the state that goes with the file, in the form that the server keeps */
export function buildState(parts) {
    const { picture } = parts;
    return {
        version: STATE_VERSION,
        scene: picture.sceneSize,
        source: { ...picture.size },
        ...captureModel(parts),
    };
}

/**
 * The state read from what was stored, or `null` if it does not belong to the picture (another
 * version, another size) or is not in the form that the editor writes.
 * @param {*} raw
 * @param {{width: number, height: number}} size the size of the picture that it is applied to
 */
export function readState(raw, size) {
    if (!raw || typeof raw !== "object" || raw.version !== STATE_VERSION) {
        return null;
    }
    if (raw.source?.width !== size.width || raw.source?.height !== size.height) {
        return null;
    }
    const { base } = raw;
    const numbers = ["angle", "cx", "cy"];
    if (!base || !numbers.every((key) => Number.isFinite(base[key]))) {
        return null;
    }
    return {
        base: {
            angle: Math.round(base.angle / 90) * 90,
            flipX: base.flipX === true,
            flipY: base.flipY === true,
            cx: base.cx,
            cy: base.cy,
        },
        filters: cleanSettings(raw.filters),
        crop: cleanRect(raw.crop),
        objects: Array.isArray(raw.objects) ? raw.objects : [],
    };
}

function cleanRect(rect) {
    if (!rect || typeof rect !== "object") {
        return null;
    }
    const keys = ["left", "top", "width", "height"];
    if (!keys.every((key) => Number.isFinite(rect[key])) || rect.width <= 0 || rect.height <= 0) {
        return null;
    }
    return Object.fromEntries(keys.map((key) => [key, rect[key]]));
}

/**
 * The objects of a state, without what the editor does not make.
 * @param {Object[]} objects
 * @returns {Object[]}
 */
export function cleanObjects(objects, depth = 0, count = { value: 0 }) {
    if (!Array.isArray(objects) || depth > MAX_DEPTH) {
        return [];
    }
    const clean = [];
    for (const object of objects) {
        if (!object || typeof object !== "object" || !ALLOWED_TYPES.has(object.type)) {
            continue;
        }
        if (object.type === "Image" && !INLINE_PICTURE.test(object.src || "")) {
            continue;
        }
        if (++count.value > MAX_OBJECTS) {
            break;
        }
        const copy = { ...object };
        for (const key of DROPPED_KEYS) {
            delete copy[key];
        }
        for (const key of PAINT_KEYS) {
            if (!isSafePaint(copy[key])) {
                copy[key] = null;
            }
        }
        if (object.type === "Group") {
            copy.objects = cleanObjects(object.objects, depth + 1, count);
        }
        clean.push(copy);
    }
    return clean;
}

/** A pattern carries its picture as data; one that points to an address is not loaded. */
function isSafePaint(value) {
    if (value && typeof value === "object" && value.type === "pattern") {
        return typeof value.source === "string" && INLINE_PICTURE.test(value.source);
    }
    return true;
}

/**
 * @returns {Promise<Object[]>} the Fabric objects of the stored ones; one that cannot be made is
 *      left out, it does not keep the others from coming back
 */
export async function reviveObjects(objects) {
    const clean = cleanObjects(objects);
    try {
        return await util.enlivenObjects(clean);
    } catch {
        const revived = [];
        for (const object of clean) {
            try {
                revived.push(...(await util.enlivenObjects([object])));
            } catch {
                // This one is lost, the rest is not.
            }
        }
        return revived;
    }
}
