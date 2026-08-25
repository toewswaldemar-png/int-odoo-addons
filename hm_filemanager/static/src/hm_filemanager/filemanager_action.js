/** @odoo-module **/

import { Component, useState, useRef, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { HmFilePreviewDialog } from "./preview_action";
import { HmInlineTags } from "./inline_tags";

const EDITABLE_EXTENSIONS = new Set([
    "doc", "docx", "odt", "rtf", "txt",
    "xls", "xlsx", "ods", "csv",
    "ppt", "pptx", "odp",
]);

const PREVIEWABLE_EXTENSIONS = new Set([
    "pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "txt",
]);

function extOf(name) {
    const i = name.lastIndexOf(".");
    return i === -1 ? "" : name.slice(i + 1).toLowerCase();
}

function formatSize(bytes) {
    if (!bytes) {
        return "";
    }
    const units = ["B", "KB", "MB", "GB"];
    let value = bytes;
    let i = 0;
    while (value >= 1024 && i < units.length - 1) {
        value /= 1024;
        i++;
    }
    return `${value.toFixed(value < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

export class HmFileManager extends Component {
    static template = "hm_filemanager.FileManager";
    static components = { HmInlineTags };
    static props = ["*"];

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.fileInput = useRef("fileInput");
        this.state = useState({
            path: "",
            breadcrumbs: [],
            entries: [],
            loading: true,
        });
        onWillStart(() => this.load(""));
    }

    async load(path) {
        this.state.loading = true;
        try {
            const res = await rpc("/hm_filemanager/list", { path });
            this.state.path = res.path;
            this.state.breadcrumbs = res.breadcrumbs;
            this.state.entries = res.entries;
        } finally {
            this.state.loading = false;
        }
    }

    formatSize(bytes) {
        return formatSize(bytes);
    }

    isEditable(name) {
        return EDITABLE_EXTENSIONS.has(extOf(name));
    }

    isPreviewable(name) {
        return PREVIEWABLE_EXTENSIONS.has(extOf(name));
    }

    entryPath(entry) {
        return this.state.path ? `${this.state.path}/${entry.name}` : entry.name;
    }

    onOpenEntry(entry) {
        if (entry.is_dir) {
            this.load(this.entryPath(entry));
        } else if (this.isEditable(entry.name)) {
            this.onEdit(entry);
        } else if (this.isPreviewable(entry.name)) {
            this.onPreview(entry);
        } else {
            this.onDownload(entry);
        }
    }

    onBreadcrumb(crumb) {
        this.load(crumb.path);
    }

    onPreview(entry) {
        this.dialog.add(HmFilePreviewDialog, { path: this.entryPath(entry) });
    }

    onDownload(entry) {
        const url = `/hm_filemanager/download?path=${encodeURIComponent(this.entryPath(entry))}`;
        window.open(url, "_blank");
    }

    async onEdit(entry) {
        try {
            const res = await rpc("/hm_filemanager/open_editor", { path: this.entryPath(entry) });
            this.actionService.doAction({
                type: "ir.actions.client",
                tag: "onlyoffice_editor",
                params: { attachment_id: res.attachment_id },
            });
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        }
    }

    async onNewFolder() {
        const name = window.prompt("Name des neuen Ordners:");
        if (!name) {
            return;
        }
        try {
            await rpc("/hm_filemanager/mkdir", { path: this.state.path, name });
            this.load(this.state.path);
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        }
    }

    async onRename(entry) {
        const name = window.prompt("Neuer Name:", entry.name);
        if (!name || name === entry.name) {
            return;
        }
        try {
            await rpc("/hm_filemanager/rename", { path: this.entryPath(entry), new_name: name });
            this.load(this.state.path);
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        }
    }

    onTagsSaved(entry, metaId) {
        entry.meta_id = metaId;
    }

    async onDelete(entry) {
        if (!window.confirm(`"${entry.name}" wirklich löschen?`)) {
            return;
        }
        try {
            await rpc("/hm_filemanager/delete", { path: this.entryPath(entry) });
            this.load(this.state.path);
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        }
    }

    triggerUpload() {
        this.fileInput.el.click();
    }

    async onFileInputChange(ev) {
        const files = ev.target.files;
        if (!files.length) {
            return;
        }
        const formData = new FormData();
        formData.append("path", this.state.path);
        for (const f of files) {
            formData.append("ufile", f);
        }
        try {
            const resp = await fetch("/hm_filemanager/upload", { method: "POST", body: formData });
            const data = await resp.json();
            if (!data.ok) {
                throw new Error("Upload fehlgeschlagen");
            }
            this.load(this.state.path);
        } catch (e) {
            this.notification.add("Upload fehlgeschlagen", { type: "danger" });
        } finally {
            ev.target.value = "";
        }
    }
}

registry.category("actions").add("hm_filemanager_browser", HmFileManager);
