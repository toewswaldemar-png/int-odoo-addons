/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";

const MODEL = "int_liedanzeige.state";
const NOTIFICATION_TYPE = "int_liedanzeige_notify";
const SHOW_HYMN_KEY = "int_liedanzeige.conductor_show_hymn";

/**
 * The conductor view: the choir number with the text of its song, for one person's tablet.
 *
 * Whether the hymn number is shown next to it is a choice of this browser only.
 */
export class IntLiedanzeigeConductor extends Component {
    static template = "int_liedanzeige.Conductor";
    static props = { config: Object };

    setup() {
        this.orm = useService("orm");
        this.busService = useState(useService("bus_service"));
        this.state = useState({
            ...this.props.config.state,
            showHymn: browser.localStorage.getItem(SHOW_HYMN_KEY) === "1",
        });
        this.onNotification = (payload) => {
            if (payload.target === "conductor") {
                this.applyValues(payload);
            }
        };
        useBus(this.busService, "BUS:RECONNECT", () => this.loadState());
        onMounted(() => {
            this.busService.subscribe(NOTIFICATION_TYPE, this.onNotification);
            this.busService.start();
        });
        onWillUnmount(() => this.busService.unsubscribe(NOTIFICATION_TYPE, this.onNotification));
    }

    get connected() {
        return this.busService.workerState === "CONNECTED";
    }

    get statusLabel() {
        return this.connected ? _t("Connected") : _t("Connecting…");
    }

    get hymnLabel() {
        return _t("Hymn %s", this.state.hymn_number);
    }

    get hasHymn() {
        return this.state.showHymn && this.state.hymn_number.length > 0;
    }

    toggleHymn() {
        this.state.showHymn = !this.state.showHymn;
        browser.localStorage.setItem(SHOW_HYMN_KEY, this.state.showHymn ? "1" : "0");
    }

    applyValues(values) {
        this.state.choir_number = values.choir_number;
        this.state.hymn_number = values.hymn_number;
        this.state.song_name = values.song_name;
        this.state.song_text = values.song_text;
    }

    async loadState() {
        this.applyValues(await this.orm.call(MODEL, "get_conductor_state", []));
    }
}
