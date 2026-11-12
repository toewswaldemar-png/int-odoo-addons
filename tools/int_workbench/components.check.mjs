// node --import ./register.mjs components.check.mjs
// The page of int_workbench (overview and errors) with the real Owl in jsdom: the templates are compiled, the components are mounted
// with props validation on, and Odoo (the controller record with the report of the service) is played by a fake ORM. The process
// values and the clamps are not on the page: they are the list "Process values" (see parameters.check.mjs).
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
const until = async (condition, timeout = 3000) => {
    for (let waited = 0; waited < timeout; waited += 10) {
        if (condition()) {
            return true;
        }
        await wait(10);
    }
    return condition();
};
const text = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");


// ---- Odoo, as far as the page uses it -------------------------------------------------------------------------------

const state = {
    reportAge: 1, // seconds since the service reported, by the clock of the server (null: it never did)
    seenAge: 1, // seconds since the service last asked Odoo (-1: never)
    calls: [], // {method, model, ids}
    watches: [], // the controllers the page said it looks at
    busUsed: false, // did the page touch the bus
};
const report = () => ({
    status: { state: "connected", connected: true, since: "2026-11-04T10:14:48+01:00", last_read: new Date().toISOString(), last_error: "", cycles: 12, last_cycle_ms: 3100, entries: 123, device: "11HA30" },
    errors: {
        active: [{ word: "FWort001", bit: 7, text: "1001 CAN Netz Stoerung" }],
        words: [{ name: "FWort001", address: "M256", raw: "0140", bits: [{ bit: 7, text: "1001 CAN Netz Stoerung", active: true }, { bit: 1, text: "2012 RT-Fuehler def", active: false }] }],
    },
    errors_memory: { active_count: 4, history_count: 2, status_total: 66, read_at: new Date().toISOString(), history: [{ code: 9998, text: "Speicherinitialisierung", count: 0, time: "2025-11-05T14:38:26" }, { code: 9997, text: "Spannungswiederkehr", count: 1, time: "2025-11-05T14:39:04" }] },
    clock: { local_time: "2026-11-04 10:15:01", error: "" },
});

globalThis.__user = { hasGroup: async () => false };
globalThis.__services = {
    orm: {
        searchRead: async (model) => {
            state.calls.push({ method: "searchRead", model });
            return [
                { id: 1, name: "Bench", device_ref: "main" },
                { id: 2, name: "Other", device_ref: "main" },
            ];
        },
        read: async (model, ids) => {
            state.calls.push({ method: "read", model, ids });
            if (state.reportAge === null) {
                return [{ id: ids[0], snapshot: false, snapshot_at: false, report_age: -1, seen_age: state.seenAge }];
            }
            return [{ id: ids[0], snapshot: report(), snapshot_at: "2026-11-09 10:00:00", report_age: state.reportAge, seen_age: state.seenAge }];
        },
        silent: {
            call: async (model, method, args) => {
                state.calls.push({ method: "silent." + method, model });
                if (method === "watch") {
                    state.watches.push(args[0][0]);
                }
                return true;
            },
        },
    },
    // the page does not use the bus and the notifications any more: if it did, this would show
    bus_service: new Proxy({}, { get: () => { state.busUsed = true; return () => {}; } }),
    notification: { add: () => {} },
};

// ---- mount ------------------------------------------------------------------------------------------------------------

const { IntReglerApp } = await import("../../int_workbench/static/src/workbench_app.js");
ok("the page registers itself as the client action", globalThis.__registered.some((r) => r.category === "actions" && r.key === "int_workbench.app" && r.value === IntReglerApp));

const target = document.getElementById("stage");
async function start() {
    const app = new owl.App(IntReglerApp, { env: {}, props: {}, dev: true, warnIfNoStaticProps: false });
    for (const name of ["workbench_app.xml", "workbench_views.xml"]) {
        app.addTemplates(fs.readFileSync(`${MODULE_SRC}/${name}`, "utf8"));
    }
    await app.mount(target);
    return app;
}

const $ = (selector, root = target) => root.querySelector(selector);
const $$ = (selector, root = target) => [...root.querySelectorAll(selector)];
const click = async (el, ms = 50) => {
    el.click();
    await wait(ms);
};
const tab = (label) => $$(".nav-pills .nav-link").find((a) => text(a).startsWith(label));
const button = (label, root = target) => $$("button", root).find((b) => text(b).includes(label));
const change = async (el, value, ms = 60) => {
    el.value = value;
    el.dispatchEvent(new window.Event("change", { bubbles: true }));
    await wait(ms);
};
const deviceReads = () => state.calls.filter((c) => c.method === "read" && c.model === "int.workbench.device").length;
const setHidden = (hidden) => {
    Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
    document.dispatchEvent(new window.Event("visibilitychange"));
};

// ===== the page ===========================================================================================================
let app = await start();
await until(() => text(target).includes("status records") && text(target).includes("1001 CAN Netz Stoerung"));

ok("the controllers of Odoo are in the list", $$("select option").map((o) => text(o)).join() === "Bench,Other");
ok("the status of the controller is shown", text($(".badge.rounded-pill")) === "Connected", text($(".badge.rounded-pill")));
ok("the views are the overview and the errors: the values and clamps are the list of process values", $$(".nav-pills .nav-link").map((a) => text(a)).join() === "Overview,Errors", $$(".nav-pills .nav-link").map((a) => text(a)).join());
ok("the report of the first controller is read from its record", state.calls.some((c) => c.method === "read" && c.model === "int.workbench.device" && c.ids[0] === 1));
ok("there is no sign-in at the service: the page does not know the service", !button("Sign in") && !$("form") && !text(target).includes("Sign out"));
ok("somebody looks: the page says so at once", state.watches.join() === "1", state.watches.join());
ok("the page only reads: no clamp, no table of values, no bus", !$("table.o_int_workbench_table") && !text(target).includes("Release all") && !state.busUsed);

// overview
ok("overview: the cycle", text(target).includes("3.1 s"));
ok("overview: the active error is named", text(target).includes("1001 CAN Netz Stoerung"));
ok("overview: the error memory counts", text(target).includes("66") && text(target).includes("status records"));
ok("overview: the controller time", text(target).includes("2026-11-04 10:15:01"));
ok("overview: a fresh report has no age shown", !text(target).includes("s old"));
const readsAtOnce = deviceReads();
ok("overview: the four readings share few reads of Odoo", readsAtOnce <= 3, String(readsAtOnce));

// errors
await click(tab("Errors"));
await until(() => text(target).includes("FWort001.7"));
ok("errors: the active signal", text(target).includes("1001 CAN Netz Stoerung") && text(target).includes("FWort001.7"));
await click($$(".nav-tabs .nav-link").find((a) => text(a).startsWith("History")));
await until(() => $$("tbody tr").length === 2);
ok("errors: the history", $$("tbody tr").length === 2 && text($("tbody")).includes("2025-11-05 14:38:26"));
await click($$(".nav-tabs .nav-link").find((a) => text(a).startsWith("Error words")));
await until(() => $$(".badge.text-bg-danger").length === 1);
ok("errors: the error words with their bits", text(target).includes("FWort001") && $$(".badge.text-bg-danger").length === 1);

// the report is old: the service keeps quiet while nobody looks, and has just been asked to report
state.reportAge = 45;
await until(() => text(target).includes("report 45 s old"));
ok("old report: it is shown with its age, and no alarm", text(target).includes("report 45 s old") && !$(".alert-danger") && text($(".badge.rounded-pill")) === "Connected");
state.reportAge = 1;
await until(() => !text(target).includes("s old"));
ok("fresh report: the age goes", !text(target).includes("s old"));

// the service is gone, or never came, or has not reported
state.seenAge = 30;
await until(() => !!$(".alert-danger"));
ok("service gone: the page says so with the time", text($(".alert-danger")).includes("No report from the controller service") && text($(".alert-danger")).includes("not been seen for 30 s"));
ok("service gone: the badge is not green", text($(".badge.rounded-pill")) === "No report");
state.seenAge = -1;
await until(() => text($(".alert-danger")).includes("never been seen"));
ok("never seen: the page says so", text($(".alert-danger")).includes("never been seen"));
state.seenAge = 1;
state.reportAge = null;
await until(() => text($(".alert-danger")).includes("not reported yet"));
ok("seen but no report yet: the page says so", text($(".alert-danger")).includes("not reported yet"));
state.reportAge = 1;
await until(() => !$(".alert-danger"));
ok("the service is back: the message goes", !$(".alert-danger"));

// a tab that nobody sees: no reading, no heartbeat; when it is seen again, both start at once
const watchesBefore = state.watches.length;
setHidden(true);
await wait(60);
ok("hidden: the heartbeat is not sent", state.watches.length === watchesBefore);
const readsHidden = deviceReads();
await wait(2700);
ok("hidden: the page does not read the report", deviceReads() === readsHidden, `${deviceReads() - readsHidden} reads`);
setHidden(false);
await until(() => state.watches.length === watchesBefore + 1);
ok("seen again: the heartbeat goes at once", state.watches.length === watchesBefore + 1);
await until(() => deviceReads() > readsHidden, 3500);
ok("seen again: the reading goes on", deviceReads() > readsHidden);

// another controller: its own record, and it is the one that somebody looks at now
const callsBefore = state.calls.length;
await change($("select"), "2", 150);
ok("switch: the report of the other controller is read", state.calls.slice(callsBefore).some((c) => c.method === "read" && c.model === "int.workbench.device" && c.ids[0] === 2));
ok("switch: the page says that it looks at the other controller", state.watches.at(-1) === 2, state.watches.join());

// leaving the page stops the reading
app.destroy();
await wait(100);
const afterDestroy = state.calls.length;
await wait(2800);
ok("destroy: nothing is read any more", state.calls.length === afterDestroy, `${state.calls.length - afterDestroy} calls after the end`);
ok("the page asked of Odoo only to read, to list and to say that somebody looks", state.calls.every((c) => ["searchRead", "read", "silent.watch"].includes(c.method)));

console.log(fails ? `${fails} FAILED` : "ALL PASSED");
process.exit(fails ? 1 : 0);
