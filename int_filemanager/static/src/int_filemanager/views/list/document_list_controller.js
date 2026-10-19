import { useRef } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useCustomDropzone } from "@web/core/dropzone/dropzone_hook";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { DocumentDropzone } from "../../dropzone/document_dropzone";
import {
    allFolders,
    foldersToMake,
    readChosenFolder,
    readDroppedFolders,
    uploadError,
} from "./document_folder_upload";
import { getFoldersSection, useNewFolder } from "./document_new_folder";

export const UPLOAD_ROUTE = "/int_filemanager/upload";
const FINISHED_STATES = ["loaded", "error", "abort"];
// Folders made in one call (the server takes 500), and how many files in a row may fail before the
// upload of a folder stops: a session that is over or a disk that is full fails them all.
const FOLDERS_PER_CALL = 200;
const FAILURES_IN_A_ROW = 5;
const FAILURES_SHOWN = 5;

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
        this.folderInputRef = useRef("folderInput");
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
     * "Upload folder" of the menu "New": the folder dialog of the input beside the menu.
     */
    onUploadFolderSelected() {
        this.folderInputRef.el.click();
    }

    /**
     * "New folder" of the menu "New": the folder of the panel is the default of the parent.
     */
    onNewFolder() {
        return this.newFolder(this.uploadFolderId);
    }

    /**
     * "Download folder" of the menu "New": the folder of the panel with what is below it, as one
     * ZIP. The method of the folder tells at once what cannot work (an archived folder, too many
     * bytes) and gives the address of the route.
     */
    async onDownloadFolder() {
        const action = await this.orm.call("int.filemanager.folder", "action_download", [
            [this.uploadFolderId],
        ]);
        return this.actionService.doAction(action);
    }

    async onFilesSelected(ev) {
        const files = [...ev.target.files];
        // Reset the input, so that the same file can be chosen again.
        ev.target.value = "";
        await this.uploadFiles(files);
    }

    async onFolderSelected(ev) {
        const files = [...ev.target.files];
        ev.target.value = "";
        await this.uploadTree(readChosenFolder(files));
    }

    /**
     * Files and folders dropped on the list. A folder of the disk is read with everything in it
     * and goes as a tree, to the folder of the panel. In the list of the documents of a record
     * there is no folder to make: it is told and left out, the files beside it go.
     * @param {DragEvent} ev
     */
    async onDrop(ev) {
        // The items of a drop are gone after the first await: sort them out first.
        const files = [];
        const directories = [];
        for (const item of Array.from(ev.dataTransfer.items)) {
            if (item.kind !== "file") {
                continue;
            }
            const entry = item.webkitGetAsEntry?.();
            if (entry?.isDirectory) {
                directories.push(entry);
            } else {
                files.push(item.getAsFile());
            }
        }
        if (directories.length && !this.linkRecord) {
            const tree = await readDroppedFolders(directories);
            tree.files.push(...files.filter(Boolean).map((file) => ({ file, dir: "" })));
            await this.uploadTree(tree);
            return;
        }
        if (directories.length) {
            this.notification.add(_t("Folders cannot be uploaded, only files."), {
                type: "warning",
            });
        }
        await this.uploadFiles(files.filter(Boolean));
    }

    /**
     * Upload folders of the disk: the folders are made first, in packages, then the files go one
     * after the other to their folders through the route of the single upload. The user is told
     * what happens before it starts, and what came of it when it is over; a file that fails is
     * left out and named in the end.
     * @param {Object} tree see `document_folder_upload.js`
     */
    async uploadTree(tree) {
        const parentId = this.uploadFolderId;
        if (!parentId) {
            this.notification.add(_t("Choose a folder in the panel on the left first."), {
                type: "warning",
            });
            return;
        }
        const total = tree.files.length;
        if (!total && !tree.folders.length) {
            return;
        }
        const confirmed = await new Promise((resolve) =>
            this.dialogService.add(ConfirmationDialog, {
                title: _t("Upload a folder"),
                body: _t(
                    "%(files)s files in %(folders)s folders go into %(target)s. A folder that is " +
                        "there already is filled up, a file whose name is taken gets a number " +
                        "(2); nothing is overwritten. If you stop and start again, what was " +
                        "saved is saved a second time.",
                    {
                        files: total,
                        folders: allFolders(tree).size,
                        target: this.uploadFolderName,
                    }
                ),
                confirmLabel: _t("Upload"),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            })
        );
        if (!confirmed) {
            return;
        }
        const job = { stopped: false, upload: null };
        const closeStop = this.notification.add(_t("Uploading a folder."), {
            sticky: true,
            type: "info",
            buttons: [
                {
                    name: _t("Stop"),
                    primary: true,
                    onClick: () => {
                        job.stopped = true;
                        job.upload?.xhr.abort();
                    },
                },
            ],
        });
        const failed = [];
        let stored = 0;
        try {
            const folderIds = await this.makeFolders(parentId, foldersToMake(tree));
            let inARow = 0;
            for (const { file, dir } of tree.files) {
                if (job.stopped) {
                    break;
                }
                const upload = await this.fileUploadService.upload(UPLOAD_ROUTE, [file], {
                    displayErrorNotification: false,
                    buildFormData: (formData) =>
                        formData.append("folder_id", dir ? folderIds[dir] : parentId),
                });
                upload.title = _t("%(done)s of %(total)s files: %(name)s", {
                    done: stored + failed.length + 1,
                    total,
                    name: file.name,
                });
                job.upload = upload;
                await this.waitForEnd(upload);
                if (upload.state === "loaded") {
                    stored++;
                    inARow = 0;
                } else if (upload.state !== "abort") {
                    failed.push({
                        path: dir ? `${dir}/${file.name}` : file.name,
                        reason: uploadError(upload.xhr),
                    });
                    if (++inARow >= FAILURES_IN_A_ROW) {
                        job.stopped = true;
                    }
                }
            }
        } finally {
            closeStop();
            this.reportTreeUpload({ stored, failed, unreadable: tree.unreadable, total, job });
            await this.actionService.doAction("soft_reload");
        }
    }

    /**
     * @param {Number} parentId the folder of the upload
     * @param {String[]} paths folders to make below it
     * @returns {Promise<Object>} the id of each path
     */
    async makeFolders(parentId, paths) {
        const folderIds = {};
        for (let index = 0; index < paths.length; index += FOLDERS_PER_CALL) {
            Object.assign(
                folderIds,
                await this.orm.call("int.filemanager.folder", "action_make_paths", [
                    [parentId],
                    paths.slice(index, index + FOLDERS_PER_CALL),
                ])
            );
        }
        return folderIds;
    }

    reportTreeUpload({ stored, failed, unreadable, total, job }) {
        const problems = [
            ...failed.map(({ path, reason }) => (reason ? `${path} (${reason})` : path)),
            ...unreadable,
        ];
        let message = _t("%(stored)s of %(total)s files saved.", { stored, total });
        if (job.stopped && stored + failed.length < total) {
            message += " " + _t("The upload was stopped.");
        }
        if (problems.length) {
            const shown = problems.slice(0, FAILURES_SHOWN).join(", ");
            message +=
                " " +
                _t("Not saved: %(names)s", {
                    names:
                        problems.length > FAILURES_SHOWN
                            ? `${shown} … (${problems.length})`
                            : shown,
                });
        }
        this.notification.add(message, {
            type: problems.length || job.stopped ? "warning" : "success",
            sticky: Boolean(problems.length || job.stopped),
        });
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
