/** @odoo-module **/

import { Component, useState, useRef, useEffect, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { WithSearch } from "@web/search/with_search/with_search";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { IntFilePreviewDialog } from "./preview_action";
import { IntInlineTags } from "./inline_tags";
import { IntFolderTree } from "./folder_tree";
import { IntTextInputDialog } from "./text_input_dialog";

const EDITABLE_EXTENSIONS = new Set([
    "doc", "docx", "odt", "rtf", "txt",
    "xls", "xlsx", "ods", "csv",
    "ppt", "pptx", "odp",
]);

const PREVIEWABLE_EXTENSIONS = new Set([
    "pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "txt",
]);

// Uses the FontAwesome icon set already bundled with Odoo's web client.
const EXTENSION_ICONS = {
    pdf: "fa-file-pdf-o",
    doc: "fa-file-word-o", docx: "fa-file-word-o", odt: "fa-file-word-o", rtf: "fa-file-word-o",
    xls: "fa-file-excel-o", xlsx: "fa-file-excel-o", ods: "fa-file-excel-o", csv: "fa-file-excel-o",
    ppt: "fa-file-powerpoint-o", pptx: "fa-file-powerpoint-o", odp: "fa-file-powerpoint-o",
    png: "fa-file-image-o", jpg: "fa-file-image-o", jpeg: "fa-file-image-o",
    gif: "fa-file-image-o", webp: "fa-file-image-o", bmp: "fa-file-image-o", svg: "fa-file-image-o",
    zip: "fa-file-archive-o", rar: "fa-file-archive-o", "7z": "fa-file-archive-o", tar: "fa-file-archive-o", gz: "fa-file-archive-o",
    mp3: "fa-file-audio-o", wav: "fa-file-audio-o", flac: "fa-file-audio-o", ogg: "fa-file-audio-o",
    mp4: "fa-file-video-o", mkv: "fa-file-video-o", avi: "fa-file-video-o", mov: "fa-file-video-o", webm: "fa-file-video-o",
    txt: "fa-file-text-o", md: "fa-file-text-o", log: "fa-file-text-o",
    json: "fa-file-code-o", xml: "fa-file-code-o", html: "fa-file-code-o", js: "fa-file-code-o", py: "fa-file-code-o", css: "fa-file-code-o",
};

function extOf(name) {
    const i = name.lastIndexOf(".");
    return i === -1 ? "" : name.slice(i + 1).toLowerCase();
}

function fileIconClass(name) {
    return EXTENSION_ICONS[extOf(name)] || "fa-file-o";
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

export class IntFileManager extends Component {
    static template = "int_filemanager.FileManager";
    static components = { IntInlineTags, IntFolderTree, SearchBar };
    static props = {
        domain: { type: Array, optional: true },
    };

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.fileUpload = useService("file_upload");
        this.fileInput = useRef("fileInput");
        useBus(this.fileUpload.bus, "FILE_UPLOAD_LOADED", (ev) => {
            if (ev.detail.upload.id === this.pendingUploadId) {
                this.load(this.state.path);
            }
        });
        // Reload when the native search bar's domain (name/tag facets) changes.
        this._searchInitialized = false;
        useEffect(
            () => {
                if (this._searchInitialized) {
                    this.load(this.state.path);
                } else {
                    this._searchInitialized = true;
                }
            },
            () => [JSON.stringify(this.props.domain)]
        );
        this.state = useState({
            path: "",
            breadcrumbs: [],
            entries: [],
            loading: true,
            treeVersion: 0,
            recursive: false,
            offset: 0,
            total: 0,
            limit: 200,
        });
        onWillStart(() => this.load(""));
    }

    fileIconClass(name) {
        return fileIconClass(name);
    }

    onNavigate(path) {
        this.load(path);
    }

    refreshTree() {
        this.state.treeVersion++;
    }

    toggleRecursive() {
        this.state.recursive = !this.state.recursive;
        this.load(this.state.path);
    }

    async load(path, offset = 0) {
        this.state.loading = true;
        try {
            const res = await rpc("/int_filemanager/list", {
                path,
                recursive: this.state.recursive,
                domain: this.props.domain || [],
                offset,
            });
            this.state.path = res.path;
            this.state.breadcrumbs = res.breadcrumbs;
            this.state.entries = res.entries;
            this.state.total = res.total;
            this.state.offset = res.offset;
            this.state.limit = res.limit;
        } finally {
            this.state.loading = false;
        }
    }

    nextPage() {
        if (this.state.offset + this.state.limit < this.state.total) {
            this.load(this.state.path, this.state.offset + this.state.limit);
        }
    }

    prevPage() {
        if (this.state.offset > 0) {
            this.load(this.state.path, Math.max(0, this.state.offset - this.state.limit));
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
        // entry.path already is the real relative path from the backend - this
        // matters in particular for recursive search results, where the entry's
        // parent folder can differ from the currently browsed state.path.
        return entry.path;
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
        this.dialog.add(IntFilePreviewDialog, { path: this.entryPath(entry) });
    }

    onDownload(entry) {
        const url = `/int_filemanager/download?path=${encodeURIComponent(this.entryPath(entry))}`;
        window.open(url, "_blank");
    }

    async onEdit(entry) {
        try {
            const res = await rpc("/int_filemanager/open_editor", { path: this.entryPath(entry) });
            this.actionService.doAction({
                type: "ir.actions.client",
                tag: "onlyoffice_editor",
                params: { attachment_id: res.attachment_id },
            });
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        }
    }

    onNewFolder() {
        this.dialog.add(IntTextInputDialog, {
            title: "Neuer Ordner",
            label: "Name des neuen Ordners",
            confirmLabel: "Anlegen",
            confirm: async (name) => {
                try {
                    await rpc("/int_filemanager/mkdir", { path: this.state.path, name });
                    this.load(this.state.path);
                    this.refreshTree();
                } catch (e) {
                    this.notification.add(e.data?.message || e.message, { type: "danger" });
                }
            },
        });
    }

    onRename(entry) {
        this.dialog.add(IntTextInputDialog, {
            title: "Umbenennen",
            label: "Neuer Name",
            value: entry.name,
            confirmLabel: "Umbenennen",
            confirm: async (name) => {
                if (name === entry.name) {
                    return;
                }
                try {
                    await rpc("/int_filemanager/rename", { path: this.entryPath(entry), new_name: name });
                    this.load(this.state.path);
                    if (entry.is_dir) {
                        this.refreshTree();
                    }
                } catch (e) {
                    this.notification.add(e.data?.message || e.message, { type: "danger" });
                }
            },
        });
    }

    onTagsSaved(entry, metaId) {
        entry.meta_id = metaId;
    }

    onDelete(entry) {
        this.dialog.add(ConfirmationDialog, {
            title: "Löschen bestätigen",
            body: `"${entry.name}" wirklich löschen?`,
            confirmLabel: "Löschen",
            confirmClass: "btn-danger",
            confirm: async () => {
                try {
                    await rpc("/int_filemanager/delete", { path: this.entryPath(entry) });
                    this.load(this.state.path);
                    if (entry.is_dir) {
                        this.refreshTree();
                    }
                } catch (e) {
                    this.notification.add(e.data?.message || e.message, { type: "danger" });
                }
            },
        });
    }

    triggerUpload() {
        this.fileInput.el.click();
    }

    async onFileInputChange(ev) {
        const files = [...ev.target.files];
        ev.target.value = "";
        if (!files.length) {
            return;
        }
        // The upload itself is fire-and-forget (xhr sent, promise resolves right after);
        // completion/errors surface via the file_upload service's bus events
        // (FILE_UPLOAD_LOADED below, FILE_UPLOAD_ERROR shows its own toast automatically).
        const upload = await this.fileUpload.upload("/int_filemanager/upload", files, {
            buildFormData: (formData) => formData.append("path", this.state.path),
        });
        this.pendingUploadId = upload.id;
    }
}

// Passed explicitly to WithSearch instead of letting it resolve the search view
// server-side: an empty/late-loaded searchViewFields makes Odoo's built-in "Add a
// custom filter" dropdown item crash with "No field found" (getDefaultPath in
// @web/core/tree_editor/utils needs at least one key). Providing both this and
// SEARCH_VIEW_ARCH below also skips that extra RPC round-trip.
const SEARCH_VIEW_FIELDS = {
    name: { name: "name", type: "char", string: "Name", searchable: true },
    tag_ids: {
        name: "tag_ids",
        type: "many2many",
        relation: "int_filemanager.tag",
        string: "Tags",
        searchable: true,
    },
};
const SEARCH_VIEW_ARCH = `<search>
    <field name="name" string="Name"/>
    <field name="tag_ids" string="Tags"/>
    <filter name="filter_folders" string="Nur Ordner" domain="[('is_dir','=',True)]"/>
    <filter name="filter_files" string="Nur Dateien" domain="[('is_dir','=',False)]"/>
    <separator/>
    <filter name="filter_tagged" string="Mit Tags" domain="[('tag_ids','!=',False)]"/>
    <filter name="filter_untagged" string="Ohne Tags" domain="[('tag_ids','=',False)]"/>
</search>`;

export class IntFileManagerAction extends Component {
    static template = "int_filemanager.FileManagerAction";
    static components = { WithSearch, IntFileManager };
    static props = ["*"];

    setup() {
        this.searchViewFields = SEARCH_VIEW_FIELDS;
        this.searchViewArch = SEARCH_VIEW_ARCH;
    }
}

registry.category("actions").add("int_filemanager_browser", IntFileManagerAction);
