import { onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { FOLDER_MODEL } from "@int_filemanager/int_filemanager/views/list/document_new_folder";
import {
    DocumentSearchPanel,
    FOLDER_MENU_PASS_ON_GROUP,
} from "@int_filemanager/int_filemanager/views/search_panel/document_search_panel";

const SHARE_MODEL = "int.filemanager.share";

patch(DocumentSearchPanel.prototype, {
    setup() {
        super.setup(...arguments);
        onWillStart(async () => {
            this.canShare = await user.checkAccessRight(SHARE_MODEL, "create");
        });
    },

    /**
     * The item "Share" in the menu of a folder, for those who may make a share.
     * @override
     */
    getFolderMenuItems(folder) {
        const items = super.getFolderMenuItems(folder);
        if (this.canShare) {
            items.push({
                key: "share",
                icon: "fa fa-share-alt",
                description: _t("Share"),
                groupNumber: FOLDER_MENU_PASS_ON_GROUP,
                onSelected: () => this.shareFolder(folder),
            });
        }
        return items;
    },

    /** The dialog of a new share, filled in with the folder (the button of the form does the same). */
    async shareFolder(folder) {
        const action = await this.orm.call(FOLDER_MODEL, "action_share", [[folder.id]]);
        return this.actionService.doAction(action);
    },
});
