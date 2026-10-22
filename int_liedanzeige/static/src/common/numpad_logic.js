/** @odoo-module **/

export const MAX_DIGITS = 4;

/**
 * Tell whether the digit keys of a control page are locked.
 *
 * The choir control is locked while a hymn number stands; the hymn control is locked
 * while the choir display shows a number of its own.
 */
export function isNumpadLocked(target, hymnState, choirState) {
    if (target === "choir") {
        return hymnState.length > 0;
    }
    return choirState.length > 0 && choirState !== hymnState;
}

/**
 * Return the target that a backspace press goes to.
 *
 * While the digit keys are locked, the backspace acts on the number that locks them.
 */
export function backspaceTarget(target, locked) {
    if (!locked) {
        return target;
    }
    return target === "choir" ? "hymn" : "choir";
}

/** Tell whether one more digit fits into the number shown on the control pages. */
export function canTypeDigit(controlState) {
    return controlState.length < MAX_DIGITS;
}

/**
 * Return how the hymn number changed between two states.
 *
 * @returns {"input" | "backspace" | "same"}
 */
export function hymnChange(previous, next) {
    if (next.length > previous.length) {
        return "input";
    }
    return next.length < previous.length ? "backspace" : "same";
}
