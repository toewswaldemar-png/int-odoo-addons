import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { OdooClient, REPORT_OLD_SECONDS } from "./workbench_client";
import { usePoll } from "./workbench_poll";
import { ReglerErrors, ReglerOverview } from "./workbench_views";

const TABS = [
    { id: "overview", label: _t("Overview"), icon: "fa-tachometer" },
    { id: "errors", label: _t("Errors"), icon: "fa-exclamation-triangle" },
];

/** How often the page tells Odoo that somebody looks (Odoo counts a look for 30 s). */
export const WATCH_EVERY_MS = 10000;

/**
 * The page of the module (client action int_workbench.app): the controllers of Odoo in a list, and for the chosen one the views of
 * what its controller service reported to Odoo: the overview and the errors. The process values and the clamps are in the list
 * "Process values" (int.workbench.parameter), not here. The page never talks to the service and only reads.
 *
 * While the page is open and visible it tells Odoo every ten seconds that somebody looks at the controller. Then the service
 * asks and reports often; otherwise it keeps quiet and the load on Odoo is small.
 */
export class IntReglerApp extends Component {
    static template = "int_workbench.App";
    static components = { ReglerOverview, ReglerErrors };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.tabs = TABS;
        this.client = null;
        this.state = useState({
            devices: [],
            deviceId: null,
            tab: "overview",
        });
        this.status = usePoll(() => this.client);
        this.watchTimer = null;
        this.onVisible = () => {
            if (!document.hidden) {
                this.watch();
            }
        };

        onWillStart(async () => {
            this.state.devices = await this.orm.searchRead("int.workbench.device", [], ["name", "device_ref"]);
        });
        onMounted(() => {
            document.addEventListener("visibilitychange", this.onVisible);
            this.watchTimer = setInterval(() => this.onVisible(), WATCH_EVERY_MS);
            if (this.state.devices.length) {
                this.selectDevice(this.state.devices[0].id);
            }
        });
        onWillUnmount(() => {
            document.removeEventListener("visibilitychange", this.onVisible);
            clearInterval(this.watchTimer);
        });
    }

    get device() {
        return this.state.devices.find((d) => d.id === this.state.deviceId) || null;
    }

    /** No usable report: the service has not reported, has stopped asking, or Odoo itself cannot be reached. */
    get serviceUnreachable() {
        return !!this.status.state.error;
    }

    /** What the last report says, and only while the reports come: after the last good one the badge must not stay green. */
    get connected() {
        return !this.serviceUnreachable && !!this.status.state.data?.connected;
    }

    /** The report is old (the service was quiet and has just been asked to report), or null. */
    get reportAgeText() {
        const age = this.client?.reportAge;
        return !this.serviceUnreachable && age > REPORT_OLD_SECONDS ? _t("report %s s old", Math.round(age)) : null;
    }

    selectDevice(id) {
        this.state.deviceId = Number(id);
        this.client = new OdooClient(this.orm, this.device);
        this.status.watch("/status", 2000);
        this.watch();
    }

    /** Says to Odoo that somebody looks at this controller now; nothing is said while the tab is hidden. */
    watch() {
        if (this.state.deviceId === null) {
            return undefined;
        }
        // silent: no loading indicator, and an error of a heartbeat is no error of the page
        return this.orm.silent.call("int.workbench.device", "watch", [[this.state.deviceId]]).catch(() => {});
    }
}

registry.category("actions").add("int_workbench.app", IntReglerApp);
