// Plain geometry of the editor: no Fabric, no DOM. A point is `{x, y}`, a size `{width, height}`,
// a rectangle `{left, top, width, height}`; all in units of the picture (the scene).

/** @returns {{x: number, y: number}} the point after the scene turned a quarter clockwise */
export function turnPoint({ x, y }, { height }) {
    return { x: height - y, y: x };
}

/** @returns {{width: number, height: number}} the size after a quarter turn */
export function turnSize({ width, height }) {
    return { width: height, height: width };
}

/** @returns {{left: number, top: number, width: number, height: number}} the rectangle after a quarter turn */
export function turnRect(rect, size) {
    const a = turnPoint({ x: rect.left, y: rect.top }, size);
    const b = turnPoint({ x: rect.left + rect.width, y: rect.top + rect.height }, size);
    return boxOf(a, b);
}

/** @returns {{x: number, y: number}} the point after the scene flipped, across (`horizontal`) or down */
export function flipPoint({ x, y }, { width, height }, horizontal) {
    return horizontal ? { x: width - x, y } : { x, y: height - y };
}

export function flipRect(rect, size, horizontal) {
    const a = flipPoint({ x: rect.left, y: rect.top }, size, horizontal);
    const b = flipPoint({ x: rect.left + rect.width, y: rect.top + rect.height }, size, horizontal);
    return boxOf(a, b);
}

/** @returns {{left: number, top: number, width: number, height: number}} the box of two corners */
export function boxOf(a, b) {
    return {
        left: Math.min(a.x, b.x),
        top: Math.min(a.y, b.y),
        width: Math.abs(a.x - b.x),
        height: Math.abs(a.y - b.y),
    };
}

/** @returns {number} `value`, but between `low` and `high` */
export function clamp(value, low, high) {
    return Math.min(Math.max(value, low), high);
}

/** @returns {{left: number, top: number, width: number, height: number}} `rect` kept inside the scene */
export function keepInside(rect, { width, height }) {
    const w = clamp(rect.width, 1, width);
    const h = clamp(rect.height, 1, height);
    return {
        left: clamp(rect.left, 0, width - w),
        top: clamp(rect.top, 0, height - h),
        width: w,
        height: h,
    };
}

/**
 * The largest rectangle of the given ratio (width / height) that fits in `size`, in the middle.
 * @param {number} ratio
 */
export function ratioRect({ width, height }, ratio) {
    let w = width;
    let h = w / ratio;
    if (h > height) {
        h = height;
        w = h * ratio;
    }
    return { left: (width - w) / 2, top: (height - h) / 2, width: w, height: h };
}

/**
 * The view of a region in a stage: the zoom that shows all of it, and where it lies.
 * @param {{width: number, height: number}} stage the room in screen pixels
 * @param {{left: number, top: number, width: number, height: number}} region
 * @param {number} margin
 * @returns {number} screen pixels per unit
 */
export function fitZoom(stage, region, margin) {
    const room = {
        width: Math.max(stage.width - margin * 2, 1),
        height: Math.max(stage.height - margin * 2, 1),
    };
    return Math.min(room.width / region.width, room.height / region.height);
}

/**
 * The viewport transform that puts `region` in the middle of the stage at `zoom`, moved by `pan`
 * (screen pixels).
 * @returns {number[]} Fabric's `[a, b, c, d, e, f]`
 */
export function viewTransform(stage, region, zoom, pan) {
    const e = (stage.width - region.width * zoom) / 2 - region.left * zoom + pan.x;
    const f = (stage.height - region.height * zoom) / 2 - region.top * zoom + pan.y;
    return [zoom, 0, 0, zoom, e, f];
}

/**
 * Keeps the picture from being pushed out of the stage: at least `keep` screen pixels of the
 * region stay in view on each axis.
 * @returns {{x: number, y: number}} the pan, limited
 */
export function limitPan(stage, region, zoom, pan, keep) {
    const slackX = (stage.width + region.width * zoom) / 2 - keep;
    const slackY = (stage.height + region.height * zoom) / 2 - keep;
    return { x: clamp(pan.x, -slackX, slackX), y: clamp(pan.y, -slackY, slackY) };
}

/** @returns {number} `value` moved to the nearest multiple of `step` */
export function snapTo(value, step) {
    return Math.round(value / step) * step;
}

/**
 * The nearest of `targets` within `distance` of `value`, or `null`.
 * @param {number} value
 * @param {number[]} targets
 */
export function nearest(value, targets, distance) {
    let best = null;
    for (const target of targets) {
        const gap = Math.abs(target - value);
        if (gap <= distance && (best === null || gap < Math.abs(best - value))) {
            best = target;
        }
    }
    return best;
}

/** @returns {{x: number, y: number}} `to` brought to a multiple of 45 degrees around `from` */
export function snapAngle(from, to) {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.hypot(dx, dy);
    const step = Math.PI / 4;
    const angle = Math.round(Math.atan2(dy, dx) / step) * step;
    return { x: from.x + Math.cos(angle) * length, y: from.y + Math.sin(angle) * length };
}

/** @returns {{x: number, y: number}} `to` moved so that the box from `from` is a square */
export function squareTo(from, to) {
    const side = Math.max(Math.abs(to.x - from.x), Math.abs(to.y - from.y));
    return {
        x: from.x + Math.sign(to.x - from.x || 1) * side,
        y: from.y + Math.sign(to.y - from.y || 1) * side,
    };
}

/** @returns {{width: number, height: number}} the size that the biggest side is `edge` at most */
export function limitEdge({ width, height }, edge) {
    const ratio = Math.min(1, edge / Math.max(width, height));
    return { width: Math.max(1, Math.round(width * ratio)), height: Math.max(1, Math.round(height * ratio)) };
}
