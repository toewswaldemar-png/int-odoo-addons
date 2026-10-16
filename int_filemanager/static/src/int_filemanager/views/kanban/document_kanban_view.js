import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { DocumentKanbanController } from "./document_kanban_controller";
import { DocumentKanbanRenderer } from "./document_kanban_renderer";

export const documentKanbanView = {
    ...kanbanView,
    Controller: DocumentKanbanController,
    Renderer: DocumentKanbanRenderer,
    buttonTemplate: "int_filemanager.DocumentKanbanView.Buttons",
};

registry.category("views").add("int_filemanager_document_kanban", documentKanbanView);
