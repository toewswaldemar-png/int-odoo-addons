/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useEffect, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useBus, useService } from "@web/core/utils/hooks";

import { fontCss } from "../common/fonts";
import { formatDate, formatTime, gapPixels, heightBudget } from "../common/layout_math";
import { IntLiedanzeigeScaledText } from "./scaled_text";

// Short connection drops are not worth an overlay.
const OVERLAY_DELAY_MS = 800;
const NOTIFICATION_TYPE = "int_liedanzeige_notify";
const CHANNELS = { hymn: "int_liedanzeige_hymn", choir: "int_liedanzeige_choir" };

/**
 * A beamer display: the clock while idle, the hymn or choir number after an input.
 *
 * The page never sends anything to the server; it only shows what the bus delivers.
 */
export class IntLiedanzeigeDisplay extends Component {
    static template = "int_liedanzeige.Display";
    static components = { IntLiedanzeigeScaledText };
    static props = { config: Object };

    setup() {
        this.target = this.props.config.target;
        this.busService = useState(useService("bus_service"));
        const { state } = this.props.config;
        this.state = useState({
            number: state[`${this.target}_state`],
            settings: state.settings,
            time: formatTime(new Date()),
            date: formatDate(new Date()),
            viewportH: browser.innerHeight,
            overlay: false,
            blackout: false,
        });
        this.heights = { time: 0, date: 0, number: 0, subClock: 0 };
        this.everConnected = false;
        this.numberTimeout = null;
        this.overlayTimeout = null;

        this.onResize = () => {
            this.state.viewportH = browser.innerHeight;
            this.applyGap();
        };
        // The shared worker delivers the notifications of every display open in this browser.
        this.onNotification = (payload) => {
            if (payload.target === this.target) {
                this.applyNumber(payload.number);
                this.state.settings = payload.settings;
            }
        };
        useBus(this.busService, "BUS:RECONNECT", () => this.loadState());
        useBus(this.busService, "BUS:CONNECT", () => this.loadState());

        onMounted(() => {
            this.busService.subscribe(NOTIFICATION_TYPE, this.onNotification);
            this.busService.addChannel(CHANNELS[this.target]);
            this.clockInterval = browser.setInterval(() => {
                const now = new Date();
                this.state.time = formatTime(now);
                this.state.date = formatDate(now);
            }, 1000);
            browser.addEventListener("resize", this.onResize);
            // The kiosk dims the screen by calling this function on the window.
            window.__kioskBlackout = (show) => {
                this.state.blackout = Boolean(show);
            };
            this.applyNumber(this.state.number);
        });
        onWillUnmount(() => {
            this.busService.unsubscribe(NOTIFICATION_TYPE, this.onNotification);
            this.busService.deleteChannel(CHANNELS[this.target]);
            browser.clearInterval(this.clockInterval);
            browser.clearTimeout(this.numberTimeout);
            browser.clearTimeout(this.overlayTimeout);
            browser.removeEventListener("resize", this.onResize);
            delete window.__kioskBlackout;
        });

        // Fonts and the shadow reach every line through custom properties on the page.
        useEffect(
            (font, shadow) => {
                const style = document.documentElement.style;
                style.setProperty("--int-liedanzeige-font", fontCss(font));
                const opacity = (shadow / 100).toFixed(2);
                // Em units: the shadow grows with the font size of each line.
                style.setProperty(
                    "--int-liedanzeige-shadow",
                    `0.025em 0.025em 0.04em rgba(0, 0, 0, ${opacity})`
                );
            },
            () => [this.state.settings.font, this.state.settings.shadow_strength]
        );
        useEffect(
            (workerState) => this.watchConnection(workerState),
            () => [this.busService.workerState]
        );
        useEffect(
            () => this.applyGap(),
            () => [this.state.settings.gap_time_date, this.isInputMode]
        );
    }

    get isInputMode() {
        return this.state.number.length > 0;
    }

    get budget() {
        const { time_size, sub_clock_size } = this.state.settings;
        return heightBudget(this.state.viewportH, time_size, sub_clock_size);
    }

    get connectingLabel() {
        return _t("Connecting to server…");
    }

    applyNumber(number) {
        const changed = number !== this.state.number;
        this.state.number = number;
        if (changed || this.numberTimeout === null) {
            browser.clearTimeout(this.numberTimeout);
            this.numberTimeout = null;
            if (number.length > 0) {
                // The control page resets the server state as well; this covers a lost control page.
                this.numberTimeout = browser.setTimeout(() => {
                    this.state.number = "";
                    this.numberTimeout = null;
                }, this.state.settings.reset_delay * 60 * 1000);
            }
        }
    }

    async loadState() {
        const { hymn_state, choir_state, settings } = await rpc("/int_liedanzeige/state");
        this.applyNumber(this.target === "hymn" ? hymn_state : choir_state);
        this.state.settings = settings;
    }

    watchConnection(workerState) {
        if (workerState === "CONNECTED") {
            this.everConnected = true;
            this.state.overlay = false;
            browser.clearTimeout(this.overlayTimeout);
            return;
        }
        if (!this.everConnected) {
            return;
        }
        this.overlayTimeout = browser.setTimeout(() => {
            this.state.overlay = true;
        }, OVERLAY_DELAY_MS);
        return () => browser.clearTimeout(this.overlayTimeout);
    }

    onLineHeight(name, height) {
        this.heights[name] = height;
        this.applyGap();
    }

    applyGap() {
        const [first, second] = this.isInputMode
            ? [this.heights.number, this.heights.subClock]
            : [this.heights.time, this.heights.date];
        const gap = gapPixels(
            browser.innerHeight,
            first,
            second,
            this.state.settings.gap_time_date
        );
        if (gap !== null) {
            document.documentElement.style.setProperty("--int-liedanzeige-gap", `${gap}px`);
        }
    }
}
