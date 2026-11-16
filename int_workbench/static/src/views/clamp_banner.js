import { Component, onWillStart, useEffect, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

const PARAMETER_MODEL = "int.workbench.parameter";
const OPERATOR_GROUP = "int_workbench.int_workbench_group_operator";
/** More clamped rows than this are counted only up to here (a controller has a few dozen rows). */
const CLAMPED_LIMIT = 1000;

/**
 * The strip above the list of the process values that says whether rows are clamped, and where. A clamp stays in the controller until it
 * is released, and the row that holds one can be scrolled out of sight, filtered away or on another page: the strip counts the clamped
 * rows of every controller, not only those on the screen. It is always there and always as high as a row (parameter_list.scss), yellow
 * while something is clamped and grey when nothing is: a strip that came and went would push the table down and up under the pointer of
 * someone who is clicking the switches. The operator can release them all from it; that is the call of the button at the top of the list,
 * which asks the service for the release of every clamped row.
 */
export class ClampBanner extends Component {
    static template = "int_workbench.ClampBanner";
    static props = { list: Object };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ devices: [], canRelease: false });
        onWillStart(async () => {
            this.state.canRelease = await user.hasGroup(OPERATOR_GROUP);
        });
        // when the rows of the list change (the list loads them afresh when the service reports a change): count again
        useEffect(
            () => {
                this.refresh();
            },
            () => [this.signature]
        );
    }

    get isParameterList() {
        return this.props.list.resModel === PARAMETER_MODEL;
    }

    /** What the rows of the list say about their clamp: it changes when a clamp is set or released. */
    get signature() {
        // a grouped list has groups, not records: it keeps the count it has until the rows come into view again
        return (this.props.list.records || []).map((record) => `${record.resId}:${record.data.clamped ? 1 : 0}`).join(",");
    }

    async refresh() {
        if (!this.isParameterList) {
            return;
        }
        const rows = await this.orm.searchRead(PARAMETER_MODEL, [["clamped", "=", true]], ["device_id"], { limit: CLAMPED_LIMIT });
        const counts = new Map();
        for (const row of rows) {
            const [id, name] = row.device_id || [0, ""];
            counts.set(id, { id, name, count: (counts.get(id)?.count || 0) + 1 });
        }
        this.state.devices = [...counts.values()];
    }

    get total() {
        return this.state.devices.reduce((sum, device) => sum + device.count, 0);
    }

    /** "Clamped rows on Bench: 3"; with several controllers "Clamped rows: Bench: 3, Table 2: 1" (no plural to get wrong). */
    get message() {
        if (!this.state.devices.length) {
            return _t("No row is clamped");
        }
        if (this.state.devices.length === 1) {
            return _t("Clamped rows on %(device)s: %(count)s", { device: this.state.devices[0].name, count: this.total });
        }
        const parts = this.state.devices.map((device) => `${device.name}: ${device.count}`);
        return _t("Clamped rows: %(devices)s", { devices: parts.join(", ") });
    }

    async releaseAll() {
        const result = await this.orm.call(PARAMETER_MODEL, "action_release_all", [[]], {
            context: { active_domain: [["clamped", "=", true]] },
        });
        if (result) {
            await this.action.doAction(result);
        }
        await this.refresh();
    }
}
