import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { documentFileFromRecord } from "./document_file";

/**
 * Where the words of the full text search are in a file: up to three hits, each with the page
 * and an excerpt in which the words are bold. It only shows; a click on a hit is taken by the
 * list (`DocumentListRenderer`), which opens the file in the file viewer on that page.
 */
export class DocumentContentHitsField extends Component {
    static template = "int_filemanager.DocumentContentHitsField";
    static props = { ...standardFieldProps };

    get hits() {
        return this.props.record.data[this.props.name]?.hits || [];
    }

    /** @returns {Number} how many pages with a hit are left out */
    get more() {
        return this.props.record.data[this.props.name]?.more || 0;
    }

    /**
     * A PDF has pages; the text of any other file lies in blocks that no viewer shows as such.
     * @param {{page: number}} hit
     * @returns {string}
     */
    label(hit) {
        const { isPdf } = documentFileFromRecord(this.props.record);
        return isPdf
            ? _t("p. %(page)s", { page: hit.page })
            : _t("Block %(page)s", { page: hit.page });
    }

    get moreLabel() {
        return _t("+ %(count)s more", { count: this.more });
    }
}

export const documentContentHitsField = {
    component: DocumentContentHitsField,
    displayName: _t("Hits in the text"),
    supportedTypes: ["json"],
    fieldDependencies: [
        { name: "mimetype", type: "char" },
        { name: "checksum", type: "char" },
        { name: "size", type: "float" },
    ],
};

registry.category("fields").add("int_filemanager_content_hits", documentContentHitsField);
