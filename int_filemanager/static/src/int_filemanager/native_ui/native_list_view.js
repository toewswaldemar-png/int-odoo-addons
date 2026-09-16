/** @odoo-module **/

// A real Odoo list view, bound directly to int_filemanager.file, as the file browser -
// started as an experiment on this branch (see docs/int_filemanager_native_ui.md), now the
// only UI: legacy_ui (the hand-rolled OWL component predating this) was deleted 2026-09-04
// once this reached feature parity with it. Only override needed for navigation: clicking a
// folder row navigates via env.searchModel.setIntFilemanagerFolderPath() (own FolderTree
// component, see folder_tree.js, replacing Odoo's native SearchPanel category field since
// 2026-09-16 - see native_search_model.js for why) instead of opening a (non-existent) form
// view - see ListRenderer's onCellClicked -> this.props.openRecord(record) in
// list_renderer.js, which comes from ListController.openRecord (list_controller.js). The
// resulting reload itself is entirely native (searchModel -> WithSearch -> props.domain
// -> useModel's own onWillUpdateProps, see filemanager_controller_mixin.js's setup() for why
// that MUST stay the only writer). Sort, optional columns incl. Properties splitting,
// pager are untouched native ListView behaviour; breadcrumbs are rebuilt from
// the active folder path string (see updateBreadcrumbs()).
//
// Everything shared with the native Kanban view (native_kanban_view.js) - navigation,
// mutations, breadcrumbs, chatter panel, action menu - lives in
// filemanager_controller_mixin.js. This class only adds the pieces that genuinely differ
// per view type: which native template/component set is extended, and the list-only
// left-alignment scoping class.
import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
// Dieselbe Komponente, die Odoo intern in jedem Formular fuer den Chatter nutzt
// (form_renderer.js) - kein eigener Nachbau, nur direkt eingebunden statt ueber
// ein Formular-Arch (das <chatter/>-Tag funktioniert nur innerhalb einer echten
// Form-View, siehe docs/int_filemanager_native_ui.md Punkt 23).
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { filemanagerControllerMixin } from "./filemanager_controller_mixin";
import { FolderTree } from "./folder_tree";
import { IntFilemanagerListRenderer } from "./native_list_renderer";
import { IntFilemanagerSearchModel } from "./native_search_model";

export class IntFilemanagerListController extends filemanagerControllerMixin(ListController) {
    static template = "int_filemanager.ListView";
    // Muss die geerbten Eintraege (Layout, SearchBar, ActionMenus, ...) mitnehmen -
    // eine Neuzuweisung ohne Spread wuerde sie durch die statische Feld-Ueberschreibung
    // verdecken und jedes t-component/<Tag>, das das geerbte web.ListView-Template nutzt,
    // bräche.
    static components = { ...ListController.components, Chatter, Dropdown, DropdownItem, SearchBar, FolderTree };

    // Scoping-Klasse fuer native_list_view.scss - rechtsbuendige Zahlenspalten (o_list_number,
    // list_renderer.scss) sind fuer "Groesse" hier bewusst unerwuenscht (User-Wunsch: wie alle
    // anderen Spalten linksbuendig). Ueberschrieben nur innerhalb dieser Klasse, nicht global -
    // jede andere native Odoo-Liste im System behaelt die rechtsbuendige Zahlendarstellung.
    get className() {
        const classes = [super.className, "o_int_filemanager_list"];
        // Odoos eigener isSmall-Schwellwert (768px, ui-Service) statt eines separaten Kontext-
        // Flags - siehe native_list_view.xml/native_list_view.scss fuer Header-Markup bzw.
        // Ordnerbaum-Sheet-Positionierung, beide an dieselbe Klasse gekoppelt. Damit greift die
        // mobile Darstellung automatisch in der produktiven Desktop-Action
        // (action_filemanager_file_list_native), sobald der Viewport schmal genug ist - kein
        // eigener Menuepunkt/eigene Action mehr noetig.
        if (this.env.isSmall) {
            classes.push("o_int_filemanager_mobile");
            if (this.mobileTreeState.open) {
                classes.push("o_int_filemanager_mobile_tree_open");
            }
        }
        return classes.filter(Boolean).join(" ");
    }
}

registry.category("views").add("int_filemanager_list", {
    ...listView,
    Controller: IntFilemanagerListController,
    // Datei-Explorer-Klickverhalten (Einzelklick=auswaehlen, Doppelklick=oeffnen,
    // Rubberband-Auswahl) - siehe native_list_renderer.js. Genauso ein austauschbarer
    // Registry-Schluessel wie Controller oben (list_view.js: "Renderer: ListRenderer"),
    // deshalb echte Unterklasse statt patch(ListRenderer.prototype, ...) - vormals ein
    // separater list_renderer_patch.js mit manuellen resModel-Laufzeitchecks, 2026-09-11
    // hierher umgezogen fuer dieselbe Kapselung wie beim Controller.
    Renderer: IntFilemanagerListRenderer,
    // Ordner-Pfad-Domain-Logik - siehe native_search_model.js fuer die ausfuehrliche
    // Begruendung. Derselbe Registry-Umzug wie Renderer oben, vormals search_model_patch.js
    // (patch(SearchModel.prototype, ...)). Braucht denselben Eintrag auch in
    // native_kanban_view.js - beide Ansichten teilen sich dieselbe Ordner-Navigation.
    SearchModel: IntFilemanagerSearchModel,
});
