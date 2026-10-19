import { Component } from "@odoo/owl";
import { DocumentFileViewer } from "./document_file_viewer";

/** The preview on the page of a document: the file viewer without its full screen frame. */
export class DocumentPreview extends Component {
    static template = "int_filemanager.DocumentPreview";
    static components = { DocumentFileViewer };
    static props = { file: Object };
}
