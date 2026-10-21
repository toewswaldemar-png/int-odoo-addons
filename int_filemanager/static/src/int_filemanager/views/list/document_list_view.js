import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { DocumentSearchModel } from "../document_search_model";
import { DocumentListController } from "./document_list_controller";
import { DocumentListContextMenuRenderer } from "./document_list_context_menu_renderer";

export const documentListView = {
    ...listView,
    SearchModel: DocumentSearchModel,
    Controller: DocumentListController,
    Renderer: DocumentListContextMenuRenderer,
    buttonTemplate: "int_filemanager.DocumentListView.Buttons",
};

registry.category("views").add("int_filemanager_document_list", documentListView);
