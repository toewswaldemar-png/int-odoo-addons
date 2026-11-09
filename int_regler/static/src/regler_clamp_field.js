import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * The state of a row and the buttons to clamp or release it, in the list of process values. The field it is put on is "clamped".
 * A row that can be clamped shows [Auto | 0 | 1] (a digital row) or [Auto] and a number (an analog row): the filled segment is what the
 * row is now, Auto being the controller's own value. A click makes a request like the page of the module does (int.regler.command) and
 * waits until the service has carried it out; the row itself changes when the list reloads after the next report. Only a user of the
 * group Operator can press (the server decides in the end); the others see the state.
 */
export class ReglerClampField extends Component {
    static template = "int_regler.ClampField";
    static props = { ...standardFieldProps };

    setup() {
        this.clamping = useService("int_regler_clamping");
        this.notification = useService("notification");
        this.state = useState({ busy: false, typed: null });
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

    /** The number in the input of an analog row: what the user typed, else what the row is clamped to, else its value now. */
    get number() {
        if (this.state.typed !== null) {
            return this.state.typed;
        }
        return this.data.clamped ? this.data.clamp_value : this.data.value;
    }

    /** Auto: releases the row (nothing to do if it is not clamped). */
    auto() {
        return this.isAuto ? undefined : this.send("release", 0);
    }

    /** 0 or 1 for a digital row (nothing to do if it is clamped to that already). */
    pick(value) {
        return this.isClampedTo(value) ? undefined : this.send("set", value);
    }

    /**
     * While the user types, the input keeps what was typed: the row changes with every report (a temperature does) and the value of the
     * input must not be replaced under the cursor. Core fields do the same (useInputField: "isDirty").
     */
    onInput(ev) {
        if (ev.target.validity?.badInput) {
            return; // "-" or "2e": the browser reports no value yet, the input keeps the text
        }
        this.state.typed = ev.target.value;
    }

    /** Leaving the input without a change: what was typed is dropped, the input shows the row again. */
    onBlur() {
        if (!this.state.busy) {
            this.state.typed = null;
        }
    }

    /** The input of an analog row: the number is clamped when the user ends it (Enter or leaving the input). */
    onNumber(ev) {
        const raw = ev.target.value;
        const value = Number(raw);
        if (raw === "" || Number.isNaN(value)) {
            this.state.typed = null;
            ev.target.value = this.number; // not a number: the input shows what the row has
            return undefined;
        }
        return this.isClampedTo(value) ? undefined : this.send("set", value);
    }

    async send(action, value) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
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
            this.state.typed = null; // the row shows what the controller has now
        }
    }
}

export const reglerClampField = {
    component: ReglerClampField,
    displayName: _t("Clamp"),
    supportedTypes: ["boolean"],
    isEmpty: () => false,
};

registry.category("fields").add("int_regler.clamp", reglerClampField);
