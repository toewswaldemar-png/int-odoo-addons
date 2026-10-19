import { CANCEL_GLOBAL_CLICK, KanbanRecord } from "@web/views/kanban/kanban_record";
import { documentFilesFromRecords } from "../../document_file";
import { useDocumentFileViewer } from "../../file_viewer/document_file_viewer";

/**
 * A card of the kanban of documents: a click shows the file in the file viewer, as in the list;
 * a file the browser cannot show opens the form.
 */
export class DocumentKanbanRecord extends KanbanRecord {
    setup() {
        super.setup();
        this.fileViewer = useDocumentFileViewer();
    }

    /** @override */
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
