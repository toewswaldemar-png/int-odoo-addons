import { Component } from "@odoo/owl";
import { Dropzone } from "@web/core/dropzone/dropzone";
import { _t } from "@web/core/l10n/translation";

/**
 * The core's dropzone with a text that says where the files go: the record, the folder chosen in
 * the search panel, or that none is chosen yet.
 */
export class DocumentDropzone extends Component {
    static template = "int_filemanager.DocumentDropzone";
    static components = { Dropzone };
    static props = {
        ...Dropzone.props,
        getFolderName: Function,
        getRecordName: { type: Function, optional: true },
    };

    /** @returns {String} */
    get message() {
        const record = this.props.getRecordName?.();
        if (record) {
            return _t("Drop the files to attach them to %(record)s", { record });
        }
        const folder = this.props.getFolderName();
        return folder
            ? _t("Drop the files into %(folder)s", { folder })
            : _t("Choose a folder in the panel on the left first.");
    }
}
