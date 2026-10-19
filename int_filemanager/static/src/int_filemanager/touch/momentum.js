// Only the last SAMPLE_TIME ms count for the speed; a finger resting REST_TIME ms throws nothing.
const SAMPLE_TIME = 100;
const REST_TIME = 80;
// The speed falls to a third in this time (ms), as for a page gliding in a browser.
const TIME_CONSTANT = 325;
// Speeds in px per ms: no gliding below MIN_SPEED, a faster finger is capped at MAX_SPEED.
const MIN_SPEED = 0.02;
const MAX_SPEED = 6;

/** Easing for `element.animate` with `flingPlan`. */
export const FLING_EASING = "cubic-bezier(0.22, 1, 0.36, 1)";

/** Speed of a finger at the lift (px per ms); `release` gives `null` if it is not worth a glide. */
export function createVelocityTracker() {
    let samples = [];

    function reset() {
        samples = [];
    }

    function track(x, y, time) {
        samples.push({ x, y, time });
        while (samples.length > 2 && time - samples[0].time > SAMPLE_TIME) {
            samples.shift();
        }
    }

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

/** The way (px) and time (ms) of the glide after a lift at `speed` (px per ms). */
export function flingPlan(speed) {
    const fast = Math.hypot(speed.x, speed.y);
    // The speed integrated until it falls to `MIN_SPEED`.
    const factor = TIME_CONSTANT * (1 - MIN_SPEED / fast);
    return {
        dx: speed.x * factor,
        dy: speed.y * factor,
        duration: TIME_CONSTANT * Math.log(fast / MIN_SPEED),
    };
}
