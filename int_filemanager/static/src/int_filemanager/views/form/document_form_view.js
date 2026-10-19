import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { DocumentFormController } from "./document_form_controller";

export const documentFormView = {
    ...formView,
    Controller: DocumentFormController,
};

registry.category("views").add("int_filemanager_document_form", documentFormView);
