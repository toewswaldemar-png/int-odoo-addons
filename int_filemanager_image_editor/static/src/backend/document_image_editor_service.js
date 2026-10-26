import { LazyComponent } from "@web/core/assets";
import { routerBus } from "@web/core/browser/router";
import { registry } from "@web/core/registry";

export const IMAGE_EDITOR_BUNDLE = "int_filemanager_image_editor.assets_image_editor";
const IMAGE_EDITOR = "int_filemanager_image_editor.DocumentImageEditor";
const COMPONENT_ID = "int_filemanager_image_editor.editor";

/**
 * Opens the image editor over the page. The editor and its library (Fabric) are in a bundle of
 * their own that is loaded at the first call, as the core does it for its builders.
 *
 * It is a service so that the viewer finds it without being told (the service
 * `int_filemanager.image_editor` is the extension point of the filemanager): where this module is
 * not installed, and on the page of the guests, there is none and so no "Edit" button.
 */
export const imageEditorService = {
    start() {
        const mainComponents = registry.category("main_components");

        function close() {
            mainComponents.remove(COMPONENT_ID);
        }

        /** @param {Object} file the picture to draw on, a `DocumentFile` */
        function open(file) {
            close();
            mainComponents.add(COMPONENT_ID, {
                Component: LazyComponent,
                props: {
                    Component: IMAGE_EDITOR,
                    bundle: IMAGE_EDITOR_BUNDLE,
                    props: { file, close },
                },
            });
        }

        // The editor covers the page: a way back or on in the history takes it away.
        routerBus.addEventListener("ROUTE_CHANGE", close);
        return { open, close };
    },
};

registry.category("services").add("int_filemanager.image_editor", imageEditorService);
