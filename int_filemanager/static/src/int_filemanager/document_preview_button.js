import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { documentFileFromRecord } from "./document_file";
import { useDocumentFileViewer } from "./document_file_viewer";

/**
 * A button in the form of a document that opens its file in the file viewer. Beside the form
 * the core docks the preview from the width XXL on (see `DocumentFormRenderer`); below it
 * there is none, and this button is the way to it.
 */
export class DocumentPreviewButton extends Component {
    static template = "int_filemanager.DocumentPreviewButton";
    static props = { ...standardWidgetProps };

    setup() {
        this.fileViewer = useDocumentFileViewer();
    }

    get file() {
        return documentFileFromRecord(this.props.record);
    }

    onClick() {
        this.fileViewer.open(this.file);
    }
}

export const documentPreviewButton = {
    component: DocumentPreviewButton,
    fieldDependencies: [
        { name: "name", type: "char" },
        { name: "mimetype", type: "char" },
        { name: "checksum", type: "char" },
        { name: "size", type: "float" },
    ],
};

registry.category("view_widgets").add("int_filemanager_preview_button", documentPreviewButton);
