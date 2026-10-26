import { onWillStart, useRef } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { makeContext } from "@web/core/context";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useCustomDropzone } from "@web/core/dropzone/dropzone_hook";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { STATIC_ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";
import { ListController } from "@web/views/list/list_controller";
import { DocumentDropzone } from "../../dropzone/document_dropzone";
import { MOVE_MODEL } from "../drag/document_move";
import {
    allFolders,
    foldersToMake,
    readChosenFolder,
    readDroppedFolders,
    uploadError,
} from "./document_folder_upload";
import { getFoldersSection, useFolderRights, useNewFolder } from "./document_new_folder";

export const UPLOAD_ROUTE = "/int_filemanager/upload";
const FINISHED_STATES = ["loaded", "error", "abort"];
// The server takes 500 folders per call. An expired session or a full disk fails every file, so
// the upload of a folder stops after a few failures in a row.
const FOLDERS_PER_CALL = 200;
const FAILURES_IN_A_ROW = 5;
const FAILURES_SHOWN = 5;
const MOVE_ACTION = "int_filemanager.int_filemanager_move_document_action";
// Groups of the "Actions" menu (a divider lies between two groups), in the order of the `sequence`
// of the static items: what leaves the list (print, export; the group of the core), what puts
// records elsewhere (move), what ends a record (archive, delete). The actions that other modules
// bind to the model stay in the last group of the core.
const ACTIONS_MOVE_GROUP = STATIC_ACTIONS_GROUP_NUMBER + 1;
const ACTIONS_LIFECYCLE_GROUP = ACTIONS_MOVE_GROUP + 1;

/**
 * The list of documents with the menu "New" (upload, new folder) and files dropped on the list.
 * One request carries one file (the route wants it so), the files go one after the other.
 */
export class DocumentListController extends ListController {
    static template = "int_filemanager.DocumentListView";
    static components = { ...ListController.components, Dropdown };

    setup() {
        super.setup();
        this.fileInputRef = useRef("fileInput");
        this.folderInputRef = useRef("folderInput");
        this.newFolder = useNewFolder();
        this.folderRights = useFolderRights();
        this.fileUploadService = useService("file_upload");
        this.notification = useService("notification");
        onWillStart(async () => {
            this.canMove = await user.checkAccessRight(MOVE_MODEL, "create");
        });
        useCustomDropzone(
            this.rootRef,
            DocumentDropzone,
            {
                onDrop: (ev) => this.onDrop(ev),
                getFolderName: () => this.uploadFolderName,
                getTarget: () => this.uploadTarget,
            },
            () => this.canUpload
        );
    }

    /** A reader may not upload; a module that sends the files elsewhere says by what right. */
    get canUpload() {
        return Boolean(this.uploadTarget) || this.folderRights.write;
    }

    /**
     * Where the files go instead of the folder of the panel: nothing in the core. A module that
     * does that (the files of a record, say) returns the text of the dropzone and what it adds
     * to the form of the upload, which the controller of the route reads.
     * @returns {{message: String, appendTo: Function}|false}
     */
    get uploadTarget() {
        return false;
    }

    /** @override "Move to..." is an item of the menu like "Export", so that it has an icon. */
    getStaticActionMenuItems() {
        const items = super.getStaticActionMenuItems();
        items.move = {
            isAvailable: () => this.canMove,
            sequence: 20,
            icon: "fa fa-folder-open",
            description: _t("Move to..."),
            groupNumber: ACTIONS_MOVE_GROUP,
            callback: () => this.onMoveSelected(),
        };
        // Archive and delete are a group of their own, below the others.
        for (const key of ["archive", "unarchive", "delete"]) {
            items[key].groupNumber = ACTIONS_LIFECYCLE_GROUP;
        }
        return items;
    }

    /** @returns {Object[]} the items of the menu that the right click on a row shows as well */
    get contextMenuItems() {
        return this.actionMenuItems.action.filter(
            (item) => item.groupNumber === ACTIONS_MOVE_GROUP
        );
    }

    /** Opens the dialog for the ticked rows, as the `ActionMenus` of the core runs an action. */
    async onMoveSelected() {
        const resIds = await this.model.root.getResIds(true);
        return this.actionService.doAction(MOVE_ACTION, {
            additionalContext: makeContext([
                this.model.root.context,
                {
                    active_id: resIds[0],
                    active_ids: resIds,
                    active_model: this.props.resModel,
                    active_domain: this.props.domain,
                },
            ]),
            onClose: () => this.model.load(),
        });
    }

    get foldersSection() {
        return getFoldersSection(this.env.searchModel);
    }

    get uploadFolderId() {
        return this.foldersSection?.activeValueId || false;
    }

    get uploadFolderName() {
        const folders = this.foldersSection;
        const folder = folders?.activeValueId && folders.values.get(folders.activeValueId);
        return folder?.display_name || false;
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

    onUploadSelected() {
        // The input is beside the menu: inside it, it is gone before the files are chosen.
        this.fileInputRef.el.click();
    }

    onUploadFolderSelected() {
        this.folderInputRef.el.click();
    }

    onNewFolder() {
        return this.newFolder(this.uploadFolderId);
    }

    /**
     * Downloads the folder of the panel with everything below it as one ZIP. The server method
     * refuses at once what cannot work (an archived folder, too many bytes).
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
     * Files and folders dropped on the list. Folders go as a tree, except in the documents of a
     * record: there they are refused and the files beside them go.
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
        if (directories.length && !this.uploadTarget) {
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
     * Uploads folders of the disk: the folders are made first, in packages, then the files go one
     * by one. A file that fails is left out and named in the end.
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

    async uploadFiles(files) {
        if (!files.length) {
            return;
        }
        const target = this.uploadTarget;
        const folderId = this.uploadFolderId;
        if (!target && !folderId) {
            this.notification.add(_t("Choose a folder in the panel on the left first."), {
                type: "warning",
            });
            return;
        }
        for (const file of files) {
            const upload = await this.fileUploadService.upload(UPLOAD_ROUTE, [file], {
                buildFormData: (formData) => {
                    if (target) {
                        target.appendTo(formData);
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
