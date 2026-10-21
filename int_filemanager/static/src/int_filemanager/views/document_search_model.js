import { SearchModel } from "@web/search/search_model";

/**
 * The core selects a folder of the search panel with ``child_of``, so a folder shows the
 * documents of all folders below it. Here a folder shows only its own documents.
 */
export class DocumentSearchModel extends SearchModel {
    _getCategoryDomain(excludedCategoryId) {
        return super._getCategoryDomain(excludedCategoryId).map((condition) =>
            condition[0] === "folder_id" && condition[1] === "child_of"
                ? [condition[0], "=", condition[2]]
                : condition
        );
    }
}
