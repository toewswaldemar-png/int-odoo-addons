import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { imageUrl } from "@web/core/utils/urls";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { documentFileFromRecord, MODEL } from "./document_file";

const THUMBNAIL_SIZE = 256;

/**
 * The picture of a document on its kanban card: a small version of the image itself, else the
 * core's symbol of the file type (as `DocumentNameField` does for the list, only larger).
 */
export class DocumentThumbnailField extends Component {
    static template = "int_filemanager.DocumentThumbnailField";
    static props = { ...standardFieldProps };

    get mimetype() {
        return this.props.record.data.mimetype;
    }

    /** The address of the small picture, only for an image. `unique` lets the browser keep it
     * for good: the checksum changes with the content. */
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

export const documentThumbnailField = {
    component: DocumentThumbnailField,
    displayName: _t("Document picture"),
    supportedTypes: ["char"],
    fieldDependencies: [
        { name: "name", type: "char" },
        { name: "checksum", type: "char" },
        { name: "size", type: "float" },
    ],
};

registry.category("fields").add("int_filemanager_document_thumbnail", documentThumbnailField);
