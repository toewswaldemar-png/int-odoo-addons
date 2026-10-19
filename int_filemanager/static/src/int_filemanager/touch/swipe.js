// The least sideways way (px) of a swipe, and how many times it must exceed the vertical way:
// a finger that scrolls a page drifts a little to the side.
const SWIPE_DISTANCE = 60;
const SWIPE_RATIO = 2;
// Rounding: a scroller this much wider than it shows does not count as scrolling.
const SCROLL_TOLERANCE = 1;

export function swipeDirection(dx, dy) {
    if (Math.abs(dx) < SWIPE_DISTANCE || Math.abs(dx) < SWIPE_RATIO * Math.abs(dy)) {
        return null;
    }
    return dx < 0 ? "left" : "right";
}

/**
 * Whether `element` or a parent scrolls sideways (a zoomed PDF page, a long line of text); the
 * swipe then belongs to that scrolling, as in the core's `ActionSwiper`.
 */
export function scrollsSideways(element) {
    const doc = element.ownerDocument;
    const page = doc.scrollingElement;
    if (page && page.scrollWidth > page.clientWidth + SCROLL_TOLERANCE) {
        return true;
    }
    for (let node = element; node?.nodeType === Node.ELEMENT_NODE; node = node.parentElement) {
        const overflow = doc.defaultView.getComputedStyle(node).overflowX;
        if (
            ["auto", "scroll"].includes(overflow) &&
            node.scrollWidth > node.clientWidth + SCROLL_TOLERANCE
        ) {
            return true;
        }
    }
    return false;
}

/**
 * Call `onSwipe` when one finger swipes over `target`. The listeners are passive, so scrolling,
 * pinching and clicks are unaffected. A swipe that ends with text selected is ignored: a finger
 * that selects text moves sideways too.
 *
 * @param {function(TouchEvent): Boolean} [params.canSwipe] asked when a finger touches down
 * @returns {function(): void} removes the listeners
 */
export function attachSwipe(target, { onSwipe, canSwipe = () => true }) {
    const doc = target.ownerDocument || target;
    let start = null;

    const onTouchStart = (ev) => {
        const [touch] = ev.touches;
        const allowed = ev.touches.length === 1 && canSwipe(ev) && !scrollsSideways(ev.target);
        start = allowed ? { x: touch.clientX, y: touch.clientY } : null;
    };
    const onTouchMove = (ev) => {
        if (ev.touches.length > 1) {
            start = null;
        }
    };
    const onTouchEnd = (ev) => {
        const from = start;
        start = null;
        if (!from || ev.touches.length || doc.getSelection()?.isCollapsed === false) {
            return;
        }
        const touch = ev.changedTouches[0];
        const direction = swipeDirection(touch.clientX - from.x, touch.clientY - from.y);
        if (direction) {
            onSwipe(direction);
        }
    };
    const onTouchCancel = () => {
        start = null;
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
