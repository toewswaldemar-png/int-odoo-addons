import { onWillDestroy, useEffect, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { FileViewer } from "@web/core/file_viewer/file_viewer";
import { registry } from "@web/core/registry";

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
 * The core's file viewer with the zoom of the PDF viewer, which the core's own image zoom
 * lacks: two fingers (or the wheel, the buttons) zoom around the point they are at, one finger
 * moves the image, and it cannot be moved off the screen. The core's viewer knows the mouse
 * only (wheel, buttons, drag) and zooms about the middle of the screen, so a touch screen
 * cannot zoom an image at all; a PDF can, it is shown by the browser. The mouse keeps the
 * core's ways (wheel, buttons, keys, drag); the state is the core's own (`state.scale`,
 * `translate`), the fingers only drive it.
 */
export class DocumentFileViewer extends FileViewer {
    setup() {
        super.setup();
        this.minScale = MIN_SCALE;
        /** @type {Map<number, {x: number, y: number}>} the fingers on the image */
        this.touches = new Map();
        /** @type {{distance: number}|null} set while two fingers zoom */
        this.pinch = null;
        // Where the zoomer lies now, in px from its place in the middle (see `updateZoomerStyle`).
        this.shift = { x: 0, y: 0 };
        this.wheelTicks = 0;
        this.animation = useState({ rotating: false });
        this.rotateTimer = null;
        onWillDestroy(() => browser.clearTimeout(this.rotateTimer));
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
                return () => {
                    for (const type of TOUCH_EVENTS) {
                        image.removeEventListener(type, handlers[type]);
                    }
                };
            },
            () => [this.imageRef.el]
        );
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
        const image = this.imageRef.el;
        const zoomer = this.zoomerRef.el;
        const turned = this.state.angle % 180 !== 0;
        const width = (turned ? image.offsetHeight : image.offsetWidth) * this.state.scale;
        const height = (turned ? image.offsetWidth : image.offsetHeight) * this.state.scale;
        const limitX = Math.max((width - zoomer.offsetWidth) / 2, 0);
        const limitY = Math.max((height - zoomer.offsetHeight) / 2, 0);
        const keep = (value, limit) => Math.min(Math.max(value, -limit), limit);
        const translate = this.translate;
        translate.x = keep(translate.x, limitX);
        translate.y = keep(translate.y, limitY);
        // While the image is dragged, `dx` and `dy` are the way of the drag so far.
        translate.dx = keep(translate.x + translate.dx, limitX) - translate.x;
        translate.dy = keep(translate.y + translate.dy, limitY) - translate.y;
        this.shift = { x: translate.x + translate.dx, y: translate.y + translate.dy };
        zoomer.style.transform = `translate(${this.shift.x}px, ${this.shift.y}px)`;
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

    /** @param {PointerEvent} ev */
    onTouchStart(ev) {
        if (ev.pointerType !== "touch") {
            return;
        }
        this.touches.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
        if (this.touches.size === 1) {
            this.onMousedownImage(ev);
        } else if (this.touches.size === 2) {
            // The second finger ends the move of the first and starts the zoom.
            this.onMouseupImage();
            this.pinch = { distance: this.fingers.distance };
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
        } else if (this.touches.size === 2) {
            // The image grows with the distance of the fingers, about their middle, and does
            // not move while they zoom (the PDF viewer does not move either).
            const { x, y, distance } = this.fingers;
            this.zoomAt((this.state.scale * distance) / this.pinch.distance, x, y);
            this.pinch = { distance };
        }
    }

    /** @param {PointerEvent} ev */
    onTouchEnd(ev) {
        if (!this.touches.delete(ev.pointerId)) {
            return;
        }
        if (this.pinch) {
            // The finger left over does not move the image: it waits until all are up.
            if (!this.touches.size) {
                this.pinch = null;
            }
            return;
        }
        this.onMouseupImage();
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
