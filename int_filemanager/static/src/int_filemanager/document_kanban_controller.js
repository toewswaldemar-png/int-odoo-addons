import { KanbanController } from "@web/views/kanban/kanban_controller";
import { documentFilesFromRecords } from "./document_file";
import { useDocumentFileViewer } from "./document_file_viewer";

/**
 * The kanban of documents: a click on a card shows the file in the file viewer, as a click on
 * a row of the list does (the arrow keys go through the cards of the page); a file a browser
 * cannot show opens the form. The form is also in the menu of each card.
 */
export class DocumentKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.fileViewer = useDocumentFileViewer();
    }

    /**
     * @override
     * A click for a new window (Ctrl, middle button) keeps the core's behavior.
     */
    async openRecord(record, { newWindow } = {}) {
        if (!newWindow) {
            const { root } = this.model;
            const records = root.isGrouped
                ? root.groups.flatMap((group) => group.list.records)
                : root.records;
            const { file, files } = documentFilesFromRecords(records, record);
            if (file.isViewable) {
                this.fileViewer.open(file, files);
                return;
            }
        }
        return super.openRecord(...arguments);
    }
}
