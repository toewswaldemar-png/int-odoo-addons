// node --test int_keepass/tools/header.test.mjs
import assert from "node:assert/strict";
import test from "node:test";

import { HEADER, HEADER_EMAIL, encodePassword, wrapRpc } from "../static/src/keepass_header.js";

const calls = [];
const original = function (url, params, settings) {
    calls.push({ url, params, settings, self: this });
    return Promise.resolve("sent");
};

test("the password travels as base64 of its UTF-8 bytes", () => {
    assert.equal(Buffer.from(encodePassword("pässwörd-€"), "base64").toString("utf8"), "pässwörd-€");
    assert.match(encodePassword("pässwörd-€"), /^[A-Za-z0-9+/=]+$/);
});

test("a call to a keepass model carries the header and keeps other settings", async () => {
    calls.length = 0;
    const keepass = { password: "secret", onLocked: () => assert.fail("must not lock") };
    const rpc = wrapRpc(original, keepass);
    const result = await rpc("/web/dataset/call_kw/x", { model: "int.keepass.entry" }, { silent: true, headers: { A: "1" } });
    assert.equal(result, "sent");
    assert.equal(calls[0].settings.headers[HEADER], encodePassword("secret"));
    assert.equal(calls[0].settings.headers.A, "1");
    assert.equal(calls[0].settings.silent, true);
});

test("a call to another model is left alone", async () => {
    calls.length = 0;
    const keepass = { password: "secret", onLocked: () => assert.fail("must not lock") };
    const settings = {};
    await wrapRpc(original, keepass)("/x", { model: "res.partner" }, settings);
    assert.equal(calls[0].settings, settings);
    assert.equal(settings.headers, undefined);
    await wrapRpc(original, keepass)("/web/session/check", {}, settings);
    assert.equal(calls.length, 2);
});

test("without a password the call is held back and the unlock screen is asked for", async () => {
    calls.length = 0;
    let locked = 0;
    const keepass = { password: null, onLocked: () => locked++ };
    const held = wrapRpc(original, keepass)("/x", { model: "int.keepass.group" }, {});
    assert.equal(calls.length, 0);
    assert.equal(locked, 1);
    assert.equal(typeof held.abort, "function");
    const outcome = await Promise.race([held.then(() => "settled"), new Promise((resolve) => setTimeout(() => resolve("pending"), 20))]);
    assert.equal(outcome, "pending");
});

test("the password is not part of the sent parameters", async () => {
    calls.length = 0;
    const keepass = { password: "secret", onLocked: null };
    await wrapRpc(original, keepass)("/x", { model: "int.keepass.entry", kwargs: {} }, {});
    assert.equal(JSON.stringify(calls[0].params).includes("secret"), false);
});

test("the e-mail address of a Vaultwarden account travels as its own header, only when there is one", async () => {
    calls.length = 0;
    const rpc = wrapRpc(original, { password: "secret", email: "wäldi@example.test", onLocked: null });
    await rpc("/x", { model: "int.keepass.entry", method: "web_search_read" }, {});
    assert.equal(Buffer.from(calls[0].settings.headers[HEADER_EMAIL], "base64").toString("utf8"), "wäldi@example.test");
    await wrapRpc(original, { password: "secret", email: null, onLocked: null })("/x", { model: "int.keepass.entry" }, {});
    assert.equal(calls[1].settings.headers[HEADER_EMAIL], undefined);
});

test("asking where the data comes from works before there is a password", async () => {
    calls.length = 0;
    const keepass = { password: null, email: null, onLocked: () => assert.fail("must not lock") };
    const result = await wrapRpc(original, keepass)("/x", { model: "int.keepass.entry", method: "get_source_info" }, {});
    assert.equal(result, "sent");
    assert.equal(calls[0].settings.headers, undefined);
});
