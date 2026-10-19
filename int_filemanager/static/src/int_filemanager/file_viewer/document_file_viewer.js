import { onWillDestroy, useEffect, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { FileViewer } from "@web/core/file_viewer/file_viewer";
import { registry } from "@web/core/registry";
import { attachDoubleTap } from "../touch/double_tap";
import { useFileViewerFrameZoom } from "./file_viewer_frame_zoom_hook";
import { useFileViewerSwipe } from "./file_viewer_swipe_hook";
import { createVelocityTracker, FLING_EASING, flingPlan } from "../touch/momentum";

// The zoom of the PDF viewer the core ships (`addons/web/static/lib/pdfjs/web/viewer.js`):
// the same range, the same steps, the zoom around the point under the fingers or the pointer.
const MIN_SCALE = 0.1;
const MAX_SCALE = 10;
// `DEFAULT_SCALE_DELTA`: one step of the buttons and keys, and one tick of the wheel.
const SCALE_DELTA = 1.1;
// `PIXELS_PER_LINE_SCALE`: a wheel that reports pixels makes one tick per this many.
const PIXELS_PER_TICK = 30;
const TOUCH_EVENTS = ["pointerdown", "pointermove", "pointerup", "pointercancel"];
// How long the image may slide while it turns (ms): a little more than its transition (0.2 s).
const ROTATE_ANIMATION_TIME = 300;

let nextViewerId = 1;

/**
 * @param {Number} value
 * @param {Number} limit
 * @returns {Number} `value`, but between `-limit` and `limit`
 */
function keep(value, limit) {
    return Math.min(Math.max(value, -limit), limit);
}

/**
 * The core's file viewer with the zoom of the PDF viewer, which the core's own image zoom
 * lacks: two fingers (or the wheel, the buttons) zoom around the point they are at, one finger
 * moves the image, and it cannot be moved off the screen. The core's viewer knows the mouse
 * only (wheel, buttons, drag) and zooms about the middle of the screen, so a touch screen
 * cannot zoom an image at all; a PDF can, it is shown by the browser. The mouse keeps the
 * core's ways (wheel, buttons, keys, drag); the state is the core's own (`state.scale`,
 * `translate`), the fingers only drive it. Two fingers zoom and take the image along when they
 * move; a finger that is left goes on moving it, and the image glides on when it lifts; a
 * double tap sets the zoom back. One finger
 * swipes to the next or the previous file, for every type of file (`useFileViewerSwipe`); a
 * text zooms with two fingers in its frame (`useFileViewerFrameZoom`).
 */
export class DocumentFileViewer extends FileViewer {
    setup() {
        super.setup();
        this.minScale = MIN_SCALE;
        useFileViewerSwipe(this);
        useFileViewerFrameZoom(this);
        /** @type {Map<number, {x: number, y: number}>} the fingers on the image */
        this.touches = new Map();
        /** @type {{x: number, y: number, distance: number}|null} the two fingers that zoom, at the last event */
        this.pinch = null;
        // Where the zoomer lies now, in px from its place in the middle (see `updateZoomerStyle`).
        this.shift = { x: 0, y: 0 };
        this.wheelTicks = 0;
        this.animation = useState({ rotating: false });
        this.rotateTimer = null;
        // The picture glides on when the finger that moved it lifts. The browser plays the
        // gliding (`fling`), on its own thread: moving the picture by code in every frame was
        // jerky, and the PDF viewer, which is smooth, lets the browser do it as well.
        this.velocity = createVelocityTracker();
        /** @type {Animation|null} the gliding the browser is playing */
        this.glideAnimation = null;
        /** @type {Map<string, HTMLImageElement>} the pictures loaded ahead, by their source */
        this.preloads = new Map();
        onWillDestroy(() => {
            browser.clearTimeout(this.rotateTimer);
            this.stopGlide();
            this.dropPreloads(new Set());
        });
        useEffect(
            (image) => {
                if (!image) {
                    return;
                }
                const handlers = {
                    pointerdown: this.onTouchStart.bind(this),
                    pointermove: this.onTouchMove.bind(this),
                    pointerup: this.onTouchEnd.bind(this),
                    pointercancel: this.onTouchEnd.bind(this),
                };
                for (const type of TOUCH_EVENTS) {
                    image.addEventListener(type, handlers[type]);
                }
                // Its own layer, so that the browser only moves it (it need not draw the picture
                // again) when the picture is moved.
                this.zoomerRef.el.style.willChange = "transform";
                // A double tap on a picture that is zoomed sets the zoom back.
                const detachDoubleTap = attachDoubleTap(image, {
                    canDoubleTap: () => this.state.scale !== 1,
                    onDoubleTap: () => this.resetZoom(),
                });
                return () => {
                    detachDoubleTap();
                    for (const type of TOUCH_EVENTS) {
                        image.removeEventListener(type, handlers[type]);
                    }
                };
            },
            () => [this.imageRef.el]
        );
        useEffect(
            (iframe) => {
                if (!iframe) {
                    return;
                }
                const onLoad = () => this.showHit(iframe);
                iframe.addEventListener("load", onLoad);
                return () => iframe.removeEventListener("load", onLoad);
            },
            () => [this.iframeViewerPdfRef.el]
        );
    }

    /**
     * @override
     * The picture on show has loaded: the ones the arrow keys lead to are loaded ahead. The
     * core's template calls this at every load of the picture, so it runs after each change of
     * the file.
     */
    onImageLoaded() {
        super.onImageLoaded();
        this.preloadNeighbours();
    }

    /**
     * Load the next and the previous picture in the background, so that the browser has them
     * when the viewer shows them. The core has no preloading; this is the way the survey module
     * preloads a picture (`preloadBackground`): an `Image` that is given the source, which the
     * `<img>` of the template uses again (the address carries the checksum, the route answers
     * with a cache of a year). The neighbours are those of `next` and `previous` of the core,
     * which go round at the ends of the list. Only pictures: a PDF or a text is not loaded.
     * What is loaded for a picture that is no neighbour any more is stopped, so at most two
     * pictures are loaded ahead at a time.
     */
    preloadNeighbours() {
        const { files } = this.props;
        const { index, file } = this.state;
        const last = files.length - 1;
        const sources = new Set(
            [files[index === last ? 0 : index + 1], files[index === 0 ? last : index - 1]]
                .filter((neighbour) => neighbour !== file && neighbour.isImage)
                .map((neighbour) => neighbour.defaultSource)
        );
        this.dropPreloads(new Set([...sources, file.defaultSource]));
        for (const source of sources) {
            if (!this.preloads.has(source)) {
                const image = new Image();
                image.src = source;
                this.preloads.set(source, image);
            }
        }
    }

    /**
     * Stop the pictures loaded ahead that are not wanted any more (one that has loaded stays in
     * the cache of the browser, one that is still loading is cancelled).
     * @param {Set<string>} keep the sources to leave alone
     */
    dropPreloads(keep) {
        for (const [source, image] of this.preloads) {
            if (!keep.has(source)) {
                image.removeAttribute("src");
                this.preloads.delete(source);
            }
        }
    }

    /**
     * Mark the words of the hit in the PDF viewer of the iframe and show the first one in the
     * middle of the screen. The viewer (`PDFViewerApplication`, the same origin) is told after
     * its pages are there and it stands on the page of the hit, so its search begins on that
     * page. The viewer scrolls the first word to 50 px below the upper edge; see
     * `centerSelectedMatch` for how it is put in the middle.
     * @param {HTMLIFrameElement} iframe
     */
    async showHit(iframe) {
        const hit = this.state.file.hit;
        const app = iframe.contentWindow?.PDFViewerApplication;
        if (!hit?.terms?.length || !app) {
            return;
        }
        await app.initializedPromise;
        const search = () => {
            if (!iframe.isConnected) {
                return;
            }
            app.pdfViewer.currentPageNumber = hit.page;
            this.centerSelectedMatch(app);
            app.eventBus.dispatch("find", {
                source: this,
                type: "",
                query: hit.terms,
                caseSensitive: false,
                // Whole words, as the search of the server finds them: not `pegel` in `Kanalausspielpegel`.
                entireWord: true,
                highlightAll: true,
                findPrevious: false,
                matchDiacritics: true,
            });
        };
        if (app.pdfViewer.pagesCount) {
            search();
        } else {
            app.eventBus.on("pagesloaded", search, { once: true });
        }
    }

    /**
     * Put the word that the search selects in the middle of the screen. The viewer scrolls to
     * it once, when it draws the text of the page (`scrollMatchIntoView` of its find
     * controller, called for the selected word at every draw, but scrolling only the first
     * time); the word is then centered in the same call, whenever the viewer has moved. No
     * waiting: it happens at the moment the viewer scrolls, and not at all when it only draws
     * the page again (zoom).
     * @param {Object} app the `PDFViewerApplication` of the iframe
     */
    centerSelectedMatch(app) {
        const finder = app.findController;
        const container = app.appConfig.viewerContainer;
        const scrollMatchIntoView = finder.scrollMatchIntoView.bind(finder);
        finder.scrollMatchIntoView = (params) => {
            const { scrollTop, scrollLeft } = container;
            scrollMatchIntoView(params);
            if (container.scrollTop !== scrollTop || container.scrollLeft !== scrollLeft) {
                params.element
                    .querySelector(".highlight.selected")
                    ?.scrollIntoView({ block: "center", inline: "center" });
            }
        };
    }

    /**
     * @override
     * `touch-action: none`: the browser leaves the fingers to us (no scrolling, no zoom of the
     * page). Set in the style the template binds, which replaces the whole attribute at every
     * change. The image does not slide into its new size, as it does in the PDF viewer: the
     * zoomer moves at once, and a slide of 0.2 s that starts anew at every touch event makes the
     * image lag behind the fingers. The class `transition-base` of the template is
     * `!important` (a Bootstrap utility), so only `!important` overrules it. While the image
     * turns it may slide.
     */
    get imageStyle() {
        const transition = this.animation.rotating ? "" : "transition: none !important;";
        return `${super.imageStyle}touch-action: none;${transition}`;
    }

    /** @override */
    rotate() {
        super.rotate();
        this.animation.rotating = true;
        browser.clearTimeout(this.rotateTimer);
        this.rotateTimer = browser.setTimeout(() => {
            this.animation.rotating = false;
        }, ROTATE_ANIMATION_TIME);
    }

    /**
     * @override
     * The next file shows at its size: the zoom and the move of the last one are gone, as the
     * PDF viewer opens every file at its own size.
     */
    activateFile(index) {
        super.activateFile(index);
        this.stopGlide();
        this.state.scale = 1;
        Object.assign(this.translate, { x: 0, y: 0, dx: 0, dy: 0 });
        if (this.zoomerRef.el && this.imageRef.el) {
            this.updateZoomerStyle();
        }
    }

    /**
     * The first step up or down from `scale`, rounded to a tenth like the PDF viewer does it
     * (1, 1.1, 1.3, 1.5, ...).
     * @param {Number} scale
     * @param {Number} steps more than 0: in, less than 0: out
     * @returns {Number}
     */
    stepScale(scale, steps) {
        const delta = steps > 0 ? SCALE_DELTA : 1 / SCALE_DELTA;
        const round = steps > 0 ? Math.ceil : Math.floor;
        for (let count = Math.abs(steps); count > 0; count--) {
            scale = round(Number((scale * delta).toFixed(2)) * 10) / 10;
        }
        return scale;
    }

    /**
     * @override
     * The buttons and keys: a step of the PDF viewer, about the middle of the screen.
     */
    zoomIn() {
        this.zoomAt(this.stepScale(this.state.scale, 1));
    }

    /** @override */
    zoomOut() {
        this.zoomAt(this.stepScale(this.state.scale, -1));
    }

    /**
     * @override
     * The wheel zooms about the pointer. A trackpad pinch arrives as a wheel with the Ctrl key
     * and small steps (a factor); a wheel turns in ticks (`onWheel` of the PDF viewer).
     * @param {WheelEvent} ev
     */
    onWheelImage(ev) {
        if (ev.ctrlKey) {
            ev.preventDefault(); // else the browser zooms the page
        }
        const factor = Math.exp(-ev.deltaY / 100);
        const isPinch =
            ev.ctrlKey &&
            ev.deltaMode === WheelEvent.DOM_DELTA_PIXEL &&
            ev.deltaX === 0 &&
            ev.deltaZ === 0 &&
            Math.abs(factor - 1) < 0.05;
        if (isPinch) {
            this.zoomAt(this.state.scale * factor, ev.clientX, ev.clientY);
            return;
        }
        const ticks =
            ev.deltaMode === WheelEvent.DOM_DELTA_PIXEL
                ? -ev.deltaY / PIXELS_PER_TICK
                : -Math.sign(ev.deltaY);
        const wholeTicks = this.takeWholeTicks(ticks);
        if (wholeTicks) {
            this.zoomAt(this.stepScale(this.state.scale, wholeTicks), ev.clientX, ev.clientY);
        }
    }

    /**
     * A wheel may turn less than a tick at once: the rest is kept for the next turn, but
     * dropped when the wheel turns the other way.
     * @param {Number} ticks
     * @returns {Number} the whole ticks, with the sign
     */
    takeWholeTicks(ticks) {
        if ((this.wheelTicks > 0 && ticks < 0) || (this.wheelTicks < 0 && ticks > 0)) {
            this.wheelTicks = 0;
        }
        this.wheelTicks += ticks;
        const wholeTicks = Math.trunc(this.wheelTicks);
        this.wheelTicks -= wholeTicks;
        return wholeTicks;
    }

    /**
     * Zoom to `scale` (kept between 0.1 and 10) so that the point `x`, `y` of the screen stays
     * where it is on the image.
     * @param {Number} scale
     * @param {Number} [x] client coordinates, default: the middle of the screen
     * @param {Number} [y]
     */
    zoomAt(scale, x, y) {
        const next = Math.min(Math.max(scale, MIN_SCALE), MAX_SCALE);
        const ratio = next / this.state.scale;
        // The zoomer lies in the middle of the screen, moved by `shift`; the point is
        // measured from that middle.
        const rect = this.zoomerRef.el.getBoundingClientRect();
        const middleX = rect.left + rect.width / 2 - this.shift.x;
        const middleY = rect.top + rect.height / 2 - this.shift.y;
        const originX = (x ?? middleX) - middleX;
        const originY = (y ?? middleY) - middleY;
        this.translate.x = originX - (originX - this.shift.x) * ratio;
        this.translate.y = originY - (originY - this.shift.y) * ratio;
        this.translate.dx = 0;
        this.translate.dy = 0;
        this.state.scale = next;
        this.updateZoomerStyle();
    }

    /**
     * @override
     * As the core's, but the image cannot be moved off the screen: it stays within the
     * zoomer as far as it is larger than it, and lies in the middle when it is smaller (the
     * PDF viewer scrolls the same way). The size is that of the image turned.
     */
    updateZoomerStyle() {
        this.stopGlide();
        const zoomer = this.zoomerRef.el;
        const limit = this.zoomLimits();
        const translate = this.translate;
        translate.x = keep(translate.x, limit.x);
        translate.y = keep(translate.y, limit.y);
        // While the image is dragged, `dx` and `dy` are the way of the drag so far.
        translate.dx = keep(translate.x + translate.dx, limit.x) - translate.x;
        translate.dy = keep(translate.y + translate.dy, limit.y) - translate.y;
        this.shift = { x: translate.x + translate.dx, y: translate.y + translate.dy };
        zoomer.style.transform = `translate(${this.shift.x}px, ${this.shift.y}px)`;
    }

    /**
     * How far the image may be moved from the middle (px) along each axis: as far as it is larger
     * than the zoomer. The size is that of the image turned.
     * @returns {{x: number, y: number}}
     */
    zoomLimits() {
        const image = this.imageRef.el;
        const zoomer = this.zoomerRef.el;
        const turned = this.state.angle % 180 !== 0;
        const width = (turned ? image.offsetHeight : image.offsetWidth) * this.state.scale;
        const height = (turned ? image.offsetWidth : image.offsetHeight) * this.state.scale;
        return {
            x: Math.max((width - zoomer.offsetWidth) / 2, 0),
            y: Math.max((height - zoomer.offsetHeight) / 2, 0),
        };
    }

    /** @returns {{x: number, y: number, distance: number}} the middle and the distance of two fingers */
    get fingers() {
        const [first, second] = [...this.touches.values()];
        return {
            x: (first.x + second.x) / 2,
            y: (first.y + second.y) / 2,
            distance: Math.max(Math.hypot(first.x - second.x, first.y - second.y), 1),
        };
    }

    /**
     * Let the picture glide on after a finger lifted at `speed`. The way is worked out at once
     * (as far as the picture may go), and the browser moves the zoomer there, with an easing
     * that slows down like a page that glides: on its own thread, so it is smooth whatever the
     * code is busy with.
     * @param {{x: number, y: number}} speed px per ms
     */
    fling(speed) {
        const limit = this.zoomLimits();
        const { dx, dy, duration } = flingPlan(speed);
        const { x: fromX, y: fromY } = this.translate;
        const toX = keep(fromX + dx, limit.x);
        const toY = keep(fromY + dy, limit.y);
        if (toX === fromX && toY === fromY) {
            return;
        }
        const place = (x, y) => `translate(${x}px, ${y}px)`;
        // `forwards`: the end holds until `settleAt` has written it, there is no jump back.
        const animation = this.zoomerRef.el.animate(
            [{ transform: place(fromX, fromY) }, { transform: place(toX, toY) }],
            { duration, easing: FLING_EASING, fill: "forwards" }
        );
        this.glideAnimation = animation;
        animation.onfinish = () => {
            if (this.glideAnimation === animation) {
                this.settleAt(toX, toY);
            }
        };
    }

    /** End the gliding where the picture is now (a finger touches it, it is zoomed ...). */
    stopGlide() {
        if (!this.glideAnimation) {
            return;
        }
        const zoomer = this.zoomerRef.el;
        const place = zoomer && new DOMMatrixReadOnly(getComputedStyle(zoomer).transform);
        this.settleAt(place?.m41 ?? this.translate.x, place?.m42 ?? this.translate.y);
    }

    /**
     * Write the place the gliding has (or had) as the place of the picture, and end the gliding.
     * @param {Number} x
     * @param {Number} y
     */
    settleAt(x, y) {
        const animation = this.glideAnimation;
        this.glideAnimation = null;
        Object.assign(this.translate, { x, y, dx: 0, dy: 0 });
        this.shift = { x, y };
        if (this.zoomerRef.el) {
            this.zoomerRef.el.style.transform = `translate(${x}px, ${y}px)`;
        }
        animation?.cancel();
    }

    /** @param {PointerEvent} ev */
    onTouchStart(ev) {
        if (ev.pointerType !== "touch") {
            return;
        }
        this.stopGlide();
        this.velocity.reset();
        this.touches.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
        if (this.touches.size === 1) {
            this.onMousedownImage(ev);
        } else if (this.touches.size === 2) {
            // The second finger ends the move of the first and starts the zoom.
            this.onMouseupImage();
            this.pinch = this.fingers;
        }
    }

    /** @param {PointerEvent} ev */
    onTouchMove(ev) {
        const touch = this.touches.get(ev.pointerId);
        if (!touch) {
            return;
        }
        touch.x = ev.clientX;
        touch.y = ev.clientY;
        if (!this.pinch) {
            this.onMousemoveView(ev);
            this.velocity.track(ev.clientX, ev.clientY, ev.timeStamp);
        } else if (this.touches.size === 2) {
            // The image grows with the distance of the fingers, about their middle as it was,
            // and then goes along with the middle to where it is now.
            const { x, y, distance } = this.fingers;
            const { x: fromX, y: fromY } = this.pinch;
            this.zoomAt((this.state.scale * distance) / this.pinch.distance, fromX, fromY);
            this.translate.x += x - fromX;
            this.translate.y += y - fromY;
            this.updateZoomerStyle();
            this.pinch = { x, y, distance };
        }
    }

    /** @param {PointerEvent} ev */
    onTouchEnd(ev) {
        if (!this.touches.delete(ev.pointerId)) {
            return;
        }
        if (this.pinch) {
            if (this.touches.size < 2) {
                this.pinch = null;
                // The finger that is left goes on moving the image from where it is.
                for (const { x, y } of this.touches.values()) {
                    this.onMousedownImage({ button: 0, clientX: x, clientY: y });
                }
            }
            return;
        }
        this.onMouseupImage();
        const speed = this.velocity.release(ev.timeStamp);
        if (speed) {
            this.fling(speed);
        }
    }
}

/**
 * Like the core's `useFileViewer`, which opens the core's viewer only: this one opens
 * `DocumentFileViewer`.
 * @returns {{open: function(Object, Object[]): void, close: function(): void}}
 */
export function useDocumentFileViewer() {
    const id = `int_filemanager.file_viewer${nextViewerId++}`;
    const mainComponents = registry.category("main_components");

    function close() {
        mainComponents.remove(id);
    }

    /**
     * @param {Object} file the file to start with
     * @param {Object[]} files the files the arrow keys go through
     */
    function open(file, files = [file]) {
        close();
        if (!file.isViewable) {
            return;
        }
        // The viewer finds the file to start with among the files by identity.
        const viewableFiles = files.filter((candidate) => candidate.isViewable);
        mainComponents.add(id, {
            Component: DocumentFileViewer,
            props: { files: viewableFiles, startIndex: viewableFiles.indexOf(file), close },
        });
    }

    onWillDestroy(close);
    return { open, close };
}
