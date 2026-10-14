// The distance of two fingers is never less than this (px): a division by it is safe.
const MIN_DISTANCE = 1;

/**
 * The middle and the distance of two fingers.
 * @param {TouchList|Touch[]} touches at least two
 * @returns {{x: number, y: number, distance: number}} client coordinates (px)
 */
export function fingersOf(touches) {
    const [first, second] = touches;
    return {
        x: (first.clientX + second.clientX) / 2,
        y: (first.clientY + second.clientY) / 2,
        distance: Math.max(
            Math.hypot(first.clientX - second.clientX, first.clientY - second.clientY),
            MIN_DISTANCE
        ),
    };
}

/**
 * Where a scroller has to be scrolled to after content is zoomed by `ratio` so that the point
 * of the content that was under the fingers is under them again, where they are now (they
 * may have moved while they zoomed: the content goes along with them). The content point is
 * `scroll + previous`; zoomed it lies at `(scroll + previous) * ratio`, and it is to appear at
 * `point`.
 * @param {Number} scroll the scroll position now (one axis)
 * @param {Number} previous the middle of the fingers before, in the scroller
 * @param {Number} point the middle of the fingers now, in the scroller
 * @param {Number} ratio the new size of the content divided by the old
 * @returns {Number}
 */
export function scrollAfterPinch(scroll, previous, point, ratio) {
    return (scroll + previous) * ratio - point;
}

/**
 * Call `onPinch` while two fingers touch `target` and move: each time with the factor by which
 * the distance of the fingers changed since the last call, and with the middle of the fingers
 * before and now. With a third finger, or with one, nothing is called; it goes on when two
 * are left. Like `attachSwipe` it only watches, except where told: with `preventDefault`
 * the browser does not scroll or zoom the page itself while two fingers are down (that
 * listener is not passive then). The browser does not scroll with a finger that is left
 * after two, either (the touch has been taken from it), so `onPan` is called with the way of
 * that finger until it lifts.
 *
 * @param {Element|Document} target
 * @param {Object} params
 * @param {function({factor: number, x: number, y: number, previous: {x: number, y: number}}): void} params.onPinch
 *      `x` and `y`: the middle of the fingers now (client coordinates)
 * @param {function({dx: number, dy: number}): void} [params.onPan] the way (px) a finger that is
 *      left after a pinch went since the last call
 * @param {function(TouchEvent): Boolean} [params.canPinch] asked when two fingers are down
 * @param {Boolean} [params.preventDefault] take the two fingers from the browser
 * @returns {function(): void} removes the listeners
 */
export function attachPinch(
    target,
    { onPinch, onPan, canPinch = () => true, preventDefault = false }
) {
    /** @type {{x: number, y: number, distance: number}|null} the fingers at the last event */
    let last = null;
    /** @type {{x: number, y: number}|null} the finger that is left after a pinch */
    let rest = null;

    const onTouchStart = (ev) => {
        rest = null;
        last = ev.touches.length === 2 && canPinch(ev) ? fingersOf(ev.touches) : null;
    };
    const onTouchMove = (ev) => {
        if (rest && ev.touches.length === 1) {
            const [touch] = ev.touches;
            if (preventDefault && ev.cancelable) {
                ev.preventDefault();
            }
            const way = { dx: touch.clientX - rest.x, dy: touch.clientY - rest.y };
            rest = { x: touch.clientX, y: touch.clientY };
            onPan?.(way);
            return;
        }
        if (!last || ev.touches.length !== 2) {
            return;
        }
        if (preventDefault && ev.cancelable) {
            ev.preventDefault();
        }
        const now = fingersOf(ev.touches);
        const previous = { x: last.x, y: last.y };
        const factor = now.distance / last.distance;
        last = now;
        onPinch({ factor, x: now.x, y: now.y, previous });
    };
    const onTouchEnd = (ev) => {
        const pinched = last !== null;
        // A finger that lifts from three leaves two: they go on from where they are.
        last = ev.touches.length === 2 && canPinch(ev) ? fingersOf(ev.touches) : null;
        if (ev.touches.length === 1 && (pinched || rest)) {
            const [touch] = ev.touches;
            rest = { x: touch.clientX, y: touch.clientY };
        } else {
            rest = null;
        }
    };

    const listeners = [
        ["touchstart", onTouchStart, { passive: true }],
        ["touchmove", onTouchMove, { passive: !preventDefault }],
        ["touchend", onTouchEnd, { passive: true }],
        ["touchcancel", onTouchEnd, { passive: true }],
    ];
    for (const [type, listener, options] of listeners) {
        target.addEventListener(type, listener, options);
    }
    return () => {
        for (const [type, listener] of listeners) {
            target.removeEventListener(type, listener);
        }
    };
}
