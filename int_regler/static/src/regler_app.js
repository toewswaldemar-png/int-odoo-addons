import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { CoreClient, CoreError } from "./core_client";
import { usePoll } from "./regler_poll";
import { ReglerClamps, ReglerErrors, ReglerOverview, ReglerValues } from "./regler_views";

const TABS = [
    { id: "overview", label: _t("Overview"), icon: "fa-tachometer" },
    { id: "values", label: _t("Process values"), icon: "fa-sliders" },
    { id: "errors", label: _t("Errors"), icon: "fa-exclamation-triangle" },
    { id: "clamps", label: _t("Clamps"), icon: "fa-plug" },
];

/**
 * The page of the module (client action int_regler.app): the controllers of Odoo in a list, and for the chosen one the
 * views that read from the controller service and, after a sign-in at the service, write to it.
 * The browser talks to the service directly. Odoo knows only its address (model int.regler.device).
 */
export class IntReglerApp extends Component {
    static template = "int_regler.App";
    static components = { ReglerOverview, ReglerValues, ReglerErrors, ReglerClamps };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.tabs = TABS;
        this.client = null;
        this.state = useState({
            devices: [],
            deviceId: null,
            tab: "overview",
            me: null,
            showLogin: false,
            loginName: "",
            loginPassword: "",
            loginError: "",
            busy: false,
        });
        this.status = usePoll(() => this.client);

        onWillStart(async () => {
            this.state.devices = await this.orm.searchRead("int.regler.device", [], ["name", "core_url", "device_ref"]);
        });
        onMounted(() => {
            if (this.state.devices.length) {
                this.selectDevice(this.state.devices[0].id);
            }
        });
    }

    get device() {
        return this.state.devices.find((d) => d.id === this.state.deviceId) || null;
    }

    get serviceUnreachable() {
        return !!this.status.state.error && !this.status.state.data;
    }

    get connected() {
        return !!this.status.state.data?.connected;
    }

    async selectDevice(id) {
        this.state.deviceId = Number(id);
        this.client = new CoreClient(this.device);
        this.state.me = null;
        this.state.showLogin = false;
        this.status.watch("/status", 2000);
        await this.loadMe();
    }

    async loadMe() {
        try {
            this.state.me = await this.client.me();
        } catch (error) {
            if (error instanceof CoreError && error.status === 401) {
                this.client.token = null; // a token that the service does not know any more
                this.state.me = await this.client.me().catch(() => null);
            } else {
                this.state.me = null;
            }
        }
    }

    get loggedIn() {
        return this.state.me?.kind === "user";
    }

    openLogin() {
        this.state.showLogin = true;
    }

    async submitLogin() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.loginError = "";
        try {
            this.state.me = await this.client.login(this.state.loginName, this.state.loginPassword);
            this.state.showLogin = false;
            this.state.loginPassword = "";
            this.notification.add(_t("Signed in at the controller service as %s", this.state.me.name), { type: "success" });
        } catch (error) {
            this.state.loginPassword = "";
            // the service does not tell a wrong name from a wrong password, and neither does the page
            this.state.loginError =
                error.status === 429
                    ? _t("Too many attempts, please wait a minute.")
                    : error.status === 0
                      ? error.message
                      : _t("Name or password wrong.");
        } finally {
            this.state.busy = false;
        }
    }

    async logout() {
        await this.client.logout().catch(() => {});
        await this.loadMe();
    }
}

registry.category("actions").add("int_regler.app", IntReglerApp);
