import { useService } from "@web/core/utils/hooks";
import { FileUploadProgressContainer } from "@web/core/file_upload/file_upload_progress_container";
import { FileUploadProgressDataRow } from "@web/core/file_upload/file_upload_progress_record";
import { ListRenderer } from "@web/views/list/list_renderer";

/** The list with the progress of the running uploads above it. */
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
    }
}
