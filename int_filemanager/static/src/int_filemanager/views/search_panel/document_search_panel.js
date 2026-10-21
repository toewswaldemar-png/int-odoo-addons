import { useEffect, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { SearchPanel } from "@web/search/search_panel/search_panel";
import { getFoldersSection } from "../list/document_new_folder";

const HOVER_DELAY = 700;

/**
 * The search panel with folders that take the documents dragged from the list or the cards. The
 * rows do the drag (see `useDocumentDragSource`): the panel marks its folders with
 * `data-drop-folder`, shows the one under the pointer and opens it when the pointer rests on it.
 */
export class DocumentSearchPanel extends SearchPanel {
    static subTemplates = {
        ...SearchPanel.subTemplates,
        category: "int_filemanager.SearchPanel.Category",
    };

    setup() {
        super.setup();
        this.drag = useState(this.env.searchModel.drag);
        useEffect(
            (folderId) => {
                if (folderId) {
                    const timer = browser.setTimeout(() => this.openFolder(folderId), HOVER_DELAY);
                    return () => browser.clearTimeout(timer);
                }
            },
            () => [this.drag.over]
        );
    }

    /** @param {number} folderId */
    openFolder(folderId) {
        const folders = getFoldersSection(this.env.searchModel);
        if (folders?.values.get(folderId)?.childrenIds.length) {
            this.state.expanded[folders.id][folderId] = true;
        }
    }
}
