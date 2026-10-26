import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { documentFileFromRecord, documentFilesFromRecords } from "@int_filemanager/int_filemanager/document_file";
import { useDocumentFileViewer } from "@int_filemanager/int_filemanager/file_viewer/document_file_viewer";
import { DocumentContentHitsPopover } from "./document_content_hits_popover";

/** The number of pages of a file with the words of the search: a badge, a click lists them. */
export class DocumentContentHitCountField extends Component {
    static template = "int_filemanager_ocr.DocumentContentHitCountField";
    static props = { ...standardFieldProps };

    setup() {
        this.popover = usePopover(DocumentContentHitsPopover, {
            popoverClass: "o_int_filemanager_hits_popover",
        });
        this.fileViewer = useDocumentFileViewer();
    }

    get count() {
        return this.props.record.data[this.props.name];
    }

    get tooltip() {
        return _t("Show the hits");
    }

    openPopover(ev) {
        const { record } = this.props;
        this.popover.open(ev.currentTarget, {
            file: documentFileFromRecord(record),
            words: record.data.content_hits?.words || [],
            total: this.count,
            onSelect: (hit) => this.openHit(hit),
        });
    }

    /** The file opens on the page of the hit; the arrow keys go through the files of the list. */
    openHit(hit) {
        const { record } = this.props;
        const { file, files } = documentFilesFromRecords(
            record.model.root.records || [],
            record,
            hit
        );
        this.fileViewer.open(file, files);
    }
}

export const documentContentHitCountField = {
    component: DocumentContentHitCountField,
    displayName: _t("Hit count"),
    supportedTypes: ["integer"],
    fieldDependencies: [
        { name: "content_hits", type: "json" },
        { name: "mimetype", type: "char" },
        { name: "checksum", type: "char" },
        { name: "ocr_checksum", type: "char" },
        { name: "size", type: "float" },
    ],
};

registry.category("fields").add("int_filemanager_content_hit_count", documentContentHitCountField);
