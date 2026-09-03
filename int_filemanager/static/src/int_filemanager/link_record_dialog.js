/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { Record } from "@web/model/record";
import { Field } from "@web/views/fields/field";
import { useService } from "@web/core/utils/hooks";

export class IntLinkRecordDialog extends Component {
    static template = "int_filemanager.LinkRecordDialog";
    static components = { Dialog, Record, Field };
    static props = {
        path: String,
        metaId: { type: [Number, Boolean], optional: true },
        close: Function,
        onSaved: Function,
    };

    setup() {
        this.orm = useService("orm");
        // The model picklist is the same "every installed model" list Odoo's own
        // ir.actions.server.resource_ref field builds server-side
        // (_selection_target_model) - fetched once since this Record is hand-built
        // rather than introspected from a real fields_get.
        this.state = useState({ selection: [] });
        onWillStart(async () => {
            const models = await this.orm.searchRead("ir.model", [], ["model", "name"]);
            this.state.selection = models.map((m) => [m.model, m.name]);
        });
    }

    get fields() {
        return {
            path: { type: "char", string: "Path" },
            res_reference: {
                type: "reference",
                string: "Verknüpfter Datensatz",
                selection: this.state.selection,
            },
        };
    }

    get activeFields() {
        return {
            path: {},
            res_reference: {},
        };
    }

    get initialValues() {
        return this.props.metaId ? undefined : { path: this.props.path, res_reference: false };
    }

    async onSave(record) {
        await record.save({ reload: false });
        this.props.onSaved(record.resId);
        this.props.close();
    }

    async onClear(record) {
        record.update({ res_reference: false });
        await record.save({ reload: false });
        this.props.onSaved(record.resId);
        this.props.close();
    }
}
