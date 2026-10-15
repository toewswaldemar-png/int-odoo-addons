import { FormRenderer } from "@web/views/form/form_renderer";
import { documentFileFromRecord } from "../../document_file";
import { DocumentPreview } from "../../file_viewer/document_preview";

/**
 * The form of a document with the preview of its file beside it, in the layout the core gives
 * to a record with an attachment (an invoice, an expense): the form on the left, the preview
 * on the right, the chatter below. The core builds it for the attachments of the record
 * (`ir.attachment`) and only for the width XXL and more; a document has none, its file lies
 * in a blob. So the renderer tells the layout that there is a file (`hasFile`) and puts its
 * own component in the place of the core's one (`mailComponents`). Both are the mail module's
 * own parts of the form renderer (`chatter/web/form_renderer.js`), not an extension point:
 * check them when Odoo is updated.
 */
export class DocumentFormRenderer extends FormRenderer {
    setup() {
        super.setup();
        this.mailComponents = { ...this.mailComponents, AttachmentView: DocumentPreview };
    }

    /**
     * @override
     * @returns {boolean} whether the document has a file that can be shown
     */
    hasFile() {
        const { record } = this.props;
        return Boolean(record.resId) && documentFileFromRecord(record).isViewable;
    }
}
