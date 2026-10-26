import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { DocumentListController } from "@int_filemanager/int_filemanager/views/list/document_list_controller";

patch(DocumentListController.prototype, {
    /**
     * The record whose documents the list shows, when the action comes from its button (the keys
     * of the context are set by `action_open_documents`): the files are linked to it, by the
     * right to change the record, not to a folder.
     * @override
     */
    get uploadTarget() {
        const context = this.props.context || {};
        if (!context.int_filemanager_link_model) {
            return super.uploadTarget;
        }
        return {
            message: _t("Drop the files to attach them to %(record)s", {
                record: context.int_filemanager_link_name || "",
            }),
            appendTo: (formData) => {
                formData.append("link_model", context.int_filemanager_link_model);
                formData.append("link_id", context.int_filemanager_link_id);
            },
        };
    },
});
