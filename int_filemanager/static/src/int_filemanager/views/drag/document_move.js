import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export const MOVE_MODEL = "int.filemanager.move";
const DOCUMENT_MODEL = "int.filemanager.document";

/**
 * @returns {(resIds: number[], folderId: number, folderName: string) => Promise} puts the
 *      documents into the folder. Nothing is checked here: `write` of the document checks the
 *      target (rights, names in use, company), all or nothing, as in the dialog "Move to...".
 */
export function useMoveDocuments() {
    const orm = useService("orm");
    const action = useService("action");
    const notification = useService("notification");
    return async (resIds, folderId, folderName) => {
        await orm.write(DOCUMENT_MODEL, resIds, { folder_id: folderId });
        notification.add(_t("Moved to %(folder)s", { folder: folderName }), { type: "success" });
        await action.doAction("soft_reload");
    };
}
