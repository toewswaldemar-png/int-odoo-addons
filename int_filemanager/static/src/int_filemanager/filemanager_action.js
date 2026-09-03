/** @odoo-module **/

import { Component, useState, useRef, useEffect, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { useBus, useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { WithSearch } from "@web/search/with_search/with_search";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { Layout } from "@web/search/layout";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { Pager } from "@web/core/pager/pager";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { IntInlineTags } from "./inline_tags";
import { IntFolderTree } from "./folder_tree";
import { IntTextInputDialog } from "./text_input_dialog";
import { IntLinkRecordDialog } from "./link_record_dialog";

const EDITABLE_EXTENSIONS = new Set([
    "doc", "docx", "odt", "rtf", "txt",
    "xls", "xlsx", "ods", "csv",
    "ppt", "pptx", "odp",
]);

const PREVIEWABLE_EXTENSIONS = new Set([
    "pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "txt",
]);

// Only Word/Excel/PowerPoint have an "ofe" protocol handler on Windows for
// launching the desktop app straight from a URL - odt/rtf/csv/ods/odp have
// no equivalent, they stay editable via ONLYOFFICE only.
const OFFICE_PROTOCOL = {
    doc: "ms-word", docx: "ms-word",
    xls: "ms-excel", xlsx: "ms-excel",
    ppt: "ms-powerpoint", pptx: "ms-powerpoint",
};

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
    static components = { IntInlineTags, IntFolderTree, SearchBar, Dropdown, DropdownItem, CheckBox, Pager, Layout };
    static props = {
        domain: { type: Array, optional: true },
        context: { type: Object, optional: true },
    };

    get display() {
        return { controlPanel: { layoutActions: true } };
    }

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.fileUpload = useService("file_upload");
        this.busService = useService("bus_service");
        this.fileViewer = useFileViewer();
        this.fileInput = useRef("fileInput");
        useBus(this.fileUpload.bus, "FILE_UPLOAD_LOADED", (ev) => {
            if (ev.detail.upload.id === this.pendingUploadId) {
                this.load(this.state.path);
            }
        });
        // Reload when anything changes the index server-side, whether from
        // this tab (mutations below) or elsewhere (another tab, the
        // filesystem watcher). Debounced since a bulk change (e.g. a large
        // folder copied in) fires one notification per touched entry.
        this._onFilemanagerChange = () => {
            clearTimeout(this._reloadTimeout);
            this._reloadTimeout = setTimeout(() => {
                this.load(this.state.path, this.state.offset);
                this.refreshTree();
            }, 800);
        };
        this.busService.addChannel("int_filemanager");
        this.busService.subscribe("int_filemanager.change", this._onFilemanagerChange);
        onWillUnmount(() => {
            clearTimeout(this._reloadTimeout);
            this.busService.unsubscribe("int_filemanager.change", this._onFilemanagerChange);
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
            () => [JSON.stringify(this.props.domain), Boolean(this.props.context?.int_filemanager_recursive)]
        );
        this.state = useState({
            path: "",
            breadcrumbs: [],
            entries: [],
            loading: true,
            treeVersion: 0,
            offset: 0,
            total: 0,
            limit: 200,
            selected: new Set(),
            orderBy: "name",
            orderAsc: true,
            // Optional column, off by default (most entries have no link) - toggled via
            // the gear icon in the header, same idea as native ListRenderer's optional
            // fields picker (list_renderer.js toggleOptionalField), persisted the same way.
            showLinkColumn: browser.localStorage.getItem("int_filemanager.showLinkColumn") === "1",
        });
        onWillStart(() => this.load(""));
    }

    toggleLinkColumn() {
        this.state.showLinkColumn = !this.state.showLinkColumn;
        browser.localStorage.setItem("int_filemanager.showLinkColumn", this.state.showLinkColumn ? "1" : "0");
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

    get recursive() {
        return Boolean(this.props.context?.int_filemanager_recursive);
    }

    sortBy(fieldName) {
        if (this.state.orderBy === fieldName) {
            this.state.orderAsc = !this.state.orderAsc;
        } else {
            this.state.orderBy = fieldName;
            this.state.orderAsc = true;
        }
        this.load(this.state.path);
    }

    columnHeaderClass(fieldName) {
        const classNames = ["align-middle", "o_column_sortable", "position-relative", "cursor-pointer", "opacity-trigger-hover"];
        if (this.state.orderBy === fieldName) {
            classNames.push("table-active");
        }
        return classNames.join(" ");
    }

    sortIconClass(fieldName) {
        if (this.state.orderBy === fieldName) {
            return this.state.orderAsc ? "fa-sort-asc" : "fa-sort-desc";
        }
        return "fa-sort opacity-0 opacity-100-hover";
    }

    async load(path, offset = 0) {
        this.state.loading = true;
        this.state.selected.clear();
        try {
            const res = await rpc("/int_filemanager/list", {
                path,
                recursive: this.recursive,
                domain: this.props.domain || [],
                offset,
                order_by: this.state.orderBy,
                order_dir: this.state.orderAsc ? "asc" : "desc",
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

    onPagerUpdate({ offset }) {
        this.load(this.state.path, offset);
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

    isLocalOfficeCapable(name) {
        return extOf(name) in OFFICE_PROTOCOL;
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

    toViewerFile(entry) {
        const path = this.entryPath(entry);
        const downloadUrl = `/int_filemanager/download?path=${encodeURIComponent(path)}&disposition=inline`;
        const ext = extOf(entry.name);
        const isPdf = ext === "pdf";
        return {
            path,
            name: entry.name,
            downloadUrl,
            isImage: PREVIEWABLE_EXTENSIONS.has(ext) && ext !== "pdf" && ext !== "txt",
            isPdf,
            isText: ext === "txt",
            isViewable: this.isPreviewable(entry.name),
            defaultSource: isPdf
                ? `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(downloadUrl)}#pagemode=none`
                : downloadUrl,
        };
    }

    onPreview(entry) {
        const files = this.state.entries
            .filter((e) => !e.is_dir && this.isPreviewable(e.name))
            .map((e) => this.toViewerFile(e));
        const file = files.find((f) => f.path === this.entryPath(entry));
        this.fileViewer.open(file, files);
    }

    onLinkRecord(entry) {
        this.dialog.add(IntLinkRecordDialog, {
            path: this.entryPath(entry),
            metaId: entry.meta_id,
            onSaved: () => this.load(this.state.path),
        });
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

    async onOpenLocal(entry) {
        const protocol = OFFICE_PROTOCOL[extOf(entry.name)];
        if (!protocol) {
            return;
        }
        try {
            const res = await rpc("/int_filemanager/webdav_token", { path: this.entryPath(entry) });
            // Not further percent-encoded - the "ofe" handler expects the
            // raw URL appended as-is, verified against real Excel 365.
            window.location.href = `${protocol}:ofe|u|${res.url}`;
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

    get singleSelectedEntry() {
        if (this.state.selected.size !== 1) {
            return null;
        }
        const [path] = this.state.selected;
        return this.state.entries.find((entry) => this.entryPath(entry) === path) || null;
    }

    onRenameSelected() {
        const entry = this.singleSelectedEntry;
        if (entry) {
            this.onRename(entry);
        }
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

    get allSelected() {
        return this.state.entries.length > 0 &&
            this.state.entries.every((entry) => this.state.selected.has(this.entryPath(entry)));
    }

    isSelected(entry) {
        return this.state.selected.has(this.entryPath(entry));
    }

    toggleSelect(entry) {
        const path = this.entryPath(entry);
        if (this.state.selected.has(path)) {
            this.state.selected.delete(path);
        } else {
            this.state.selected.add(path);
        }
    }

    toggleSelectAll() {
        if (this.allSelected) {
            this.state.entries.forEach((entry) => this.state.selected.delete(this.entryPath(entry)));
        } else {
            this.state.entries.forEach((entry) => this.state.selected.add(this.entryPath(entry)));
        }
    }

    clearSelection() {
        this.state.selected.clear();
    }

    onBulkDelete() {
        const count = this.state.selected.size;
        this.dialog.add(ConfirmationDialog, {
            title: "Löschen bestätigen",
            body: `${count} ${count === 1 ? "Eintrag" : "Einträge"} wirklich löschen?`,
            confirmLabel: "Löschen",
            confirmClass: "btn-danger",
            confirm: async () => {
                const paths = [...this.state.selected];
                const hadDir = this.state.entries.some(
                    (entry) => this.state.selected.has(this.entryPath(entry)) && entry.is_dir
                );
                const errors = [];
                for (const path of paths) {
                    try {
                        await rpc("/int_filemanager/delete", { path });
                    } catch (e) {
                        errors.push(e.data?.message || e.message);
                    }
                }
                this.load(this.state.path);
                if (hadDir) {
                    this.refreshTree();
                }
                if (errors.length) {
                    this.notification.add(errors.join("\n"), { type: "danger" });
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
    <separator/>
    <filter name="filter_recursive" string="Alle Unterordner" context="{'int_filemanager_recursive': 1}"/>
</search>`;

export class IntFileManagerAction extends Component {
    static template = "int_filemanager.FileManagerAction";
    static components = { WithSearch, IntFileManager };
    static props = ["*"];

    setup() {
        this.searchViewFields = SEARCH_VIEW_FIELDS;
        this.searchViewArch = SEARCH_VIEW_ARCH;
        // Set when opened from a "Verknüpfte Dateien" smart button on another record
        // (int_filemanager.linkable.mixin's action_view_int_filemanager_files) - combined
        // by WithSearch with whatever the user then adds via search facets, same as any
        // regular act_window action.domain.
        this.initialDomain = this.props.action?.params?.domain || [];
        // Linked files can be anywhere in the tree, not necessarily at the root - without
        // this the folder-scoped browsing (current path only) would hide most of them.
        this.initialContext = this.initialDomain.length ? { int_filemanager_recursive: 1 } : {};
    }
}

registry.category("actions").add("int_filemanager_browser", IntFileManagerAction);
