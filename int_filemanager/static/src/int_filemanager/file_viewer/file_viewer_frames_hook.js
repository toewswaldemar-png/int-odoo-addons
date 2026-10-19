import { useEffect, useRef } from "@odoo/owl";

/**
 * Call `attach` with each iframe of the file viewer and its document, and undo it when the file
 * changes or the viewer closes. A frame gets a new document at every load, so `attach` is
 * called again after each one.
 * @param {import("@web/core/file_viewer/file_viewer").FileViewer} viewer
 * @param {function(HTMLIFrameElement, Document): (function(): void)|void} attach what it returns
 *      is called to undo it
 */
export function useFrameDocuments(viewer, attach) {
    const root = useRef("autofocus");
    useEffect(
        () => {
            const removers = [];
            for (const frame of root.el?.querySelectorAll("iframe") ?? []) {
                let detach = () => {};
                const attachToDocument = () => {
                    detach();
                    // Null if the page in the frame is of another origin.
                    const doc = frame.contentDocument;
                    detach = (doc && attach(frame, doc)) || (() => {});
                };
                frame.addEventListener("load", attachToDocument);
                attachToDocument();
                removers.push(() => {
                    frame.removeEventListener("load", attachToDocument);
                    detach();
                });
            }
            return () => removers.forEach((remove) => remove());
        },
        () => [viewer.state.file]
    );
}
