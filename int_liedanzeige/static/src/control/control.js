/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";

import { backspaceTarget, canTypeDigit, hymnChange, isNumpadLocked } from "../common/numpad_logic";
import { nextStart, remainingFraction } from "../common/reset_timer";
import { SettingsQueue } from "../common/settings_queue";
import { IntLiedanzeigeSettingsPanel } from "./settings_panel";

const MODEL = "int_liedanzeige.state";
const NOTIFICATION_TYPE = "int_liedanzeige_notify";
const RESET_START_KEY = "int_liedanzeige.reset_start";
const NUMPAD_KEYS = ["7", "8", "9", "4", "5", "6", "1", "2", "3"];
const TICK_MS = 200;

/**
 * The operator page: a number pad that types into the hymn or the choir display.
 *
 * The page never changes its own numbers; it shows what the server reports back, so every
 * open control page stays equal.
 */
export class IntLiedanzeigeControl extends Component {
    static template = "int_liedanzeige.Control";
    static components = { IntLiedanzeigeSettingsPanel };
    static props = { config: Object };

    setup() {
        this.target = this.props.config.target;
        this.orm = useService("orm");
        this.busService = useState(useService("bus_service"));
        this.numpadKeys = NUMPAD_KEYS;
        this.digitSlots = [0, 1, 2, 3];
        this.state = useState({
            hymn: "",
            choir: "",
            control: "",
            settings: this.props.config.state.settings,
            ranges: this.props.config.state.ranges,
            kioskFullscreen: this.props.config.state.kiosk_fullscreen,
            settingsOpen: false,
            resetProgress: 100,
            error: null,
        });
        this.settingsQueue = new SettingsQueue((values) => this.sendSettings(values));
        // Actions are sent one after the other: digits typed fast must arrive in order.
        this.queue = Promise.resolve();
        this.resetStart = null;
        this.resetInterval = null;
        this.onNotification = (payload) => {
            if (payload.target === "control") {
                this.applyState(payload);
            }
        };
        useBus(this.busService, "BUS:RECONNECT", () => this.loadState());

        onMounted(() => {
            this.applyState(this.props.config.state);
            this.busService.subscribe(NOTIFICATION_TYPE, this.onNotification);
            this.busService.start();
        });
        onWillUnmount(() => {
            this.busService.unsubscribe(NOTIFICATION_TYPE, this.onNotification);
            browser.clearInterval(this.resetInterval);
        });
    }

    get isHymn() {
        return this.target === "hymn";
    }

    get locked() {
        return isNumpadLocked(this.target, this.state.hymn, this.state.choir);
    }

    get connected() {
        return this.busService.workerState === "CONNECTED";
    }

    get title() {
        return this.isHymn ? _t("HYMN DISPLAY") : _t("CHOIR DISPLAY");
    }

    get statusLabel() {
        return this.connected ? _t("Connected") : _t("Connecting…");
    }

    get otherUrl() {
        return this.isHymn ? "/steuerung/chor" : "/steuerung/lied";
    }

    toggleSettings() {
        this.state.settingsOpen = !this.state.settingsOpen;
    }

    closeSettings() {
        this.state.settingsOpen = false;
    }

    /** Show a changed setting at once and send it, merged with the changes that follow. */
    onSettingChange(key, value) {
        this.state.settings[key] = value;
        return this.settingsQueue.push(key, value);
    }

    async sendSettings(values) {
        try {
            const result = await this.orm.call(MODEL, "apply_action", [
                "settings",
                null,
                null,
                values,
            ]);
            // A slider that is still moving owns the values on screen.
            if (!this.settingsQueue.pending) {
                this.state.settings = result.settings;
            }
            this.state.error = null;
        } catch (error) {
            this.state.error = error.data?.message || error.message || String(error);
        }
    }

    /** Send a window command to the kiosk programs. */
    async onKioskCommand(command) {
        if (command === "fullscreen" || command === "windowed") {
            // The kiosk reports the real state a moment later.
            this.state.kioskFullscreen = command === "fullscreen";
        }
        try {
            await this.orm.call(MODEL, "send_kiosk_command", [command]);
            this.state.error = null;
        } catch (error) {
            this.state.error = error.data?.message || error.message || String(error);
        }
    }

    digitAt(index) {
        return this.state.control[index] || "";
    }

    switchTarget() {
        browser.location.replace(this.otherUrl);
    }

    onKey(key) {
        if (canTypeDigit(this.state.control)) {
            this.send("input", this.target, key);
        }
    }

    onBackspace() {
        this.send("backspace", backspaceTarget(this.target, this.locked));
    }

    onClear() {
        // The clear key always resets both displays.
        this.send("reset", "hymn");
    }

    send(action, target, value = null, values = null) {
        this.queue = this.queue.then(async () => {
            try {
                const result = await this.orm.call(MODEL, "apply_action", [
                    action,
                    target,
                    value,
                    values,
                ]);
                this.applyState(result);
                this.state.error = null;
            } catch (error) {
                this.state.error = error.data?.message || error.message || String(error);
            }
        });
        return this.queue;
    }

    async loadState() {
        this.applyState(await this.orm.call(MODEL, "get_state", []));
    }

    applyState(values) {
        const change = hymnChange(this.state.hymn, values.hymn_state);
        this.state.hymn = values.hymn_state;
        this.state.choir = values.choir_state;
        this.state.control = values.control_state;
        this.state.kioskFullscreen = values.kiosk_fullscreen;
        if (!this.settingsQueue.busy) {
            this.state.settings = values.settings;
        }
        this.trackReset(change);
    }

    /** Run the idle time of the hymn number and reset the displays when it is over. */
    trackReset(change) {
        if (!this.isHymn || !this.state.hymn) {
            this.stopReset();
            return;
        }
        const stored = Number.parseInt(browser.sessionStorage.getItem(RESET_START_KEY), 10);
        this.resetStart = nextStart(
            change,
            this.resetStart,
            Number.isNaN(stored) ? null : stored,
            Date.now()
        );
        browser.sessionStorage.setItem(RESET_START_KEY, String(this.resetStart));
        if (this.resetInterval === null) {
            this.resetInterval = browser.setInterval(() => this.tickReset(), TICK_MS);
        }
        this.tickReset();
    }

    tickReset() {
        const remaining = remainingFraction(
            this.resetStart,
            Date.now(),
            this.state.settings.reset_delay
        );
        this.state.resetProgress = remaining * 100;
        if (remaining <= 0) {
            this.stopReset();
            this.state.resetProgress = 0;
            this.send("reset", "hymn");
        }
    }

    stopReset() {
        browser.clearInterval(this.resetInterval);
        this.resetInterval = null;
        this.resetStart = null;
        this.state.resetProgress = 100;
        browser.sessionStorage.removeItem(RESET_START_KEY);
    }
}
