import { attachDoubleTap } from "../touch/double_tap";
import { useFrameDocuments } from "./file_viewer_frames_hook";
import { attachPinch, createPanFollower, scrollAfterPinch } from "../touch/pinch";

// Text is not zoomed out: it fits the window as it is.
const MIN_TEXT_SCALE = 1;
const MAX_TEXT_SCALE = 5;

/**
 * Zoom the text of a text file with two fingers by scaling it as laid out, so the lines do not
 * break anew. The browser scrolls with the fingers (scrolling by code was jerky); the code only
 * keeps the point under the fingers in place.
 * @param {Document} doc
 * @returns {function(): void} removes the listeners
 */
function attachTextZoom(doc) {
    const text = doc.querySelector("pre") ?? doc.body;
    const page = doc.scrollingElement;
    let scale = 1;
    text.style.transformOrigin = "0 0";
    // The browser zooms neither the page nor on a double tap; it scrolls (`pan-x pan-y`).
    doc.documentElement.style.touchAction = "pan-x pan-y";

    /** Scale to `wanted`, so that the text point under `point` (client coordinates) stays there. */
    function zoomTo(wanted, point) {
        const next = Math.min(Math.max(wanted, MIN_TEXT_SCALE), MAX_TEXT_SCALE);
        const ratio = next / scale;
        scale = next;
        text.style.transform = scale === 1 ? "" : `scale(${scale})`;
        // The point is measured from the corner of the text, which does not move.
        const corner = text.getBoundingClientRect();
        const left = corner.left + page.scrollLeft;
        const top = corner.top + page.scrollTop;
        const scrollX = scrollAfterPinch(page.scrollLeft - left, point.x, point.x, ratio);
        const scrollY = scrollAfterPinch(page.scrollTop - top, point.y, point.y, ratio);
        page.scrollLeft = left + scrollX;
        page.scrollTop = top + scrollY;
    }

    // The finger that is left after two moves the page, unless the browser scrolls it.
    const follower = createPanFollower(page);
    const detachPinch = attachPinch(doc, {
        onPinch({ factor, x, y }) {
            follower.reset();
            zoomTo(scale * factor, { x, y });
        },
        onPan({ dx, dy }) {
            follower.pan(dx, dy);
        },
    });
    const middle = () => ({ x: page.clientWidth / 2, y: page.clientHeight / 2 });
    const detachDoubleTap = attachDoubleTap(doc, {
        canDoubleTap: () => scale > 1,
        onDoubleTap: () => zoomTo(1, middle()),
    });
    return () => {
        detachPinch();
        detachDoubleTap();
    };
}

/**
 * A double tap on a zoomed PDF resets the zoom (`zoomReset` of the core's PDF viewer). At the
 * opening size it is left alone: it selects a word.
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
 * Zoom in the frames of the file viewer: two fingers zoom a text, a double tap resets the zoom
 * of a text and of a PDF.
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
