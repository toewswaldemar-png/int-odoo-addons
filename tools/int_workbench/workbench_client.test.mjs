// node --test tools/int_workbench/workbench_client.test.mjs
import assert from "node:assert/strict";
import test from "node:test";

import { COMMAND_WAIT_MS, FIRST_CHECK_MS, OdooClient, SAFETY_CHECK_MS, SERVICE_GONE_SECONDS, SHARE_MS, ServiceError } from "../../int_workbench/static/src/workbench_client.js";

const DEVICE = { id: 7 };
const REPORT = { status: { connected: true }, errors: { active: [] }, errors_memory: { active_count: 0 } };

/** A clock that only moves when the test says so, and a sleep that moves it. */
function fakeTime() {
    const time = { t: 1_000_000 };
    return { time, now: () => time.t, sleep: async (ms) => (time.t += ms) };
}

/** A sleep that never ends: only the bus can end the wait. */
const noSleep = () => new Promise(() => {});

/** An ORM that answers from functions and notes its calls. */
function fakeOrm({ read, create }) {
    const calls = [];
    return {
        calls,
        read: async (model, ids, fields) => {
            calls.push({ method: "read", model, ids, fields });
            return read(model, ids, fields, calls.length);
        },
        create: async (model, records) => {
            calls.push({ method: "create", model, records });
            return create ? create(model, records) : [1];
        },
    };
}

const deviceRow = (extra = {}) => [{ id: 7, snapshot: REPORT, snapshot_at: "2026-11-09 10:00:00", report_age: 1.5, seen_age: 1.0, ...extra }];
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const commandReads = (orm) => orm.calls.filter((c) => c.method === "read" && c.model === "int.workbench.command");

test("a route is the part of the report that carries its name", async () => {
    const client = new OdooClient(fakeOrm({ read: () => deviceRow() }), DEVICE);
    assert.deepEqual(await client.get("/status"), { connected: true });
    assert.deepEqual(await client.get("/errors/memory"), { active_count: 0 });
    assert.deepEqual(await client.get("/errors"), { active: [] });
});

test("the report is read from the controller record, with the ages as the server counts them", async () => {
    const orm = fakeOrm({ read: () => deviceRow() });
    await new OdooClient(orm, DEVICE).get("/status");
    assert.deepEqual(orm.calls[0], { method: "read", model: "int.workbench.device", ids: [7], fields: ["snapshot", "snapshot_at", "report_age", "seen_age"] });
});

test("the views that ask together share one read", async () => {
    const { now, sleep, time } = fakeTime();
    const orm = fakeOrm({ read: () => deviceRow() });
    const client = new OdooClient(orm, DEVICE, { now, sleep });
    await Promise.all([client.get("/status"), client.get("/errors"), client.get("/clock").catch(() => null), client.get("/errors/memory")]);
    assert.equal(orm.calls.length, 1);
    time.t += SHARE_MS + 1;
    await client.get("/status");
    assert.equal(orm.calls.length, 2, "later, it is read again");
});

test("a route that the report does not have is a 404; the values and the clamps are rows now, not parts of the report", async () => {
    const client = new OdooClient(fakeOrm({ read: () => deviceRow() }), DEVICE);
    for (const path of ["/clock", "/nothing", "/values", "/clamps"]) {
        await assert.rejects(client.get(path), (error) => error instanceof ServiceError && error.status === 404);
    }
});

test("a service that is gone, never came, or has not reported, and an unreachable Odoo are all status 0", async () => {
    for (const [name, orm, message] of [
        ["never seen", fakeOrm({ read: () => deviceRow({ snapshot: false, snapshot_at: false, report_age: -1, seen_age: -1 }) }), /never been seen/],
        ["gone", fakeOrm({ read: () => deviceRow({ seen_age: SERVICE_GONE_SECONDS + 5 }) }), /not been seen for 25 s/],
        ["seen, but no report yet", fakeOrm({ read: () => deviceRow({ snapshot: false, snapshot_at: false, report_age: -1 }) }), /not reported yet/],
        ["Odoo away", fakeOrm({ read: () => Promise.reject(new Error("Connection lost")) }), /Connection lost/],
    ]) {
        await assert.rejects(new OdooClient(orm, DEVICE).get("/status"), (error) => error.status === 0 && message.test(error.message), name);
    }
});

test("an old report of a service that is there is shown, with its age", async () => {
    // the service keeps quiet while nobody looks; the page has just asked it to report: the old report is better than none
    const client = new OdooClient(fakeOrm({ read: () => deviceRow({ report_age: 45, seen_age: 1 }) }), DEVICE);
    assert.deepEqual(await client.get("/status"), { connected: true });
    assert.equal(client.reportAge, 45);
});

test("a service that was seen just in time is used", async () => {
    const client = new OdooClient(fakeOrm({ read: () => deviceRow({ seen_age: SERVICE_GONE_SECONDS }) }), DEVICE);
    assert.ok(await client.get("/status"));
});

test("a controller that was deleted is a 404", async () => {
    const client = new OdooClient(fakeOrm({ read: () => [] }), DEVICE);
    await assert.rejects(client.get("/status"), (error) => error.status === 404);
});

test("a clamp makes a request and the bus tells how it ended: nothing is asked in between", async () => {
    const orm = fakeOrm({ create: () => [42], read: () => assert.fail("the page must not ask when the bus tells") });
    const client = new OdooClient(orm, DEVICE, { sleep: noSleep });
    const done = client.post("/clamps/0016", { action: "set", value: 1 });
    await tick();
    client.settle({ id: 42, state: "done", message: "confirmed by the controller" });
    assert.deepEqual(await done, { confirmed: true, error: "" });
    assert.deepEqual(orm.calls[0], { method: "create", model: "int.workbench.command", records: [{ device_id: 7, code: "0016", action: "set", value: 1 }] });
    assert.equal(orm.calls.length, 1);
});

test("a message about a request that nobody waits for is ignored", async () => {
    const orm = fakeOrm({ create: () => [42], read: () => [{ id: 42, state: "pending", message: "" }] });
    const client = new OdooClient(orm, DEVICE, { sleep: noSleep });
    client.settle({ id: 99, state: "done", message: "" }); // another page's request
    assert.equal(client._ended.size, 0);
    assert.equal(client._waiting.size, 0);
    const done = client.post("/clamps/0016", { action: "release" });
    await tick();
    client.settle({ id: 99, state: "failed", message: "not ours" });
    client.settle({ id: 42, state: "failed", message: "no answer from the controller" });
    assert.deepEqual(await done, { confirmed: false, error: "no answer from the controller" });
});

test("a message that was missed is found by looking in Odoo", async () => {
    const { now, sleep } = fakeTime();
    const orm = fakeOrm({ create: () => [42], read: (model) => (model === "int.workbench.command" ? [{ id: 42, state: "done", message: "" }] : deviceRow()) });
    const result = await new OdooClient(orm, DEVICE, { now, sleep }).post("/clamps/0016", { action: "set", value: 1 });
    assert.deepEqual(result, { confirmed: true, error: "" });
    assert.equal(commandReads(orm).length, 1, "one look after the first short wait");
});

test("the looks in Odoo are few: not every few hundred milliseconds", async () => {
    const { now, sleep, time } = fakeTime();
    const started = time.t;
    const orm = fakeOrm({ create: () => [5], read: () => [{ id: 5, state: "pending", message: "" }] });
    await assert.rejects(new OdooClient(orm, DEVICE, { now, sleep }).post("/clamps/0013", { action: "set", value: 1 }), (error) => error.status === 504);
    assert.ok(time.t - started >= COMMAND_WAIT_MS);
    const looks = commandReads(orm).length;
    assert.ok(looks <= 1 + Math.ceil((COMMAND_WAIT_MS - FIRST_CHECK_MS) / SAFETY_CHECK_MS), `${looks} looks`);
    assert.ok(looks >= 10, `${looks} looks`);
});

test("a release has no value, and the code is the code of the row", async () => {
    const { now, sleep } = fakeTime();
    const orm = fakeOrm({ create: () => [5], read: () => [{ id: 5, state: "done", message: "" }] });
    await new OdooClient(orm, DEVICE, { now, sleep }).post("/clamps/4200", { action: "release" });
    assert.deepEqual(orm.calls[0].records, [{ device_id: 7, code: "4200", action: "release", value: 0 }]);
});

test("a request that failed, was not confirmed, is unknown or expired says why", async () => {
    for (const [state, message, error] of [
        ["failed", "the controller does not answer", "the controller does not answer"],
        ["unconfirmed", "", "unconfirmed"],
        ["unknown", "it may or may not have been carried out", "it may or may not have been carried out"],
        ["expired", "Nobody carried it out in time.", "Nobody carried it out in time."],
    ]) {
        const orm = fakeOrm({ create: () => [9], read: () => [{ id: 9, state, message }] });
        const { now, sleep } = fakeTime();
        const result = await new OdooClient(orm, DEVICE, { now, sleep }).post("/clamps/0013", { action: "set", value: 0 });
        assert.deepEqual(result, { confirmed: false, error }, state);
    }
});

test("after an answer the views read the report afresh", async () => {
    const { now, sleep } = fakeTime();
    const orm = fakeOrm({ create: () => [3], read: (model) => (model === "int.workbench.command" ? [{ id: 3, state: "done", message: "" }] : deviceRow()) });
    const client = new OdooClient(orm, DEVICE, { now, sleep });
    await client.get("/status");
    await client.post("/clamps/0013", { action: "release" });
    const before = orm.calls.length;
    await client.get("/status"); // at once, inside the time in which reads are shared
    assert.equal(orm.calls.length, before + 1, "not the report from before the answer");
});

test("only a clamp can be sent", async () => {
    const orm = fakeOrm({ read: () => deviceRow() });
    await assert.rejects(new OdooClient(orm, DEVICE).post("/reset", {}), (error) => error.status === 404);
    await assert.rejects(new OdooClient(orm, DEVICE).post("/clamps/a/b", { action: "release" }), (error) => error.status === 404);
    assert.equal(orm.calls.length, 0);
});
