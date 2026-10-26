// The view onto the scene: zoom and move. The canvas element fills the stage; where the picture
// lies on it is the viewport transform of Fabric. The zoom is in screen pixels per unit of the
// scene.
import { STAGE_MARGIN, ZOOM_MAX, ZOOM_MIN } from "./constants";
import { clamp, fitZoom, limitPan, viewTransform } from "./geometry";

const KEEP_IN_VIEW = 48;

export class Viewport {
    /**
     * @param {Object} canvas a Fabric canvas
     * @param {HTMLElement} stage the element that the canvas fills
     * @param {function(): void} onChange called after the view changed
     */
    constructor(canvas, stage, onChange = () => {}) {
        this.canvas = canvas;
        this.stage = stage;
        this.onChange = onChange;
        this.region = { left: 0, top: 0, width: 1, height: 1 };
        this.zoom = 1;
        this.pan = { x: 0, y: 0 };
        this.fitted = true;
    }

    get room() {
        return { width: this.stage.clientWidth, height: this.stage.clientHeight };
    }

    /** The part of the scene that the view is about (all of it, or what is left after a crop). */
    setRegion(region) {
        this.region = region;
        if (this.fitted) {
            this.fit();
        } else {
            this.apply();
        }
    }

    get fitZoom() {
        return fitZoom(this.room, this.region, STAGE_MARGIN);
    }

    fit() {
        this.fitted = true;
        this.pan = { x: 0, y: 0 };
        this.zoom = clamp(this.fitZoom, ZOOM_MIN, ZOOM_MAX);
        this.apply();
    }

    /** The size of the stage changed: the canvas follows, a fitted picture stays fitted. */
    resize() {
        const { width, height } = this.room;
        if (!width || !height) {
            return;
        }
        this.canvas.setDimensions({ width, height });
        if (this.fitted) {
            this.fit();
        } else {
            this.apply();
        }
    }

    /**
     * @param {number} zoom screen pixels per unit
     * @param {{x: number, y: number}} [about] a point of the stage that stays where it is
     */
    zoomTo(zoom, about) {
        const next = clamp(zoom, ZOOM_MIN, ZOOM_MAX);
        const point = about || { x: this.room.width / 2, y: this.room.height / 2 };
        const [, , , , e, f] = viewTransform(this.room, this.region, this.zoom, this.pan);
        const scene = { x: (point.x - e) / this.zoom, y: (point.y - f) / this.zoom };
        const [, , , , baseE, baseF] = viewTransform(this.room, this.region, next, { x: 0, y: 0 });
        this.pan = { x: point.x - scene.x * next - baseE, y: point.y - scene.y * next - baseF };
        this.zoom = next;
        this.fitted = false;
        this.apply();
    }

    zoomBy(factor, about) {
        this.zoomTo(this.zoom * factor, about);
    }

    panBy(dx, dy) {
        this.pan = { x: this.pan.x + dx, y: this.pan.y + dy };
        this.fitted = false;
        this.apply();
    }

    apply() {
        this.pan = limitPan(this.room, this.region, this.zoom, this.pan, KEEP_IN_VIEW);
        this.canvas.setViewportTransform(viewTransform(this.room, this.region, this.zoom, this.pan));
        this.canvas.requestRenderAll();
        this.onChange();
    }
}
