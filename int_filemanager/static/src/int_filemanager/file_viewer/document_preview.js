import { Component } from "@odoo/owl";

/**
 * The preview of the file on the page of a document, as large as the page allows. PDFs and
 * texts are shown by the browser in a frame, with the browser's own zoom and search.
 */
export class DocumentPreview extends Component {
    static template = "int_filemanager.DocumentPreview";
    static props = { file: Object };
}
