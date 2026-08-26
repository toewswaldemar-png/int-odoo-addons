/** @odoo-module **/

import { Component, useEffect } from "@odoo/owl";
import { Record } from "@web/model/record";
import { Field } from "@web/views/fields/field";

class IntTagsCell extends Component {
    static template = "int_filemanager.TagsCell";
    static components = { Field };
    static props = { record: Object, onSaved: Function };

    setup() {
        this.initialized = false;
        useEffect(
            () => {
                if (this.initialized) {
                    this.save();
                } else {
                    this.initialized = true;
                }
            },
            () => [JSON.stringify(this.props.record.data.tag_ids.currentIds)]
        );
    }

    async save() {
        await this.props.record.save({ reload: false });
        this.props.onSaved(this.props.record.resId);
    }
}

export class IntInlineTags extends Component {
    static template = "int_filemanager.InlineTags";
    static components = { Record, IntTagsCell };
    static props = {
        path: String,
        metaId: { type: [Number, Boolean], optional: true },
        onSaved: Function,
    };

    get fields() {
        return {
            path: { type: "char", string: "Path" },
            tag_ids: {
                type: "many2many",
                relation: "int_filemanager.tag",
                string: "Tags",
            },
        };
    }

    get activeFields() {
        return {
            path: {},
            tag_ids: {
                related: {
                    activeFields: { display_name: {}, color: {} },
                    fields: { display_name: { type: "char" }, color: { type: "integer" } },
                },
            },
        };
    }

    get initialValues() {
        return this.props.metaId ? undefined : { path: this.props.path, tag_ids: [] };
    }
}
