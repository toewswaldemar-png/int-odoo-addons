// A touch longer (ms) or wider (px) than this is a press or a drag, not a tap.
const MAX_TAP_TIME = 250;
const MAX_TAP_MOVE = 10;
// The second tap must come within this time (ms) and distance (px) of the first.
const MAX_GAP_TIME = 300;
const MAX_GAP_DISTANCE = 40;

/**
 * Call `onDoubleTap` when one finger taps twice at the same place on `target`. The listeners
 * are passive: to stop the browser's own double-tap zoom, set `touch-action: manipulation`.
 *
 * @param {function(TouchEvent): Boolean} [params.canDoubleTap] asked when a finger touches down
 * @returns {function(): void} removes the listeners
 */
export function attachDoubleTap(target, { onDoubleTap, canDoubleTap = () => true }) {
    let down = null;
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

function far(point, from, distance) {
    const x = point.clientX ?? point.x;
    const y = point.clientY ?? point.y;
    return Math.hypot(x - from.x, y - from.y) > distance;
}
