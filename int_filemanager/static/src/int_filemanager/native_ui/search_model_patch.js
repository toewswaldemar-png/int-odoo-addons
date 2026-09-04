/** @odoo-module **/

// Two Odoo SearchPanel category defaults are wrong for a folder tree, both fixed here
// instead of via arch attributes (an earlier attempt used hierarchize="0" for the first
// one, but that also suppresses the server from sending parent_id per value at all -
// web/models/models.py, search_panel_select_range: "if hierarchize and parent_name in
// Comodel._fields: field_names.append(parent_name)" - which broke both the tree's visual
// nesting AND native_list_view.js's breadcrumb reconstruction, live observed. Overriding
// the domain here instead needs no arch attribute and keeps parent_id flowing normally):
//
// 1. A many2one category with a self-referencing parent field defaults to operator
//    "child_of" (_getCategoryDomain in search_model.js) - selecting a folder shows ALL
//    descendants recursively. Right for product categories, wrong for a folder browser,
//    which needs exactly one level per click (operator "=").
// 2. An unselected ("Alle") category value is treated as "no filter at all" (the clause
//    is skipped entirely when activeValueId is falsy) - correct for e.g. product
//    categories, wrong for a folder tree, where "nothing selected" must mean "root level"
//    (parent_id = False). Verified live: without this fix, clicking "Alle" loaded every
//    row in the table regardless of nesting depth instead of just the root folders.
//
// A third case, found live (2026-09-04): plain "=" also breaks combining folder
// navigation with a search bar term (e.g. a tag) - browsing one level above a matching
// file returns zero rows even though the file exists further down, because "=" only ever
// matches direct children. Fix: fall back to Odoo's own native "child_of" (indexed via
// parent_path, same mechanism product.category uses) whenever a search facet is active
// (this.query.length > 0 - populated by search bar terms/filters, independent of the
// category's own activeValueId), so a search recurses into subfolders instead of being
// silently scoped to the current level. At "Alle" (activeValueId falsy) while searching,
// no parent_id clause at all is pushed - not "= false" - so the search covers the whole
// tree instead of only literal root-level rows, matching Odoo's original unselected-
// category default. Plain navigation (no search facet) keeps "=" exactly as before.
//
// A fourth case, found live (2026-09-04): "child_of" on parent_id is self-inclusive when
// the field is the model's own _parent_name (verified by logging _getCategoryDomain's own
// result live) - it matches the selected folder ITSELF, not just its descendants. Browsing
// into a folder that is itself tagged with the searched tag showed that folder listed as a
// row of itself instead of its (empty, in that case) matching contents - breadcrumb
// navigated in correctly, the list just re-displayed what was already visible one level up,
// looking exactly like navigation silently failed. Fix: explicitly exclude the folder's own
// id alongside child_of, so navigating in always shows descendants only, never the folder
// currently being browsed.
//
// A fifth case, added when the "Verknuepfte Dateien"-smart-button (filemanager_linkable_mixin.py)
// was ported off the now-deleted legacy_ui client action tag (2026-09-04): that action opens this
// same native list permanently domain-restricted (res_reference = the linking record), not via a
// user-typed search facet - this.query stays empty there, so the third case above never fires and
// browsing would default to root only (parent_id = False), almost always empty since a linked
// file/folder is essentially never a filesystem root item itself. Reusing the exact context key
// legacy_ui used for its own equivalent "always recursive" mode (int_filemanager_recursive) keeps
// this scoped to actions that explicitly opt in, rather than recursing for every domain-restricted
// use of this view.
//
// Scoped to int_filemanager.file via this.resModel so every other SearchPanel category in
// the instance (product categories, stock reports, ...) keeps Odoo's default behaviour
// untouched - same scoping pattern int_web_tweaks already uses in list_column_reorder.js
// (there via this.props.list.resModel).
import { patch } from "@web/core/utils/patch";
import { SearchModel } from "@web/search/search_model";

patch(SearchModel.prototype, {
    _getCategoryDomain(excludedCategoryId) {
        if (this.resModel !== "int_filemanager.file") {
            return super._getCategoryDomain(excludedCategoryId);
        }
        const recursive = this.query.length > 0 || Boolean(this.globalContext.int_filemanager_recursive);
        const domain = [];
        for (const category of this.categories) {
            if (category.id === excludedCategoryId) {
                continue;
            }
            if (category.fieldName === "parent_id") {
                const value = category.activeValueId || false;
                if (recursive) {
                    if (value) {
                        domain.push(["parent_id", "child_of", value]);
                        domain.push(["id", "!=", value]);
                    }
                } else {
                    domain.push(["parent_id", "=", value]);
                }
                continue;
            }
            if (!category.activeValueId) {
                continue;
            }
            const field = this.searchViewFields[category.fieldName];
            const operator = field.type === "many2one" && category.parentField ? "child_of" : "=";
            domain.push([category.fieldName, operator, category.activeValueId]);
        }
        return domain;
    },
});
