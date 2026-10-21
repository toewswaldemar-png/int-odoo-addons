import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { useDocumentDragSource } from "../drag/document_drag_source_hook";
import { DocumentKanbanRecord } from "./document_kanban_record";

/** The kanban of documents; its cards can be dragged to a folder of the search panel. */
export class DocumentKanbanRenderer extends KanbanRenderer {
    static components = {
        ...KanbanRenderer.components,
        KanbanRecord: DocumentKanbanRecord,
    };

    setup() {
        super.setup();
        useDocumentDragSource({
            ref: this.rootRef,
            elements: ".o_kanban_record",
            getList: () => this.props.list,
            // In groups the core drags the cards from one group to the next (also by pointer).
            canDrag: (record) => !record.model.root.isGrouped,
        });
    }
}
