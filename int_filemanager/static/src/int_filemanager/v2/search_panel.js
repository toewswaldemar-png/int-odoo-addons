/** @odoo-module **/

// The search panel of the explorer: Odoo's own panel, with a folder tree that is loaded one
// level at a time. Registered next to the search model in the two views (list, kanban), so
// no other search panel changes. See search_model.js for the loading itself.
import { SearchPanel } from "@web/search/search_panel/search_panel";

export class IntFilemanagerV2SearchPanel extends SearchPanel {
    // The category template knows the folders that are dragged onto (see search_panel.xml).
    static subTemplates = {
        ...SearchPanel.subTemplates,
        category: "int_filemanager.v2.SearchPanel.Category",
    };

    /**
     * A folder with sub-folders that are not loaded yet loads them before it opens, so the
     * base method finds something to show.
     */
    async toggleCategory(category, value) {
        if (category.fieldName === "parent_id" && value.has_children) {
            await this.env.searchModel.loadFolderChildren(value.id);
        }
        return super.toggleCategory(category, value);
    }
}
