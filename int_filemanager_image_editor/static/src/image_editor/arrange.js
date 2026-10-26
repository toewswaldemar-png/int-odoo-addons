// What the user does with marks that are already there: stack them, group them, copy them, line
// them up, lock them. Every function takes the canvas and works on the selection; the selection
// is given up first and taken again at the end, because the objects of a multiple selection
// live in the space of the selection, not of the scene.
import { MARK_PROPS } from "./constants";

const { ActiveSelection, Group, util } = window.fabric;

const SPECIAL_GROUPS = ["arrow"];

function stackIndex(canvas, object) {
    return canvas.getObjects().indexOf(object);
}

/** @returns {Object[]} the selected marks, bottom to top, with the selection given up */
function takeSelection(canvas) {
    const selected = canvas.getActiveObjects();
    canvas.discardActiveObject();
    return selected.sort((a, b) => stackIndex(canvas, a) - stackIndex(canvas, b));
}

export function select(canvas, objects) {
    if (objects.length === 1) {
        canvas.setActiveObject(objects[0]);
    } else if (objects.length > 1) {
        canvas.setActiveObject(new ActiveSelection(objects, { canvas }));
    }
    canvas.requestRenderAll();
}

export function selectAll(canvas) {
    canvas.discardActiveObject();
    select(
        canvas,
        canvas.getObjects().filter((object) => object.selectable !== false && !object.helper)
    );
}

/** @param {"front"|"forward"|"backward"|"back"} how */
export function order(canvas, how) {
    const objects = takeSelection(canvas);
    if (how === "front") {
        objects.forEach((object) => canvas.bringObjectToFront(object));
    } else if (how === "back") {
        [...objects].reverse().forEach((object) => canvas.sendObjectToBack(object));
    } else if (how === "forward") {
        [...objects].reverse().forEach((object) => canvas.bringObjectForward(object));
    } else {
        objects.forEach((object) => canvas.sendObjectBackwards(object));
    }
    select(canvas, objects);
}

export function canGroup(canvas) {
    return canvas.getActiveObjects().length > 1;
}

export function canUngroup(canvas) {
    const object = canvas.getActiveObject();
    return object?.type === "group" && !SPECIAL_GROUPS.includes(object.mark);
}

export function group(canvas) {
    const objects = takeSelection(canvas);
    if (objects.length < 2) {
        select(canvas, objects);
        return;
    }
    canvas.remove(...objects);
    const grouped = new Group(objects);
    canvas.add(grouped);
    select(canvas, [grouped]);
}

export function ungroup(canvas) {
    const [object] = takeSelection(canvas);
    if (object?.type !== "group" || SPECIAL_GROUPS.includes(object.mark)) {
        select(canvas, object ? [object] : []);
        return;
    }
    // The place of each part on the scene is worked out first: what `removeAll` leaves in `left`
    // and `top` is wrong for a part whose origin is not its middle.
    const groupMatrix = object.calcTransformMatrix();
    const parts = [...object.getObjects()];
    const matrices = parts.map((part) => util.multiplyTransformMatrices(groupMatrix, part.calcOwnMatrix()));
    object.removeAll();
    canvas.remove(object);
    parts.forEach((part, index) => {
        util.applyTransformToObject(part, matrices[index]);
        part.setCoords();
    });
    canvas.add(...parts);
    select(canvas, parts);
}

/** @returns {Promise<Object[]>} copies of the marks, as they stand */
export async function cloneAll(objects) {
    return Promise.all(objects.map((object) => object.clone(MARK_PROPS)));
}

/**
 * Puts copies on the canvas, moved by `offset`, and selects them.
 * @returns {Promise<Object[]>} the copies
 */
export async function addCopies(canvas, objects, offset) {
    const copies = await cloneAll(objects);
    for (const copy of copies) {
        copy.set({ left: copy.left + offset, top: copy.top + offset });
        copy.setCoords();
        canvas.add(copy);
    }
    select(canvas, copies);
    return copies;
}

export async function duplicate(canvas, offset) {
    const objects = takeSelection(canvas);
    if (!objects.length) {
        return [];
    }
    return addCopies(canvas, objects, offset);
}

/**
 * @param {Object} canvas
 * @param {"left"|"center"|"right"|"top"|"middle"|"bottom"} how
 * @param {{left: number, top: number, width: number, height: number}} region what a single mark is
 *      lined up with (a selection of several is lined up with its own box)
 */
export function align(canvas, how, region) {
    const objects = takeSelection(canvas);
    if (!objects.length) {
        return;
    }
    const boxes = objects.map((object) => object.getBoundingRect());
    const box = objects.length === 1 ? region : unionOf(boxes);
    objects.forEach((object, index) => {
        const mine = boxes[index];
        const shift = {
            left: box.left - mine.left,
            center: box.left + box.width / 2 - (mine.left + mine.width / 2),
            right: box.left + box.width - (mine.left + mine.width),
            top: box.top - mine.top,
            middle: box.top + box.height / 2 - (mine.top + mine.height / 2),
            bottom: box.top + box.height - (mine.top + mine.height),
        }[how];
        const horizontal = ["left", "center", "right"].includes(how);
        object.set(horizontal ? { left: object.left + shift } : { top: object.top + shift });
        object.setCoords();
    });
    select(canvas, objects);
}

/** Spaces three or more marks evenly between the outer two. @param {"horizontal"|"vertical"} axis */
export function distribute(canvas, axis) {
    const objects = takeSelection(canvas);
    if (objects.length < 3) {
        select(canvas, objects);
        return;
    }
    const horizontal = axis === "horizontal";
    const start = horizontal ? "left" : "top";
    const length = horizontal ? "width" : "height";
    const entries = objects
        .map((object) => ({ object, box: object.getBoundingRect() }))
        .sort((a, b) => a.box[start] - b.box[start]);
    const first = entries[0].box;
    const last = entries.at(-1).box;
    const inner = entries.slice(1, -1);
    const taken = entries.reduce((sum, { box }) => sum + box[length], 0);
    const gap = (last[start] + last[length] - first[start] - taken) / (entries.length - 1);
    let at = first[start] + first[length] + gap;
    for (const { object, box } of inner) {
        object.set({ [start]: object[start] + (at - box[start]) });
        object.setCoords();
        at += box[length] + gap;
    }
    select(canvas, objects);
}

function unionOf(boxes) {
    const left = Math.min(...boxes.map((box) => box.left));
    const top = Math.min(...boxes.map((box) => box.top));
    const right = Math.max(...boxes.map((box) => box.left + box.width));
    const bottom = Math.max(...boxes.map((box) => box.top + box.height));
    return { left, top, width: right - left, height: bottom - top };
}

/** @returns {boolean} whether the mark is locked against moving and changing */
export function isLocked(object) {
    return Boolean(object?.locked);
}

export function setLocked(object, locked) {
    object.set({
        locked,
        lockMovementX: locked,
        lockMovementY: locked,
        lockRotation: locked,
        lockScalingX: locked,
        lockScalingY: locked,
        lockSkewingX: locked,
        lockSkewingY: locked,
        hasControls: !locked,
    });
    object.setCoords();
}

/** Mirrors the marks on their own axis. @param {"horizontal"|"vertical"} axis */
export function mirror(canvas, axis) {
    const objects = takeSelection(canvas);
    for (const object of objects) {
        object.set(axis === "horizontal" ? { flipX: !object.flipX } : { flipY: !object.flipY });
        object.setCoords();
    }
    select(canvas, objects);
}

/** Moves the marks by `dx`, `dy`. */
export function nudge(canvas, dx, dy) {
    const objects = takeSelection(canvas);
    for (const object of objects) {
        object.set({ left: object.left + dx, top: object.top + dy });
        object.setCoords();
    }
    select(canvas, objects);
}
