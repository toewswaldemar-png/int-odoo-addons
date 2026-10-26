import { Component } from "@odoo/owl";
import { Dropzone } from "@web/core/dropzone/dropzone";
import { _t } from "@web/core/l10n/translation";

/** The core's dropzone with a text that says where the files go. */
export class DocumentDropzone extends Component {
    static template = "int_filemanager.DocumentDropzone";
    static components = { Dropzone };
    static props = {
        ...Dropzone.props,
        getFolderName: Function,
        getTarget: { type: Function, optional: true },
    };

    /** @returns {String} */
    get message() {
        const target = this.props.getTarget?.();
        if (target) {
            return target.message;
        }
        const folder = this.props.getFolderName();
        return folder
            ? _t("Drop the files into %(folder)s", { folder })
            : _t("Choose a folder in the panel on the left first.");
    }
}
