/** @odoo-module **/

/**
 * Return the share of the idle time that is left, from 1 down to 0.
 *
 * @param {number} startMs time of the last input
 * @param {number} nowMs
 * @param {number} delayMinutes idle time before the displays go back to the clock
 */
export function remainingFraction(startMs, nowMs, delayMinutes) {
    const total = delayMinutes * 60 * 1000;
    if (total <= 0) {
        return 0;
    }
    return Math.min(1, Math.max(0, 1 - (nowMs - startMs) / total));
}

/**
 * Decide the start of the idle time after a new state arrived on the hymn control page.
 *
 * A new digit restarts the time, a deleted digit keeps it, and a state taken over from the
 * server (page load, reconnect) continues the time stored by an earlier page of the same tab.
 *
 * @param {"input" | "backspace" | "same"} change
 * @param {number | null} currentStart start now running, if any
 * @param {number | null} storedStart start kept in the tab session, if any
 * @param {number} nowMs
 */
export function nextStart(change, currentStart, storedStart, nowMs) {
    if (change === "input") {
        return nowMs;
    }
    if (change === "backspace" && currentStart !== null) {
        return currentStart;
    }
    return currentStart ?? storedStart ?? nowMs;
}
