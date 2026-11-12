import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { ReglerClampPopover } from "./workbench_clamp_popover";
import { formatNumber } from "./workbench_numbers";

/**
 * The state of a row and the buttons to clamp or release it, in the list of process values. The field it is put on is "clamped".
 * A row that can be clamped shows [Auto | 0 | 1] (a digital row) or [Auto | number] (an analog row): the filled segment is what the
 * row is now, Auto being the controller's own value. A clamp is the exception, so it is what stands out (yellow, with a lock); Auto
 * is quiet. The number segment of an analog row shows the value now (or what the row is clamped to) and opens a popover where the
 * number is entered and clamped (workbench_clamp_popover.js): the list has no input in it, so its rows are of one height and a number is
 * never asked of the controller by a slip.
 * A click makes a request like the page of the module does (int.workbench.command) and waits until the service has carried it out; the
 * row itself changes when the list reloads after the next report. Only a user of the group Operator can press (the server decides in
 * the end); the others see the state as text, as a read-only field of Odoo shows it.
 */
export class ReglerClampField extends Component {
    static template = "int_workbench.ClampField";
    static props = { ...standardFieldProps };

    setup() {
        this.clamping = useService("int_workbench_clamping");
        this.notification = useService("notification");
        this.popover = usePopover(ReglerClampPopover, { position: "bottom-start" });
        this.state = useState({ busy: false, pending: null });
        this.operator = false;
        onWillStart(async () => {
            this.operator = await this.clamping.canClamp();
        });
    }

    get data() {
        return this.props.record.data;
    }

    /** Can the user press the buttons? Others see the state of the row all the same. */
    get canUse() {
        return this.operator && !this.state.busy;
    }

    get isAuto() {
        return !this.data.clamped;
    }

    isClampedTo(value) {
        return !!this.data.clamped && Number(this.data.clamp_value) === value;
    }

    /** The number segment of an analog row: what the row is clamped to, else the value now. */
    get numberText() {
        return formatNumber(this.data.clamped ? this.data.clamp_value : this.data.value);
    }

    /** What a user who cannot press sees of a clamped row. */
    get clampText() {
        return formatNumber(this.data.clamp_value);
    }

    /** Auto: releases the row (nothing to do if it is not clamped). */
    auto() {
        return this.isAuto ? undefined : this.send("release", 0);
    }

    /** 0 or 1 for a digital row (nothing to do if it is clamped to that already). */
    pick(value) {
        return this.isClampedTo(value) ? undefined : this.send("set", value);
    }

    /** The number segment: opens the popover (a second click closes it again). */
    openNumber(ev) {
        if (this.popover.isOpen) {
            this.popover.close();
            return;
        }
        if (!this.canUse) {
            return;
        }
        this.popover.open(ev.currentTarget, {
            title: `${_t("Row %s", this.data.code)} · ${this.data.name}`,
            now: this.data.text || undefined,
            unit: this.data.unit || undefined,
            value: this.numberText,
            onConfirm: (value) => this.setNumber(value),
        });
    }

    /** The number of the popover: clamped (nothing to do if the row is clamped to that already). */
    setNumber(value) {
        return this.isClampedTo(value) ? undefined : this.send("set", value);
    }

    async send(action, value) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        // which of the segments waits (it shows a spinner): Auto, 0, 1 or the number
        this.state.pending = action === "release" ? "auto" : this.data.analog ? "set" : String(value);
        try {
            const answer = await this.clamping.clamp(this.data.device_id.id, this.data.code, action, value);
            if (!answer.confirmed) {
                this.notification.add(answer.error || _t("The controller did not confirm."), {
                    title: _t("Row %s", this.data.code),
                    type: "danger",
                });
            }
        } catch (error) {
            this.notification.add(error?.message || String(error), { title: _t("Row %s", this.data.code), type: "danger" });
        } finally {
            this.state.busy = false;
            this.state.pending = null;
        }
    }
}

export const reglerClampField = {
    component: ReglerClampField,
    displayName: _t("Clamp"),
    supportedTypes: ["boolean"],
    isEmpty: () => false,
};

registry.category("fields").add("int_workbench.clamp", reglerClampField);
