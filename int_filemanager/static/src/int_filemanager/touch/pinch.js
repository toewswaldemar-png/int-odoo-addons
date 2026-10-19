// Lower bound of the finger distance (px), so that dividing by it is safe.
const MIN_DISTANCE = 1;

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
 * Where to scroll after content is zoomed by `ratio` so that the content point that was under
 * the fingers (`scroll + previous`, now at `(scroll + previous) * ratio`) is under them at
 * `point`.
 * @param {Number} previous the middle of the fingers before, in the scroller
 * @param {Number} point the middle of the fingers now, in the scroller
 */
export function scrollAfterPinch(scroll, previous, point, ratio) {
    return (scroll + previous) * ratio - point;
}

/**
 * Call `onPinch` while two fingers move on `target`, with the factor by which their distance
 * changed since the last call and the middle of the fingers before (`previous`) and now (`x`,
 * `y`, client coordinates). The listeners are passive, so the browser still scrolls; set
 * `touch-action` on the element to stop it from zooming the page. Some browsers do not scroll
 * with the finger left after a pinch: `onPan` gets its way (see `createPanFollower`).
 *
 * @param {function(TouchEvent): Boolean} [params.canPinch] asked when two fingers are down
 * @returns {function(): void} removes the listeners
 */
export function attachPinch(target, { onPinch, onPan, canPinch = () => true }) {
    let last = null;
    let rest = null;

    const onTouchStart = (ev) => {
        rest = null;
        last = ev.touches.length === 2 && canPinch(ev) ? fingersOf(ev.touches) : null;
    };
    const onTouchMove = (ev) => {
        if (rest && ev.touches.length === 1) {
            const [touch] = ev.touches;
            const way = { dx: touch.clientX - rest.x, dy: touch.clientY - rest.y };
            rest = { x: touch.clientX, y: touch.clientY };
            onPan?.(way);
            return;
        }
        if (!last || ev.touches.length !== 2) {
            return;
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
        const [left] = ev.touches;
        const keeps = ev.touches.length === 1 && (pinched || rest);
        rest = keeps ? { x: left.clientX, y: left.clientY } : null;
    };

    const listeners = [
        ["touchstart", onTouchStart, { passive: true }],
        ["touchmove", onTouchMove, { passive: true }],
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

/**
 * Scroll `scroller` with the finger left after a pinch, unless the browser does it. Browsers
 * differ and the touch event does not tell (`cancelable` does not); the scroller does: if it is
 * not where the last move left it, the browser scrolls and the page would go twice as far.
 * The first move is ours, a few pixels at most. Call `pan` with the way of the finger (px) and
 * `reset` when a new pinch begins.
 */
export function createPanFollower(scroller) {
    let left = null;
    let browserScrolls = false;

    function reset() {
        left = null;
        browserScrolls = false;
    }

    function pan(dx, dy) {
        if (browserScrolls) {
            return;
        }
        if (left && (scroller.scrollLeft !== left.x || scroller.scrollTop !== left.y)) {
            browserScrolls = true;
            return;
        }
        scroller.scrollLeft -= dx;
        scroller.scrollTop -= dy;
        // Read back: the scroller rounds and limits what it is given.
        left = { x: scroller.scrollLeft, y: scroller.scrollTop };
    }

    return { pan, reset };
}
