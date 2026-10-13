import { CANCEL_GLOBAL_CLICK, KanbanRecord } from "@web/views/kanban/kanban_record";
import { documentFilesFromRecords } from "./document_file";
import { useDocumentFileViewer } from "./document_file_viewer";

/**
 * A card of the kanban of documents: a click on it shows the file in the file viewer, as a click
 * on a row of the list does (the arrow keys go through the cards of the page); a file a browser
 * cannot show opens the form. The core's own kanban of documents (`product.document`) takes the
 * click in its record as well. `openRecord` of the controller stays the core's: the entry
 * "Properties" of the menu of the card (`type="open"`) opens the form with the pager over the
 * cards of the page.
 */
export class DocumentKanbanRecord extends KanbanRecord {
    setup() {
        super.setup();
        this.fileViewer = useDocumentFileViewer();
    }

    /**
     * @override
     * What the core does with a click stays: ticking cards, a link or the menu of the card,
     * a click for a new window (Ctrl, middle button).
     */
    onGlobalClick(ev, newWindow) {
        const isPlainClick =
            !newWindow &&
            !ev.altKey &&
            !ev.target.closest(CANCEL_GLOBAL_CLICK) &&
            !this.props.getSelection().length;
        if (isPlainClick) {
            const { root } = this.props.record.model;
            const records = root.isGrouped
                ? root.groups.flatMap((group) => group.list.records)
                : root.records;
            const { file, files } = documentFilesFromRecords(records, this.props.record);
            if (file.isViewable) {
                this.fileViewer.open(file, files);
                return;
            }
        }
        return super.onGlobalClick(...arguments);
    }
}
