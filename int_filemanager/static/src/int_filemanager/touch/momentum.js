// Only the last part of the way of the finger tells its speed at the lift (ms).
const SAMPLE_TIME = 100;
// A finger that rests this long (ms) before it lifts does not throw anything.
const REST_TIME = 80;
// The speed falls to a third in this time (ms), as it does when a page glides in a browser.
const TIME_CONSTANT = 325;
// Below this speed (px per ms) the gliding ends; above the other it is not faster.
const MIN_SPEED = 0.02;
const MAX_SPEED = 6;

/**
 * The easing of a gliding that the browser plays: it starts fast and slows down to a stop, the
 * way a page glides. With the way and the time of `flingPlan` its start is about the speed of
 * the finger (a little more).
 */
export const FLING_EASING = "cubic-bezier(0.22, 1, 0.36, 1)";

/**
 * Follow a finger and tell how fast it went when it lifts. The way of the finger is told to
 * `track` while it moves; `release` gives the speed of the end of that way, or `null` if there
 * is none worth a gliding (a finger that rested, a slow one, one point only).
 *
 * @returns {{track: function(number, number, number): void, release: function(number): ({x: number, y: number}|null), reset: function(): void}}
 *      speeds in px per ms
 */
export function createVelocityTracker() {
    /** @type {{x: number, y: number, time: number}[]} the last points of the way of the finger */
    let samples = [];

    function reset() {
        samples = [];
    }

    /**
     * @param {Number} x where the finger is (px, any origin that does not change)
     * @param {Number} y
     * @param {Number} time when (ms, as `timeStamp` of the event)
     */
    function track(x, y, time) {
        samples.push({ x, y, time });
        while (samples.length > 2 && time - samples[0].time > SAMPLE_TIME) {
            samples.shift();
        }
    }

    /** @param {Number} time when the finger lifts (ms, as `timeStamp` of the event) */
    function release(time) {
        const taken = samples;
        samples = [];
        const first = taken[0];
        const last = taken.at(-1);
        if (taken.length < 2 || time - last.time > REST_TIME) {
            return null;
        }
        const span = Math.max(last.time - first.time, 1);
        const speed = { x: (last.x - first.x) / span, y: (last.y - first.y) / span };
        const fast = Math.hypot(speed.x, speed.y);
        if (fast < MIN_SPEED) {
            return null;
        }
        const limit = Math.min(1, MAX_SPEED / fast);
        return { x: speed.x * limit, y: speed.y * limit };
    }

    return { track, release, reset };
}

/**
 * How far and how long a thing glides on after a finger lifted at `speed`, if it is slowed down
 * as a browser slows a page: the speed falls to a third in `TIME_CONSTANT`, and it is over at
 * `MIN_SPEED`. The way is `speed * time constant`, the time is the time that takes. The
 * caller lets the browser play it (`element.animate` with `FLING_EASING`), which does it on
 * its own thread, smoothly, whatever this one is busy with.
 *
 * @param {{x: number, y: number}} speed px per ms
 * @returns {{dx: number, dy: number, duration: number}} the way (px, the direction of the
 *      finger) and the time (ms)
 */
export function flingPlan(speed) {
    const fast = Math.hypot(speed.x, speed.y);
    // The way is the speed integrated until it is `MIN_SPEED`, along the direction of the finger.
    const factor = TIME_CONSTANT * (1 - MIN_SPEED / fast);
    return {
        dx: speed.x * factor,
        dy: speed.y * factor,
        duration: TIME_CONSTANT * Math.log(fast / MIN_SPEED),
    };
}
