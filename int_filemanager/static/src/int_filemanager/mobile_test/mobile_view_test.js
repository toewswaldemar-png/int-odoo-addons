/** @odoo-module **/

// Spike (2026-09-15): prueft, ob display={controlPanel: false} an einer eingebetteten
// View-Komponente den nativen ControlPanel wirklich abschaltet, waehrend Datenladen/Paging/
// Interaktion der eingebetteten View unveraendert funktionieren - Kernfrage aus dem Chat
// "Zone ueber der Liste frei gestalten". Rein additiver Spike ueber einen eigenen
// Test-Menuepunkt/eigene Action - ruehrt action_filemanager_file_list_native nicht an.
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";

class IntFilemanagerMobileTest extends Component {
    static template = "int_filemanager.MobileViewTest";
    static components = { View };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        // View() ohne explizite searchViewId fragt beim Backend gar keine <search>-Arch an
        // (siehe view.js: loadSearchView bleibt false, wenn searchViewId undefined ist) -
        // ohne die geht der parent_id-Kategorieabschnitt verloren, den
        // filemanagerControllerMixin fuer Ordnernavigation/Breadcrumbs braucht (genau das im
        // ersten Testlauf beobachtete "zeigt alles flach"-Verhalten). Deshalb hier die echte
        // DB-Id der bestehenden int_filemanager_file_search-View auflösen, statt sie als
        // Zahl zu raten.
        this.state = useState({ searchViewId: null, viewId: null });
        onWillStart(async () => {
            const [, searchViewId] = await this.orm.call(
                "ir.model.data",
                "check_object_reference",
                ["int_filemanager", "int_filemanager_file_search"]
            );
            const [, viewId] = await this.orm.call(
                "ir.model.data",
                "check_object_reference",
                ["int_filemanager", "view_filemanager_file_list_native"]
            );
            this.state.searchViewId = searchViewId;
            this.state.viewId = viewId;
        });
    }
}

registry.category("actions").add("int_filemanager_mobile_test", IntFilemanagerMobileTest);
