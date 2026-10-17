// The views of the page of the guests: the core's list and kanban with the components of the
// module (renderers, card, fields). Only the controllers differ: no upload, no dropzone, and the
// size of the cards is not written to the server.
import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { listView } from "@web/views/list/list_view";
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
    Renderer: DocumentListRenderer,
});

registry.category("views").add("int_filemanager_guest_kanban", {
    ...kanbanView,
    Controller: GuestKanbanController,
    Renderer: DocumentKanbanRenderer,
    buttonTemplate: "int_filemanager.DocumentKanbanView.Buttons",
});
