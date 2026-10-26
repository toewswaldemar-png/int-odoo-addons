// The core's list and kanban with the module's renderers; the controller writes no tile size.
import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { listView } from "@web/views/list/list_view";
import { DocumentSearchModel } from "@int_filemanager/int_filemanager/views/document_search_model";
import { DocumentKanbanController } from "@int_filemanager/int_filemanager/views/kanban/document_kanban_controller";
import { DocumentKanbanRenderer } from "@int_filemanager/int_filemanager/views/kanban/document_kanban_renderer";
import { DocumentListRenderer } from "@int_filemanager/int_filemanager/views/list/document_list_renderer";

class GuestKanbanController extends DocumentKanbanController {
    async setTileSize(size) {
        this.tile.size = size;
    }
}

registry.category("views").add("int_filemanager_guest_list", {
    ...listView,
    SearchModel: DocumentSearchModel,
    Renderer: DocumentListRenderer,
});

registry.category("views").add("int_filemanager_guest_kanban", {
    ...kanbanView,
    SearchModel: DocumentSearchModel,
    Controller: GuestKanbanController,
    Renderer: DocumentKanbanRenderer,
    buttonTemplate: "int_filemanager.DocumentKanbanView.Buttons",
});
