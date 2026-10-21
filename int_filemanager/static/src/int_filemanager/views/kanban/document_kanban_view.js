import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { DocumentSearchModel } from "../document_search_model";
import { DocumentSearchPanel } from "../search_panel/document_search_panel";
import { DocumentKanbanController } from "./document_kanban_controller";
import { DocumentKanbanRenderer } from "./document_kanban_renderer";

export const documentKanbanView = {
    ...kanbanView,
    SearchModel: DocumentSearchModel,
    SearchPanel: DocumentSearchPanel,
    Controller: DocumentKanbanController,
    Renderer: DocumentKanbanRenderer,
    buttonTemplate: "int_filemanager.DocumentKanbanView.Buttons",
};

registry.category("views").add("int_filemanager_document_kanban", documentKanbanView);
