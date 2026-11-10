import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/views/fields/formatters";
import { useNumpadDecimal } from "@web/views/fields/numpad_decimal_hook";
import { parseFloat as parseLocaleFloat } from "@web/views/fields/parsers";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/** The digits of the numbers of a row (the fields "value" and "clamp_value" of int.regler.parameter have three). */
const DIGITS = [16, 3];

/**
 * The state of a row and the buttons to clamp or release it, in the list of process values. The field it is put on is "clamped".
 * A row that can be clamped shows [Auto | 0 | 1] (a digital row) or [Auto] and a number (an analog row): the filled segment is what the
 * row is now, Auto being the controller's own value. A clamp is the exception, so it is what stands out (yellow, with a lock); Auto
 * is quiet. A click makes a request like the page of the module does (int.regler.command) and waits until the service has carried it
 * out; the row itself changes when the list reloads after the next report. Only a user of the group Operator can press (the server
 * decides in the end); the others see the state as text, as a read-only field of Odoo shows it.
 * The number of an analog row is an input like the one of the float field of Odoo (text, decimal keyboard, the decimal key of the
 * numpad, the number format of the user): while the row is on Auto it shows the value now as a placeholder, the user types over it.
 */
export class ReglerClampField extends Component {
    static template = "int_regler.ClampField";
    static props = { ...standardFieldProps };

    setup() {
        this.clamping = useService("int_regler_clamping");
        this.notification = useService("notification");
        this.state = useState({ busy: false, typed: null, pending: null });
        this.operator = false;
        useNumpadDecimal();
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

    /** A number as the user writes it (the decimal point of the language, no thousands separator, no trailing zeros). */
    format(value) {
        return formatFloat(Number(value) || 0, { digits: DIGITS, trailingZeros: false, thousandsSep: "" });
    }

    /** The number in the input of an analog row: what the user typed, else what the row is clamped to, else nothing (Auto). */
    get number() {
        if (this.state.typed !== null) {
            return this.state.typed;
        }
        return this.data.clamped ? this.format(this.data.clamp_value) : "";
    }

    /** On Auto the input is empty and shows the value now, grey: it is what the controller has, not what is asked for. */
    get placeholder() {
        return this.data.clamped ? "" : this.format(this.data.value);
    }

    /** What a user who cannot press sees of a clamped row. */
    get clampText() {
        return this.format(this.data.clamp_value);
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
        this.state.typed = ev.target.value;
    }

    /** Escape: what was typed is dropped, the input shows the row again (and the list does not see the key). */
    onKeydown(ev) {
        if (ev.key === "Escape" && this.state.typed !== null) {
            ev.stopPropagation();
            this.state.typed = null;
            ev.target.value = this.number;
        }
    }

    /** Leaving the input without a change: what was typed is dropped, the input shows the row again. */
    onBlur() {
        if (!this.state.busy) {
            this.state.typed = null;
        }
    }

    /** The input of an analog row: the number is clamped when the user ends it (Enter or leaving the input). */
    onNumber(ev) {
        let value = NaN;
        const raw = ev.target.value.trim();
        if (raw !== "") {
            try {
                value = parseLocaleFloat(raw); // the number format of the user, as every float field reads it
            } catch {
                value = NaN;
            }
        }
        if (Number.isNaN(value)) {
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
