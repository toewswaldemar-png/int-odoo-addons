import { reactive } from "@odoo/owl";
import { SearchModel } from "@web/search/search_model";
import { DocumentDragState } from "./drag/document_drag_state";

/**
 * The core selects a folder of the search panel with ``child_of``, so a folder shows the
 * documents of all folders below it. Here a folder shows only its own documents. The documents
 * dragged to a folder of the panel are kept here (`drag`, reactive: the panel shows the folder
 * under the pointer), where the list and the panel meet.
 */
export class DocumentSearchModel extends SearchModel {
    setup() {
        super.setup(...arguments);
        this.drag = reactive(new DocumentDragState());
    }

    _getCategoryDomain(excludedCategoryId) {
        return super._getCategoryDomain(excludedCategoryId).map((condition) =>
            condition[0] === "folder_id" && condition[1] === "child_of"
                ? [condition[0], "=", condition[2]]
                : condition
        );
    }
}
