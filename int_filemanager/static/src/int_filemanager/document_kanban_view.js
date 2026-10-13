import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { DocumentKanbanController } from "./document_kanban_controller";

export const documentKanbanView = {
    ...kanbanView,
    Controller: DocumentKanbanController,
};

registry.category("views").add("int_filemanager_document_kanban", documentKanbanView);
