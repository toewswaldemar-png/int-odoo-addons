import { useRef } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useCustomDropzone } from "@web/core/dropzone/dropzone_hook";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { DocumentDropzone } from "../../dropzone/document_dropzone";
import { getFoldersSection, useNewFolder } from "./document_new_folder";

export const UPLOAD_ROUTE = "/int_filemanager/upload";
const FINISHED_STATES = ["loaded", "error", "abort"];

/**
 * The list of documents with the menu "New" (upload, new folder), and files that are dropped on
 * the list.
 * One request carries one file (the route wants it so); the files go one after the other,
 * the core's `file_upload` service shows their progress and reports the errors of the route.
 */
export class DocumentListController extends ListController {
    static components = { ...ListController.components, Dropdown };

    setup() {
        super.setup();
        this.fileInputRef = useRef("fileInput");
        this.newFolder = useNewFolder();
        this.fileUploadService = useService("file_upload");
        this.notification = useService("notification");
        useCustomDropzone(this.rootRef, DocumentDropzone, {
            onDrop: (ev) => this.onDrop(ev),
            getFolderName: () => this.uploadFolderName,
            getRecordName: () => this.linkRecord?.name || false,
        });
    }

    /**
     * The record whose documents the list shows, when the action comes from the button of a
     * record (the keys of the context are set by `action_open_documents`). The files go to the
     * folder that the settings name for its model, and are linked to the record.
     * @returns {{model: String, id: Number, name: String}|false}
     */
    get linkRecord() {
        const context = this.props.context || {};
        if (!context.int_filemanager_link_model) {
            return false;
        }
        return {
            model: context.int_filemanager_link_model,
            id: context.int_filemanager_link_id,
            name: context.int_filemanager_link_name,
        };
    }

    /**
     * The folders of the search panel.
     * @returns {Object|undefined}
     */
    get foldersSection() {
        return getFoldersSection(this.env.searchModel);
    }

    /**
     * The folder chosen in the search panel, where the files go.
     * @returns {Number|false}
     */
    get uploadFolderId() {
        return this.foldersSection?.activeValueId || false;
    }

    /**
     * @returns {String|false} the name of the folder where the files go
     */
    get uploadFolderName() {
        const folders = this.foldersSection;
        const folder = folders?.activeValueId && folders.values.get(folders.activeValueId);
        return folder?.display_name || false;
    }

    /**
     * @override
     * "Properties" (a button for the ticked row): the form opens as a click on a row of a core
     * list opens it, with the pager over the rows of the page. The method of the model would
     * open an action of its own: one record, and no list in the breadcrumb. With more rows
     * ticked the method stays, it tells the user to choose one.
     */
    async beforeExecuteActionButton(clickParams) {
        const { selection } = this.model.root;
        if (clickParams.name === "action_open_form" && selection.length === 1) {
            await this.openRecord(selection[0]);
            return false;
        }
        return super.beforeExecuteActionButton(...arguments);
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

    /**
     * "Upload" of the menu "New": the file dialog of the input beside the menu (the input
     * cannot be in the menu: it is gone with it before the files are chosen).
     */
    onUploadSelected() {
        this.fileInputRef.el.click();
    }

    /**
     * "New folder" of the menu "New": the folder of the panel is the default of the parent.
     */
    onNewFolder() {
        return this.newFolder(this.uploadFolderId);
    }

    async onFilesSelected(ev) {
        const files = [...ev.target.files];
        // Reset the input, so that the same file can be chosen again.
        ev.target.value = "";
        await this.uploadFiles(files);
    }

    /**
     * Files dropped on the list. A folder of the disk comes as an entry that is no file to
     * read: it is told and left out, the files beside it go.
     * @param {DragEvent} ev
     */
    async onDrop(ev) {
        // The items of a drop are gone after the first await: sort them out first.
        const files = [];
        let hasDirectory = false;
        for (const item of Array.from(ev.dataTransfer.items)) {
            if (item.kind !== "file") {
                continue;
            }
            if (item.webkitGetAsEntry?.()?.isDirectory) {
                hasDirectory = true;
            } else {
                files.push(item.getAsFile());
            }
        }
        if (hasDirectory) {
            this.notification.add(_t("Folders cannot be uploaded, only files."), {
                type: "warning",
            });
        }
        await this.uploadFiles(files.filter(Boolean));
    }

    /**
     * @param {File[]} files
     */
    async uploadFiles(files) {
        if (!files.length) {
            return;
        }
        const record = this.linkRecord;
        const folderId = this.uploadFolderId;
        if (!record && !folderId) {
            this.notification.add(_t("Choose a folder in the panel on the left first."), {
                type: "warning",
            });
            return;
        }
        for (const file of files) {
            const upload = await this.fileUploadService.upload(UPLOAD_ROUTE, [file], {
                buildFormData: (formData) => {
                    if (record) {
                        formData.append("link_model", record.model);
                        formData.append("link_id", record.id);
                    } else {
                        formData.append("folder_id", folderId);
                    }
                },
            });
            await this.waitForEnd(upload);
        }
        await this.model.load();
    }
}
