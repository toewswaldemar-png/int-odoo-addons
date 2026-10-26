// The upload area of the page of a shared folder (``share_upload_area``): sends the files one by
// one, keeps the receipts in the browser, and shows "My uploads". The texts come from the template
// (``data-msg``), where they are translated; nothing from the server is put in as HTML.
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { humanSize } from "@web/core/utils/binary";
import { loadReceipts, saveReceipts, withReceipt, withoutReceipt } from "./receipts";

const SHARE_PATH = "/int_filemanager/share";

/**
 * The text of a failed upload: the message of the share (`{"error": {"message": ...}}`) or, for an
 * answer of Odoo itself (a body too big for the share is turned away before it is asked), one for
 * the status.
 *
 * @param {number} status
 * @param {string} body
 * @param {(name: string) => string} msg the texts of the page
 */
export function failureMessage(status, body, msg) {
    try {
        const text = JSON.parse(body)?.error?.message;
        if (text) {
            return text;
        }
    } catch {
        // not JSON: the answer of Odoo itself
    }
    switch (status) {
        case 413:
            return msg("too_large");
        case 403:
        case 410:
            return msg("closed");
        case 429:
            return msg("busy");
        default:
            return msg("failed");
    }
}

export class ShareUpload extends Interaction {
    static selector = ".o_if_share_upload";
    dynamicContent = {
        ".o_if_share_choose": { "t-on-click": () => this.fileInput.click() },
        "input[type=file]": { "t-on-change": this.onFilesSelected },
    };

    setup() {
        this.token = this.el.dataset.token;
        this.maxSize = Number(this.el.dataset.maxSize);
        this.base = `${SHARE_PATH}/${encodeURIComponent(this.token)}`;
        this.fileInput = this.el.querySelector("input[type=file]");
        this.progress = this.el.querySelector(".o_if_share_progress");
        this.mine = this.el.querySelector(".o_if_share_mine");
        this.mineList = this.el.querySelector(".o_if_share_mine_list");
        this.closedAlert = this.el.querySelector(".o_if_share_closed");
        this.entries = loadReceipts(this.token);
    }

    async start() {
        // One listener for the buttons that the list gets later (``addListener`` is for ``start``:
        // the interaction is not ready before it).
        this.addListener(this.mineList, "click", (ev) => {
            const button = ev.target.closest(".o_if_share_remove");
            const entry = button && this.entries.find((e) => e.id === Number(button.dataset.id));
            if (entry) {
                this.remove(entry, button);
            }
        });
        this.render();
        await this.waitFor(this.refresh());
    }

    msg(name) {
        return this.el.querySelector(`[data-msg="${name}"]`)?.textContent.trim() || "";
    }

    async onFilesSelected(ev) {
        const files = [...ev.target.files];
        ev.target.value = ""; // so that the same file can be chosen again
        for (const file of files) {
            await this.waitFor(this.uploadOne(file));
        }
        await this.waitFor(this.refresh());
    }

    /** One line of the list of what is being sent: the name, then how far it is, then why not. */
    progressLine(file) {
        const doc = this.el.ownerDocument;
        const item = doc.createElement("li");
        const name = doc.createElement("strong");
        name.textContent = file.name;
        const state = doc.createElement("span");
        state.className = "ms-2";
        state.textContent = this.msg("uploading");
        item.append(name, state);
        this.progress.append(item);
        return { item, state };
    }

    uploadOne(file) {
        const { item, state } = this.progressLine(file);
        if (file.size > this.maxSize) {
            this.fail(item, state, this.msg("too_large"));
            return Promise.resolve();
        }
        return new Promise((resolve) => {
            const xhr = new XMLHttpRequest();
            xhr.open("POST", `${this.base}/upload`);
            xhr.upload.onprogress = (ev) => {
                if (ev.lengthComputable) {
                    state.textContent = `${Math.round((100 * ev.loaded) / ev.total)} %`;
                }
            };
            xhr.onerror = () => {
                this.fail(item, state, this.msg("failed"));
                resolve();
            };
            xhr.onload = () => {
                if (xhr.status === 200) {
                    const answer = JSON.parse(xhr.responseText);
                    this.entries = withReceipt(this.entries, {
                        id: answer.id,
                        receipt: answer.receipt,
                        name: answer.name,
                        size: answer.size,
                        time: "",
                    });
                    saveReceipts(this.token, this.entries);
                    item.remove();
                } else {
                    this.closed(xhr.status);
                    this.fail(
                        item,
                        state,
                        failureMessage(xhr.status, xhr.responseText, (name) => this.msg(name))
                    );
                }
                resolve();
            };
            const form = new FormData();
            form.append("ufile", file);
            xhr.send(form);
        });
    }

    fail(item, state, message) {
        state.textContent = message;
        item.classList.add("text-danger");
    }

    /** A link that does not take files any more says so once. */
    closed(status) {
        if ([403, 410].includes(status)) {
            this.closedAlert.classList.remove("d-none");
        }
    }

    async post(path, body) {
        return fetch(`${this.base}/${path}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
    }

    /**
     * Asks the share for "My uploads": files it does not answer for are gone and leave the list; an
     * error leaves the list as it was.
     */
    async refresh() {
        if (!this.entries.length) {
            return;
        }
        let response;
        try {
            response = await this.post("uploads", {
                receipts: this.entries.map(({ id, receipt }) => ({ id, receipt })),
            });
        } catch {
            return; // offline: the list stays as the browser has it
        }
        if (!response.ok) {
            this.closed(response.status);
            return;
        }
        const receipts = new Map(this.entries.map((entry) => [entry.id, entry.receipt]));
        this.entries = (await response.json()).map((item) => ({
            ...item,
            receipt: receipts.get(item.id),
        }));
        saveReceipts(
            this.token,
            this.entries.map(({ id, receipt, name, size, time }) => ({
                id,
                receipt,
                name,
                size,
                time,
            }))
        );
        this.render();
    }

    async remove(entry, button) {
        button.disabled = true;
        const response = await this.waitFor(
            this.post("uploads/delete", { id: entry.id, receipt: entry.receipt })
        );
        if (response.ok || response.status === 404) {
            // 404: the share does not know the file (any more); the receipt is of no use
            this.entries = withoutReceipt(this.entries, entry.id);
            saveReceipts(this.token, this.entries);
        } else if (response.status === 403) {
            entry.removable = false;
            window.alert(this.msg("taken_over"));
        } else {
            button.disabled = false;
            window.alert(this.msg("remove_failed"));
        }
        this.render();
    }

    /** The list "My uploads", made with text nodes only. */
    render() {
        const doc = this.el.ownerDocument;
        this.mine.classList.toggle("d-none", !this.entries.length);
        this.mineList.replaceChildren(
            ...this.entries.map((entry) => {
                const item = doc.createElement("li");
                item.className = "list-group-item d-flex align-items-center gap-2 px-0";
                const name = doc.createElement("span");
                name.className = "text-truncate flex-grow-1";
                name.textContent = entry.name;
                const size = doc.createElement("span");
                size.className = "text-muted small text-nowrap";
                size.textContent = humanSize(entry.size);
                item.append(name, size);
                if (entry.removable === false) {
                    const badge = doc.createElement("span");
                    badge.className = "badge text-bg-secondary";
                    badge.textContent = this.msg("taken");
                    item.append(badge);
                } else {
                    const button = doc.createElement("button");
                    button.type = "button";
                    button.className = "btn btn-sm btn-outline-danger o_if_share_remove";
                    button.dataset.id = entry.id;
                    button.textContent = this.msg("remove");
                    item.append(button);
                }
                return item;
            })
        );
    }
}

registry.category("public.interactions").add("int_filemanager_share.share_upload", ShareUpload);
