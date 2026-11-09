import { Component, onMounted, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { usePoll } from "./regler_poll";

const props = { client: Object };

function formatTime(iso) {
    if (!iso) {
        return "–";
    }
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

function ago(iso) {
    if (!iso) {
        return _t("never");
    }
    const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    if (seconds < 5) {
        return _t("just now");
    }
    if (seconds < 60) {
        return _t("%s s ago", seconds);
    }
    if (seconds < 3600) {
        return _t("%s min ago", Math.floor(seconds / 60));
    }
    return _t("%s h ago", Math.floor(seconds / 3600));
}

export class ReglerOverview extends Component {
    static template = "int_regler.Overview";
    static props = props;

    setup() {
        const client = () => this.props.client;
        this.status = usePoll(client);
        this.errors = usePoll(client);
        this.memory = usePoll(client);
        this.clock = usePoll(client);
        onMounted(() => {
            this.status.watch("/status", 2000);
            this.errors.watch("/errors", 4000);
            this.memory.watch("/errors/memory", 10000);
            this.clock.watch("/clock", 10000);
        });
    }

    get cycleSeconds() {
        return ((this.status.state.data?.last_cycle_ms || 0) / 1000).toFixed(1);
    }

    formatTime = formatTime;
    ago = ago;
}

export class ReglerErrors extends Component {
    static template = "int_regler.Errors";
    static props = props;

    setup() {
        const client = () => this.props.client;
        this.errors = usePoll(client);
        this.memory = usePoll(client);
        this.state = useState({ tab: "active" });
        onMounted(() => {
            this.errors.watch("/errors", 4000);
            this.memory.watch("/errors/memory", 10000);
        });
    }
}
