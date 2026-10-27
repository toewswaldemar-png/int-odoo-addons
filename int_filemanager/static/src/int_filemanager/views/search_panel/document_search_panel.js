import { onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { groupBy } from "@web/core/utils/arrays";
import { useService } from "@web/core/utils/hooks";
import { SearchPanel } from "@web/search/search_panel/search_panel";
import { MOVE_MODEL } from "../drag/document_move";
import {
    FOLDER_MODEL,
    getFoldersSection,
    useFolderRights,
    useNewFolder,
} from "../list/document_new_folder";

const HOVER_DELAY = 700;
const RENAME_ACTION = "int_filemanager.int_filemanager_folder_action_rename";
const MOVE_ACTION = "int_filemanager.int_filemanager_move_folder_action";
// Groups of the menu of a folder (a divider lies between two groups), as the items of the core's
// `ActionMenus` carry a `groupNumber`: what changes the folder, what passes it on or puts it
// elsewhere (a module adds its items there), what ends it.
export const FOLDER_MENU_CHANGE_GROUP = 1;
export const FOLDER_MENU_PASS_ON_GROUP = 2;
export const FOLDER_MENU_END_GROUP = 3;

/**
 * The search panel with folders that take the documents dragged from the list or the cards. The
 * rows do the drag (see `useDocumentDragSource`): the panel marks its folders with
 * `data-drop-folder`, shows the one under the pointer and opens it when the pointer rests on it.
 *
 * A right click on a folder opens its menu, built as the one of a row of the list
 * (`DocumentListContextMenuRenderer`): the core's `Dropdown` is opened by hand, its toggler a point
 * without size moved to the pointer. The items are those of the folder in "Configuration".
 */
export class DocumentSearchPanel extends SearchPanel {
    static components = { ...SearchPanel.components, DropdownItem };
    static subTemplates = {
        ...SearchPanel.subTemplates,
        category: "int_filemanager.SearchPanel.Category",
    };

    setup() {
        super.setup();
        this.drag = useState(this.env.searchModel.drag);
        useEffect(
            (folderId) => {
                if (folderId) {
                    const timer = browser.setTimeout(() => this.openFolder(folderId), HOVER_DELAY);
                    return () => browser.clearTimeout(timer);
                }
            },
            () => [this.drag.over]
        );
        this.anchorRef = useRef("contextMenuAnchor");
        this.menuState = useDropdownState();
        this.menu = useState({ title: "", sections: [] });
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.dialogService = useService("dialog");
        this.newFolder = useNewFolder();
        this.folderRights = useFolderRights();
        onWillStart(async () => {
            this.canMove = await user.checkAccessRight(MOVE_MODEL, "create");
        });
    }

    /** @param {number} folderId */
    openFolder(folderId) {
        const folders = getFoldersSection(this.env.searchModel);
        if (folders?.values.get(folderId)?.childrenIds.length) {
            this.state.expanded[folders.id][folderId] = true;
        }
    }

    /**
     * Opens the menu of a folder at the pointer; the folder of the list stays as it is.
     * @param {MouseEvent} ev
     * @param {Object} section the section of the panel the value belongs to
     * @param {Object} folder the value of the section
     */
    onFolderContextMenu(ev, section, folder) {
        // A small screen has no right click; the other sections keep the menu of the browser.
        if (this.env.isSmall || section.fieldName !== "folder_id") {
            return;
        }
        ev.preventDefault();
        this.menuState.close();
        Object.assign(this.anchorRef.el.style, { left: `${ev.clientX}px`, top: `${ev.clientY}px` });
        this.menu.title = folder.display_name;
        this.menu.sections = Object.values(
            groupBy(this.getFolderMenuItems(folder), (item) => item.groupNumber)
        );
        this.menuState.open();
    }

    /**
     * The items of the menu of a folder. The server checks what the user may do: the items only
     * leave out what the user can never do (a reader may not change a folder).
     * @param {Object} folder the value of the section of the panel
     * @returns {Object[]} `{key, icon, description, groupNumber, onSelected}`
     */
    getFolderMenuItems(folder) {
        const { create, write } = this.folderRights;
        const items = [];
        if (create) {
            items.push({
                key: "new_folder",
                icon: "fa fa-folder",
                description: _t("New subfolder"),
                groupNumber: FOLDER_MENU_CHANGE_GROUP,
                onSelected: () => this.newFolder(folder.id),
            });
        }
        if (write) {
            items.push({
                key: "rename",
                icon: "fa fa-pencil",
                description: _t("Rename"),
                groupNumber: FOLDER_MENU_CHANGE_GROUP,
                onSelected: () => this.renameFolder(folder),
            });
        }
        if (write && this.canMove) {
            items.push({
                key: "move",
                icon: "fa fa-folder-open",
                description: _t("Move to..."),
                groupNumber: FOLDER_MENU_PASS_ON_GROUP,
                onSelected: () => this.moveFolder(folder),
            });
        }
        items.push({
            key: "download",
            icon: "fa fa-download",
            description: _t("Download"),
            groupNumber: FOLDER_MENU_PASS_ON_GROUP,
            onSelected: () => this.downloadFolder(folder),
        });
        if (write) {
            items.push({
                key: "archive",
                icon: "oi oi-archive",
                description: _t("Archive"),
                groupNumber: FOLDER_MENU_END_GROUP,
                onSelected: () => this.archiveFolder(folder),
            });
        }
        return items;
    }

    /** The dialog of the name; the panel does not reload its tree, so the view is restored. */
    renameFolder(folder) {
        return this.actionService.doAction(RENAME_ACTION, {
            props: { resId: folder.id },
            onClose: () => this.actionService.doAction("soft_reload"),
        });
    }

    /** The dialog "Move to..." of the list of folders; it reloads the view when it is done. */
    moveFolder(folder) {
        return this.actionService.doAction(MOVE_ACTION, {
            additionalContext: {
                active_id: folder.id,
                active_ids: [folder.id],
                active_model: FOLDER_MODEL,
            },
        });
    }

    /** The server method refuses at once what cannot work (an archived folder, too many bytes). */
    async downloadFolder(folder) {
        const action = await this.orm.call(FOLDER_MODEL, "action_download", [[folder.id]]);
        return this.actionService.doAction(action);
    }

    /** As the list does it: the dialog first; the folder takes everything below it with it. */
    archiveFolder(folder) {
        this.dialogService.add(ConfirmationDialog, {
            body: _t(
                "Are you sure that you want to archive %(folder)s? The folders and documents in it are archived too.",
                { folder: folder.display_name }
            ),
            confirmLabel: _t("Archive"),
            confirm: async () => {
                await this.orm.call(FOLDER_MODEL, "action_archive", [[folder.id]]);
                await this.actionService.doAction("soft_reload");
            },
            cancel: () => {},
        });
    }
}
