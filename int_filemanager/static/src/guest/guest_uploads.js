// The upload area of the page of the guests of a share that takes files: a button, a dropzone over
// the whole page, the progress of the running uploads, and "My uploads" (the files that this
// browser has a receipt for, with a button to take them away again).
//
// The core's `file_upload` service does the sending. It does not wait for an upload to end and does
// not hand back the answer of the server (it only looks at it for errors), so the page listens for
// its events and reads the receipt from `upload.xhr.responseText`. One request carries one file; the
// files go one after the other.
import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { useCustomDropzone } from "@web/core/dropzone/dropzone_hook";
import { FileUploadProgressContainer } from "@web/core/file_upload/file_upload_progress_container";
import { FileUploadProgressDataRow } from "@web/core/file_upload/file_upload_progress_record";
import { formatDateTime, deserializeDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { checkFileSize } from "@web/core/utils/files";
import { humanSize } from "@web/core/utils/binary";
import { useService } from "@web/core/utils/hooks";
import { url } from "@web/core/utils/urls";
import { DocumentDropzone } from "@int_filemanager/int_filemanager/dropzone/document_dropzone";
import { loadReceipts, saveReceipts, withReceipt, withoutReceipt } from "./guest_receipts";
import { shareKey, shareToken, shareUrl } from "./guest_share";

const FINISHED_STATES = ["loaded", "error", "abort"];

/**
 * What to tell the guest when an upload failed: the text that the share sent (its answer is
 * `{"error": {"message": ...}}`), or, for an answer of Odoo itself (the body was too big for the
 * share: Odoo turns it away before the share is asked), one for the status.
 */
export function failureMessage(xhr) {
    try {
        const text = JSON.parse(xhr.responseText)?.error?.message;
        if (text) {
            return text;
        }
    } catch {
        // not JSON: the answer of Odoo itself
    }
    switch (xhr.status) {
        case 413:
            return _t("This file is too large, or this link takes no more files.");
        case 403:
        case 410:
            return _t("This link does not take files any more.");
        case 429:
            return _t("Too many files at once. Try again in a minute.");
        default:
            return _t("The upload failed. Try again.");
    }
}

/**
 * The area above the page of the guests, with the page itself as its content: the dropzone covers
 * both. Without the right to upload it shows only the content.
 */
export class GuestUploads extends Component {
    static template = "int_filemanager.GuestUploads";
    static components = { FileUploadProgressContainer, FileUploadProgressDataRow };
    static props = { enabled: Boolean, slots: { type: Object, optional: true } };

    setup() {
        this.fileUploadService = useService("file_upload");
        this.notification = useService("notification");
        this.root = useRef("root");
        this.fileInput = useRef("fileInput");
        this.token = shareToken();
        this.rights = odoo.int_filemanager_rights;
        this.state = useState({ uploads: loadReceipts(this.token), failures: [], closed: false });
        useCustomDropzone(
            this.root,
            DocumentDropzone,
            {
                onDrop: (ev) => this.onDrop(ev),
                getFolderName: () => odoo.int_filemanager_folder_name,
            },
            () => this.props.enabled
        );
        onMounted(() => {
            if (this.props.enabled) {
                this.refresh();
            }
        });
    }

    get hint() {
        const parts = [
            _t("Up to %(size)s per file", { size: humanSize(this.rights.upload_max_file) }),
        ];
        if (this.rights.upload_extensions.length) {
            parts.push(
                _t("Allowed: %(kinds)s", { kinds: this.rights.upload_extensions.join(", ") })
            );
        }
        return parts.join(". ");
    }

    humanSize(size) {
        return humanSize(size);
    }

    formatTime(time) {
        return time ? formatDateTime(deserializeDateTime(time)) : "";
    }

    choose() {
        this.fileInput.el.click();
    }

    async onFilesSelected(ev) {
        const files = [...ev.target.files];
        ev.target.value = ""; // so that the same file can be chosen again
        await this.uploadFiles(files);
    }

    /**
     * Files dropped on the page. A folder of the disk comes as an entry that is no file to read:
     * it is told and left out, the files beside it go.
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

    /** @param {File[]} files */
    async uploadFiles(files) {
        this.state.failures = [];
        for (const file of files) {
            if (checkFileSize(file.size, this.notification)) {
                await this.uploadOne(file);
            }
        }
        await this.refresh();
    }

    async uploadOne(file) {
        const key = shareKey();
        const upload = await this.fileUploadService.upload(
            url(shareUrl("upload"), key ? { k: key } : {}),
            [file],
            { displayErrorNotification: false } // the page says why, per file, below
        );
        await this.waitForEnd(upload);
        if (upload.state === "loaded") {
            const answer = JSON.parse(upload.xhr.responseText);
            const entry = {
                id: answer.id,
                receipt: answer.receipt,
                name: answer.name,
                size: answer.size,
                time: "",
            };
            const entries = withReceipt(loadReceipts(this.token), entry);
            saveReceipts(this.token, entries);
            this.state.uploads = entries;
        } else if (upload.state === "error") {
            this.state.failures.push({ name: file.name, message: failureMessage(upload.xhr) });
        }
    }

    /** @returns {Promise} settles when the upload has ended, with or without an error */
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

    async post(path, body) {
        return browser.fetch(shareUrl(path), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ k: shareKey(), ...body }),
        });
    }

    /**
     * "My uploads" from the share: it answers for the receipts it can prove, and says which of the
     * files can still be taken away. What it does not answer for is gone (taken away by a user, or
     * not valid) and leaves the list. An answer that is an error leaves the list as it was.
     */
    async refresh() {
        const entries = loadReceipts(this.token);
        if (!entries.length) {
            this.state.uploads = [];
            return;
        }
        let response;
        try {
            response = await this.post("uploads", {
                receipts: entries.map(({ id, receipt }) => ({ id, receipt })),
            });
        } catch {
            return; // offline: the list stays as the browser has it
        }
        if (!response.ok) {
            this.state.closed = [403, 410].includes(response.status);
            return;
        }
        const receipts = new Map(entries.map((entry) => [entry.id, entry.receipt]));
        const shown = (await response.json()).map((item) => ({
            ...item,
            receipt: receipts.get(item.id),
        }));
        saveReceipts(
            this.token,
            shown.map(({ id, receipt, name, size, time }) => ({ id, receipt, name, size, time }))
        );
        this.state.uploads = shown;
    }

    async remove(entry) {
        const response = await this.post("uploads/delete", {
            id: entry.id,
            receipt: entry.receipt,
        });
        if (response.ok || response.status === 404) {
            // 404: the share does not know the file (any more); the receipt is of no use
            saveReceipts(this.token, withoutReceipt(loadReceipts(this.token), entry.id));
            this.state.uploads = withoutReceipt(this.state.uploads, entry.id);
        } else if (response.status === 403) {
            entry.removable = false;
            this.notification.add(
                _t("This file has been taken over. It cannot be removed any more."),
                {
                    type: "warning",
                }
            );
        } else {
            this.notification.add(_t("The file could not be removed. Try again."), {
                type: "danger",
            });
        }
    }
}
