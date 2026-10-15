import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { documentFileFromRecord, thumbnailUrl } from "../../document_file";

const THUMBNAIL_SIZE = 64;

/**
 * The name of a document with a small picture before it: the picture itself for an image, the
 * first page of a PDF, else the core's symbol of the file type. A char field, so the name stays
 * editable (multi edit).
 */
export class DocumentNameField extends CharField {
    static template = "int_filemanager.DocumentNameField";

    get mimetype() {
        return this.props.record.data.mimetype;
    }

    /** Whether a click on the picture shows the file (see `DocumentListRenderer`). */
    get isPreviewable() {
        return documentFileFromRecord(this.props.record).isViewable;
    }

    /** The address of the small picture, only for an image or a PDF that has one (the route
     * answers others with a placeholder, or with the whole file). */
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
    // The list view gives every column the same minimum (80px), which leaves a few letters of the
    // name beside the picture on a narrow screen: the name keeps room for its text (no maximum).
    listViewWidth: [200],
};

registry.category("fields").add("int_filemanager_document_name", documentNameField);
