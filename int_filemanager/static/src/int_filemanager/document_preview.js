import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { readDocumentFile } from "./document_file";

/**
 * The preview beside the form of a document, in the place of the core's `AttachmentView`.
 * The core shows the attachments of the record there; a document is no attachment, its file
 * lies in a blob. The markup and the classes are those of the core's, so that its layout and
 * style (`o_attachment_preview`) apply: see `DocumentFormRenderer`, which puts this in.
 */
export class DocumentPreview extends Component {
    static template = "int_filemanager.DocumentPreview";
    // The props the core's form compiler gives to the component of the preview.
    static props = ["threadId", "threadModel"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ file: null });
        this.requests = 0;
        onWillStart(() => this.load(this.props.threadId));
        onWillUpdateProps((nextProps) => {
            if (nextProps.threadId !== this.props.threadId) {
                return this.load(nextProps.threadId);
            }
        });
    }

    /**
     * @param {Number|undefined} id
     */
    async load(id) {
        const request = ++this.requests;
        const file = id ? await readDocumentFile(this.orm, id) : null;
        // The user may have moved on to another document while this one was read.
        if (request === this.requests) {
            this.state.file = file;
        }
    }
}
