import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { MODEL } from "@int_filemanager/int_filemanager/document_file";
import { hitLabel } from "./document_content_hits_field";

/** The pages of a file with the words of the search, a block at a time; a click opens the file there. */
export class DocumentContentHitsPopover extends Component {
    static template = "int_filemanager_ocr.DocumentContentHitsPopover";
    static props = {
        close: Function,
        file: Object,
        words: Array,
        total: Number,
        onSelect: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ hits: [], loading: false, exhausted: false });
        onWillStart(() => this.loadBlock());
    }

    get title() {
        return _t("%(name)s: %(count)s hits", {
            name: this.props.file.name,
            count: this.props.total,
        });
    }

    get canLoadMore() {
        return !this.state.exhausted && this.state.hits.length < this.props.total;
    }

    label(hit) {
        return hitLabel(this.props.file, hit);
    }

    async loadBlock() {
        this.state.loading = true;
        try {
            const { hits } = await this.orm.call(MODEL, "get_content_hits", [
                [this.props.file.id],
                this.props.words,
                this.state.hits.length,
            ]);
            this.state.hits.push(...hits);
            // A file read again meanwhile may have fewer hits than counted: no endless "Load more".
            this.state.exhausted = !hits.length;
        } finally {
            this.state.loading = false;
        }
    }

    select(hit) {
        this.props.close();
        this.props.onSelect(hit);
    }
}
