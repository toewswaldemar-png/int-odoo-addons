/** @odoo-module **/

// Getting files into the explorer: the file and folder choosers, drops from the desktop
// (folders included), a new version of an existing file. The work itself happens in the
// uploads service, which outlives this controller; here only the questions to the user
// and the reload when something has arrived.
import {useExternalListener, useRef, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {useBus, useService} from "@web/core/utils/hooks";
import {IntFilemanagerV2ConflictDialog} from "./conflict_dialog.js";
import {UPLOADS_IDLE_EVENT} from "./uploads_service.js";
import {IntFilemanagerV2TextInputDialog} from "./text_input_dialog.js";
import {entriesFromFiles, startDropWalk} from "./folder_walk.js";
import {errorMessage} from "./utils.js";

class UploadAborted extends Error {}

export const uploadsMixin = (Base) =>
    class extends Base {
        setup() {
            super.setup();
            this.uploads = useService("int_filemanager.uploads");
            this.uploadState = useState(this.uploads.state);
            this.fileInput = useRef("fileInput");
            this.folderInput = useRef("folderInput");
            this.newVersionInput = useRef("newVersionInput");
            this._newVersionRecord = null;

            // Something arrived (or failed for good): show it.
            useBus(this.env.bus, UPLOADS_IDLE_EVENT, () => this.reload());

            // Files dragged in from the desktop. A depth counter, because dragenter/dragleave
            // fire for every child element and a plain flag would flicker.
            this.dropState = useState({dragging: false});
            this._dragDepth = 0;
            useExternalListener(window, "dragenter", (ev) => this._onDragEnter(ev));
            useExternalListener(window, "dragleave", (ev) => this._onDragLeave(ev));
            useExternalListener(window, "dragover", (ev) => ev.preventDefault());
            useExternalListener(window, "drop", (ev) => this._onDrop(ev));
        }

        // ---------------------------------------------------------------- choosers

        triggerUpload() {
            this.fileInput.el.click();
        }

        triggerFolderUpload() {
            this.folderInput.el.click();
        }

        async onFileInputChange(ev) {
            const files = [...ev.target.files];
            ev.target.value = "";
            await this.startUpload(entriesFromFiles(files));
        }

        async onFolderInputChange(ev) {
            const files = [...ev.target.files];
            ev.target.value = "";
            await this.startUpload(entriesFromFiles(files));
        }

        // ---------------------------------------------------------------- new version

        triggerNewVersionUpload(record) {
            this._newVersionRecord = record;
            this.newVersionInput.el.click();
        }

        async onNewVersionInputChange(ev) {
            const file = ev.target.files[0];
            ev.target.value = "";
            const record = this._newVersionRecord;
            this._newVersionRecord = null;
            if (!file || !record) {
                return;
            }
            // The revision the user downloaded, if this browser remembers one; else the one
            // the list shows now (then only a change since this page loaded is caught).
            const remembered = this.uploads.takeBase(record.resId);
            const current = record.data.current_revision_id
                ? record.data.current_revision_id.id
                : false;
            this.uploads.enqueue([
                {
                    file,
                    parentId: record.data.parent_id ? record.data.parent_id.id : false,
                    name: record.data.name,
                    nodeId: record.resId,
                    baseRevisionId: remembered || current,
                },
            ]);
        }

        // ---------------------------------------------------------------- the actual start

        _askConflicts(conflicts) {
            return new Promise((resolve, reject) => {
                this.dialog.add(
                    IntFilemanagerV2ConflictDialog,
                    {
                        conflicts,
                        confirm: resolve,
                        cancel: () => reject(new UploadAborted()),
                    },
                    // Closing the dialog any other way (Escape, the cross) is a cancel too; after a
                    // confirm this is a no-op, the promise has been settled.
                    {onClose: () => reject(new UploadAborted())}
                );
            });
        }

        /**
         * @param {Array<{file?: File, path: string[], folderOnly?: boolean}>} entries
         */
        async startUpload(entries) {
            if (!entries.length) {
                return;
            }
            if (!this.canCreateHere) {
                this.notification.add(_t("Open a folder first, then upload into it."), {
                    type: "warning",
                });
                return;
            }
            try {
                const plan = await this.uploads.plan(
                    entries,
                    this.currentFolderId,
                    (conflicts) => this._askConflicts(conflicts)
                );
                if (plan.length) {
                    this.uploads.enqueue(plan);
                }
                // Folders may have been created while planning.
                await this.reload();
            } catch (error) {
                if (!(error instanceof UploadAborted)) {
                    this.notification.add(errorMessage(error), {type: "danger"});
                }
            }
        }

        // ---------------------------------------------------------------- panel actions

        onUploadRename(item) {
            this.dialog.add(IntFilemanagerV2TextInputDialog, {
                title: _t("Rename"),
                label: _t("Upload under another name"),
                value: item.name,
                confirmLabel: _t("Upload"),
                confirm: (name) => this.uploads.renameAndRetry(item.id, name),
            });
        }

        // ---------------------------------------------------------------- drops

        _isFileDrag(ev) {
            return (
                Boolean(ev.dataTransfer) &&
                Array.from(ev.dataTransfer.types || []).includes("Files")
            );
        }

        _onDragEnter(ev) {
            if (!this._isFileDrag(ev)) {
                return;
            }
            ev.preventDefault();
            this._dragDepth++;
            this.dropState.dragging = true;
        }

        _onDragLeave(ev) {
            if (!this._isFileDrag(ev)) {
                return;
            }
            ev.preventDefault();
            this._dragDepth = Math.max(0, this._dragDepth - 1);
            if (this._dragDepth === 0) {
                this.dropState.dragging = false;
            }
        }

        async _onDrop(ev) {
            if (!this._isFileDrag(ev)) {
                return;
            }
            ev.preventDefault();
            this._dragDepth = 0;
            this.dropState.dragging = false;
            // The entries must be taken while this event is being handled; walking the folders
            // (async) happens afterwards.
            const walk = startDropWalk(ev.dataTransfer);
            await this.startUpload(await walk());
        }
    };
