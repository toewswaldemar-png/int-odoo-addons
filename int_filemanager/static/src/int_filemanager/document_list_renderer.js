import { useService } from "@web/core/utils/hooks";
import { FileUploadProgressContainer } from "@web/core/file_upload/file_upload_progress_container";
import { FileUploadProgressDataRow } from "@web/core/file_upload/file_upload_progress_record";
import { ListRenderer } from "@web/views/list/list_renderer";
import { documentFilesFromRecords } from "./document_file";
import { useDocumentFileViewer } from "./document_file_viewer";

/**
 * The list with the progress of the running uploads above it. A click on the picture of a row
 * (the thumbnail or the symbol of the file type) shows the file in the file viewer (the arrow
 * keys go through the files of the page); a click on the rest of the row opens the form, as in
 * every list of the core (with the pager over the rows of the page), also for a file that a
 * browser cannot show.
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
    }

    /**
     * @override
     * Only a click on the picture is taken. Rows that are ticked keep the core's behavior (a
     * click ticks or unticks, the multi edit works); so does a click for a new window (Ctrl,
     * middle button).
     */
    async onCellClicked(record, column, ev, newWindow) {
        const isPicture = Boolean(ev.target.closest?.(".o_int_filemanager_thumbnail"));
        if (
            isPicture &&
            !newWindow &&
            !ev.target.special_click &&
            !this.props.list.selection.length
        ) {
            const { file, files } = documentFilesFromRecords(this.props.list.records, record);
            if (file.isViewable) {
                this.fileViewer.open(file, files);
                return;
            }
        }
        return super.onCellClicked(...arguments);
    }
}
