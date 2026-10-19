import { useEffect, useRef } from "@odoo/owl";
import { localization } from "@web/core/l10n/localization";
import { useFrameDocuments } from "./file_viewer_frames_hook";
import { attachSwipe } from "../touch/swipe";

const BUTTONS = ".o-FileViewer-header, .o-FileViewer-toolbarButton, .o-FileViewer-navigation";
// The height of the bar a browser draws on a video (px): a finger that starts there sets the
// position of the video and does not turn the page.
const VIDEO_CONTROLS_HEIGHT = 64;

/**
 * Swipe to the next or the previous file in the file viewer, also inside the frames of PDFs
 * and texts, which do not give their touches to the page around them.
 * @param {import("@web/core/file_viewer/file_viewer").FileViewer} viewer
 */
export function useFileViewerSwipe(viewer) {
    const root = useRef("autofocus");

    function onSwipe(direction) {
        const forward = (direction === "left") !== (localization.direction === "rtl");
        if (forward) {
            viewer.next();
        } else {
            viewer.previous();
        }
    }

    function onVideoControls(ev) {
        if (ev.target.tagName !== "VIDEO") {
            return false;
        }
        const barTop = ev.target.getBoundingClientRect().bottom - VIDEO_CONTROLS_HEIGHT;
        return ev.touches[0].clientY > barTop;
    }

    const inFrame = {
        onSwipe,
        canSwipe: () => viewer.props.files.length > 1,
    };
    const onViewer = {
        onSwipe,
        canSwipe: (ev) =>
            viewer.props.files.length > 1 &&
            // A picture that is zoomed in is moved by the finger.
            viewer.state.scale <= 1 &&
            !ev.target.closest(BUTTONS) &&
            !onVideoControls(ev),
    };

    useEffect(
        (el) => el && attachSwipe(el, onViewer),
        () => [root.el]
    );
    useFrameDocuments(viewer, (_frame, doc) => attachSwipe(doc, inFrame));
}
