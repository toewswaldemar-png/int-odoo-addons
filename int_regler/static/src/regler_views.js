import { Component, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { usePoll } from "./regler_poll";

const props = { client: Object, me: [Object, { value: null }] };

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

export class ReglerValues extends Component {
    static template = "int_regler.Values";
    static props = props;

    setup() {
        const client = () => this.props.client;
        this.pages = usePoll(client);
        this.values = usePoll(client);
        this.state = useState({ page: "all", query: "" });
        onMounted(() => {
            this.pages.watch("/pages", 60000);
            this.load();
        });
    }

    load() {
        return this.values.watch(this.state.page === "all" ? "/values" : `/pages/${this.state.page}`, 2500);
    }

    selectPage(page) {
        this.state.page = page;
        return this.load();
    }

    get rows() {
        const query = this.state.query.trim().toLowerCase();
        const all = this.values.state.data?.entries || [];
        return query ? all.filter((e) => e.name.toLowerCase().includes(query) || e.code.includes(query)) : all;
    }

    /** What to show for the state of a row: [label, bootstrap color]. */
    rowStatus(entry) {
        if (entry.clamp?.clamped) {
            return [_t("clamped"), "primary"];
        }
        if (entry.status === "out_of_range") {
            return [_t("no value"), "warning"];
        }
        if (entry.status !== "ok") {
            return [entry.status, "danger"];
        }
        return entry.stale ? [_t("stale"), "secondary"] : [_t("current"), "success"];
    }

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

export class ReglerClamps extends Component {
    static template = "int_regler.Clamps";
    static props = { ...props, login: Function };

    setup() {
        this.notification = useService("notification");
        this.clamps = usePoll(() => this.props.client);
        this.state = useState({ query: "", busy: {}, values: {} });
        onMounted(() => this.clamps.watch("/clamps", 2500));
    }

    get canClamp() {
        return !!this.props.me?.rights?.includes("clamp");
    }

    get enabled() {
        return !!this.clamps.state.data?.enabled;
    }

    get allowed() {
        return this.canClamp && this.enabled;
    }

    get rows() {
        const query = this.state.query.trim().toLowerCase();
        const all = this.clamps.state.data?.rows || [];
        return query ? all.filter((r) => r.name.toLowerCase().includes(query) || r.code.includes(query)) : all;
    }

    isClamped(row) {
        return row.held || row.state?.clamped === true;
    }

    get clampedCount() {
        return (this.clamps.state.data?.rows || []).filter((r) => this.isClamped(r)).length;
    }

    /** The value in the field of an analog row; the lowest allowed value until something is typed. */
    valueOf(row) {
        return this.state.values[row.code] ?? (row.min ?? 0);
    }

    /** The number in the field of an analog row. */
    clampValue(row) {
        return Number(this.valueOf(row));
    }

    validValue(row) {
        const value = Number(this.valueOf(row));
        return (
            String(this.valueOf(row)).trim() !== "" &&
            Number.isFinite(value) &&
            (row.min === null || value >= row.min) &&
            (row.max === null || value <= row.max)
        );
    }

    setValue(row, ev) {
        this.state.values[row.code] = ev.target.value;
    }

    async run(row, action, value) {
        this.state.busy[row.code] = true;
        try {
            const body = action === "set" ? { action, value } : { action };
            const result = await this.props.client.post(`/clamps/${encodeURIComponent(row.code)}`, body);
            if (result.confirmed) {
                this.notification.add(
                    action === "set" ? _t("%(name)s clamped to %(value)s", { name: row.name, value }) : _t("%s released", row.name),
                    { type: "success" }
                );
            } else {
                this.notification.add(result.error || _t("%s: the controller did not confirm", row.name), { type: "warning" });
            }
        } catch (error) {
            const detail = error.body?.error || error.message;
            this.notification.add(`${row.name}: ${detail}`, { type: "danger" });
        } finally {
            delete this.state.busy[row.code];
            this.clamps.refresh(); // the new state now, not at the next tick
        }
    }

    async releaseAll() {
        for (const row of (this.clamps.state.data?.rows || []).filter((r) => this.isClamped(r))) {
            await this.run(row, "release");
        }
    }
}
