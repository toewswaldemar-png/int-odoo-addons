// node --test tools/int_regler/core_client.test.mjs
import assert from "node:assert/strict";
import test from "node:test";

import { CoreClient, CoreError, deviceBase } from "../../int_regler/static/src/core_client.js";

const DEVICE = { core_url: "http://127.0.0.1:8085/", device_ref: "main" };

function memoryStorage() {
    const data = new Map();
    return {
        getItem: (key) => (data.has(key) ? data.get(key) : null),
        setItem: (key, value) => data.set(key, String(value)),
        removeItem: (key) => data.delete(key),
        data,
    };
}

/** A fetch that answers from a list and notes what it was asked. */
function fakeFetch(answers) {
    const calls = [];
    const fetchImpl = async (url, init) => {
        calls.push({ url, init });
        const answer = answers.shift();
        if (answer instanceof Error) {
            throw answer;
        }
        return {
            ok: answer.status < 400,
            status: answer.status,
            statusText: answer.statusText || "",
            json: async () => {
                if (answer.body === undefined) {
                    throw new SyntaxError("no JSON");
                }
                return answer.body;
            },
        };
    };
    return { fetchImpl, calls };
}

test("the route base has the address, the API path and the controller id, without a double slash", () => {
    assert.equal(deviceBase("http://127.0.0.1:8085/", "main"), "http://127.0.0.1:8085/api/v1/devices/main");
    assert.equal(deviceBase("/regler", "tisch 2"), "/regler/api/v1/devices/tisch%202");
    assert.equal(new CoreClient(DEVICE, { storage: memoryStorage() }).base, "http://127.0.0.1:8085/api/v1/devices/main");
});

test("a read without a sign-in sends no authorization", async () => {
    const { fetchImpl, calls } = fakeFetch([{ status: 200, body: { state: "connected" } }]);
    const client = new CoreClient(DEVICE, { storage: memoryStorage(), fetchImpl });
    assert.deepEqual(await client.get("/status"), { state: "connected" });
    assert.equal(calls[0].url, "http://127.0.0.1:8085/api/v1/devices/main/status");
    assert.equal(calls[0].init.headers.Authorization, undefined);
});

test("the sign-in keeps the token per service address and sends it afterwards", async () => {
    const storage = memoryStorage();
    const { fetchImpl, calls } = fakeFetch([
        { status: 200, body: { token: "t0k", user: { name: "tisch", kind: "user", roles: ["clamp"], rights: ["read", "clamp"] } } },
        { status: 200, body: { rows: [] } },
    ]);
    const client = new CoreClient(DEVICE, { storage, fetchImpl });
    const user = await client.login("tisch", "secret-pass");
    assert.equal(user.name, "tisch");
    assert.equal(storage.getItem("int_regler.token:http://127.0.0.1:8085"), "t0k");
    assert.equal(calls[0].url, "http://127.0.0.1:8085/api/v1/login");
    assert.deepEqual(JSON.parse(calls[0].init.body), { name: "tisch", password: "secret-pass" });
    await client.get("/clamps");
    assert.equal(calls[1].init.headers.Authorization, "Bearer t0k");
    // another service does not get this token
    const other = new CoreClient({ core_url: "http://10.0.0.9:8085", device_ref: "main" }, { storage });
    assert.equal(other.token, null);
});

test("the password is not stored and not part of any url", async () => {
    const storage = memoryStorage();
    const { fetchImpl, calls } = fakeFetch([{ status: 200, body: { token: "t", user: {} } }]);
    await new CoreClient(DEVICE, { storage, fetchImpl }).login("tisch", "secret-pass");
    assert.equal(JSON.stringify([...storage.data]).includes("secret-pass"), false);
    assert.equal(calls[0].url.includes("secret-pass"), false);
});

test("a write is a POST with a JSON body", async () => {
    const { fetchImpl, calls } = fakeFetch([{ status: 200, body: { confirmed: true } }]);
    const client = new CoreClient(DEVICE, { storage: memoryStorage(), fetchImpl });
    assert.deepEqual(await client.post("/clamps/0001", { action: "set", value: 1 }), { confirmed: true });
    assert.equal(calls[0].init.method, "POST");
    assert.equal(calls[0].init.headers["Content-Type"], "application/json");
    assert.deepEqual(JSON.parse(calls[0].init.body), { action: "set", value: 1 });
});

test("an error answer carries the status, the text of the service and the body", async () => {
    const { fetchImpl } = fakeFetch([{ status: 403, statusText: "Forbidden", body: { error: "right clamp is missing", code: "x" } }]);
    const client = new CoreClient(DEVICE, { storage: memoryStorage(), fetchImpl });
    await assert.rejects(
        () => client.post("/clamps/0001", { action: "release" }),
        (error) => error instanceof CoreError && error.status === 403 && error.message === "right clamp is missing" && error.body.code === "x"
    );
});

test("an answer without a body still gives the status text", async () => {
    const { fetchImpl } = fakeFetch([{ status: 502, statusText: "Bad Gateway" }]);
    const client = new CoreClient(DEVICE, { storage: memoryStorage(), fetchImpl });
    await assert.rejects(
        () => client.get("/status"),
        (error) => error.status === 502 && error.message === "Bad Gateway"
    );
});

test("a service that cannot be reached is status 0 with a message that says so", async () => {
    const { fetchImpl } = fakeFetch([new TypeError("Failed to fetch")]);
    const client = new CoreClient(DEVICE, { storage: memoryStorage(), fetchImpl });
    await assert.rejects(
        () => client.get("/status"),
        (error) => error instanceof CoreError && error.status === 0 && /cannot be reached/.test(error.message)
    );
});

test("an abort passes through and is not reported as an unreachable service", async () => {
    const abort = Object.assign(new Error("aborted"), { name: "AbortError" });
    const { fetchImpl } = fakeFetch([abort]);
    const client = new CoreClient(DEVICE, { storage: memoryStorage(), fetchImpl });
    await assert.rejects(() => client.get("/status"), (error) => error.name === "AbortError");
});

test("without a usable storage the page works, the sign-in just does not last", async () => {
    const broken = {
        getItem: () => {
            throw new Error("blocked");
        },
        setItem: () => {
            throw new Error("blocked");
        },
        removeItem: () => {
            throw new Error("blocked");
        },
    };
    const { fetchImpl } = fakeFetch([{ status: 200, body: { token: "t", user: { name: "x" } } }]);
    const client = new CoreClient(DEVICE, { storage: broken, fetchImpl });
    assert.equal(client.token, null);
    assert.equal((await client.login("x", "y")).name, "x");
});

test("signing out forgets the token even when the service does not answer", async () => {
    const storage = memoryStorage();
    storage.setItem("int_regler.token:http://127.0.0.1:8085", "t0k");
    const { fetchImpl } = fakeFetch([new TypeError("Failed to fetch")]);
    const client = new CoreClient(DEVICE, { storage, fetchImpl });
    await assert.rejects(() => client.logout());
    assert.equal(client.token, null);
});
