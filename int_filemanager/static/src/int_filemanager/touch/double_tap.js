// A finger that lifts after this long (ms) did not tap: it pressed.
const MAX_TAP_TIME = 250;
// A finger that moves this far (px) while it touches did not tap: it dragged.
const MAX_TAP_MOVE = 10;
// The second tap comes within this time (ms) of the first, and within this distance (px).
const MAX_GAP_TIME = 300;
const MAX_GAP_DISTANCE = 40;

/**
 * Call `onDoubleTap` when one finger taps twice on `target`, quickly and at the same place.
 * Like `attachSwipe` it only watches (passive listeners): a browser that zooms the page by a
 * double tap on its own has to be told not to, with `touch-action` (`manipulation`) on the
 * element. Not a tap: two fingers, a finger that moves or stays down, and a tap where
 * `canDoubleTap` says no.
 *
 * @param {Element|Document} target
 * @param {Object} params
 * @param {function(TouchEvent): void} params.onDoubleTap the event of the second tap's lift
 * @param {function(TouchEvent): Boolean} [params.canDoubleTap] asked when a finger touches down
 * @returns {function(): void} removes the listeners
 */
export function attachDoubleTap(target, { onDoubleTap, canDoubleTap = () => true }) {
    /** @type {{x: number, y: number, time: number}|null} the finger that is down, if it may tap */
    let down = null;
    /** @type {{x: number, y: number, time: number}|null} the last tap */
    let tap = null;

    const onTouchStart = (ev) => {
        const [touch] = ev.touches;
        if (ev.touches.length !== 1 || !canDoubleTap(ev)) {
            down = null;
            tap = null;
            return;
        }
        down = { x: touch.clientX, y: touch.clientY, time: ev.timeStamp };
    };
    const onTouchMove = (ev) => {
        const [touch] = ev.touches;
        if (down && (ev.touches.length !== 1 || far(touch, down, MAX_TAP_MOVE))) {
            down = null;
            tap = null;
        }
    };
    const onTouchEnd = (ev) => {
        const from = down;
        down = null;
        if (!from || ev.touches.length) {
            return;
        }
        const [touch] = ev.changedTouches;
        const now = { x: touch.clientX, y: touch.clientY, time: ev.timeStamp };
        if (now.time - from.time > MAX_TAP_TIME) {
            tap = null;
        } else if (tap && now.time - tap.time <= MAX_GAP_TIME && !far(now, tap, MAX_GAP_DISTANCE)) {
            tap = null;
            onDoubleTap(ev);
        } else {
            tap = now;
        }
    };
    const onTouchCancel = () => {
        down = null;
        tap = null;
    };

    const listeners = {
        touchstart: onTouchStart,
        touchmove: onTouchMove,
        touchend: onTouchEnd,
        touchcancel: onTouchCancel,
    };
    for (const [type, listener] of Object.entries(listeners)) {
        target.addEventListener(type, listener, { passive: true });
    }
    return () => {
        for (const [type, listener] of Object.entries(listeners)) {
            target.removeEventListener(type, listener);
        }
    };
}

/**
 * @param {{clientX?: number, x?: number, clientY?: number, y?: number}} point
 * @param {{x: number, y: number}} from
 * @param {Number} distance
 * @returns {Boolean} whether `point` is farther than `distance` from `from`
 */
function far(point, from, distance) {
    const x = point.clientX ?? point.x;
    const y = point.clientY ?? point.y;
    return Math.hypot(x - from.x, y - from.y) > distance;
}
