import { onMounted, onPatched, onWillDestroy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useDebounced } from "@web/core/utils/timing";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";

/**
 * The first message of the bus refreshes the list at once; messages that come within this time after it (a clamp result next to a
 * report) are taken together and refreshed once, this long after the last of them. Also the pause before a refresh is tried again
 * while a row is being edited.
 */
export const RELOAD_DEBOUNCE_MS = 300;
/**
 * Up to this many changed rows are loaded again one by one (in place: ticked rows, focus and scroll position stay). Every one is a call
 * to Odoo, and the model lets them run one after the other; from more rows on the whole list is loaded with a single call.
 */
export const ROWS_ONE_BY_ONE = 5;
/**
 * The fields a report changes that can move a row out of a filter or into another group. A list that is filtered or grouped by one of
 * them is loaded afresh when a row changes; any other list only refreshes the rows that changed. (Odoo does not regroup a row after
 * a change either; here the rows change without the user doing anything, so a filter such as "Clamped" would go stale.)
 */
export const MOVING_FIELDS = ["status", "clamped", "can_clamp"];
/** How often the list tells Odoo that somebody looks (Odoo counts a look for 30 s), as the service expects. */
export const WATCH_EVERY_MS = 10000;

const channelOf = (deviceId) => `int.workbench.device_${deviceId}`;

/**
 * The list of the process values of controllers. The rows are ordinary records; what is special is only that the list keeps itself
 * current like a page of its own would: while it is open and visible it tells Odoo which controllers it shows (then their service asks
 * and reports often), and when the bus says that a report changed rows it loads these rows again, in place (record.load(), as Live Chat
 * does for the tags of a channel). The rows stay the same records, so ticked rows, the focus and the scroll position stay. Only if rows
 * came or went, many rows changed at once (ROWS_ONE_BY_ONE), or the list is filtered or grouped by what a report changes, the whole list
 * is loaded afresh (as Live Chat does too).
 */
export class ParameterListController extends ListController {
    setup() {
        super.setup(...arguments);
        this.bus = useService("bus_service");
        this.orm = useService("orm");
        this.notification = useService("notification");
        // The first call of a message runs at once, the ones close behind it once more afterwards. The retries while a row is edited
        // are separate (they only wait): a retry that ran at once would call itself again without end.
        const atOnce = { immediate: true, trailing: true };
        this.reloadDebounced = useDebounced(() => this.reloadUnlessEdited(), RELOAD_DEBOUNCE_MS, atOnce);
        this.refreshDebounced = useDebounced(() => this.refreshRows(), RELOAD_DEBOUNCE_MS, atOnce);
        this.reloadLater = useDebounced(() => this.reloadUnlessEdited(), RELOAD_DEBOUNCE_MS);
        this.refreshLater = useDebounced(() => this.refreshRows(), RELOAD_DEBOUNCE_MS);
        this.changedRows = new Set(); // the ids of the rows that the bus said changed and that are not loaded again yet
        this.devices = new Set(); // the controllers whose rows are on the screen: what is watched and listened to
        this.onValues = (message) => this.valuesChanged(message);
        this.onCommand = (payload) => this.commandSettled(payload);
        this.onErrors = () => this.reloadDebounced();
        this.listeners = this.messages();
        this.onVisible = () => {
            if (!document.hidden) {
                this.watch();
            }
        };
        this.watchTimer = null;

        onMounted(() => {
            for (const [type, callback] of Object.entries(this.listeners)) {
                this.bus.subscribe(type, callback);
            }
            document.addEventListener("visibilitychange", this.onVisible);
            this.watchTimer = setInterval(this.onVisible, WATCH_EVERY_MS);
            this.syncDevices();
        });
        // what is on the screen changes with a search, a filter, a page: the controllers are looked at again afterwards
        onPatched(() => this.syncDevices());
        onWillDestroy(() => {
            for (const [type, callback] of Object.entries(this.listeners)) {
                this.bus.unsubscribe(type, callback);
            }
            for (const id of this.devices) {
                this.bus.deleteChannel(channelOf(id));
            }
            this.devices.clear();
            document.removeEventListener("visibilitychange", this.onVisible);
            clearInterval(this.watchTimer);
        });
    }

    /**
     * The messages of the bus this list listens to, {type: callback}. They come by controller, not by list, so each list takes only
     * those about its own rows: the ids of changed process values mean nothing to a list of errors.
     */
    messages() {
        return { "int_workbench/values": this.onValues, "int_workbench/command": this.onCommand };
    }

    /** The requests whose end this list tells (the same message goes to every list that looks at the controller). */
    handlesAction(action) {
        return action !== "clear_errors";
    }

    /** The class of this list: the style sheet next to this file (parameter_list.scss) is for the rows of this list and no other. */
    get className() {
        return `${super.className || ""} ${this.styleClass}`.trim();
    }

    get styleClass() {
        return "o_int_workbench_parameter_list";
    }

    /** Does the list show rows by something that a report changes? Then a changed row may belong to another group, or not to the list. */
    dependsOnChangingFields() {
        const root = this.model.root;
        const grouped = (root.groupBy || []).some((name) => MOVING_FIELDS.includes(String(name).split(":")[0]));
        const filter = JSON.stringify(root.domain || []);
        return grouped || MOVING_FIELDS.some((name) => filter.includes(`"${name}"`));
    }

    /** The bus says how a request ended; the ones that did not work out are told to the user (the clamp log has them all). */
    commandSettled({ action, state, message } = {}) {
        if (!this.handlesAction(action)) {
            return;
        }
        if (state === "done" && action === "clear_errors") {
            this.notification.add(_t("The error memory is cleared."), { title: _t("Clear error memory"), type: "success" });
        } else if (state && state !== "done") {
            const title = action === "clear_errors" ? _t("Clear error memory") : _t("Clamp request");
            this.notification.add(message || state, { title, type: "warning" });
            // the list showed what was asked for (the switch is on): it is read again and shows what the controller has
            this.reloadDebounced();
        }
    }

    /** The bus says which rows changed: {ids, reload}. */
    valuesChanged({ ids = [], reload = false } = {}) {
        if (reload || this.dependsOnChangingFields()) {
            this.changedRows.clear();
            this.reloadDebounced();
            return;
        }
        ids.forEach((id) => this.changedRows.add(id));
        this.refreshDebounced();
    }

    /**
     * The operator types a value into a row of the list: until it is saved, loading the row (or the list) again would take it away.
     * Such rows wait; the refresh tries again (nothing is asked of the server while it waits).
     */
    isEdited(record) {
        return Boolean(record.dirty);
    }

    reloadUnlessEdited() {
        if (this.model.root.records.some((record) => this.isEdited(record))) {
            this.reloadLater();
            return undefined;
        }
        return this.model.load();
    }

    /**
     * Loads again the rows that changed and are on the screen; the others are read when they come on the screen. Many rows at once are
     * not read one by one (a call each, one after the other) but with the whole list in one call.
     */
    async refreshRows() {
        const ids = new Set(this.changedRows);
        this.changedRows.clear();
        const shown = this.model.root.records.filter((record) => ids.has(record.resId));
        if (shown.length > ROWS_ONE_BY_ONE) {
            return this.reloadUnlessEdited(); // waits while a row is edited, as the whole list does
        }
        const waiting = shown.filter((record) => this.isEdited(record));
        if (waiting.length) {
            waiting.forEach((record) => this.changedRows.add(record.resId));
            this.refreshLater();
        }
        try {
            await Promise.all(shown.filter((record) => !this.isEdited(record) && !waiting.includes(record)).map((record) => record.load()));
        } catch {
            await this.model.load(); // a row that cannot be read (removed meanwhile): the list is read afresh
        }
    }

    /** The controllers of the rows that are loaded (a grouped list gives the rows of the open groups). */
    shownDevices() {
        const ids = new Set();
        for (const record of this.model.root.records) {
            const id = record.data.device_id?.id;
            if (id) {
                ids.add(id);
            }
        }
        return ids;
    }

    /** Listens to the controllers that are shown and not to the others; says that somebody looks if there are new ones. */
    syncDevices() {
        const shown = this.shownDevices();
        let added = false;
        for (const id of shown) {
            if (!this.devices.has(id)) {
                this.devices.add(id);
                this.bus.addChannel(channelOf(id));
                added = true;
            }
        }
        for (const id of [...this.devices]) {
            if (!shown.has(id)) {
                this.devices.delete(id);
                this.bus.deleteChannel(channelOf(id));
            }
        }
        if (added) {
            this.watch();
        }
    }

    /** Says to Odoo that somebody looks at the controllers on the screen; nothing is said while the tab is hidden. */
    watch() {
        if (!this.devices.size) {
            return undefined;
        }
        // silent: no loading indicator, and an error of a heartbeat is no error of the list
        return this.orm.silent.call("int.workbench.device", "watch", [[...this.devices]]).catch(() => {});
    }
}

/**
 * The list of the errors that are active. It keeps itself current in the same way (it tells Odoo which controllers it shows and listens
 * to their channels), but it is small and has no rows to keep in place: when the bus says that the errors changed, it is loaded afresh.
 * It tells how a request to clear the error memory ended, and nothing of the clamps.
 */
export class ErrorListController extends ParameterListController {
    messages() {
        return { "int_workbench/errors": this.onErrors, "int_workbench/command": this.onCommand };
    }

    handlesAction(action) {
        return action === "clear_errors";
    }

    get styleClass() {
        return ""; // the style sheet is for the process values
    }
}

export const parameterListView = { ...listView, Controller: ParameterListController };
export const errorListView = { ...listView, Controller: ErrorListController };

registry.category("views").add("int_workbench.parameter_list", parameterListView);
registry.category("views").add("int_workbench.error_list", errorListView);
