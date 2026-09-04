/** @odoo-module **/

// EXPERIMENT (branch experiment/native-listview): does a real Odoo list view,
// bound directly to int_filemanager.file, work well as a file browser? Only
// override needed for navigation: clicking a folder row reloads the same list
// with a new domain instead of opening a (non-existent) form view - see
// ListRenderer's onCellClicked -> this.props.openRecord(record) in
// list_renderer.js, which comes from ListController.openRecord
// (list_controller.js). Sort, optional columns incl. Properties splitting,
// pager, breadcrumbs are untouched native ListView behaviour.
//
// Mutations (mkdir/rename/delete/upload/link) deliberately keep calling the
// same /int_filemanager/* JSON-RPC routes the old custom UI
// (filemanager_action.js) uses, instead of native type="object" buttons
// bound to model methods. Those routes already run authz.require() /
// authz.require_subtree_deletable() / authz.require_rename_or_move_allowed()
// server-side (controllers/main.py) - a model method reached via a native
// object-button would NOT get those checks automatically and would have to
// repeat them explicitly (see docs/int_filemanager_native_ui.md, section
// "Sicherheitsrelevanter Stolperstein"). Routing through rpc() sidesteps
// that duplication risk entirely: there is exactly one place (the
// controller) that enforces access.
import { onWillUnmount, useRef } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useBus, useService } from "@web/core/utils/hooks";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { IntTextInputDialog } from "./text_input_dialog";
import { IntLinkRecordDialog } from "./link_record_dialog";

const PREVIEWABLE_EXTENSIONS = new Set([
    "pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "txt",
]);

function extOf(name) {
    const i = name.lastIndexOf(".");
    return i === -1 ? "" : name.slice(i + 1).toLowerCase();
}

function isPreviewable(name) {
    return PREVIEWABLE_EXTENSIONS.has(extOf(name));
}

export class IntFilemanagerListController extends ListController {
    static template = "int_filemanager.ListView";

    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.fileUpload = useService("file_upload");
        this.busService = useService("bus_service");
        this.fileViewer = useFileViewer();
        this.fileInput = useRef("fileInput");

        this.currentPath = "";
        // Everything already on the stack when this controller was created (normally
        // just the "Dateimanager (nativ, Test)" action entry itself) stays as-is; folder
        // levels get appended after it. Breadcrumbs.xml always renders the LAST array
        // entry as the current (bold, non-clickable) one and everything before it as a
        // real link - so no special-casing needed for "which crumb is active".
        this.rootBreadcrumbCount = this.env.config.breadcrumbs.length;

        useBus(this.fileUpload.bus, "FILE_UPLOAD_LOADED", (ev) => {
            if (ev.detail.upload.id === this.pendingUploadId) {
                this.reload();
            }
        });
        // Reload when anything changes the index server-side, whether from this tab
        // (mutations below) or elsewhere (another tab, the filesystem watcher).
        // Debounced since a bulk change (e.g. a large folder copied in) fires one
        // notification per touched entry. Same pattern as filemanager_action.js.
        this._onFilemanagerChange = () => {
            clearTimeout(this._reloadTimeout);
            this._reloadTimeout = setTimeout(() => this.reload(), 800);
        };
        this.busService.addChannel("int_filemanager");
        this.busService.subscribe("int_filemanager.change", this._onFilemanagerChange);
        onWillUnmount(() => {
            clearTimeout(this._reloadTimeout);
            this.busService.unsubscribe("int_filemanager.change", this._onFilemanagerChange);
        });
    }

    async openRecord(record) {
        if (record.data.is_dir) {
            await this.goToFolder(record.data.path);
            return;
        }
        if (isPreviewable(record.data.name)) {
            this.onPreview(record);
            return;
        }
        window.open(`/int_filemanager/download?path=${encodeURIComponent(record.data.path)}`, "_blank");
    }

    async goToFolder(path) {
        this.currentPath = path;
        await this.reload();
        this.updateBreadcrumbs(path);
    }

    async reload() {
        // this.props.domain trägt bei, was Suchleiste/SearchPanel gerade beisteuern (z.B.
        // eine parent_id-Ordnerbaum-Auswahl) - ANDen statt ersetzen, sonst würde jeder
        // Zeilenklick/jede Mutation eine aktive SearchPanel-Auswahl wieder verwerfen.
        // UNGETESTET: ob Klick auf einen SearchPanel-Ordnerknoten currentPath/Breadcrumbs
        // seinerseits nachzieht, ist noch offen - die beiden Navigationswege (Zeilenklick
        // über folder_path, SearchPanel über parent_id) sind bislang nicht gegenseitig
        // synchronisiert.
        const domain = [...(this.props.domain || []), ["folder_path", "=", this.currentPath || false]];
        await this.model.load({ domain });
    }

    updateBreadcrumbs(path) {
        const crumbs = this.env.config.breadcrumbs;
        crumbs.length = this.rootBreadcrumbCount;
        let acc = "";
        for (const part of path ? path.split("/").filter(Boolean) : []) {
            acc = acc ? `${acc}/${part}` : part;
            const target = acc;
            crumbs.push({
                jsId: `int_filemanager_crumb_${target}`,
                name: part,
                isFormView: false,
                url: "#",
                onSelected: () => this.goToFolder(target),
            });
        }
    }

    // -----------------------------------------------------------------
    // preview
    // -----------------------------------------------------------------

    toViewerFile(record) {
        const path = record.data.path;
        const downloadUrl = `/int_filemanager/download?path=${encodeURIComponent(path)}&disposition=inline`;
        const ext = extOf(record.data.name);
        const isPdf = ext === "pdf";
        return {
            path,
            name: record.data.name,
            downloadUrl,
            isImage: PREVIEWABLE_EXTENSIONS.has(ext) && ext !== "pdf" && ext !== "txt",
            isPdf,
            isText: ext === "txt",
            isViewable: isPreviewable(record.data.name),
            defaultSource: isPdf
                ? `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(downloadUrl)}#pagemode=none`
                : downloadUrl,
        };
    }

    onPreview(record) {
        const files = this.model.root.records
            .filter((r) => !r.data.is_dir && isPreviewable(r.data.name))
            .map((r) => this.toViewerFile(r));
        const file = files.find((f) => f.path === record.data.path);
        this.fileViewer.open(file, files);
    }

    // -----------------------------------------------------------------
    // mutations - all via rpc() against the existing authz-checked routes
    // -----------------------------------------------------------------

    onNewFolder() {
        this.dialog.add(IntTextInputDialog, {
            title: _t("Neuer Ordner"),
            label: _t("Name des neuen Ordners"),
            confirmLabel: _t("Anlegen"),
            confirm: async (name) => {
                try {
                    await rpc("/int_filemanager/mkdir", { path: this.currentPath, name });
                    await this.reload();
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
        // Fire-and-forget like filemanager_action.js: completion/errors surface via the
        // file_upload service's bus events (FILE_UPLOAD_LOADED above, FILE_UPLOAD_ERROR
        // shows its own toast automatically).
        const upload = await this.fileUpload.upload("/int_filemanager/upload", files, {
            buildFormData: (formData) => formData.append("path", this.currentPath),
        });
        this.pendingUploadId = upload.id;
    }

    onRename(record) {
        this.dialog.add(IntTextInputDialog, {
            title: _t("Umbenennen"),
            label: _t("Neuer Name"),
            value: record.data.name,
            confirmLabel: _t("Umbenennen"),
            confirm: async (name) => {
                if (name === record.data.name) {
                    return;
                }
                try {
                    await rpc("/int_filemanager/rename", { path: record.data.path, new_name: name });
                    await this.reload();
                } catch (e) {
                    this.notification.add(e.data?.message || e.message, { type: "danger" });
                }
            },
        });
    }

    onLinkRecord(record) {
        this.dialog.add(IntLinkRecordDialog, {
            path: record.data.path,
            metaId: record.resId,
            onSaved: () => this.reload(),
        });
    }

    onDeleteSelected() {
        const records = this.model.root.selection;
        const count = records.length;
        this.dialog.add(ConfirmationDialog, {
            title: _t("Löschen bestätigen"),
            body: _t("%s wirklich löschen?", count === 1 ? _t("1 Eintrag") : _t("%s Einträge", count)),
            confirmLabel: _t("Löschen"),
            confirmClass: "btn-danger",
            confirm: async () => {
                const errors = [];
                for (const record of records) {
                    try {
                        await rpc("/int_filemanager/delete", { path: record.data.path });
                    } catch (e) {
                        errors.push(e.data?.message || e.message);
                    }
                }
                await this.reload();
                if (errors.length) {
                    this.notification.add(errors.join("\n"), { type: "danger" });
                }
            },
        });
    }

    // -----------------------------------------------------------------
    // selection-dependent action menu ("Aktionen" dropdown) - replaces the
    // native export/duplicate/archive/unarchive entries, none of which are
    // meaningful for filesystem-backed records (native "delete" stays
    // disabled via delete="false" in the arch: ORM unlink() would only
    // remove the index row, not the file on disk).
    // -----------------------------------------------------------------

    getStaticActionMenuItems() {
        const selection = this.model.root.selection;
        return {
            int_link: {
                isAvailable: () => selection.length === 1,
                sequence: 10,
                icon: "fa fa-link",
                description: _t("Verknüpfen"),
                callback: () => this.onLinkRecord(selection[0]),
            },
            int_rename: {
                isAvailable: () => selection.length === 1,
                sequence: 20,
                icon: "fa fa-pencil",
                description: _t("Umbenennen"),
                callback: () => this.onRename(selection[0]),
            },
            int_delete: {
                isAvailable: () => selection.length > 0,
                sequence: 90,
                icon: "fa fa-trash-o",
                class: "text-danger",
                description: _t("Löschen"),
                callback: () => this.onDeleteSelected(),
            },
        };
    }
}

registry.category("views").add("int_filemanager_list", {
    ...listView,
    Controller: IntFilemanagerListController,
});
