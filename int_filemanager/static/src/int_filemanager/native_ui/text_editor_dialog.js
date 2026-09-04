/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { CodeEditor } from "@web/core/code_editor/code_editor";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

export class IntTextEditorDialog extends Component {
    static template = "int_filemanager.TextEditorDialog";
    static components = { Dialog, CodeEditor };
    static props = {
        title: String,
        path: String,
        content: String,
        close: Function,
        onSaved: Function,
    };

    setup() {
        this.notification = useService("notification");
        this.state = useState({ value: this.props.content, saving: false });
    }

    onChange(value) {
        this.state.value = value;
    }

    async onSave() {
        this.state.saving = true;
        try {
            await rpc("/int_filemanager/write_text", { path: this.props.path, content: this.state.value });
            this.props.onSaved();
            this.props.close();
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}
