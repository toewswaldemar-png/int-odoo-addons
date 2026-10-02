/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {CodeEditor} from "@web/core/code_editor/code_editor";
import {Dialog} from "@web/core/dialog/dialog";
import {useService} from "@web/core/utils/hooks";
import {errorMessage, newOperationKey, textToBase64} from "./utils.js";

// Edits a small text file. Saving stores a NEW version from the revision that was loaded;
// if somebody else saved in the meantime the server refuses and says so, instead of
// overwriting their change.
export class IntFilemanagerV2TextEditorDialog extends Component {
    static template = "int_filemanager.v2.TextEditorDialog";
    static components = {Dialog, CodeEditor};
    static props = {
        title: String,
        nodeId: Number,
        baseRevisionId: {type: [Number, Boolean]},
        content: String,
        close: Function,
        onSaved: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({value: this.props.content, saving: false});
    }

    onChange(value) {
        this.state.value = value;
    }

    async onSave() {
        this.state.saving = true;
        try {
            await this.orm.call("int_filemanager.node", "create_new_revision", [], {
                node_id: this.props.nodeId,
                base_revision_id: this.props.baseRevisionId || false,
                content: textToBase64(this.state.value),
                operation_key: newOperationKey(),
                origin: "edit",
            });
            this.props.onSaved();
            this.props.close();
        } catch (error) {
            this.notification.add(errorMessage(error), {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }
}
