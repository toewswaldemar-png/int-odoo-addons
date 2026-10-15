import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { DocumentKanbanRecord } from "./document_kanban_record";

export class DocumentKanbanRenderer extends KanbanRenderer {
    static components = {
        ...KanbanRenderer.components,
        KanbanRecord: DocumentKanbanRecord,
    };
}
