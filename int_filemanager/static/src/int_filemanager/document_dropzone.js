import { Component } from "@odoo/owl";
import { Dropzone } from "@web/core/dropzone/dropzone";
import { _t } from "@web/core/l10n/translation";

/**
 * The core's dropzone with a text that says where the files go, as the chatter of the mail
 * module does with its own text (`MailAttachmentDropzone`). The files go to the folder chosen
 * in the search panel; with none chosen the text says so before the user lets go.
 */
export class DocumentDropzone extends Component {
    static template = "int_filemanager.DocumentDropzone";
    static components = { Dropzone };
    static props = {
        ...Dropzone.props,
        getFolderName: Function,
    };

    /** @returns {String} */
    get message() {
        const folder = this.props.getFolderName();
        return folder
            ? _t("Drop the files into %(folder)s", { folder })
            : _t("Choose a folder in the panel on the left first.");
    }
}
