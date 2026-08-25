/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class HmFilePreviewDialog extends Component {
    static template = "hm_filemanager.FilePreviewDialog";
    static components = { Dialog };
    static props = { path: String, close: Function };

    get previewUrl() {
        return `/hm_filemanager/download?path=${encodeURIComponent(this.props.path)}&disposition=inline`;
    }

    get fileName() {
        const parts = this.props.path.split("/");
        return parts[parts.length - 1];
    }
}
