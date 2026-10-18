import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { DocumentListController } from "./document_list_controller";
import { DocumentListContextMenuRenderer } from "./document_list_context_menu_renderer";

export const documentListView = {
    ...listView,
    Controller: DocumentListController,
    Renderer: DocumentListContextMenuRenderer,
    buttonTemplate: "int_filemanager.DocumentListView.Buttons",
};

registry.category("views").add("int_filemanager_document_list", documentListView);
