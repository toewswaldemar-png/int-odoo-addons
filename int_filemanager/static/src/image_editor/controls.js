// The handles of a mark: how they look (`CONTROL_LOOK`) and which mouse cursor they show.
//
// Fabric takes the cursor of a corner from the angle between the middle of the object and the
// corner on the screen. For an object that is not square that angle is not the one of the corner:
// a wide rectangle, a line or an arrow has its corners almost level with its middle, so they get a
// horizontal arrow. The cursor here comes from the corner itself (up left, up right, ...) turned by
// the angle of the object. The handle for turning has no cursor of its own in Fabric (a cross hair);
// it gets one that shows a turn.
import { CONTROL_LOOK } from "./constants";

// The directions of the cursors of the browser, clockwise from the east (the angle of the screen
// has its zero to the east and grows downwards).
const DIRECTIONS = ["e", "se", "s", "sw", "w", "nw", "n", "ne"];

/** An arrow along a circle, white under black so that it shows on a dark and on a bright picture. */
const ROTATE_ARROW = [
    "<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none'",
    " stroke-linecap='round' stroke-linejoin='round'>",
    "<path d='M19 12a7 7 0 1 1-2.1-5' stroke='#fff' stroke-width='4'/>",
    "<path d='M18.5 2.5v5h-5' stroke='#fff' stroke-width='4'/>",
    "<path d='M19 12a7 7 0 1 1-2.1-5' stroke='#000' stroke-width='2'/>",
    "<path d='M18.5 2.5v5h-5' stroke='#000' stroke-width='2'/>",
    "</svg>",
].join("");
export const ROTATE_CURSOR = `url("data:image/svg+xml,${encodeURIComponent(ROTATE_ARROW)}") 12 12, crosshair`;

/**
 * @param {{x: number, y: number}} control where the handle sits on the object, in halves of its size
 * @param {number} angle the angle of the object on the screen, in degrees
 * @returns {string} the cursor for scaling by that corner, e.g. `nw-resize`
 */
export function cornerCursor({ x, y }, angle) {
    const degrees = (Math.atan2(y, x) * 180) / Math.PI + angle;
    const index = Math.round((((degrees % 360) + 360) % 360) / 45) % DIRECTIONS.length;
    return `${DIRECTIONS[index]}-resize`;
}

/** Whether a control sits in a corner (not on a side, not above). */
function isCorner(control) {
    return control.x !== 0 && control.y !== 0;
}

/**
 * Gives the handles of a mark their cursors. Fabric's answer is kept where it says that scaling is
 * not allowed; the direction of a corner is ours.
 */
export function setHandleCursors(object) {
    for (const control of Object.values(object.controls || {})) {
        if (control.cursorPatched) {
            continue;
        }
        control.cursorPatched = true;
        if (isCorner(control)) {
            const own = control.cursorStyleHandler;
            control.cursorStyleHandler = (event, handle, target, coord) => {
                const cursor = own(event, handle, target, coord);
                return cursor.endsWith("-resize") ? cornerCursor(handle, target.getTotalAngle()) : cursor;
            };
        }
    }
    if (object.controls?.mtr) {
        object.controls.mtr.cursorStyle = ROTATE_CURSOR;
    }
}

/**
 * A text is not stretched. The handles on its sides scale one way only, which pulls the letters
 * narrow or flat; a text box keeps the two for its width (the lines wrap anew, the letters stay as
 * they are) and loses those for its height (that follows the text), a line of text keeps the corners.
 */
export function setTextHandles(object) {
    if (object.type === "textbox") {
        object.setControlsVisibility({ mt: false, mb: false });
    } else if (object.type === "i-text") {
        object.setControlsVisibility({ ml: false, mr: false, mt: false, mb: false });
    }
}

/** The look, the cursors and the choice of handles of a mark; a crop frame has a look of its own. */
export function styleHandles(object) {
    if (!object.helper) {
        object.set(CONTROL_LOOK);
    }
    setHandleCursors(object);
    setTextHandles(object);
}
