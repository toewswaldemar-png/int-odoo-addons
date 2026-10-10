/** @odoo-module **/

// Folder navigation of the v2 explorer. The folder tree is Odoo's own search-panel category
// on int_filemanager.node.parent_id (see the search view and search_panel.js); this model
// adds what that category cannot do by itself:
//
// - The tree is loaded one level at a time (the server method answers for one parent), so
//   the model loads the sub-folders of a folder when the panel opens it, and the chain of
//   ancestors of a folder that is opened from outside the tree (a list row, F5).
// - The list shows the children of the open folder, or everything below it with
//   "Include subfolders", or the top of what the caller can see at the top. Odoo's category
//   domain would be "child_of" or nothing, so it is replaced.
//
// The folder id is kept in the URL (int_filemanager_folder) so that F5 stays where it was.
import { router } from "@web/core/browser/router";
import { SearchModel } from "@web/search/search_model";

const NODE_MODEL = "int_filemanager.node";
const FOLDER_FIELD = "parent_id";
const FOLDER_URL_KEY = "int_filemanager_folder";
// Odoo rebuilds the URL on every controller mount and drops keys it does not know
// about, unless they are registered as locked.
router.addLockedKey(FOLDER_URL_KEY);

// The name of the marker filter in the search view (no domain of its own).
const RECURSIVE_FILTER_NAME = "filter_search_recursive";

export class IntFilemanagerV2SearchModel extends SearchModel {
    setup(services) {
        super.setup(services);
        const fromUrl = Number(router.current[FOLDER_URL_KEY]);
        // The open folder (false = the top). It is known before the panel has loaded
        // anything, so the first list load already uses it.
        this.folderId = Number.isInteger(fromUrl) && fromUrl > 0 ? fromUrl : false;
    }

    get folderCategory() {
        return this.categories.find((category) => category.fieldName === FOLDER_FIELD);
    }

    /**
     * Opens a folder (false = the top); loads what the panel needs to show it first.
     * @param {number|false} folderId
     */
    async setFolder(folderId) {
        const category = this.folderCategory;
        if (category) {
            await this._ensureFolderLoaded(category, folderId);
            this.toggleCategoryValue(category.id, folderId || false);
        } else {
            this._rememberFolder(folderId);
            this._notify();
        }
    }

    /** The panel (or setFolder) chose a value of a category. */
    toggleCategoryValue(sectionId, valueId) {
        if (this.sections.get(sectionId).fieldName === FOLDER_FIELD) {
            this._rememberFolder(valueId);
        }
        super.toggleCategoryValue(sectionId, valueId);
    }

    /**
     * Loads the sub-folders of a folder into the tree, unless that already happened.
     * @param {number} folderId
     */
    async loadFolderChildren(folderId) {
        const category = this.folderCategory;
        const parent = category.values.get(folderId);
        if (!parent || parent.childrenLoaded) {
            return;
        }
        await this._loadLevel(category, parent);
    }

    /**
     * After something changed in a folder (a new, renamed or moved sub-folder): reads its
     * level again, but only when the tree showed it; false is the top.
     * @param {number|false} folderId
     */
    async reloadFolderLevel(folderId) {
        const category = this.folderCategory;
        const parent = category?.values.get(folderId || false);
        if (!parent || (folderId && !parent.childrenLoaded)) {
            return;
        }
        await this._loadLevel(category, parent);
        this.trigger("update");
    }

    _rememberFolder(folderId) {
        this.folderId = folderId || false;
        // replaceState, not pushState: every folder click updates the URL without adding
        // a browser history entry.
        router.replaceState({ [FOLDER_URL_KEY]: this.folderId || undefined });
    }

    /** Reads the sub-folders of ``parent`` (the top is the value false) into the tree. */
    async _loadLevel(category, parent) {
        const result = await this.orm.call(
            NODE_MODEL,
            "search_panel_select_range",
            [FOLDER_FIELD],
            {
                comodel_domain: parent.id ? [[FOLDER_FIELD, "=", parent.id]] : [],
                context: this.globalContext,
            }
        );
        const ids = [];
        for (const value of result.values) {
            ids.push(value.id);
            // What is known about a folder deeper down survives a reload of its level.
            const known = category.values.get(value.id) || { childrenIds: [] };
            category.values.set(
                value.id,
                Object.assign(known, value, { parentId: parent.id || false })
            );
        }
        if (parent.id) {
            parent.childrenIds = ids;
            parent.has_children = ids.length > 0;
            parent.childrenLoaded = true;
        } else {
            category.rootIds = [false, ...ids];
        }
    }

    /**
     * Makes sure the tree knows a folder, loading the levels of its ancestors from the top
     * down (the server leaves out ancestors the caller may not read).
     * @returns {Promise<boolean>} whether the folder is in the tree now
     */
    async _ensureFolderLoaded(category, folderId) {
        if (!folderId || category.values.has(folderId)) {
            return true;
        }
        const chain = await this.orm.call(NODE_MODEL, "breadcrumb", [folderId]);
        if (!chain.length || chain.at(-1).id !== folderId) {
            return false;
        }
        for (const crumb of chain.slice(0, -1)) {
            await this.loadFolderChildren(crumb.id);
        }
        return category.values.has(folderId);
    }

    /**
     * Odoo calls this with the top level whenever its cached answer was replaced by a
     * changed one, long after the user opened some folders: what was loaded below the top
     * and the open folder must survive that.
     */
    _createCategoryTree(sectionId, result) {
        const category = this.sections.get(sectionId);
        if (category.fieldName !== FOLDER_FIELD) {
            super._createCategoryTree(sectionId, result);
            return;
        }
        const known = new Map(category.values);
        super._createCategoryTree(sectionId, result);
        for (const [id, value] of known) {
            const fresh = category.values.get(id);
            if (!id) {
                continue;
            }
            if (!fresh) {
                category.values.set(id, value);
            } else if (value.childrenLoaded) {
                fresh.childrenIds = value.childrenIds;
                fresh.childrenLoaded = true;
            }
        }
        category.activeValueId = this.folderId;
    }

    /** At startup: the folder from the URL must be in the tree, or the top is opened. */
    async _fetchCategories(categories) {
        await super._fetchCategories(categories);
        const category = this.folderCategory;
        if (!category || !categories.includes(category)) {
            return;
        }
        if (this.folderId && !(await this._ensureFolderLoaded(category, this.folderId))) {
            // Gone, or not readable any more.
            this._rememberFolder(false);
            this._notify();
        }
        category.activeValueId = this.folderId;
    }

    _isRecursive() {
        const filterActive = this.query.some(
            (element) => this.searchItems[element.searchItemId]?.name === RECURSIVE_FILTER_NAME
        );
        return filterActive || Boolean(this.globalContext.int_filemanager_recursive);
    }

    /** The domain of the open folder; Odoo's own would be "child_of" or nothing. */
    _getCategoryDomain(excludedCategoryId) {
        const category = this.folderCategory;
        const domain = super._getCategoryDomain(category ? category.id : excludedCategoryId);
        if (!category || category.id === excludedCategoryId) {
            return domain;
        }
        const folderId = this.folderId;
        if (this._isRecursive()) {
            // Everything below the folder, not the folder itself.
            return folderId
                ? [...domain, ["id", "child_of", folderId], ["id", "!=", folderId]]
                : domain;
        }
        return [
            ...domain,
            folderId ? [FOLDER_FIELD, "=", folderId] : ["is_visible_top", "=", true],
        ];
    }
}
