/** @odoo-module **/

import { Component, useEffect } from "@odoo/owl";
import { Record } from "@web/model/record";
import { Field } from "@web/views/fields/field";

class HmTagsCell extends Component {
    static template = "hm_filemanager.TagsCell";
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

export class HmInlineTags extends Component {
    static template = "hm_filemanager.InlineTags";
    static components = { Record, HmTagsCell };
    static props = {
        path: String,
        metaId: { type: [Number, Boolean], optional: true },
        onSaved: Function,
    };

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
