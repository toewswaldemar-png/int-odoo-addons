// The least way a finger goes sideways to be a swipe (px). The navigation of the web client
// (`navbar.js`) asks for 100 px to close the menu, Bootstrap's swipe for 40; a swipe between
// files is made quickly and often, so it is between.
const SWIPE_DISTANCE = 60;
// The way sideways must be this many times the way up or down: a finger that scrolls a page
// drifts a little to the side, and that is no swipe.
const SWIPE_RATIO = 2;
// A scroller may be this much wider than it shows and still count as not scrolling (rounding).
const SCROLL_TOLERANCE = 1;

/**
 * Tell whether a way of a finger is a swipe, and to which side.
 * @param {Number} dx the way to the right (px), negative to the left
 * @param {Number} dy the way down (px), negative up
 * @returns {"left"|"right"|null} the side the finger went to, `null` if it is no swipe
 */
export function swipeDirection(dx, dy) {
    if (Math.abs(dx) < SWIPE_DISTANCE || Math.abs(dx) < SWIPE_RATIO * Math.abs(dy)) {
        return null;
    }
    return dx < 0 ? "left" : "right";
}

/**
 * Tell whether a finger that touches `element` would move something sideways instead: the
 * element or one of its parents scrolls to the sides (a page of the PDF viewer that is zoomed
 * in, a text with a long line). The swipe then belongs to that scrolling, as in the core's
 * `ActionSwiper`.
 * @param {Element} element
 * @returns {Boolean}
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
 * Call `onSwipe` when one finger swipes over `target`. It does not take anything from the
 * target: the listeners only watch (they are passive), so scrolling, zooming with two fingers
 * and the clicks stay as they are. Not a swipe: two fingers, a swipe that starts where
 * `canSwipe` says no, one that starts on something that scrolls sideways, and one that ends
 * with text selected (a finger that selects text moves sideways too).
 *
 * @param {Element|Document} target
 * @param {Object} params
 * @param {function("left"|"right"): void} params.onSwipe
 * @param {function(TouchEvent): Boolean} [params.canSwipe] asked when a finger touches down
 * @returns {function(): void} removes the listeners
 */
export function attachSwipe(target, { onSwipe, canSwipe = () => true }) {
    const doc = target.ownerDocument || target;
    /** @type {{x: number, y: number}|null} where the finger touched down, if it may swipe */
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
