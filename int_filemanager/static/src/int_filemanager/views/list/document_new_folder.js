import { useService } from "@web/core/utils/hooks";

/**
 * The folders of the search panel of the list.
 * @param {Object} searchModel
 * @returns {Object|undefined} undefined where the list has no panel (the documents of a record)
 */
export function getFoldersSection(searchModel) {
    const [folders] = searchModel.getSections(
        (section) => section.type === "category" && section.fieldName === "folder_id"
    );
    return folders;
}

/**
 * "New folder": opens the dialog of the action (name and parent folder). The panel does not
 * reload its tree by itself, so the view is restored afterwards.
 * @returns {(parentId: Number|false) => Promise} opens the dialog; the folder `parentId` is the
 *      default of the parent, none makes a folder of the top level
 */
export function useNewFolder() {
    const actionService = useService("action");
    return (parentId) =>
        actionService.doAction("int_filemanager.int_filemanager_folder_action_new", {
            additionalContext: parentId ? { default_parent_id: parentId } : {},
            onClose: () => actionService.doAction("soft_reload"),
        });
}
