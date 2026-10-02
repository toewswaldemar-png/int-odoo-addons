/** @odoo-module **/

// The file explorer as a real Odoo list view on int_filemanager.node. Everything the list
// and the kanban share is in controller_mixin.js; this class only says which native
// controller it extends and which template it uses.
import {registry} from "@web/core/registry";
import {Dropdown} from "@web/core/dropdown/dropdown";
import {DropdownItem} from "@web/core/dropdown/dropdown_item";
import {ResizablePanel} from "@web/core/resizable_panel/resizable_panel";
import {SearchBar} from "@web/search/search_bar/search_bar";
import {listView} from "@web/views/list/list_view";
import {ListController} from "@web/views/list/list_controller";
// The same component Odoo uses for the chatter of every form; only usable inside a form
// arch as a <chatter/> tag, so it is mounted here directly.
import {Chatter} from "@mail/chatter/web_portal/chatter";
import {filemanagerV2Mixin} from "./controller_mixin.js";
import {IntFilemanagerV2FolderTree} from "./folder_tree.js";
import {IntFilemanagerV2ListRenderer} from "./list_renderer.js";
import {IntFilemanagerV2SearchModel} from "./search_model.js";
import {IntFilemanagerV2UploadPanel} from "./upload_panel.js";

export class IntFilemanagerV2ListController extends filemanagerV2Mixin(ListController) {
    static template = "int_filemanager.v2.ListView";
    // The inherited components must be carried along: a re-assignment without the spread
    // would hide them and every tag of the inherited template would break.
    static components = {
        ...ListController.components,
        Chatter,
        Dropdown,
        DropdownItem,
        ResizablePanel,
        SearchBar,
        FolderTree: IntFilemanagerV2FolderTree,
        UploadPanel: IntFilemanagerV2UploadPanel,
    };

    get className() {
        const classes = [super.className, "o_int_filemanager_list"];
        // Odoo's own small-screen threshold (768px, ui service): the mobile layout switches
        // on by itself in the desktop action, no separate menu entry.
        if (this.env.isSmall) {
            classes.push("o_int_filemanager_mobile");
            if (this.mobileTreeState.open) {
                classes.push("o_int_filemanager_mobile_tree_open");
            }
        }
        // Pushes the list aside for the chatter panel instead of lying under it.
        if (this.chatterState.open) {
            classes.push("o_int_filemanager_chatter_open");
        }
        return classes.filter(Boolean).join(" ");
    }
}

registry.category("views").add("int_filemanager_v2_list", {
    ...listView,
    Controller: IntFilemanagerV2ListController,
    Renderer: IntFilemanagerV2ListRenderer,
    SearchModel: IntFilemanagerV2SearchModel,
});
