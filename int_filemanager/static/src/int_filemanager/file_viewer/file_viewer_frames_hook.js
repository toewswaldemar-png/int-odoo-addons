import { useEffect, useRef } from "@odoo/owl";

/**
 * Do something with the document of each frame (iframe) of the file viewer, and undo it when
 * the file changes or the viewer closes. The viewer shows PDFs and texts in a frame, which does
 * not give its touches (or anything else) to the page around it; but a frame of the same
 * origin can be reached. A frame gets a new document with every file it loads, so `attach` is
 * called again after each load (and at once, for a document that is there).
 *
 * To be called in `setup` of the viewer, which needs `state.file`: the core's `FileViewer`
 * has it.
 * @param {import("@web/core/file_viewer/file_viewer").FileViewer} viewer
 * @param {function(HTMLIFrameElement, Document): (function(): void)|void} attach called with
 *      the frame and its document; what it returns is called to undo it
 */
export function useFrameDocuments(viewer, attach) {
    // The element of the template that the core's viewer gives the focus to.
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
