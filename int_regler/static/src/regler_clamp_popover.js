import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { useNumpadDecimal } from "@web/views/fields/numpad_decimal_hook";
import { formatNumber, parseNumber } from "./regler_numbers";

/** How much the step buttons of the popover change the number. */
const STEPS = [-1, -0.1, 0.1, 1];

/**
 * The popover of an analog row: where the number to clamp is entered. The core closes it (Escape, a click elsewhere, the row going
 * away) and keeps the focus in it; what is here is the input, the steps and the two buttons. Nothing is asked of the controller
 * before "Clamp" (or Enter): a click on a step or a typo changes only what stands in the input.
 * The input is the one of the float field of Odoo: text, decimal keyboard, the decimal key of the numpad, the number format of the user.
 */
export class ReglerClampPopover extends Component {
    static template = "int_regler.ClampPopover";
    static props = {
        close: Function,
        title: String,
        now: { type: String, optional: true },
        unit: { type: String, optional: true },
        /** What the input starts with: the number the row is clamped to, else the value now (already written for the user). */
        value: String,
        /** Called with the number when the user clamps (not called for a number that is no number). */
        onConfirm: Function,
    };

    setup() {
        this.state = useState({ text: this.props.value, invalid: false });
        this.inputRef = useRef("numpadDecimal");
        this.steps = STEPS;
        useNumpadDecimal();
        onMounted(() => this.inputRef.el?.focus()); // the hook selects the text when the input gets the focus
    }

    stepLabel(step) {
        return (step < 0 ? "−" : "+") + formatNumber(Math.abs(step));
    }

    onInput(ev) {
        this.state.text = ev.target.value;
        this.state.invalid = false;
    }

    /** A step changes the number of the input (from what stands there, else from what the input started with), not the controller. */
    step(delta) {
        let base = parseNumber(this.state.text);
        if (Number.isNaN(base)) {
            base = parseNumber(this.props.value) || 0;
        }
        this.state.text = formatNumber(Math.round((base + delta) * 1000) / 1000);
        this.state.invalid = false;
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.confirm();
        }
    }

    confirm() {
        const value = parseNumber(this.state.text);
        if (Number.isNaN(value)) {
            this.state.invalid = true; // stays open: the user corrects it
            return;
        }
        this.props.onConfirm(value);
        this.props.close();
    }
}
