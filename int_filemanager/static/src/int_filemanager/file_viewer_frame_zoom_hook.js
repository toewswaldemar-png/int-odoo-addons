import { attachDoubleTap } from "./double_tap";
import { useFrameDocuments } from "./file_viewer_frames_hook";
import { attachPinch, scrollAfterPinch } from "./pinch";

// How far a text may be zoomed in (a factor). It is not zoomed out: it fits the window as it is.
const MIN_TEXT_SCALE = 1;
const MAX_TEXT_SCALE = 5;

/**
 * Two fingers zoom the text of a text file like a picture: the text is enlarged as it was laid
 * out, the lines do not break anew (they would, if the letters were made larger, and
 * everything would move). What does not fit the window is reached by scrolling, and the text
 * goes along with the fingers while they move (it is scrolled so that what was under the
 * fingers stays under them). A double tap sets the size back. A new file has a new document,
 * so it opens at its own size.
 * @param {Document} doc
 * @returns {function(): void} removes the listeners
 */
function attachTextZoom(doc) {
    const text = doc.querySelector("pre") ?? doc.body;
    const page = doc.scrollingElement;
    let scale = 1;
    // The corner that stays where it is when the text is scaled.
    text.style.transformOrigin = "0 0";
    // A double tap is ours (the browser would zoom the page); the pinch is taken below.
    doc.documentElement.style.touchAction = "manipulation";

    /**
     * Scale the text to `wanted` (within the limits), so that the point of it that was at
     * `previous` is at `point` after (client coordinates).
     */
    function zoomTo(wanted, previous, point) {
        const next = Math.min(Math.max(wanted, MIN_TEXT_SCALE), MAX_TEXT_SCALE);
        const ratio = next / scale;
        scale = next;
        text.style.transform = scale === 1 ? "" : `scale(${scale})`;
        // The fingers are measured from the corner of the text, which does not move.
        const corner = text.getBoundingClientRect();
        const left = corner.left + page.scrollLeft;
        const top = corner.top + page.scrollTop;
        const scrollX = scrollAfterPinch(page.scrollLeft - left, previous.x, point.x, ratio);
        const scrollY = scrollAfterPinch(page.scrollTop - top, previous.y, point.y, ratio);
        page.scrollLeft = left + scrollX;
        page.scrollTop = top + scrollY;
    }

    // With `preventDefault` the browser does not scroll or zoom by itself while two fingers
    // are down, nor with the finger that is left: the text is scrolled here.
    const detachPinch = attachPinch(doc, {
        preventDefault: true,
        onPan({ dx, dy }) {
            page.scrollLeft -= dx;
            page.scrollTop -= dy;
        },
        onPinch({ factor, x, y, previous }) {
            zoomTo(scale * factor, previous, { x, y });
        },
    });
    // Back to the size as it is, about what is in the middle of the window.
    const middle = () => ({ x: page.clientWidth / 2, y: page.clientHeight / 2 });
    const detachDoubleTap = attachDoubleTap(doc, {
        canDoubleTap: () => scale > 1,
        onDoubleTap: () => zoomTo(1, middle(), middle()),
    });
    return () => {
        detachPinch();
        detachDoubleTap();
    };
}

/**
 * A double tap on a PDF that is zoomed sets its zoom back, with the way the PDF viewer of the
 * core has for it (`zoomReset`: the size it opens at). A PDF at that size is left alone: a
 * double tap selects a word there.
 * @param {HTMLIFrameElement} frame
 * @param {Document} doc
 * @returns {function(): void} removes the listeners
 */
function attachPdfZoomReset(frame, doc) {
    const viewer = () => frame.contentWindow?.PDFViewerApplication?.pdfViewer;
    return attachDoubleTap(doc, {
        canDoubleTap: () => viewer() && viewer().currentScaleValue !== "auto",
        onDoubleTap: () => {
            frame.contentWindow.PDFViewerApplication.zoomReset();
            doc.getSelection()?.removeAllRanges();
        },
    });
}

/**
 * Zoom in the frames of the file viewer: a text is zoomed with two fingers, and a double tap
 * sets the zoom of a text and of a PDF back. The viewer zooms pictures itself
 * (`DocumentFileViewer`), a PDF is zoomed by its own viewer, and a video has no zoom.
 *
 * To be called in `setup` of the viewer, which needs `state.file`: the core's `FileViewer` has
 * it.
 * @param {import("@web/core/file_viewer/file_viewer").FileViewer} viewer
 */
export function useFileViewerFrameZoom(viewer) {
    useFrameDocuments(viewer, (frame, doc) => {
        const { file } = viewer.state;
        if (file.isText) {
            return attachTextZoom(doc);
        }
        if (file.isPdf) {
            return attachPdfZoomReset(frame, doc);
        }
    });
}
