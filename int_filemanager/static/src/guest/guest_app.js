// The root of the guest page: a kanban/list switch and the core's `View` component.
import { Component, useState } from "@odoo/owl";
import { useOwnDebugContext } from "@web/core/debug/debug_context";
import { View } from "@web/views/view";
import { GuestUploads } from "./guest_uploads";

export class GuestApp extends Component {
    static template = "int_filemanager.GuestApp";
    static components = { View, GuestUploads };
    static props = {};

    setup() {
        // The views ask for it in debug mode; the webclient normally provides it.
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
