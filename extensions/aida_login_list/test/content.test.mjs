// node --test test/*.test.mjs   (from extensions/aida_login_list, after `npm install`)
import assert from "node:assert/strict";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { JSDOM } from "jsdom";

const require = createRequire(import.meta.url);
const { loadConfig, fetchUsers, getUsers, attachList, watchField, main, LIST_ID, CACHE_KEY } = require("../content.js");

const FORM = `
<div ng-controller="C">
  <div id="login" ng-if="!$root.eingeloggt">
    <form>
      <div id="loginForm"><div id="loginInputs">
        <div class="loginControl">
          <input ng-virtual-keyboard class="loginFields loginFieldImg inputWidth minLogIn" placeholder="Benutzername"
                 ng-model="$root.login.UserName" type="text" autofocus/>
        </div>
        <input id="passwordFieldDirective" type="password" ng-model="$root.loginPassword"/>
      </div></div>
    </form>
  </div>
</div>`;

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

function page(html = FORM, options = {}) {
    const dom = new JSDOM(`<!doctype html><html><body>${html}</body></html>`, { runScripts: "outside-only", ...options });
    return dom.window;
}

function fakeStorage({ managed = {}, local = {} } = {}) {
    const area = (data) => ({
        get: async (keys) => Object.fromEntries(keys.filter((key) => key in data).map((key) => [key, data[key]])),
        set: async (values) => Object.assign(data, values),
    });
    return { managed: area(managed), local: area(local), data: { managed, local } };
}

const answer = (body, status = 200) => async () => ({ ok: status === 200, status, json: async () => body });

test("the settings: the policy wins over the options, both need an address and a token", async () => {
    assert.deepEqual(await loadConfig(fakeStorage({ local: { odooUrl: "http://o/", token: "t" } })), { odooUrl: "http://o", token: "t" });
    assert.deepEqual(
        await loadConfig(fakeStorage({ managed: { odooUrl: "http://managed", token: "m" }, local: { odooUrl: "http://o", token: "t" } })),
        { odooUrl: "http://managed", token: "m" }
    );
    assert.equal(await loadConfig(fakeStorage({ local: { odooUrl: "http://o" } })), null);
    assert.equal(await loadConfig(fakeStorage()), null);
    const broken = { managed: { get: async () => { throw new Error("no policy"); } }, local: fakeStorage({ local: { odooUrl: "http://o", token: "t" } }).local };
    assert.deepEqual(await loadConfig(broken), { odooUrl: "http://o", token: "t" });
});

test("the request: address, token escaped, no cache; only a list of names is accepted", async () => {
    let seen;
    const fetchFn = async (url, options) => {
        seen = { url, options };
        return { ok: true, status: 200, json: async () => ({ users: ["Epp, Nikolai"] }) };
    };
    assert.deepEqual(await fetchUsers({ odooUrl: "http://o:8069", token: "a b&c=€" }, fetchFn), ["Epp, Nikolai"]);
    assert.equal(seen.url, "http://o:8069/int_keepass/aida_users?token=a%20b%26c%3D%E2%82%AC");
    assert.equal(seen.options.cache, "no-store");
    await assert.rejects(fetchUsers({ odooUrl: "http://o", token: "t" }, answer({}, 404)), /404/);
    for (const body of [{}, { users: "x" }, { users: [1] }, null]) {
        await assert.rejects(fetchUsers({ odooUrl: "http://o", token: "t" }, answer(body)), /list of names/);
    }
});

test("an Odoo that does not answer in time is given up on", async () => {
    const never = (url, { signal }) => new Promise((resolve, reject) => signal.addEventListener("abort", () => reject(new Error("aborted"))));
    await assert.rejects(fetchUsers({ odooUrl: "http://o", token: "t" }, never, 20), /aborted/);
});

test("the names of the last time are used when Odoo is not there", async () => {
    const storage = fakeStorage();
    const config = { odooUrl: "http://o", token: "t" };
    assert.deepEqual(await getUsers(config, storage, answer({ users: ["A", "B"] })), ["A", "B"]);
    assert.deepEqual(storage.data.local[CACHE_KEY], ["A", "B"]);
    assert.deepEqual(await getUsers(config, storage, answer({}, 404)), ["A", "B"]);
    assert.deepEqual(await getUsers(config, storage, async () => { throw new Error("offline"); }), ["A", "B"]);
    assert.deepEqual(await getUsers(config, fakeStorage(), answer({}, 404)), []);
});

test("the list sits at the field, once, and follows a new list of names", () => {
    const window = page();
    const input = window.document.querySelector('input[ng-model="$root.login.UserName"]');
    attachList(input, ["Pauli, David", "Epp, Nikolai"]);
    attachList(input, ["Epp, Nikolai", "Keller, Max"]);
    assert.equal(window.document.querySelectorAll(`#${LIST_ID}`).length, 1);
    assert.deepEqual([...window.document.querySelectorAll(`#${LIST_ID} option`)].map((o) => o.value), ["Epp, Nikolai", "Keller, Max"]);
    assert.equal(input.getAttribute("list"), LIST_ID);
    assert.equal(input.getAttribute("autocomplete"), "off");
    assert.equal(window.document.querySelector(`#${LIST_ID}`).previousElementSibling, input);
});

test("a name with markup is text, not markup", () => {
    const window = page();
    const input = window.document.querySelector('input[ng-model="$root.login.UserName"]');
    attachList(input, ['<img src=x onerror="boom()">']);
    assert.equal(window.document.querySelectorAll("img").length, 0);
    assert.equal(window.document.querySelector(`#${LIST_ID} option`).value, '<img src=x onerror="boom()">');
});

test("a choice moves the cursor to the password, typing the name does not", () => {
    const window = page();
    const { document } = window;
    const input = document.querySelector('input[ng-model="$root.login.UserName"]');
    attachList(input, ["Epp, Nikolai"]);
    input.focus();
    input.value = "Epp, Nikolai";
    input.dispatchEvent(new window.InputEvent("input", { bubbles: true, inputType: "insertText", data: "i" }));
    assert.equal(document.activeElement, input, "typed letter by letter: stay");
    input.dispatchEvent(new window.InputEvent("input", { bubbles: true, inputType: "insertReplacementText" }));
    assert.equal(document.activeElement.id, "passwordFieldDirective", "chosen from the list: password");
    input.focus();
    input.value = "Someone else";
    input.dispatchEvent(new window.InputEvent("input", { bubbles: true, inputType: "insertReplacementText" }));
    assert.equal(document.activeElement, input, "a name that is not in the list: stay");
});

test("the field is waited for and found again when it is drawn again", async () => {
    const window = page("<div id='root'></div>");
    const { document } = window;
    const found = [];
    const observer = watchField(document, (input) => {
        found.push(input);
        input.dataset.aidaLoginList = "1";
    });
    await tick();
    assert.equal(found.length, 0);
    document.getElementById("root").innerHTML = FORM;
    await tick();
    assert.equal(found.length, 1);
    document.getElementById("root").innerHTML = "";
    document.getElementById("root").innerHTML = FORM;
    await tick();
    assert.equal(found.length, 2);
    observer.disconnect();
});

test("without settings the script does nothing; with them the list appears", async () => {
    const window = page();
    assert.equal(await main({ storage: fakeStorage() }, window.document, answer({ users: ["A"] })), null);
    assert.equal(window.document.getElementById(LIST_ID), null);
    const observer = await main({ storage: fakeStorage({ local: { odooUrl: "http://o", token: "t" } }) }, window.document, answer({ users: ["A", "B"] }));
    assert.equal(window.document.querySelectorAll(`#${LIST_ID} option`).length, 2);
    observer.disconnect();
});

// With the AngularJS that AIDA-Web ships, read from the server once (the file is not part of the repo).
async function angularSource() {
    const cache = path.join(os.tmpdir(), "aida-angular.min.js");
    if (existsSync(cache)) return readFileSync(cache, "utf8");
    const url = process.env.AIDA_ANGULAR_URL;
    if (!url) return null;
    try {
        const response = await fetch(url, { signal: AbortSignal.timeout(8000) });
        if (!response.ok) return null;
        const source = await response.text();
        writeFileSync(cache, source);
        return source;
    } catch {
        return null;
    }
}

test("AngularJS of AIDA-Web takes a choice from the list into its model", async (t) => {
    const source = await angularSource();
    if (!source) return t.skip("the AngularJS of AIDA-Web could not be read");
    const window = page(FORM);
    window.eval(source);
    window.angular
        .module("t", [])
        .controller("C", ["$rootScope", ($rootScope) => { $rootScope.login = { UserName: "" }; $rootScope.eingeloggt = false; }]);
    window.angular.bootstrap(window.document.body, ["t"]);
    const root = window.angular.element(window.document.body).injector().get("$rootScope");
    const observer = watchField(window.document, (input) => attachList(input, ["Epp, Nikolai", "Keller, Max"]));
    const input = () => window.document.querySelector('input[ng-model="$root.login.UserName"]');
    assert.equal(input().getAttribute("list"), LIST_ID);

    input().value = "Epp, Nikolai";
    input().dispatchEvent(new window.InputEvent("input", { bubbles: true, inputType: "insertReplacementText" }));
    assert.equal(root.login.UserName, "Epp, Nikolai", "the model of AngularJS has the chosen name");
    assert.equal(window.document.activeElement.id, "passwordFieldDirective");

    // log in and out: AngularJS draws the form anew (ng-if), the list has to come back
    root.$apply(() => { root.eingeloggt = true; });
    assert.equal(window.document.querySelector("#login"), null);
    root.$apply(() => { root.eingeloggt = false; });
    await tick();
    assert.equal(input().getAttribute("list"), LIST_ID, "the new field has the list");
    assert.equal(window.document.querySelectorAll(`#${LIST_ID}`).length, 1);
    observer.disconnect();
});
