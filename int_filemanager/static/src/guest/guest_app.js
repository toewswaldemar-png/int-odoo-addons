// The root of the page of the guests: a switch between kanban and list, and the core's `View`
// component (control panel, search bar, search panel, the view itself).
import { Component, useState } from "@odoo/owl";
import { useOwnDebugContext } from "@web/core/debug/debug_context";
import { View } from "@web/views/view";

export class GuestApp extends Component {
    static template = "int_filemanager.GuestApp";
    static components = { View };
    static props = {};

    setup() {
        // The views ask for it in debug mode; the webclient provides it, so does this root.
        useOwnDebugContext();
        this.state = useState({ type: "kanban" });
        this.folderName = odoo.int_filemanager_folder_name;
        this.rights = odoo.int_filemanager_rights;
    }

    /** Whether there is a list to show: a share to upload only is a mailbox. */
    get canRead() {
        return this.rights.can_view || this.rights.can_download;
    }

    get viewProps() {
        return {
            type: this.state.type,
            resModel: "int.filemanager.document",
            viewId: false,
            searchViewId: false,
            context: {},
            loadIrFilters: false,
            loadActionMenus: false,
            // No favorites: they are records of ir.filters, written by the user.
            searchMenuTypes: ["filter", "groupBy"],
            display: { controlPanel: {} },
        };
    }

    setType(type) {
        this.state.type = type;
    }
}
