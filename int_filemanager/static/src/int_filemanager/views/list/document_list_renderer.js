import { useService } from "@web/core/utils/hooks";
import { FileUploadProgressContainer } from "@web/core/file_upload/file_upload_progress_container";
import { FileUploadProgressDataRow } from "@web/core/file_upload/file_upload_progress_record";
import { ListRenderer } from "@web/views/list/list_renderer";
import { documentFilesFromRecords } from "../../document_file";
import { useDocumentFileViewer } from "../../file_viewer/document_file_viewer";
import { useDocumentDragSource } from "../drag/document_drag_source_hook";

/** The list with the progress of the running uploads above it; its rows can be dragged to a folder. */
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
    }

    /** @override Ticked rows and clicks for a new window keep the core's behavior. */
    async onCellClicked(record, column, ev, newWindow) {
        const hit = ev.target.closest?.(".o_int_filemanager_hit");
        const isPicture = Boolean(ev.target.closest?.(".o_int_filemanager_thumbnail"));
        if (
            (isPicture || hit) &&
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
