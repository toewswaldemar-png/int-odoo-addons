/** @odoo-module **/

// The cards view of the explorer (a gallery for image-heavy folders), next to the list. No
// grouping, no columns. Navigation, mutations, uploads and the chatter come from the shared
// controller mixin - including openRecord: KanbanController.openRecord would open a form,
// which is as wrong for a folder as it is in the list.
import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { filemanagerV2Mixin } from "./controller_mixin.js";
import { IntFilemanagerV2SearchModel } from "./search_model.js";
import { IntFilemanagerV2SearchPanel } from "./search_panel.js";
import { IntFilemanagerV2UploadPanel } from "./upload_panel.js";

export class IntFilemanagerV2KanbanController extends filemanagerV2Mixin(KanbanController) {
    static template = "int_filemanager.v2.KanbanView";
    static components = {
        ...KanbanController.components,
        Chatter,
        Dropdown,
        DropdownItem,
        UploadPanel: IntFilemanagerV2UploadPanel,
    };

    get className() {
        const classes = [super.className, "o_int_filemanager_kanban"];
        if (this.chatterState.open) {
            classes.push("o_int_filemanager_chatter_open");
        }
        return classes.filter(Boolean).join(" ");
    }
}

registry.category("views").add("int_filemanager_v2_kanban", {
    ...kanbanView,
    Controller: IntFilemanagerV2KanbanController,
    SearchModel: IntFilemanagerV2SearchModel,
    SearchPanel: IntFilemanagerV2SearchPanel,
});
