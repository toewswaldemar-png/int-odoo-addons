/** @odoo-module **/

// Folder navigation of the explorer controller: which folder is open, the breadcrumbs
// (desktop: Odoo's own; mobile: an own header), the chatter panel. The folder tree is the
// search panel (search_panel.js), which Odoo lays out and resizes itself. Mixed into the
// list and the kanban controller alike (JS has no multiple inheritance: a function taking
// the base class and returning the extended one).
//
// The ONLY writer of the open folder is env.searchModel.setFolder(): the list model reloads
// by itself when the search model notifies, a second writer would race it.
import {
    onMounted,
    onPatched,
    onWillDestroy,
    useExternalListener,
    useRef,
    useState,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";

export const NODE_MODEL = "int_filemanager.node";

export const navigationMixin = (Base) =>
    class extends Base {
        setup() {
            super.setup();
            this.orm = useService("orm");
            this.dialog = useService("dialog");
            this.notification = useService("notification");
            this.actionService = useService("action");

            // The chatter opens as a fixed panel over the right side, below the toolbar row
            // (topPx is measured: the search bar can wrap to two lines).
            this.chatterState = useState({ open: false, topPx: 0 });
            this.folderCrumbs = [];
            this._crumbChains = new Map();
            this._crumbRequest = 0;
            this._destroyed = false;
            onWillDestroy(() => {
                this._destroyed = true;
            });
            this.mobileBreadcrumbState = useState({ collapsed: false });
            this.mobileBreadcrumbNavRef = useRef("mobileBreadcrumbNav");

            useExternalListener(window, "resize", () => this._measureChatterTop());

            // Whatever was on the breadcrumb stack when this controller was created (the
            // action itself, or a calling record) stays; folder levels are appended after it.
            this.rootBreadcrumbCount = this.env.config.breadcrumbs.length;
            // Odoo's own onSelected on the root crumb restores the same controller, which does
            // not leave a folder - so it must also go back to the top.
            const ownRootCrumb = this.env.config.breadcrumbs[this.rootBreadcrumbCount - 1];
            if (ownRootCrumb) {
                const nativeOnSelected = ownRootCrumb.onSelected;
                ownRootCrumb.onSelected = () => {
                    nativeOnSelected?.();
                    this.env.searchModel.setFolder(false);
                };
            }

            // Every view switch creates a fresh controller with a freshly computed breadcrumb
            // array, so each one has to subscribe and rebuild its folder crumbs itself.
            useBus(this.env.searchModel, "update", () => this.updateBreadcrumbs());
            // Not synchronously in setup(): Odoo's breadcrumb template needs controller.state for
            // every crumb but the last, and that is only set in the controller's own onMounted;
            // pushing folder crumbs first made the root crumb a non-last one and crashed.
            onMounted(() => {
                this.updateBreadcrumbs();
                this._measureChatterTop();
            });
            onPatched(() => {
                this._checkMobileBreadcrumbOverflow();
                this._measureChatterTop();
            });
        }

        get currentFolderId() {
            return this.env.searchModel.folderId;
        }

        /** Uploads and new folders need a folder to put them in: the top is not one. */
        get canCreateHere() {
            return Boolean(this.currentFolderId);
        }

        get createTooltip() {
            return this.canCreateHere ? undefined : _t("Open a folder first");
        }

        get chatterTitle() {
            return this.chatterRecord ? this.chatterRecord.data.name : _t("Notes / activities");
        }

        onToggleChatterPanel() {
            this.chatterState.open = !this.chatterState.open;
        }

        _measureChatterTop() {
            const contentEl = this.rootRef.el?.querySelector(".o_content");
            this.chatterState.topPx = contentEl
                ? Math.round(contentEl.getBoundingClientRect().top)
                : 0;
        }

        /** The first selected row: the chatter shows this one. */
        get chatterRecord() {
            return this.model.root.selection[0] || null;
        }

        // ---------------------------------------------------------------- breadcrumbs

        /**
         * [{id, name}] from the top of what the caller can see down to a folder. Cached: the
         * common step is one level deeper than a chain already known.
         */
        async _chainFor(folderId) {
            if (this._crumbChains.has(folderId)) {
                return this._crumbChains.get(folderId);
            }
            const chain = await this.orm.call(NODE_MODEL, "breadcrumb", [folderId]);
            this._crumbChains.set(folderId, chain);
            return chain;
        }

        /** Names and parents change: forget everything known about the chains. */
        forgetCrumbs() {
            this._crumbChains.clear();
        }

        async updateBreadcrumbs() {
            // A new folder is first shown in full again; the mobile row re-measures and
            // collapses if it does not fit.
            this.mobileBreadcrumbState.collapsed = false;
            const folderId = this.currentFolderId;
            const request = ++this._crumbRequest;
            const crumbs = this.env.config.breadcrumbs;
            crumbs.length = this.rootBreadcrumbCount;
            this.folderCrumbs = [];
            if (!folderId) {
                return;
            }
            let chain = [];
            try {
                chain = await this._chainFor(folderId);
            } catch {
                return; // The folder vanished: the list shows the error itself
            }
            if (request !== this._crumbRequest || this._destroyed) {
                return; // The user has moved on (or left) while this was loading
            }
            for (const { id, name } of chain) {
                const crumb = {
                    jsId: `int_filemanager_crumb_${id}`,
                    name,
                    isFormView: false,
                    url: "#",
                    onSelected: () => this.env.searchModel.setFolder(id),
                };
                this.folderCrumbs.push(crumb);
                // Only on the desktop in Odoo's own array: on a phone the own header replaces
                // it, and a second entry would show a back arrow and duplicate the folder name.
                if (!this.env.isSmall) {
                    crumbs.push(crumb);
                }
            }
            // These arrays are plain, not reactive: ask for a render now that they changed.
            this.render(true);
        }

        /**
         * Opens a folder from a row, seeding the crumb chain from what is already known so the
         * breadcrumb does not wait for the server.
         */
        openFolder(record) {
            const known = this._crumbChains.get(this.currentFolderId) || [];
            if (!this._crumbChains.has(record.resId)) {
                this._crumbChains.set(record.resId, [
                    ...known,
                    { id: record.resId, name: record.data.name },
                ]);
            }
            this.env.searchModel.setFolder(record.resId);
        }

        get mobileBreadcrumbs() {
            return [
                {
                    jsId: "int_filemanager_crumb_root",
                    name: _t("All folders"),
                    onSelected: () => this.onMobileGoHome(),
                },
                ...this.folderCrumbs,
            ];
        }

        onMobileGoHome() {
            this.env.searchModel.setFolder(false);
        }

        // Does the fully rendered crumb row overflow? Then it collapses to first / "…" / last.
        // Measured, not a fixed number of segments, so a few long names count like many short
        // ones.
        _checkMobileBreadcrumbOverflow() {
            if (this.mobileBreadcrumbState.collapsed) {
                return;
            }
            const el = this.mobileBreadcrumbNavRef.el;
            if (el && el.scrollWidth > el.clientWidth + 1) {
                this.mobileBreadcrumbState.collapsed = true;
            }
        }

        /** After anything that changes folder contents: refresh the tree level being shown. */
        async refreshTree() {
            await this.env.searchModel.reloadFolderLevel(this.currentFolderId);
        }
    };
