import { reactive } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

/** How often the state of the controllers is read (a read of a few records, as long as the tab is visible). */
export const REFRESH_EVERY_MS = 15000;

/** The states of the line to a controller, worst first. */
export const STATES = ["disconnected", "silent", "unknown", "connected"];

/** The colour of the state, in the way Odoo colours a state (the text classes of Bootstrap). */
export const STATE_COLORS = {
    connected: "success",
    disconnected: "warning",
    silent: "warning",
    unknown: "secondary",
};

export function stateLabels() {
    return {
        connected: _t("Connected"),
        disconnected: _t("Disconnected"),
        silent: _t("Service silent"),
        unknown: _t("Unknown"),
    };
}

/** The worst state of the given controllers ("" if there are none). */
export function worstState(devices) {
    let worst = "";
    for (const device of devices) {
        if (!worst || STATES.indexOf(device.connection_state) < STATES.indexOf(worst)) {
            worst = device.connection_state;
        }
    }
    return worst;
}

/**
 * The state of the line to the controllers, for everything that shows it (the item of the systray, the banner of a list): one reactive
 * state, read from Odoo now and then. Only for users of the Workbench; for all others nothing is read.
 */
export const connectionService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        const state = reactive({ devices: [] });
        let allowed = false;

        async function refresh() {
            if (!allowed || document.hidden) {
                return;
            }
            try {
                state.devices = await orm.silent.searchRead("int.workbench.device", [], ["name", "connection_state"]);
            } catch {
                // a failed look is no error of the page: what was shown stays
            }
        }

        user.hasGroup("int_workbench.int_workbench_group_user").then((has) => {
            allowed = has;
            refresh();
        });
        setInterval(refresh, REFRESH_EVERY_MS);
        document.addEventListener("visibilitychange", refresh);
        return { state, refresh };
    },
};

registry.category("services").add("int_workbench_connection", connectionService);
