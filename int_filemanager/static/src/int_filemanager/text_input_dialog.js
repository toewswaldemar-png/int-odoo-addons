/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useAutofocus } from "@web/core/utils/hooks";

export class IntTextInputDialog extends Component {
    static template = "int_filemanager.TextInputDialog";
    static components = { Dialog };
    static props = {
        title: String,
        label: { type: String, optional: true },
        value: { type: String, optional: true },
        confirmLabel: { type: String, optional: true },
        confirm: Function,
        close: Function,
    };
    static defaultProps = {
        value: "",
        confirmLabel: "OK",
    };

    setup() {
        this.state = useState({ value: this.props.value });
        useAutofocus({ selectAll: true });
    }

    onConfirm() {
        const value = this.state.value.trim();
        if (!value) {
            return;
        }
        this.props.confirm(value);
        this.props.close();
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            this.onConfirm();
        }
    }
}
