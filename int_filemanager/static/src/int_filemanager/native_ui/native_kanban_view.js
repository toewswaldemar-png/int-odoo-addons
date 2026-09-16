/** @odoo-module **/

// Zweite native Ansicht neben native_list_view.js, fuer denselben Dateimanager (siehe
// docs/int_filemanager_native_ui.md) - eine Karten-Galerie mit Thumbnail/Datei-Icon, gedacht
// fuer bildlastige Ordner (Scans/Fotos), nicht als Ersatz fuer die Liste. Bewusst KEIN
// gruppiertes Board: kein groupBy, keine Spalten, kein Drag&Drop (Nutzerentscheidung - ein
// Status-Spalten-Board mit Drag&Drop wuerde die bewusste Baustein-4-Entscheidung
// "Status-Badge ist read-only in der Liste, Aendern nur ueber das Formular" wieder aufmachen,
// was hier explizit nicht gewollt ist).
//
// Navigation, Mutationen, Breadcrumbs, Chatter-Panel und das Aktionsmenue kommen unveraendert
// aus filemanager_controller_mixin.js - inklusive openRecord() fuer die Ordner-Navigation
// (env.searchModel.setIntFilemanagerFolderPath(), siehe native_search_model.js), da
// KanbanController.openRecord() normalerweise this.props.selectRecord() (Formular oeffnen)
// aufruft, was fuer is_dir=true genauso falsch waere wie bei der Liste. Kein eigener Override
// noetig: das Mixin ueberschreibt openRecord() bereits vollstaendig (nicht additiv zu
// KanbanControllers eigenem), dieselbe Implementierung passt fuer beide View-Typen unveraendert.
import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { filemanagerControllerMixin } from "./filemanager_controller_mixin";
import { FolderTree } from "./folder_tree";
import { IntFilemanagerSearchModel } from "./native_search_model";

export class IntFilemanagerKanbanController extends filemanagerControllerMixin(KanbanController) {
    static template = "int_filemanager.KanbanView";
    static components = { ...KanbanController.components, Chatter, Dropdown, DropdownItem, FolderTree };

    // Eigene Scoping-Klasse (native_kanban_view.scss) statt der Listen-Klasse - hier geht es um
    // die Kartengroesse/das Cover-Layout, nicht um Zahlenspalten-Ausrichtung wie bei der Liste.
    get className() {
        return [super.className, "o_int_filemanager_kanban"].filter(Boolean).join(" ");
    }
}

registry.category("views").add("int_filemanager_kanban", {
    ...kanbanView,
    Controller: IntFilemanagerKanbanController,
    // Dieselbe Ordner-Pfad-Domain-Logik wie native_list_view.js - beide Ansichten teilen sich
    // dieselbe Navigation, siehe native_search_model.js fuer die Begruendung.
    SearchModel: IntFilemanagerSearchModel,
});
