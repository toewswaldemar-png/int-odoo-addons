import { useEffect, useRef } from "@odoo/owl";

/**
 * Calls `attach(frame, document)` for each iframe of the viewer, again after each load; what it
 * returns undoes it when the file changes or the viewer closes.
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
