// node --import ./register.mjs components.check.mjs
// The page of int_regler with the real Owl in jsdom: the templates are compiled, the components are mounted with props
// validation on, and the controller service is played by a fake fetch. Odoo services are stand-ins.
import fs from "node:fs";
import { createRequire } from "node:module";
import { HERE, MODULE_SRC, owlFile } from "./paths.mjs";

const { JSDOM } = createRequire(import.meta.url)("jsdom");
const dom = new JSDOM("<!doctype html><body><div id='stage'></div></body>", {
    url: "http://odoo.test/",
    pretendToBeVisual: true,
    runScripts: "outside-only",
});
const { window } = dom;
window.eval(fs.readFileSync(owlFile(), "utf8"));
globalThis.owl = window.owl;
globalThis.window = window;
globalThis.document = window.document;
globalThis.sessionStorage = window.sessionStorage;
globalThis.__registered = [];

let fails = 0;
const ok = (name, cond, extra = "") => {
    console.log((cond ? "PASS " : "FAIL ") + name + (extra ? "  " + extra : ""));
    if (!cond) {
        fails++;
    }
};
const wait = (ms = 25) => new Promise((resolve) => setTimeout(resolve, ms));
// Owl renders on animation frames and the reads go through several promises: wait for the thing itself, not for a guess.
const until = async (condition, timeout = 2000) => {
    for (let waited = 0; waited < timeout; waited += 10) {
        if (condition()) {
            return true;
        }
        await wait(10);
    }
    return condition();
};
const text = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");

// ---- the controller service, as far as the page uses it -------------------------------------------------------------

const CORE = "http://core.test:8085";
const TOKEN = "tok-123";
const state = {
    reachable: true,
    refuseClamps: false,
    clampsEnabled: true,
    calls: [], // {method, url, auth, body}
    clamps: [
        { code: "0001", name: "Klima Auto", analog: false, held: false, dirty: false, min: null, max: null, state: { text: "0", clamped: false, unit: "" }, last: null },
        { code: "0005", name: "Aussentemp", analog: true, held: false, dirty: false, min: -50, max: 124, step: 1, state: { text: "0.0°C", clamped: false, unit: "°C" }, last: null },
        { code: "0015", name: "Verdichter", analog: false, held: true, dirty: false, min: null, max: null, state: { text: "1", clamped: true, unit: "" }, last: null },
    ],
};
const entry = (id, code, name, text, status = "ok", extra = {}) => ({
    id, code, name, text, unit: "", status, stale: false, time: new Date().toISOString(), clamp: null, ...extra,
});
const ENTRIES = [
    entry(1, "0001", "Klima Auto (Option)", "0"),
    entry(5, "0005", "Aussentemp A1", "????", "out_of_range"),
    entry(15, "0015", "Verdichter A1", "1", "ok", { clamp: { clamped: true } }),
    entry(90, "0090", "COP_NodeID", "80", "ok", { stale: true }),
];
const json = (status, body) => ({ ok: status < 400, status, statusText: status === 401 ? "Unauthorized" : "x", json: async () => body });

globalThis.fetch = async (url, init = {}) => {
    const method = init.method || "GET";
    const headers = init.headers || {};
    const body = init.body ? JSON.parse(init.body) : null;
    state.calls.push({ method, url, auth: headers.Authorization, body });
    if (!state.reachable) {
        throw new TypeError("Failed to fetch");
    }
    const path = url.replace(CORE, "");
    const signedIn = headers.Authorization === `Bearer ${TOKEN}`;
    if (path === "/api/v1/me") {
        return json(
            200,
            signedIn
                ? { name: "tisch", kind: "user", roles: ["clamp"], rights: ["read", "clamp"] }
                : { name: "local", kind: "local", roles: ["read"], rights: ["read"] }
        );
    }
    if (path === "/api/v1/login") {
        return body.password === "right-pass"
            ? json(200, { token: TOKEN, user: { name: body.name, kind: "user", roles: ["clamp"], rights: ["read", "clamp"] } })
            : json(401, { error: "wrong user name or password" });
    }
    if (path === "/api/v1/logout") {
        return json(200, {});
    }
    const route = path.replace("/api/v1/devices/main", "");
    if (route === "/status") {
        return json(200, { state: "connected", connected: true, since: "2026-11-04T10:14:48+01:00", last_read: new Date().toISOString(), last_error: "", cycles: 12, last_cycle_ms: 3100, entries: 123, device: "11HA30" });
    }
    if (route === "/errors") {
        return json(200, {
            active: [{ word: "FWort001", bit: 7, text: "1001 CAN Netz Stoerung" }],
            words: [{ name: "FWort001", address: "M256", raw: "0140", bits: [{ bit: 7, text: "1001 CAN Netz Stoerung", active: true }, { bit: 1, text: "2012 RT-Fuehler def", active: false }] }],
        });
    }
    if (route === "/errors/memory") {
        return json(200, { active_count: 4, history_count: 2, status_total: 66, read_at: new Date().toISOString(), history: [{ code: 9998, text: "Speicherinitialisierung", count: 0, time: "2025-11-05T14:38:26" }, { code: 9997, text: "Spannungswiederkehr", count: 1, time: "2025-11-05T14:39:04" }] });
    }
    if (route === "/clock") {
        return json(200, { local_time: "2026-11-04 10:15:01", error: "" });
    }
    if (route === "/pages") {
        return json(200, { pages: [{ page: 0, entries: 4 }, { page: 1, entries: 2 }] });
    }
    if (route === "/values") {
        return json(200, { entries: ENTRIES });
    }
    if (route === "/pages/1") {
        return json(200, { entries: ENTRIES.slice(0, 2) });
    }
    if (route === "/clamps" && method === "GET") {
        return json(200, { enabled: state.clampsEnabled, rows: state.clamps });
    }
    const set = route.match(/^\/clamps\/(\d+)$/);
    if (set && method === "POST") {
        if (!signedIn) {
            return json(401, { error: "sign in first" });
        }
        if (state.refuseClamps) {
            return json(403, { error: "right clamp is missing" });
        }
        const row = state.clamps.find((r) => r.code === set[1]);
        if (body.action === "set") {
            row.held = true;
            row.state = { ...row.state, clamped: true, text: String(body.value) };
        } else {
            row.held = false;
            row.state = { ...row.state, clamped: false };
        }
        return json(200, { code: row.code, action: body.action, confirmed: true });
    }
    return json(404, { error: "unknown path" });
};

// ---- the services of Odoo that the page uses -------------------------------------------------------------------------

const notes = [];
globalThis.__services = {
    orm: {
        searchRead: async (model) => {
            if (model !== "int.regler.device") {
                throw new Error(`searchRead on ${model}`);
            }
            return [
                { id: 1, name: "Bench", core_url: CORE, device_ref: "main" },
                { id: 2, name: "Other", core_url: "http://other.test:8085", device_ref: "main" },
            ];
        },
    },
    notification: { add: (message, options) => notes.push({ message, ...options }) },
};

// ---- mount ------------------------------------------------------------------------------------------------------------

const { IntReglerApp } = await import("../../int_regler/static/src/regler_app.js");
ok("the page registers itself as the client action", globalThis.__registered.some((r) => r.category === "actions" && r.key === "int_regler.app" && r.value === IntReglerApp));

const target = document.getElementById("stage");
const app = new owl.App(IntReglerApp, { env: {}, props: {}, dev: true, warnIfNoStaticProps: false });
for (const name of ["regler_app.xml", "regler_views.xml"]) {
    app.addTemplates(fs.readFileSync(`${MODULE_SRC}/${name}`, "utf8"));
}
await app.mount(target);
await until(() => text(target).includes("status records") && text(target).includes("1001 CAN Netz Stoerung"));

const $ = (selector, root = target) => root.querySelector(selector);
const $$ = (selector, root = target) => [...root.querySelectorAll(selector)];
const click = async (el, ms = 50) => {
    el.click();
    await wait(ms);
};
const tab = (label) => $$(".nav-pills .nav-link").find((a) => text(a).startsWith(label));
const button = (label, root = target) => $$("button", root).find((b) => text(b).includes(label));
const lastNote = () => notes[notes.length - 1];
const type = async (el, value) => {
    el.value = value;
    el.dispatchEvent(new window.Event("input", { bubbles: true }));
    await wait(50);
};

// the header
ok("the controllers of Odoo are in the list", $$("select option").map((o) => text(o)).join() === "Bench,Other");
ok("the status of the service is shown", text($(".badge.rounded-pill")) === "Connected", text($(".badge.rounded-pill")));
ok("the four views are there", $$(".nav-pills .nav-link").map((a) => text(a)).join() === "Overview,Process values,Errors,Clamps");
ok("the first read goes to the address of the first controller", state.calls.some((c) => c.url === `${CORE}/api/v1/devices/main/status`));
ok("nothing but the service is called (Odoo gets no values)", state.calls.every((c) => c.url.startsWith(CORE)));
ok("no sign-in yet: no token is sent", state.calls.every((c) => c.auth === undefined));

// overview
ok("overview: the cycle", text(target).includes("3.1 s"));
ok("overview: the active error is named", text(target).includes("1001 CAN Netz Stoerung"));
ok("overview: the error memory counts", text(target).includes("66") && text(target).includes("status records"));
ok("overview: the controller time", text(target).includes("2026-11-04 10:15:01"));

// values
await click(tab("Process values"));
await until(() => $$("tbody tr").length === 4);
let rows = $$("tbody tr");
ok("values: one row per entry", rows.length === 4, String(rows.length));
ok("values: the text of a row", text(rows[0]).includes("Klima Auto (Option)") && text(rows[0]).includes("current"));
ok("values: a sensor without a value says so", text(rows[1]).includes("no value"));
ok("values: a clamped row says so", text(rows[2]).includes("clamped"));
ok("values: an old row says so", text(rows[3]).includes("stale"));
ok("values: the pages are tabs", ["All", "Auxiliary page", "Page 1"].every((l) => tab(l)));
await type($("input[type=search]"), "cop_");
ok("values: the search narrows the rows", $$("tbody tr").length === 1 && text($("tbody tr")).includes("COP_NodeID"));
await type($("input[type=search]"), "0005");
ok("values: the search takes the code too", $$("tbody tr").length === 1 && text($("tbody tr")).includes("Aussentemp"));
await type($("input[type=search]"), "nothing like this");
ok("values: nothing found is said", text($("tbody")).includes("No entries found"));
await type($("input[type=search]"), "");
await click(tab("Page 1"));
await until(() => $$("tbody tr").length === 2);
ok("values: a page tab reads that page", state.calls.some((c) => c.url.endsWith("/devices/main/pages/1")) && $$("tbody tr").length === 2);

// errors
await click($$(".nav-pills .nav-link").find((a) => text(a).startsWith("Errors")));
await until(() => text(target).includes("FWort001.7"));
ok("errors: the active signal", text(target).includes("1001 CAN Netz Stoerung") && text(target).includes("FWort001.7"));
await click($$(".nav-tabs .nav-link").find((a) => text(a).startsWith("History")));
await until(() => $$("tbody tr").length === 2);
ok("errors: the history", $$("tbody tr").length === 2 && text($("tbody")).includes("2025-11-05 14:38:26"));
await click($$(".nav-tabs .nav-link").find((a) => text(a).startsWith("Error words")));
await until(() => $$(".badge.text-bg-danger").length === 1);
ok("errors: the error words with their bits", text(target).includes("FWort001") && $$(".badge.text-bg-danger").length === 1);

// clamps, not signed in
await click(tab("Clamps"));
await until(() => $$("tbody tr").length === 3);
ok("clamps: sign-in needed", text($(".alert")).includes("Sign-in needed"));
ok("clamps: every control is locked", $$("tbody button").every((b) => b.disabled) && $$("tbody input[type=number]").every((i) => i.disabled));
ok("clamps: a clamped row is marked", text($$("tbody tr")[2]).includes("clamped"));
const before = state.calls.length;
await click($$("tbody button").find((b) => text(b).includes("To 1")));
ok("clamps: a locked button sends nothing", state.calls.slice(before).every((c) => c.method === "GET"));

// the sign-in at the service
await click(button("Sign in at the service"));
ok("sign-in: the form opens", !!$("form"));
await type($("#int_regler_name"), "tisch");
await type($("#int_regler_password"), "wrong-pass");
await click($("form button[type=submit]"), 60);
ok("sign-in: a wrong password gives one neutral message", text($("form")).includes("Name or password wrong."));
ok("sign-in: the password field is empty again", $("#int_regler_password").value === "");
await type($("#int_regler_password"), "right-pass");
await click($("form button[type=submit]"), 80);
ok("sign-in: it works", text(target).includes("tisch") && text(target).includes("clamp") && !$("form"));
ok("sign-in: the token is kept for this service only", window.sessionStorage.getItem(`int_regler.token:${CORE}`) === TOKEN);
ok("sign-in: nothing is stored under another key", window.sessionStorage.length === 1);
ok("sign-in: the password goes to the service only", !JSON.stringify(state.calls.filter((c) => !c.url.endsWith("/login"))).includes("right-pass"));
ok("sign-in: a message tells it", lastNote()?.type === "success");
await wait(60);
ok("clamps: the controls are open now", !!$$("tbody button").find((b) => text(b).includes("To 1") && !b.disabled));

// clamp, release
await click($$("tbody button").find((b) => text(b).includes("To 1")), 80);
let post = state.calls.filter((c) => c.method === "POST" && c.url.includes("/clamps/")).pop();
ok("clamp: a POST to the row with the value", post?.url === `${CORE}/api/v1/devices/main/clamps/0001` && post.body.action === "set" && post.body.value === 1, JSON.stringify(post?.body));
ok("clamp: the token goes with it", post?.auth === `Bearer ${TOKEN}`);
ok("clamp: it went out with one click, without a question in between", !$(".modal, [role=dialog]"));
ok("clamp: the answer is told", lastNote()?.type === "success" && lastNote().message.includes("clamped to 1"), lastNote()?.message);
ok("clamp: the new state is read at once", text($$("tbody tr")[0]).includes("clamped"));
await click($$("tbody button").find((b) => text(b).includes("To 0")), 80);
post = state.calls.filter((c) => c.method === "POST" && c.url.includes("/clamps/")).pop();
ok("clamp: to 0 sends 0, not nothing", post.body.value === 0 && post.body.action === "set");

// analog row
const analog = $$("tbody tr")[1];
const field = $("input[type=number]", analog);
ok("analog: the field starts at the lowest value and has the limits", field.value === "-50" && field.min === "-50" && field.max === "124");
await type(field, "500");
ok("analog: a value above the limit cannot be sent", button("Clamp", analog).disabled);
await type(field, "");
ok("analog: an empty field cannot be sent", button("Clamp", analog).disabled);
await type(field, "21");
ok("analog: a value inside the limits can", !button("Clamp", analog).disabled);
await click(button("Clamp", analog), 80);
post = state.calls.filter((c) => c.method === "POST" && c.url.includes("/clamps/")).pop();
ok("analog: the number is sent as a number", post.url.endsWith("/clamps/0005") && post.body.action === "set" && post.body.value === 21 && typeof post.body.value === "number", JSON.stringify(post.body));

// release
await click(button("Release", $$("tbody tr")[2]), 80);
post = state.calls.filter((c) => c.method === "POST" && c.url.includes("/clamps/")).pop();
ok("release: a POST with the action only", post.url.endsWith("/clamps/0015") && post.body.action === "release" && !("value" in post.body), JSON.stringify(post.body));
ok("release: a row that is not clamped has its release button locked", button("Release", $$("tbody tr")[2]).disabled);
const posts = state.calls.filter((c) => c.method === "POST" && c.url.includes("/clamps/")).length;
await click(button("Release all"), 200);
const released = state.calls.filter((c) => c.method === "POST" && c.url.includes("/clamps/")).slice(posts);
ok("release all: only the clamped rows are released", released.length === 2 && released.every((c) => c.body.action === "release"), `${released.length}`);
ok("release all: nothing is clamped afterwards", text(target).includes("0 clamps active"));

// a service that says no
state.refuseClamps = true;
await click($$("tbody button").find((b) => text(b).includes("To 1")), 80);
ok("a refusal of the service is told with its text", lastNote()?.type === "danger" && lastNote().message.includes("right clamp is missing"), lastNote()?.message);
state.refuseClamps = false;

// the sign-out
await click(button("Sign out"), 80);
ok("sign-out: the token is gone", window.sessionStorage.getItem(`int_regler.token:${CORE}`) === null);
ok("sign-out: the controls are locked again", $$("tbody button").every((b) => b.disabled));

// the clamps are not released at the service
state.clampsEnabled = false;
await wait(2700);
ok("not released: the page says so", text($(".alert")).includes("Clamps are not released"));
state.clampsEnabled = true;

// another controller: its own address, its own token
const callsBefore = state.calls.length;
const select = $("select");
select.value = "2";
select.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait(120);
ok("switch: the other service is asked", state.calls.slice(callsBefore).some((c) => c.url.startsWith("http://other.test:8085")));

// a service that cannot be reached
state.reachable = false;
select.value = "1";
select.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait(150);
ok("unreachable: the page says so and names the address", text($(".alert-danger")).includes("cannot be reached") && text($(".alert-danger")).includes(CORE));
state.reachable = true;

// leaving the page stops the reading
app.destroy();
const afterDestroy = state.calls.length;
await wait(2800);
ok("destroy: nothing is read any more", state.calls.length === afterDestroy, `${state.calls.length - afterDestroy} calls after the end`);

console.log(fails ? `${fails} FAILED` : "ALL PASSED");
process.exit(fails ? 1 : 0);
