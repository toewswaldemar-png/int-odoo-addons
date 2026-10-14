import { useEffect, useRef } from "@odoo/owl";
import { localization } from "@web/core/l10n/localization";
import { useFrameDocuments } from "./file_viewer_frames_hook";
import { attachSwipe } from "./swipe";

// What a swipe must not start on: the buttons of the viewer (the arrows, the toolbar, the
// header) are for the finger to press.
const BUTTONS = ".o-FileViewer-header, .o-FileViewer-toolbarButton, .o-FileViewer-navigation";
// The height of the bar a browser draws on a video (px): a finger that starts there sets the
// position of the video and does not turn the page.
const VIDEO_CONTROLS_HEIGHT = 64;

/**
 * Swipe to the next or the previous file in the file viewer: to the left for the next, to the
 * right for the previous (the other way round in a language written from right to left). It is
 * the swipe of the pictures of a phone, for every type of file the viewer shows.
 *
 * The viewer has a part of its own for the touch of a picture (zoom with two fingers, move
 * with one), and it shows PDFs and texts in a frame, which does not give its touches to the
 * page around it. So the swipe is watched on the viewer and inside each frame
 * (`useFrameDocuments`). A picture that is zoomed in, or a page that scrolls to the
 * sides, keeps the finger for itself (see `attachSwipe`).
 *
 * To be called in `setup` of the viewer, which needs `next`, `previous`, `props.files` and
 * `state` with `file` and `scale`: the core's `FileViewer` has them.
 * @param {import("@web/core/file_viewer/file_viewer").FileViewer} viewer
 */
export function useFileViewerSwipe(viewer) {
    // The element of the template that the core's viewer gives the focus to.
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
