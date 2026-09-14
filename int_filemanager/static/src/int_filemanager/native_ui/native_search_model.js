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
// same native list permanently domain-restricted (partner_id = the linking contact), not via a
// user-typed search facet - this.query stays empty there, so the third case above never fires and
// browsing would default to root only (parent_id = False), almost always empty since a linked
// file/folder is essentially never a filesystem root item itself. Reusing the exact context key
// legacy_ui used for its own equivalent "always recursive" mode (int_filemanager_recursive) keeps
// this scoped to actions that explicitly opt in, rather than recursing for every domain-restricted
// use of this view.
//
// Echte Unterklasse statt patch(SearchModel.prototype, ...) - view.js reicht "SearchModel" aus dem
// View-Deskriptor genauso durch wie "Controller"/"Renderer" (descr.SearchModel), und with_search.js
// nutzt es als expliziten Fallback-Slot ("this.props.SearchModel || SearchModel") - live gegen
// Odoos eigenen Quellcode verifiziert, derselbe austauschbare Registry-Schluessel wie beim
// Renderer-Umzug (siehe native_list_renderer.js). Registriert in BEIDEN Views
// (native_list_view.js UND native_kanban_view.js, siehe SearchModel: IntFilemanagerSearchModel
// dort) - anders als beim Renderer (nur die Liste hat eine eigene Klick-Semantik) braucht die
// Ordner-Navigation dieselbe Domain-Logik in beiden Ansichten. Kapselung kommt damit aus der
// Registrierung, kein resModel-Laufzeit-Check mehr noetig.
import { SearchModel } from "@web/search/search_model";

// Facet-Namen (aus <filter name="...">), die NICHT als "der Nutzer sucht gerade" zaehlen sollen
// fuer die recursive-Erkennung unten - live gefunden 2026-09-14: filter_hide_lock_files
// (filemanager_file_search.xml) ist per search_default_ dauerhaft aktiv, zaehlte also
// permanent als aktives Facet und schaltete die Ordnernavigation faelschlich global-rekursiv
// (Root zeigte Ordner aus dem GESAMTEN Baum statt nur echte Wurzelordner). Node.name kommt
// 1:1 aus dem <filter>-XML-Attribut durch (search_arch_parser.js: preSearchItem.name =
// node.getAttribute("name"), am Odoo-Quellcode verifiziert).
const NON_SEARCH_FACET_NAMES = new Set(["filter_hide_lock_files"]);

export class IntFilemanagerSearchModel extends SearchModel {
    _getCategoryDomain(excludedCategoryId) {
        const hasRealSearchFacet = this.query.some(
            (queryElem) => !NON_SEARCH_FACET_NAMES.has(this.searchItems[queryElem.searchItemId]?.name)
        );
        const recursive = hasRealSearchFacet || Boolean(this.globalContext.int_filemanager_recursive);
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
    }
}
