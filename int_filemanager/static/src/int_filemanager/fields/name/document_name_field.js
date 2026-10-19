import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { documentFileFromRecord, thumbnailUrl } from "../../document_file";

const THUMBNAIL_SIZE = 64;

/** The name of a document with a small picture before it (a char field: multi edit works). */
export class DocumentNameField extends CharField {
    static template = "int_filemanager.DocumentNameField";

    get mimetype() {
        return this.props.record.data.mimetype;
    }

    /** Whether a click on the picture shows the file (see `DocumentListRenderer`). */
    get isPreviewable() {
        return documentFileFromRecord(this.props.record).isViewable;
    }

    /** Only for an image or a PDF that has one: the route answers others with a placeholder. */
    get thumbnailUrl() {
        return thumbnailUrl(this.props.record, THUMBNAIL_SIZE);
    }
}

export const documentNameField = {
    ...charField,
    component: DocumentNameField,
    displayName: _t("Document name"),
    fieldDependencies: [
        { name: "mimetype", type: "char" },
        { name: "checksum", type: "char" },
        { name: "ocr_checksum", type: "char" },
        { name: "size", type: "float" },
        { name: "thumbnail_state", type: "selection" },
    ],
    // The list gives every column a minimum of 80px: too narrow for the name beside the picture.
    listViewWidth: [200],
};

registry.category("fields").add("int_filemanager_document_name", documentNameField);
