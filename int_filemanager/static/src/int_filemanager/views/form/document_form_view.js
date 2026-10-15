import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { DocumentFormRenderer } from "./document_form_renderer";

export const documentFormView = {
    ...formView,
    Renderer: DocumentFormRenderer,
};

registry.category("views").add("int_filemanager_document_form", documentFormView);
