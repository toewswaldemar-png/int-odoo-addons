import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";

export const UPLOAD_ROUTE = "/int_filemanager/upload";
const FINISHED_STATES = ["loaded", "error", "abort"];

/**
 * The list of documents with an "Upload" button. One request carries one file (the route
 * wants it so); the files go one after the other, the core's `file_upload` service shows
 * their progress and reports the errors of the route.
 */
export class DocumentListController extends ListController {
    setup() {
        super.setup();
        this.fileUploadService = useService("file_upload");
        this.notification = useService("notification");
    }

    /**
     * The folder chosen in the search panel, where the files go.
     * @returns {Number|false}
     */
    get uploadFolderId() {
        const [folders] = this.env.searchModel.getSections(
            (section) => section.type === "category" && section.fieldName === "folder_id"
        );
        return folders?.activeValueId || false;
    }

    /**
     * @param {Object} upload an upload of the `file_upload` service
     * @returns {Promise} settles when the upload has ended, with or without an error
     */
    waitForEnd(upload) {
        const bus = this.fileUploadService.bus;
        return new Promise((resolve) => {
            if (FINISHED_STATES.includes(upload.state)) {
                resolve();
                return;
            }
            const onEnd = ({ detail }) => {
                if (detail.upload !== upload) {
                    return;
                }
                bus.removeEventListener("FILE_UPLOAD_LOADED", onEnd);
                bus.removeEventListener("FILE_UPLOAD_ERROR", onEnd);
                resolve();
            };
            bus.addEventListener("FILE_UPLOAD_LOADED", onEnd);
            bus.addEventListener("FILE_UPLOAD_ERROR", onEnd);
        });
    }

    async onFilesSelected(ev) {
        const files = [...ev.target.files];
        // Reset the input, so that the same file can be chosen again.
        ev.target.value = "";
        if (!files.length) {
            return;
        }
        const folderId = this.uploadFolderId;
        if (!folderId) {
            this.notification.add(_t("Choose a folder in the panel on the left first."), {
                type: "warning",
            });
            return;
        }
        for (const file of files) {
            const upload = await this.fileUploadService.upload(UPLOAD_ROUTE, [file], {
                buildFormData: (formData) => formData.append("folder_id", folderId),
            });
            await this.waitForEnd(upload);
        }
        await this.model.load();
    }
}
