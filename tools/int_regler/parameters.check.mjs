// node --import ./register.mjs parameters.check.mjs
// The list of process values of int_regler with the real Owl in jsdom: the controller (bus, heartbeat, reload), the field widget with
// the clamp buttons, and the service that makes the requests. The list of Odoo is a stand-in with the rows and the model the controller
// reads; the ORM, the bus and the notifications are fakes.
import fs from "node:fs";
import { createRequire } from "node:module";
import { MODULE_SRC, owlFile } from "./paths.mjs";

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

const state = { operator: true, watches: [], channels: new Set(), subscribers: new Map(), created: [], notes: [], clampCalls: [], settled: [], answer: { confirmed: true, error: "" } };
globalThis.__user = { hasGroup: async (group) => group === "int_regler.group_regler_operator" && state.operator };
let nextId = 100;
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
    int_regler_clamping: {
        canClamp: async () => state.operator,
        settle: (payload) => state.settled.push(payload),
        clamp: async (...args) => {
            state.clampCalls.push(args);
            await wait(120);
            return state.answer;
        },
    },
};
const emit = (type, payload) => {
    for (const callback of state.subscribers.get(type) || []) {
        callback(payload);
    }
};

// ---- the controller --------------------------------------------------------------------------------------------------------

const { ReglerParameterListController, reglerParameterListView } = await import("../../int_regler/static/src/regler_parameters.js");
ok("the list is registered as a view with its own controller", globalThis.__registered.some((r) => r.category === "views" && r.key === "int_regler.parameter_list" && r.value === reglerParameterListView) && reglerParameterListView.Controller === ReglerParameterListController);

const target = document.getElementById("stage");
model.root.records = [row(1, 1, "0001"), row(2, 1, "0002"), row(3, 2, "0001")];
const app = new owl.App(ReglerParameterListController, { env: {}, props: {}, dev: true, warnIfNoStaticProps: false });
await app.mount(target);
await wait(30);

ok("the controllers of the rows on the screen are listened to", [...state.channels].sort().join() === "int.regler.device_1,int.regler.device_2", [...state.channels].join());
ok("the list says to Odoo which controllers somebody looks at", state.watches.length === 1 && state.watches[0].sort().join() === "1,2", JSON.stringify(state.watches));
ok("it listens for changed rows and for how requests end", (state.subscribers.get("int_regler/values") || []).length === 1 && (state.subscribers.get("int_regler/command") || []).length === 1);

emit("int_regler/command", { id: 7, state: "done", message: "" });
ok("how a request ended goes to the service that waits for it", state.settled.length === 1 && state.settled[0].id === 7);

// ---- what a message about changed rows does ----
const settle = () => wait(450); // the refresh waits a little for more messages
emit("int_regler/values", { ids: [1], reload: false });
emit("int_regler/values", { ids: [3], reload: false });
emit("int_regler/values", { ids: [1], reload: false });
await wait(50);
ok("nothing is loaded at once", model.loads === 0 && rowLoads.length === 0, `${model.loads} ${rowLoads.length}`);
await settle();
ok("messages that come close together refresh the rows that changed, each once, in place", rowLoads.slice().sort().join() === "1,3" && model.loads === 0, `${rowLoads} / list loads ${model.loads}`);

rowLoads.length = 0;
emit("int_regler/values", { ids: [999], reload: false });
await settle();
ok("a row that is not on the screen is not loaded", rowLoads.length === 0 && model.loads === 0);

emit("int_regler/values", { ids: [], reload: true });
await settle();
ok("rows came or went: the whole list is loaded afresh", model.loads === 1 && rowLoads.length === 0, `${model.loads}`);

emit("int_regler/values", { ids: [2], reload: true });
emit("int_regler/values", { ids: [1], reload: false });
await settle();
ok("a message that says reload makes the rows of the others needless", model.loads === 2 && rowLoads.join() === "1", `${model.loads} ${rowLoads}`);

// a list that is filtered or grouped by what a report changes
rowLoads.length = 0;
model.root.domain = [["clamped", "=", true]];
emit("int_regler/values", { ids: [1], reload: false });
await settle();
ok("filtered by Clamped: a changed row may leave the list, so it is loaded afresh", model.loads === 3 && rowLoads.length === 0, `${model.loads}`);
model.root.domain = [["is_favorite", "=", true]];
emit("int_regler/values", { ids: [1], reload: false });
await settle();
ok("filtered by Favorites: a report does not move a row, so only the row is loaded", model.loads === 3 && rowLoads.join() === "1", `${model.loads} ${rowLoads}`);
model.root.domain = [];
for (const [group, expectLoads] of [["status", 4], ["device_id", 4], ["clamped", 5], ["status:day", 6]]) {
    rowLoads.length = 0;
    model.root.groupBy = [group];
    emit("int_regler/values", { ids: [2], reload: false });
    await settle();
    ok(`grouped by ${group}: ${expectLoads === 4 && group === "device_id" ? "rows are refreshed in place" : "the list is loaded afresh"}`, model.loads === expectLoads && rowLoads.length === (group === "device_id" ? 1 : 0), `${model.loads} ${rowLoads}`);
}
model.root.groupBy = [];

// a row that cannot be read any more
const loadsBefore = model.loads;
globalThis.__rowLoadFails = true;
emit("int_regler/values", { ids: [1], reload: false });
await settle();
ok("a row that cannot be loaded: the list is read afresh", model.loads === loadsBefore + 1, `${model.loads}`);
globalThis.__rowLoadFails = false;

// the screen shows other rows (a filter): the controller that is gone is left, nothing new is said
const comp = app.root.component;
model.root.records = [row(1, 1, "0001")];
comp.render();
await wait(60);
ok("a controller that is not on the screen any more is not listened to", [...state.channels].join() === "int.regler.device_1", [...state.channels].join());
ok("no new controller, so nothing new is said", state.watches.length === 1, JSON.stringify(state.watches));
model.root.records = [row(1, 1, "0001"), row(4, 3, "0009")];
comp.render();
await wait(60);
ok("a new controller on the screen is listened to and looked at", state.channels.has("int.regler.device_3") && JSON.stringify(state.watches[state.watches.length - 1]) === "[1,3]", JSON.stringify(state.watches));

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
ok("when the list is left, the channels and the subscriptions are given up", state.channels.size === 0 && (state.subscribers.get("int_regler/values") || []).length === 0 && (state.subscribers.get("int_regler/command") || []).length === 0, [...state.channels].join());

// ---- the field widget ------------------------------------------------------------------------------------------------------

const { ReglerClampField } = await import("../../int_regler/static/src/regler_clamp_field.js");
ok("the widget is registered as a field", globalThis.__registered.some((r) => r.category === "fields" && r.key === "int_regler.clamp"));

async function field(data) {
    const stage = document.createElement("div");
    document.body.appendChild(stage);
    const fieldApp = new owl.App(ReglerClampField, { env: {}, props: { name: "clamped", record: { data: { device_id: { id: 1 }, code: "0016", ...data } } }, dev: true, warnIfNoStaticProps: false });
    fieldApp.addTemplates(fs.readFileSync(`${MODULE_SRC}/regler_clamp_field.xml`, "utf8"));
    await fieldApp.mount(stage);
    await wait(30);
    return { stage, fieldApp };
}
const buttons = (stage) => [...stage.querySelectorAll("button")].map((b) => text(b));

state.operator = true;
const seg = (stage, name) => stage.querySelector(".o_int_regler_" + name);
// a segment that is the state of the row: Auto is quiet (grey, active), a clamp is yellow
const filled = (el) => el.classList.contains("btn-secondary") || el.classList.contains("btn-warning");
const last = () => JSON.stringify(state.clampCalls[state.clampCalls.length - 1]);

let w = await field({ can_clamp: true, analog: false, clamped: false, value: 0 });
ok("a digital row that can be clamped is [Auto | 0 | 1] with Auto filled", buttons(w.stage).join() === "Auto,0,1" && filled(seg(w.stage, "auto")) && !filled(seg(w.stage, "zero")) && !filled(seg(w.stage, "one")), buttons(w.stage).join());
ok("a segment is no wider than a button and the group is no form", !w.stage.querySelector("input") && !!w.stage.querySelector(".btn-group"));
seg(w.stage, "auto").click();
await wait(40);
ok("Auto on a row that is not clamped does nothing", state.clampCalls.length === 0);
seg(w.stage, "one").click();
await wait(40);
ok("a click on 1 makes a request for that row of that controller", last() === JSON.stringify([1, "0016", "set", 1]), last());
ok("while it is waited for, the buttons cannot be pressed again", [...w.stage.querySelectorAll("button")].every((b) => b.disabled));
ok("the segment that waits shows a spinner, the others their label", !!seg(w.stage, "one").querySelector(".fa-spinner") && !seg(w.stage, "zero").querySelector(".fa-spinner") && text(seg(w.stage, "zero")) === "0");
await wait(150);
ok("afterwards they can, and the spinner is gone", [...w.stage.querySelectorAll("button")].every((b) => !b.disabled) && !w.stage.querySelector(".fa-spinner"));
ok("a confirmed request says nothing", state.notes.length === 0);
state.answer = { confirmed: false, error: "No confirmation" };
seg(w.stage, "zero").click();
await wait(200);
ok("a request that ended badly is told, with the row", state.notes.length === 1 && state.notes[0].message === "No confirmation" && state.notes[0].title === "Row 0016" && state.notes[0].type === "danger", JSON.stringify(state.notes));
w.fieldApp.destroy();

state.answer = { confirmed: true, error: "" };
w = await field({ can_clamp: true, analog: false, clamped: true, clamp_value: 1, value: 0 });
ok("a row clamped to 1 has 1 filled and Auto open", filled(seg(w.stage, "one")) && seg(w.stage, "one").classList.contains("btn-warning") && !filled(seg(w.stage, "auto")) && !filled(seg(w.stage, "zero")), buttons(w.stage).join());
ok("there is no extra Release button and no badge", !buttons(w.stage).includes("Release") && !w.stage.querySelector(".badge"));
ok("a clamped row has the lock, Auto in the same place of a row that is not clamped has none", !!w.stage.querySelector(".o_int_regler_lock .fa-lock") && !seg(w.stage, "auto").classList.contains("btn-secondary"));
const calls = state.clampCalls.length;
seg(w.stage, "one").click();
await wait(40);
ok("a click on what the row is clamped to already does nothing", state.clampCalls.length === calls);
seg(w.stage, "auto").click();
await wait(40);
ok("Auto releases the row: a request without a value", last() === JSON.stringify([1, "0016", "release", 0]), last());
await wait(150);
w.fieldApp.destroy();

w = await field({ can_clamp: true, analog: true, clamped: false, value: 22.5 });
const input = w.stage.querySelector("input");
ok("an analog row is [Auto] and a number: empty on Auto, the value now grey as placeholder, in the format of the user", buttons(w.stage).join() === "Auto" && input && input.value === "" && input.placeholder === "22,5" && filled(seg(w.stage, "auto")), buttons(w.stage).join() + " " + (input && input.value) + " " + (input && input.placeholder));
ok("the input is the one of the float field: text with a decimal keyboard and no spinner arrows", input.type === "text" && input.getAttribute("inputmode") === "decimal" && input.classList.contains("o_input") && !w.stage.querySelector(".o_int_regler_lock .fa-lock"));
ok("there is no Set button", !buttons(w.stage).includes("Set"));
// the user types, the row changes (a temperature does): the input keeps the text
const record = w.fieldApp.root.props.record;
input.value = "3";
input.dispatchEvent(new window.Event("input", { bubbles: true }));
await wait(20);
record.data.value = 23.1;
w.fieldApp.root.component.render(true);
await wait(40);
ok("while the user types, a change of the row does not replace the input", input.value === "3", input.value);
input.dispatchEvent(new window.Event("blur", { bubbles: true }));
await wait(40);
ok("after leaving the input it shows the row again (Auto: empty, the value now as placeholder)", input.value === "" && input.placeholder === "23,1", input.value + " " + input.placeholder);
input.value = "7";
input.dispatchEvent(new window.Event("input", { bubbles: true }));
await wait(20);
let escapeReached = false;
w.stage.addEventListener("keydown", () => { escapeReached = true; });
input.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
await wait(20);
ok("Escape drops what was typed, and the list does not see the key", input.value === "" && !escapeReached, input.value);
input.value = "30";
input.dispatchEvent(new window.Event("input", { bubbles: true }));
await wait(20);
input.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait(40);
ok("the number is clamped when the input is ended", last() === JSON.stringify([1, "0016", "set", 30]), last());
ok("while it is waited for, the number shows a spinner", !!w.stage.querySelector(".fa-spinner"));
await wait(150);
input.value = "21,5";
input.dispatchEvent(new window.Event("input", { bubbles: true }));
input.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait(40);
ok("a number with the decimal comma of the user is read as a number", last() === JSON.stringify([1, "0016", "set", 21.5]), last());
await wait(150);
input.value = "abc";
input.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait(40);
ok("something that is no number clamps nothing", last() === JSON.stringify([1, "0016", "set", 21.5]));
w.fieldApp.destroy();

w = await field({ can_clamp: true, analog: true, clamped: true, clamp_value: 30, value: 22.5 });
const clampedInput = w.stage.querySelector("input");
ok("a clamped analog row shows the clamp value, marked", clampedInput.value === "30" && clampedInput.classList.contains("border-warning") && !filled(seg(w.stage, "auto")), clampedInput.value);
const callsBefore = state.clampCalls.length;
clampedInput.value = "30";
clampedInput.dispatchEvent(new window.Event("change", { bubbles: true }));
await wait(40);
ok("the same number again clamps nothing", state.clampCalls.length === callsBefore);
w.fieldApp.destroy();

w = await field({ can_clamp: false, analog: false, clamped: false, value: 1 });
ok("a row that cannot be clamped shows nothing", buttons(w.stage).length === 0 && text(w.stage) === "", text(w.stage));
w.fieldApp.destroy();

state.operator = false;
w = await field({ can_clamp: true, analog: false, clamped: true, clamp_value: 1, value: 0 });
ok("a user who is not an operator sees the state as text, no buttons: the lock and the clamp value", buttons(w.stage).length === 0 && !w.stage.querySelector("input") && !!w.stage.querySelector(".fa-lock") && text(w.stage.querySelector(".o_int_regler_state")) === "1", text(w.stage));
w.fieldApp.destroy();
w = await field({ can_clamp: true, analog: true, clamped: true, clamp_value: 21.5, value: 22.5 });
ok("an analog clamp is shown with the number of the user", text(w.stage.querySelector(".o_int_regler_state")) === "21,5", text(w.stage));
w.fieldApp.destroy();
w = await field({ can_clamp: true, analog: false, clamped: false, value: 1 });
ok("a row that is not clamped says Auto, quietly", buttons(w.stage).length === 0 && text(w.stage.querySelector(".o_int_regler_state")) === "Auto" && !w.stage.querySelector(".fa-lock"), text(w.stage));
w.fieldApp.destroy();
state.operator = true;

// ---- the service -----------------------------------------------------------------------------------------------------------

const { reglerClampingService } = await import("../../int_regler/static/src/regler_clamping_service.js");
ok("the service is registered", globalThis.__registered.some((r) => r.category === "services" && r.key === "int_regler_clamping"));
const service = reglerClampingService.start({}, { orm: globalThis.__services.orm });
ok("only an operator may clamp, as the service says", (await service.canClamp()) === true);
state.created.length = 0;
const pending = service.clamp(5, "0017", "set", 1);
await wait(10);
ok("a request is made for the controller and the row", state.created.length === 1 && JSON.stringify(state.created[0]) === JSON.stringify({ device_id: 5, code: "0017", action: "set", value: 1 }), JSON.stringify(state.created));
service.settle({ id: nextId, state: "done", message: "" });
const result = await Promise.race([pending, wait(2000).then(() => "timeout")]);
ok("it ends when the bus tells how the request ended", result && result.confirmed === true, JSON.stringify(result));

console.log(fails ? `${fails} FAILED` : "ALL PASSED");
process.exit(fails ? 1 : 0);
