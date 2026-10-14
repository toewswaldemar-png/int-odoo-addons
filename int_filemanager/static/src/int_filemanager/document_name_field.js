import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { imageUrl } from "@web/core/utils/urls";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { documentFileFromRecord, MODEL } from "./document_file";

const THUMBNAIL_SIZE = 64;

/**
 * The name of a document with a small picture before it: the picture itself for an image, else
 * the core's symbol of the file type. A char field, so the name stays editable (multi edit).
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

    /** The address of the small picture, only for an image (the route answers others with a
     * placeholder, or with the whole file). `unique` lets the browser keep it for good: the
     * checksum changes with the content. */
    get thumbnailUrl() {
        const file = documentFileFromRecord(this.props.record);
        if (!file.isImage || !this.props.record.resId) {
            return false;
        }
        return imageUrl(MODEL, file.id, "content", {
            width: THUMBNAIL_SIZE,
            height: THUMBNAIL_SIZE,
            unique: file.checksum,
        });
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
    ],
};

registry.category("fields").add("int_filemanager_document_name", documentNameField);
