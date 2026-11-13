// node --import ./register.mjs parameters.check.mjs
// The list of process values of int_workbench with the real Owl in jsdom: the controller (bus, heartbeat, reload, the message when a
// clamp request did not work out). The list of Odoo is a stand-in with the rows and the model the controller reads; the ORM, the bus
// and the notifications are fakes.
import fs from "node:fs";
import { createRequire } from "node:module";
import { owlFile } from "./paths.mjs";

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

// ---- the stand-in for the list of Odoo -------------------------------------------------------------------------------------

const rowLoads = []; // the resIds of the rows that were loaded again in place
const row = (id, deviceId, code, extra = {}) => ({
    id: `rec${id}`,
    resId: id,
    load: async () => {
        if (globalThis.__rowLoadFails) {
            throw new Error("gone");
        }
        rowLoads.push(id);
    },
    data: { device_id: { id: deviceId, display_name: `Device ${deviceId}` }, code, can_clamp: true, analog: false, clamped: false, clamp_value: 0, value: 0, ...extra },
});
const model = {
    loads: 0,
    root: { records: [], groupBy: [], domain: [] },
    async load() {
        this.loads++;
    },
};
class FakeListController extends owl.Component {
    static template = owl.xml`<div class="fake-list"><span class="n" t-esc="model.root.records.length"/></div>`;
    static props = ["*"];
    setup() {
        this.model = model;
    }
}
globalThis.__ListController = FakeListController;

// ---- Odoo's services -------------------------------------------------------------------------------------------------------

const state = { watches: [], channels: new Set(), subscribers: new Map(), notes: [] };
globalThis.__services = {
    orm: {
        create: async (modelName, records) => {
            state.created.push(...records);
            return records.map(() => ++nextId);
        },
        read: async () => [{ state: "pending", message: "" }],
        silent: {
            call: async (modelName, method, args) => {
                if (method === "watch") {
                    state.watches.push([...args[0]]);
                }
                return true;
            },
        },
    },
    bus_service: {
        addChannel: (channel) => state.channels.add(channel),
        deleteChannel: (channel) => state.channels.delete(channel),
        subscribe: (type, callback) => state.subscribers.set(type, [...(state.subscribers.get(type) || []), callback]),
        unsubscribe: (type, callback) => state.subscribers.set(type, (state.subscribers.get(type) || []).filter((c) => c !== callback)),
    },
    notification: { add: (message, options) => state.notes.push({ message, ...options }) },
};
const emit = (type, payload) => {
    for (const callback of state.subscribers.get(type) || []) {
        callback(payload);
    }
};

// ---- the controller --------------------------------------------------------------------------------------------------------

const { ParameterListController, parameterListView } = await import("../../int_workbench/static/src/views/parameter_list.js");
ok("the list is registered as a view with its own controller", globalThis.__registered.some((r) => r.category === "views" && r.key === "int_workbench.parameter_list" && r.value === parameterListView) && parameterListView.Controller === ParameterListController);

const target = document.getElementById("stage");
model.root.records = [row(1, 1, "0001"), row(2, 1, "0002"), row(3, 2, "0001")];
const app = new owl.App(ParameterListController, { env: {}, props: {}, dev: true, warnIfNoStaticProps: false });
await app.mount(target);
await wait(30);

ok("the controllers of the rows on the screen are listened to", [...state.channels].sort().join() === "int.workbench.device_1,int.workbench.device_2", [...state.channels].join());
ok("the list says to Odoo which controllers somebody looks at", state.watches.length === 1 && state.watches[0].sort().join() === "1,2", JSON.stringify(state.watches));
ok("it listens for changed rows and for how requests end", (state.subscribers.get("int_workbench/values") || []).length === 1 && (state.subscribers.get("int_workbench/command") || []).length === 1);

emit("int_workbench/command", { id: 7, state: "done", message: "" });
ok("a request that worked says nothing", state.notes.length === 0);
emit("int_workbench/command", { id: 8, state: "failed", message: "No confirmation" });
emit("int_workbench/command", { id: 9, state: "expired", message: "" });
ok("a request that did not work out is told, with the reason if there is one", state.notes.length === 2 && state.notes[0].message === "No confirmation" && state.notes[0].type === "warning" && state.notes[1].message === "expired", JSON.stringify(state.notes));
await wait(450);
ok("and the list is read again (at once for the first, once more for the one close behind it), so the switch shows what the controller has", model.loads === 2, `${model.loads}`);
model.loads = 0;

// ---- what a message about changed rows does ----
const settle = () => wait(450); // the messages that come close behind the first are taken together after a little wait
emit("int_workbench/values", { ids: [1], reload: false });
await wait(50);
ok("the first message loads its row at once, in place", rowLoads.join() === "1" && model.loads === 0, `${model.loads} ${rowLoads}`);
emit("int_workbench/values", { ids: [3], reload: false });
emit("int_workbench/values", { ids: [1], reload: false });
await wait(50);
ok("the ones close behind it wait", rowLoads.join() === "1", `${rowLoads}`);
await settle();
ok("and are taken together: the rows that changed, each once, in place", rowLoads.slice().sort().join() === "1,1,3" && model.loads === 0, `${rowLoads} / list loads ${model.loads}`);

rowLoads.length = 0;
emit("int_workbench/values", { ids: [999], reload: false });
await settle();
ok("a row that is not on the screen is not loaded", rowLoads.length === 0 && model.loads === 0);

emit("int_workbench/values", { ids: [], reload: true });
await settle();
ok("rows came or went: the whole list is loaded afresh", model.loads === 1 && rowLoads.length === 0, `${model.loads}`);

emit("int_workbench/values", { ids: [2], reload: true });
emit("int_workbench/values", { ids: [1], reload: false });
await settle();
ok("a message that says reload makes the rows of the others needless", model.loads === 2 && rowLoads.join() === "1", `${model.loads} ${rowLoads}`);

// a list that is filtered or grouped by what a report changes
rowLoads.length = 0;
model.root.domain = [["clamped", "=", true]];
emit("int_workbench/values", { ids: [1], reload: false });
await settle();
ok("filtered by Clamped: a changed row may leave the list, so it is loaded afresh", model.loads === 3 && rowLoads.length === 0, `${model.loads}`);
model.root.domain = [["is_favorite", "=", true]];
emit("int_workbench/values", { ids: [1], reload: false });
await settle();
ok("filtered by Favorites: a report does not move a row, so only the row is loaded", model.loads === 3 && rowLoads.join() === "1", `${model.loads} ${rowLoads}`);
model.root.domain = [];
for (const [group, expectLoads] of [["status", 4], ["device_id", 4], ["clamped", 5], ["status:day", 6]]) {
    rowLoads.length = 0;
    model.root.groupBy = [group];
    emit("int_workbench/values", { ids: [2], reload: false });
    await settle();
    ok(`grouped by ${group}: ${expectLoads === 4 && group === "device_id" ? "rows are refreshed in place" : "the list is loaded afresh"}`, model.loads === expectLoads && rowLoads.length === (group === "device_id" ? 1 : 0), `${model.loads} ${rowLoads}`);
}
model.root.groupBy = [];

// many rows at once are not read one by one: one call with the whole list
const shownBefore = model.root.records;
model.root.records = [1, 2, 3, 4, 5, 6, 7].map((id) => row(id, 1, `00${id}`));
rowLoads.length = 0;
const loadsMany = model.loads;
emit("int_workbench/values", { ids: [1, 2, 3, 4, 5], reload: false });
await settle();
ok("up to five rows that changed are loaded one by one, in place", rowLoads.slice().sort().join() === "1,2,3,4,5" && model.loads === loadsMany, `${model.loads} ${rowLoads}`);
rowLoads.length = 0;
emit("int_workbench/values", { ids: [1, 2, 3, 4, 5, 6], reload: false });
await settle();
ok("more than five: the list is loaded with one call, no row alone", rowLoads.length === 0 && model.loads === loadsMany + 1, `${model.loads} ${rowLoads}`);
model.root.records[0].dirty = true;
emit("int_workbench/values", { ids: [1, 2, 3, 4, 5, 6], reload: false });
await settle();
ok("more than five while a row is edited: nothing is loaded", rowLoads.length === 0 && model.loads === loadsMany + 1, `${model.loads} ${rowLoads}`);
model.root.records[0].dirty = false;
await settle();
ok("and the list is loaded when the change is saved", model.loads === loadsMany + 2, `${model.loads}`);
model.root.records = shownBefore;

// a value that is typed into a row and not saved yet is not taken away by a report
rowLoads.length = 0;
const edited = model.root.records[0];
edited.dirty = true;
emit("int_workbench/values", { ids: [1], reload: false });
await settle();
ok("a row with an unsaved change is not loaded again", rowLoads.length === 0, `${rowLoads}`);
const listLoads = model.loads;
emit("int_workbench/values", { ids: [], reload: true });
await settle();
ok("the list is not loaded afresh while a change is typed", model.loads === listLoads, `${model.loads} ${listLoads}`);
edited.dirty = false;
await settle();
ok("when the change is saved, the list catches up (it covers the rows)", rowLoads.length === 0 && model.loads === listLoads + 1, `${rowLoads} ${model.loads}`);
// a row that was waiting alone is loaded when its change is saved
edited.dirty = true;
emit("int_workbench/values", { ids: [1], reload: false });
await settle();
ok("a row that waits is not loaded while the change is open", rowLoads.length === 0, `${rowLoads}`);
edited.dirty = false;
await settle();
ok("and it is loaded when the change is saved", rowLoads.join() === "1", `${rowLoads}`);
rowLoads.length = 0;

// a row that cannot be read any more
const loadsBefore = model.loads;
globalThis.__rowLoadFails = true;
emit("int_workbench/values", { ids: [1], reload: false });
await settle();
ok("a row that cannot be loaded: the list is read afresh", model.loads === loadsBefore + 1, `${model.loads}`);
globalThis.__rowLoadFails = false;

// the screen shows other rows (a filter): the controller that is gone is left, nothing new is said
const comp = app.root.component;
ok("the list carries its own class, for its style sheet", comp.className.split(" ").includes("o_int_workbench_parameter_list"), comp.className);
model.root.records = [row(1, 1, "0001")];
comp.render();
await wait(60);
ok("a controller that is not on the screen any more is not listened to", [...state.channels].join() === "int.workbench.device_1", [...state.channels].join());
ok("no new controller, so nothing new is said", state.watches.length === 1, JSON.stringify(state.watches));
model.root.records = [row(1, 1, "0001"), row(4, 3, "0009")];
comp.render();
await wait(60);
ok("a new controller on the screen is listened to and looked at", state.channels.has("int.workbench.device_3") && JSON.stringify(state.watches[state.watches.length - 1]) === "[1,3]", JSON.stringify(state.watches));

// a hidden tab says nothing
const setHidden = (hidden) => {
    Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
    document.dispatchEvent(new window.Event("visibilitychange"));
};
const before = state.watches.length;
setHidden(true);
await wait(30);
ok("a hidden tab does not say that somebody looks", state.watches.length === before);
setHidden(false);
await wait(30);
ok("a visible tab says it again", state.watches.length === before + 1);

app.destroy();
await wait(30);
ok("when the list is left, the channels and the subscriptions are given up", state.channels.size === 0 && (state.subscribers.get("int_workbench/values") || []).length === 0 && (state.subscribers.get("int_workbench/command") || []).length === 0, [...state.channels].join());

console.log(fails ? `${fails} FAILED` : "ALL PASSED");
process.exit(fails ? 1 : 0);
