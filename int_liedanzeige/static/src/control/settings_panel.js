/** @odoo-module **/

import { Component, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";

import { FONTS } from "../common/fonts";

/**
 * The side panel of the hymn control page for the look of the displays.
 *
 * Each slider reports its value while it is dragged; the page decides how to send it.
 */
export class IntLiedanzeigeSettingsPanel extends Component {
    static template = "int_liedanzeige.SettingsPanel";
    static props = {
        settings: Object,
        ranges: Object,
        kioskFullscreen: Boolean,
        onKioskCommand: Function,
        onChange: Function,
        onClose: Function,
    };

    setup() {
        this.fonts = FONTS;
        this.state = useState({ confirmQuit: false });
        this.confirmTimeout = null;
        onWillUnmount(() => browser.clearTimeout(this.confirmTimeout));
    }

    get sliders() {
        const { settings, ranges } = this.props;
        const row = (key, label, unit, step = 1) => ({
            key,
            label,
            step,
            min: ranges[key][0],
            max: ranges[key][1],
            value: settings[key],
            text: unit(settings[key]),
        });
        const percent = (value) => `${value} %`;
        const minutes = (value) => (value === 1 ? _t("1 minute") : _t("%s minutes", value));
        return [
            row("time_size", _t("Font size"), percent),
            row("sub_clock_size", _t("Clock below the number"), percent),
            row("gap_time_date", _t("Gap between time and date"), percent),
            row("shadow_strength", _t("Shadow"), percent, 5),
            row("reset_delay", _t("Automatic reset"), minutes),
        ];
    }

    get fontStyle() {
        const font = this.fonts.find((candidate) => candidate.key === this.props.settings.font);
        return font ? font.css : "";
    }

    onSlider(slider, ev) {
        this.props.onChange(slider.key, Number(ev.target.value));
    }

    onToggleFullscreen() {
        this.props.onKioskCommand(this.props.kioskFullscreen ? "windowed" : "fullscreen");
    }

    /** Quitting needs a second press within three seconds. */
    onQuit() {
        if (!this.state.confirmQuit) {
            this.state.confirmQuit = true;
            this.confirmTimeout = browser.setTimeout(() => {
                this.state.confirmQuit = false;
            }, 3000);
            return;
        }
        browser.clearTimeout(this.confirmTimeout);
        this.state.confirmQuit = false;
        this.props.onKioskCommand("quit");
    }

    get quitLabel() {
        return this.state.confirmQuit ? _t("Sure?") : _t("Quit");
    }

    get fullscreenLabel() {
        return this.props.kioskFullscreen ? _t("Window") : _t("Fullscreen");
    }

    onFont(ev) {
        this.props.onChange("font", ev.target.value);
    }
}
