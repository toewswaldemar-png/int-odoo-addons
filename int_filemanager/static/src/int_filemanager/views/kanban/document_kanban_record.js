import { CANCEL_GLOBAL_CLICK, KanbanRecord } from "@web/views/kanban/kanban_record";
import { useRefListener } from "@web/core/utils/hooks";
import { documentFilesFromRecords } from "../../document_file";
import { useDocumentFileViewer } from "../../file_viewer/document_file_viewer";
import { opensWithDoubleClick, waitsForDoubleClick } from "../document_open_mode";

/**
 * A card of the kanban of documents: a click (or a double click, as the user chose, see
 * `useDocumentOpenMode`) shows the file in the file viewer, as in the list; a file the browser
 * cannot show opens the form.
 */
export class DocumentKanbanRecord extends KanbanRecord {
    setup() {
        super.setup();
        this.fileViewer = useDocumentFileViewer();
        useRefListener(this.rootRef, "dblclick", (ev) => this.onDoubleClick(ev));
    }

    /** @override */
    onGlobalClick(ev, newWindow) {
        if (this.isPlainClick(ev, newWindow)) {
            // A card that opens with a double click does nothing until the second click.
            if (waitsForDoubleClick(this.env, ev)) {
                // The card has the focus, which the core shows with a frame of its own.
                this.rootRef.el.focus();
                return;
            }
            if (this.openInViewer()) {
                return;
            }
        }
        return super.onGlobalClick(...arguments);
    }

    /** The double click on a card opens it as a click does when the kanban opens with one. */
    onDoubleClick(ev) {
        if (!opensWithDoubleClick(this.env) || !this.isPlainClick(ev, false)) {
            return;
        }
        // The browser has marked the word under the pointer by now.
        window.getSelection()?.removeAllRanges();
        if (!this.openInViewer()) {
            // The core opens the form as it does for a click; it waits for no second click here.
            super.onGlobalClick(ev, false);
        }
    }

    /** A click that no selection, no key and no link or menu of the card takes. */
    isPlainClick(ev, newWindow) {
        return (
            !newWindow &&
            !ev.altKey &&
            !ev.target.closest(CANCEL_GLOBAL_CLICK) &&
            !this.props.getSelection().length
        );
    }

    /** @returns {boolean} whether the file was shown in the viewer */
    openInViewer() {
        const { root } = this.props.record.model;
        const records = root.isGrouped
            ? root.groups.flatMap((group) => group.list.records)
            : root.records;
        const { file, files } = documentFilesFromRecords(records, this.props.record);
        if (!file.isViewable) {
            return false;
        }
        this.fileViewer.open(file, files);
        return true;
    }
}
