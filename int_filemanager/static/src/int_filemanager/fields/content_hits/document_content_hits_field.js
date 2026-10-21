import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { documentFileFromRecord } from "../../document_file";

/** @returns {String} what an excerpt is headed with: the page of a PDF, the block of a text */
export function hitLabel(file, hit) {
    if (file.isImage) {
        return "";
    }
    return file.isPdf
        ? _t("p. %(page)s", { page: hit.page })
        : _t("Block %(page)s", { page: hit.page });
}

/** The hit of the full text search in a file: page and excerpt. */
export class DocumentContentHitsField extends Component {
    static template = "int_filemanager.DocumentContentHitsField";
    static props = { ...standardFieldProps };

    get hits() {
        return this.props.record.data[this.props.name]?.hits || [];
    }

    label(hit) {
        return hitLabel(documentFileFromRecord(this.props.record), hit);
    }

    /**
     * The excerpt in three: the text before the first marked word, that word, and the rest. A
     * narrow column cuts the text around the word, never the word.
     */
    split(hit) {
        const index = hit.parts.findIndex(([, isMatch]) => isMatch);
        if (index < 0) {
            return { before: "", match: "", after: hit.parts };
        }
        return {
            before: hit.parts
                .slice(0, index)
                .map(([text]) => text)
                .join(""),
            match: hit.parts[index][0],
            after: hit.parts.slice(index + 1),
        };
    }
}

export const documentContentHitsField = {
    component: DocumentContentHitsField,
    displayName: _t("Hits in the text"),
    supportedTypes: ["json"],
    fieldDependencies: [
        { name: "mimetype", type: "char" },
        { name: "checksum", type: "char" },
        { name: "ocr_checksum", type: "char" },
        { name: "size", type: "float" },
    ],
};

registry.category("fields").add("int_filemanager_content_hits", documentContentHitsField);
