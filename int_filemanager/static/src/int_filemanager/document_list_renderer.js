import { useService } from "@web/core/utils/hooks";
import { FileUploadProgressContainer } from "@web/core/file_upload/file_upload_progress_container";
import { FileUploadProgressDataRow } from "@web/core/file_upload/file_upload_progress_record";
import { ListRenderer } from "@web/views/list/list_renderer";
import { documentFilesFromRecords } from "./document_file";
import { useDocumentFileViewer } from "./document_file_viewer";

/**
 * The list with the progress of the running uploads above it. A click on a row shows the
 * file in the file viewer (the arrow keys go through the files of the page); what a
 * browser cannot show opens the form, where the download is.
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
     * Rows that are ticked keep the core's behavior (a click ticks or unticks, the multi edit
     * works); so does a click for a new window (Ctrl, middle button).
     */
    async onCellClicked(record, column, ev, newWindow) {
        if (!newWindow && !ev.target.special_click && !this.props.list.selection.length) {
            const { file, files } = documentFilesFromRecords(this.props.list.records, record);
            if (file.isViewable) {
                this.fileViewer.open(file, files);
                return;
            }
        }
        return super.onCellClicked(...arguments);
    }
}
