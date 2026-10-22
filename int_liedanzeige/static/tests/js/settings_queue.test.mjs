// Plain Node tests for the queue that sends slider values to the server.
import assert from "node:assert/strict";
import { setImmediate } from "node:timers";
import test from "node:test";

import { SettingsQueue } from "../../src/common/settings_queue.js";

function makeQueue() {
    const sent = [];
    const releases = [];
    const queue = new SettingsQueue((values) => {
        sent.push(values);
        return new Promise((resolve) => releases.push(resolve));
    });
    return { queue, sent, release: () => releases.shift()() };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

test("a single change is sent at once", async () => {
    const { queue, sent, release } = makeQueue();
    const done = queue.push("time_size", 50);
    assert.deepEqual(sent, [{ time_size: 50 }]);
    assert.equal(queue.busy, true);
    release();
    await done;
    assert.equal(queue.busy, false);
});

test("changes that pile up are merged into one request, newest value wins", async () => {
    const { queue, sent, release } = makeQueue();
    const done = queue.push("time_size", 50);
    queue.push("time_size", 51);
    queue.push("time_size", 52);
    queue.push("font", "georgia");
    assert.equal(sent.length, 1, "only the first request is on its way");
    release();
    await tick();
    assert.deepEqual(sent[1], { time_size: 52, font: "georgia" });
    release();
    await done;
    assert.equal(sent.length, 2);
    assert.equal(queue.busy, false);
});

test("the queue works again after it ran empty", async () => {
    const { queue, sent, release } = makeQueue();
    const first = queue.push("shadow_strength", 10);
    release();
    await first;
    const second = queue.push("shadow_strength", 15);
    assert.deepEqual(sent.at(-1), { shadow_strength: 15 });
    release();
    await second;
    assert.equal(queue.busy, false);
});

test("a failing request does not block the next one", async () => {
    const sent = [];
    const queue = new SettingsQueue(async (values) => {
        sent.push(values);
        if (sent.length === 1) {
            throw new Error("boom");
        }
    });
    await assert.rejects(queue.push("reset_delay", 3), /boom/);
    assert.equal(queue.busy, false);
    await queue.push("reset_delay", 4);
    assert.deepEqual(sent.at(-1), { reset_delay: 4 });
});
