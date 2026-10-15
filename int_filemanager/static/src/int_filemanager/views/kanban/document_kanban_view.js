import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { DocumentKanbanRenderer } from "./document_kanban_renderer";

export const documentKanbanView = {
    ...kanbanView,
    Renderer: DocumentKanbanRenderer,
};

registry.category("views").add("int_filemanager_document_kanban", documentKanbanView);
