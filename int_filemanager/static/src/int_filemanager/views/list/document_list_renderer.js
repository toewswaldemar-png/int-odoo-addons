import { useRefListener, useService } from "@web/core/utils/hooks";
import { FileUploadProgressContainer } from "@web/core/file_upload/file_upload_progress_container";
import { FileUploadProgressDataRow } from "@web/core/file_upload/file_upload_progress_record";
import { ListRenderer } from "@web/views/list/list_renderer";
import { documentFilesFromRecords } from "../../document_file";
import { useDocumentFileViewer } from "../../file_viewer/document_file_viewer";
import { useDocumentDragSource } from "../drag/document_drag_source_hook";
import { opensWithDoubleClick, waitsForDoubleClick } from "../document_open_mode";

// What keeps its own click: a double click on it does not open the row.
const OWN_CLICK = "a, button, input, textarea, select, label, .o_list_record_selector";

/**
 * The list with the progress of the running uploads above it; its rows can be dragged to a folder.
 * A row opens with one click or two, as the user chose (`useDocumentOpenMode`).
 */
export class DocumentListRenderer extends ListRenderer {
    static template = "int_filemanager.DocumentListRenderer";
    static components = {
        ...ListRenderer.components,
        FileUploadProgressContainer,
        FileUploadProgressDataRow,
    };

    setup() {
        super.setup();
        this.fileUploadService = useService("file_upload");
        this.fileViewer = useDocumentFileViewer();
        useDocumentDragSource({
            ref: this.rootRef,
            elements: "tr.o_data_row",
            getList: () => this.props.list,
        });
        // The row is a template of the core; one listener on the list serves all of them.
        useRefListener(this.rootRef, "dblclick", (ev) => this.onRowDoubleClicked(ev));
    }

    /**
     * @override Ticked rows and clicks for a new window keep the core's behavior. The picture and
     * the hits of a row show the file in the viewer with one click, whatever the open mode is;
     * a list that opens with a double click leaves the single click on the rest of an unticked row
     * to the second one (the row only gets the focus).
     */
    async onCellClicked(record, column, ev, newWindow) {
        const { list } = this.props;
        if (!newWindow && !ev.target.special_click && !list.selection.length) {
            if (this.openInViewer(record, ev)) {
                return;
            }
            if (waitsForDoubleClick(this.env, ev)) {
                // The mouse ends the keyboard navigation, as the core does when a click leaves the
                // edited row (`onGlobalClick`): the cell of the focus is no darker than the row.
                for (const tbody of this.tableRef.el.getElementsByTagName("tbody")) {
                    tbody.classList.remove("o_keyboard_navigation");
                }
                // The cell has the focus, as in a list of the core that opens nothing: the core
                // marks the row of the focus, and the arrows and Enter go from there.
                ev.target.closest("td")?.focus();
                return;
            }
        }
        return super.onCellClicked(...arguments);
    }

    /** The double click on a row opens it as a click does when the list opens with one. */
    onRowDoubleClicked(ev) {
        const { list } = this.props;
        const row = ev.target.closest("tr.o_data_row");
        if (
            !row ||
            !opensWithDoubleClick(this.env) ||
            list.selection.length ||
            ev.target.closest(OWN_CLICK)
        ) {
            return;
        }
        const record = list.records.find((each) => each.id === row.dataset.id);
        if (!record) {
            return;
        }
        // The browser has marked the word under the pointer by now.
        window.getSelection()?.removeAllRanges();
        // The first click of the picture or of a hit has shown the file already.
        if (this.viewableFile(record, ev)) {
            return;
        }
        if (!this.props.archInfo.noOpen) {
            this.props.openRecord(record);
        }
    }

    /** @returns {Object|undefined} the file of the row, if the click is on the picture or a hit */
    viewableFile(record, ev) {
        const hit = ev.target.closest?.(".o_int_filemanager_hit");
        const isPicture = Boolean(ev.target.closest?.(".o_int_filemanager_thumbnail"));
        if (!isPicture && !hit) {
            return;
        }
        const { file, files } = documentFilesFromRecords(this.props.list.records, record);
        return file.isViewable ? { file, files } : undefined;
    }

    /**
     * The picture and the hits of a row show the file in the viewer; the rest of the row opens
     * the form.
     * @returns {boolean} whether the viewer was opened
     */
    openInViewer(record, ev) {
        const viewable = this.viewableFile(record, ev);
        if (viewable) {
            this.fileViewer.open(viewable.file, viewable.files);
        }
        return Boolean(viewable);
    }
}
