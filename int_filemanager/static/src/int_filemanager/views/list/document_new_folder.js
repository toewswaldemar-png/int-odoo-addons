import { onWillStart, useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

export const FOLDER_MODEL = "int.filemanager.folder";

/** @returns {{create: Boolean, write: Boolean}} what the user may do with folders (a reader may not) */
export function useFolderRights() {
    const rights = useState({ create: false, write: false });
    onWillStart(async () => {
        rights.create = await user.checkAccessRight(FOLDER_MODEL, "create");
        rights.write = await user.checkAccessRight(FOLDER_MODEL, "write");
    });
    return rights;
}

/** @returns {Object|undefined} the folders of the search panel; none where the list has no panel */
export function getFoldersSection(searchModel) {
    const [folders] = searchModel.getSections(
        (section) => section.type === "category" && section.fieldName === "folder_id"
    );
    return folders;
}

/** Opens the "New folder" dialog; the panel does not reload its tree, so the view is restored. */
export function useNewFolder() {
    const actionService = useService("action");
    return (parentId) =>
        actionService.doAction("int_filemanager.int_filemanager_folder_action_new", {
            additionalContext: parentId ? { default_parent_id: parentId } : {},
            onClose: () => actionService.doAction("soft_reload"),
        });
}
