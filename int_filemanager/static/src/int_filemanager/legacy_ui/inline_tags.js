/** @odoo-module **/

import { Component, useEffect, useRef } from "@odoo/owl";
import { Record } from "@web/model/record";
import { Field } from "@web/views/fields/field";

class IntTagsCell extends Component {
    static template = "int_filemanager.TagsCell";
    static components = { Field };
    static props = { record: Object, onSaved: Function };

    setup() {
        this.cellRef = useRef("cell");
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

    onClickCell() {
        if (!this.props.record.isInEdition) {
            this.props.record.switchMode("edit");
        }
    }

    onFocusOut() {
        // Clicking a dropdown option blurs the input a tick before the click itself
        // is handled (and, for a plain option click, refocuses it right after) - decide
        // on the next tick instead of immediately, or a legitimate selection click gets
        // cut off mid-flight by an instant switch back to readonly.
        setTimeout(() => {
            // "Search more..." opens a SelectCreateDialog owned by the autocomplete
            // (useOwnedDialogs ties its lifetime to that component). Switching this
            // field to readonly here would tear down that component mid-flight and
            // Odoo would auto-close the dialog it just opened as an orphan. Odoo's own
            // dialog service flags any open dialog on the body, so defer until it's gone.
            if (document.body.classList.contains("modal-open")) {
                return;
            }
            const stillInside = this.cellRef.el && this.cellRef.el.contains(document.activeElement);
            if (this.cellRef.el && !stillInside) {
                this.props.record.switchMode("readonly");
            }
        });
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
