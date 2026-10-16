import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { thumbnailUrl } from "../../document_file";
import { DEFAULT_TILE_SIZE, tileSizeOf } from "../../views/kanban/document_tile_size";

/**
 * The picture of a document on its kanban card: a small version of the image itself, the first
 * page of a PDF, else the core's symbol of the file type (as `DocumentNameField` does for the
 * list, only larger). The kanban sets the size of its cards in `env.documentTile`; the picture
 * of a large card is asked for in a larger version.
 */
export class DocumentThumbnailField extends Component {
    static template = "int_filemanager.DocumentThumbnailField";
    static props = { ...standardFieldProps };

    setup() {
        this.tile = useState(this.env.documentTile || { size: DEFAULT_TILE_SIZE });
    }

    get mimetype() {
        return this.props.record.data.mimetype;
    }

    /** The address of the small picture, only for an image or a PDF that has one. */
    get thumbnailUrl() {
        return thumbnailUrl(this.props.record, tileSizeOf(this.tile.size).pictureWidth);
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
        { name: "thumbnail_state", type: "selection" },
    ],
};

registry.category("fields").add("int_filemanager_document_thumbnail", documentThumbnailField);
