// node --import ./register.mjs parameters.check.mjs
// The list of process values of int_workbench with the real Owl in jsdom: the controller (bus, heartbeat, reload), the field widget with
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
globalThis.__popoverOpened = [];
globalThis.__popoverTemplates = fs.readFileSync(`${MODULE_SRC}/workbench_clamp_popover.xml`, "utf8");

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
globalThis.__user = { hasGroup: async (group) => group === "int_workbench.group_workbench_operator" && state.operator };
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
    int_workbench_clamping: {
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

const { ReglerParameterListController, reglerParameterListView } = await import("../../int_workbench/static/src/workbench_parameters.js");
ok("the list is registered as a view with its own controller", globalThis.__registered.some((r) => r.category === "views" && r.key === "int_workbench.parameter_list" && r.value === reglerParameterListView) && reglerParameterListView.Controller === ReglerParameterListController);

const target = document.getElementById("stage");
model.root.records = [row(1, 1, "0001"), row(2, 1, "0002"), row(3, 2, "0001")];
const app = new owl.App(ReglerParameterListController, { env: {}, props: {}, dev: true, warnIfNoStaticProps: false });
await app.mount(target);
await wait(30);

ok("the controllers of the rows on the screen are listened to", [...state.channels].sort().join() === "int.workbench.device_1,int.workbench.device_2", [...state.channels].join());
ok("the list says to Odoo which controllers somebody looks at", state.watches.length === 1 && state.watches[0].sort().join() === "1,2", JSON.stringify(state.watches));
ok("it listens for changed rows and for how requests end", (state.subscribers.get("int_workbench/values") || []).length === 1 && (state.subscribers.get("int_workbench/command") || []).length === 1);

emit("int_workbench/command", { id: 7, state: "done", message: "" });
ok("how a request ended goes to the service that waits for it", state.settled.length === 1 && state.settled[0].id === 7);

// ---- what a message about changed rows does ----
const settle = () => wait(450); // the refresh waits a little for more messages
emit("int_workbench/values", { ids: [1], reload: false });
emit("int_workbench/values", { ids: [3], reload: false });
emit("int_workbench/values", { ids: [1], reload: false });
await wait(50);
ok("nothing is loaded at once", model.loads === 0 && rowLoads.length === 0, `${model.loads} ${rowLoads.length}`);
await settle();
ok("messages that come close together refresh the rows that changed, each once, in place", rowLoads.slice().sort().join() === "1,3" && model.loads === 0, `${rowLoads} / list loads ${model.loads}`);

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

// a row that cannot be read any more
const loadsBefore = model.loads;
globalThis.__rowLoadFails = true;
emit("int_workbench/values", { ids: [1], reload: false });
await settle();
ok("a row that cannot be loaded: the list is read afresh", model.loads === loadsBefore + 1, `${model.loads}`);
globalThis.__rowLoadFails = false;

// the screen shows other rows (a filter): the controller that is gone is left, nothing new is said
const comp = app.root.component;
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

// ---- the field widget ------------------------------------------------------------------------------------------------------

const { ReglerClampField } = await import("../../int_workbench/static/src/workbench_clamp_field.js");
ok("the widget is registered as a field", globalThis.__registered.some((r) => r.category === "fields" && r.key === "int_workbench.clamp"));

async function field(data) {
    const stage = document.createElement("div");
    document.body.appendChild(stage);
    const fieldApp = new owl.App(ReglerClampField, { env: {}, props: { name: "clamped", record: { data: { device_id: { id: 1 }, code: "0016", ...data } } }, dev: true, warnIfNoStaticProps: false });
    fieldApp.addTemplates(fs.readFileSync(`${MODULE_SRC}/workbench_clamp_field.xml`, "utf8"));
    await fieldApp.mount(stage);
    await wait(30);
    return { stage, fieldApp };
}
const buttons = (stage) => [...stage.querySelectorAll("button")].map((b) => text(b));

state.operator = true;
const seg = (stage, name) => stage.querySelector(".o_int_workbench_" + name);
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
ok("a clamped row has the lock, Auto in the same place of a row that is not clamped has none", !!w.stage.querySelector(".o_int_workbench_lock .fa-lock") && !seg(w.stage, "auto").classList.contains("btn-secondary"));
const calls = state.clampCalls.length;
seg(w.stage, "one").click();
await wait(40);
ok("a click on what the row is clamped to already does nothing", state.clampCalls.length === calls);
seg(w.stage, "auto").click();
await wait(40);
ok("Auto releases the row: a request without a value", last() === JSON.stringify([1, "0016", "release", 0]), last());
await wait(150);
w.fieldApp.destroy();

w = await field({ can_clamp: true, analog: true, clamped: false, value: 22.5, name: "Aussentemp", unit: "°C", text: "22.5°C" });
const numberBtn = () => w.stage.querySelector(".o_int_workbench_number");
const popovers = () => document.querySelectorAll(".o_int_workbench_popover");
const pinput = () => document.querySelector(".o_int_workbench_popover input");
const steps = () => [...document.querySelectorAll(".o_int_workbench_step")];
const press = (el) => el.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const typeInto = async (el, value) => {
    el.value = value;
    el.dispatchEvent(new window.Event("input", { bubbles: true }));
    await wait(20);
};
ok("an analog row is [Auto | number]: the number is the value now in the format of the user, and there is no input in the list", buttons(w.stage)[0] === "Auto" && !w.stage.querySelector("input") && text(numberBtn()).trim() === "22,5" && !filled(numberBtn()) && filled(seg(w.stage, "auto")), buttons(w.stage).join());
ok("the number is a segment of the group, with a pencil", !!numberBtn().closest(".btn-group") && !!numberBtn().querySelector(".fa-pencil"));
ok("there is no popover before the click", popovers().length === 0);
press(numberBtn());
await wait(40);
ok("a click on the number opens the popover on that button", popovers().length === 1 && globalThis.__popoverOpened.at(-1).target === numberBtn());
ok("the popover says the row, the value now and the unit", text(popovers()[0]).includes("Row 0016 · Aussentemp") && text(popovers()[0]).includes("Now: 22.5°C") && text(popovers()[0]).includes("°C"), text(popovers()[0]));
ok("its input starts with the value now (the row is on Auto), as text with a decimal keyboard", pinput().value === "22,5" && pinput().type === "text" && pinput().getAttribute("inputmode") === "decimal" && pinput().classList.contains("o_input"), pinput() && pinput().value);
ok("the steps are -1, -0,1, +0,1 and +1", steps().map((b) => text(b).trim()).join() === "−1,−0,1,+0,1,+1", steps().map((b) => text(b).trim()).join());
const callsPopover = state.clampCalls.length;
press(steps()[3]);
await wait(20);
press(steps()[1]);
await wait(20);
ok("a step changes the number in the input, and asks nothing of the controller", pinput().value === "23,4" && state.clampCalls.length === callsPopover, pinput().value);
press(document.querySelector(".o_int_workbench_cancel"));
await wait(20);
ok("Cancel closes the popover and clamps nothing", popovers().length === 0 && state.clampCalls.length === callsPopover);
press(numberBtn());
await wait(40);
ok("a second opening starts afresh", pinput().value === "22,5");
press(numberBtn());
await wait(20);
ok("a click on the number while the popover is open closes it", popovers().length === 0);
press(numberBtn());
await wait(40);
await typeInto(pinput(), "30");
press(document.querySelector(".o_int_workbench_confirm"));
await wait(40);
ok("Clamp makes the request with the number and closes the popover", last() === JSON.stringify([1, "0016", "set", 30]) && popovers().length === 0, last());
ok("while it is waited for, the number shows a spinner and cannot be pressed", !!numberBtn().querySelector(".fa-spinner") && numberBtn().disabled);
await wait(150);
ok("afterwards the spinner is gone", !numberBtn().querySelector(".fa-spinner") && !numberBtn().disabled);
press(numberBtn());
await wait(40);
await typeInto(pinput(), "21,5");
pinput().dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
await wait(40);
ok("Enter clamps, and a number with the decimal comma of the user is read as a number", last() === JSON.stringify([1, "0016", "set", 21.5]) && popovers().length === 0, last());
await wait(150);
const callsBad = state.clampCalls.length;
press(numberBtn());
await wait(40);
await typeInto(pinput(), "abc");
press(document.querySelector(".o_int_workbench_confirm"));
await wait(40);
ok("something that is no number clamps nothing, the popover stays and says so", state.clampCalls.length === callsBad && popovers().length === 1 && !!document.querySelector(".o_int_workbench_invalid") && pinput().classList.contains("is-invalid"));
await typeInto(pinput(), "5");
ok("what the user types takes the message away", !document.querySelector(".o_int_workbench_invalid") && !pinput().classList.contains("is-invalid"));
press(steps()[0]);
await wait(20);
ok("a step from a number the user typed goes on from it", pinput().value === "4", pinput().value);
numberBtn().click();
await wait(20);
w.fieldApp.destroy();
await wait(20);
ok("when the row goes away, its popover goes with it", popovers().length === 0);

w = await field({ can_clamp: true, analog: true, clamped: true, clamp_value: 30, value: 22.5, name: "Aussentemp", unit: "°C", text: "22.5°C" });
ok("a clamped analog row shows the clamp in the number, yellow, with the lock; Auto is open", text(numberBtn()).trim() === "30" && numberBtn().classList.contains("btn-warning") && !filled(seg(w.stage, "auto")) && !!w.stage.querySelector(".o_int_workbench_lock .fa-lock"), text(numberBtn()));
const callsSame = state.clampCalls.length;
press(numberBtn());
await wait(40);
ok("its popover starts with the number the row is clamped to", pinput().value === "30", pinput().value);
press(document.querySelector(".o_int_workbench_confirm"));
await wait(40);
ok("the same number again clamps nothing, and the popover closes", state.clampCalls.length === callsSame && popovers().length === 0);
w.fieldApp.destroy();

w = await field({ can_clamp: false, analog: false, clamped: false, value: 1 });
ok("a row that cannot be clamped shows nothing", buttons(w.stage).length === 0 && text(w.stage) === "", text(w.stage));
w.fieldApp.destroy();

state.operator = false;
w = await field({ can_clamp: true, analog: false, clamped: true, clamp_value: 1, value: 0 });
ok("a user who is not an operator sees the state as text, no buttons: the lock and the clamp value", buttons(w.stage).length === 0 && !w.stage.querySelector("input") && !!w.stage.querySelector(".fa-lock") && text(w.stage.querySelector(".o_int_workbench_state")) === "1", text(w.stage));
w.fieldApp.destroy();
w = await field({ can_clamp: true, analog: true, clamped: true, clamp_value: 21.5, value: 22.5 });
ok("an analog clamp is shown with the number of the user", text(w.stage.querySelector(".o_int_workbench_state")) === "21,5", text(w.stage));
w.fieldApp.destroy();
w = await field({ can_clamp: true, analog: false, clamped: false, value: 1 });
ok("a row that is not clamped says Auto, quietly", buttons(w.stage).length === 0 && text(w.stage.querySelector(".o_int_workbench_state")) === "Auto" && !w.stage.querySelector(".fa-lock"), text(w.stage));
w.fieldApp.destroy();
state.operator = true;

// ---- the service -----------------------------------------------------------------------------------------------------------

const { reglerClampingService } = await import("../../int_workbench/static/src/workbench_clamping_service.js");
ok("the service is registered", globalThis.__registered.some((r) => r.category === "services" && r.key === "int_workbench_clamping"));
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
