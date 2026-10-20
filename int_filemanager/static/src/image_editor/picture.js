// The picture the editor works on: the background of the canvas. A big picture is shown by a
// smaller copy (the filters and the redaction run on that copy, and the screen cannot show more)
// and put back in full only while the file is made.
import { EXPORT_SCALES } from "./constants";
import { buildFilters } from "./filters";
import { limitEdge, turnSize } from "./geometry";

const { FabricImage, Point, util } = window.fabric;

/**
 * Whether the browser can make a canvas of this size (a limit of its own: the width, the height,
 * the area, and on phones the memory). A canvas it cannot make is zero wide or draws nothing.
 */
export function canvasFits(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(width));
    canvas.height = Math.max(1, Math.round(height));
    const context = canvas.getContext("2d");
    if (!context || canvas.width !== Math.round(width) || canvas.height !== Math.round(height)) {
        return false;
    }
    context.fillStyle = "#000";
    context.fillRect(canvas.width - 1, canvas.height - 1, 1, 1);
    return context.getImageData(canvas.width - 1, canvas.height - 1, 1, 1).data[3] === 255;
}

/**
 * The biggest scale of the list (1 is the full size) at which a canvas of the picture can be made.
 * @returns {number} 0 if even the smallest fails
 */
export function largestExportScale({ width, height }, fits = canvasFits) {
    return EXPORT_SCALES.find((scale) => fits(width * scale, height * scale)) || 0;
}

/** @returns {Promise<HTMLImageElement>} the picture at `url`, loaded */
export async function loadPicture(url) {
    const image = await util.loadImage(url, { crossOrigin: "anonymous" });
    if (!image.naturalWidth || !image.naturalHeight) {
        throw new Error("The picture has no size.");
    }
    return image;
}

export class Picture {
    /**
     * @param {HTMLImageElement|HTMLCanvasElement} full the picture at its size
     * @param {number} edge the longest side of the copy that is shown
     */
    constructor(full, edge) {
        this.full = full;
        this.size = { width: full.naturalWidth || full.width, height: full.naturalHeight || full.height };
        const small = limitEdge(this.size, edge);
        /** the share of the full size that the copy has */
        this.scale = small.width / this.size.width;
        this.work = this.scale < 1 ? this.shrink(small) : full;
        this.image = new FabricImage(this.work, {
            originX: "left",
            originY: "top",
            left: 0,
            top: 0,
            scaleX: 1 / this.scale,
            scaleY: 1 / this.scale,
            selectable: false,
            evented: false,
            objectCaching: false,
        });
        this.image.filterVersion = 0;
        // What the picture object shows: the filters replace its own element by a filtered one.
        this.shown = { element: this.work, factor: this.scale };
    }

    shrink({ width, height }) {
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext("2d");
        context.imageSmoothingQuality = "high";
        context.drawImage(this.full, 0, 0, width, height);
        return canvas;
    }

    /** @returns {{width: number, height: number}} the size of the scene: that of the picture, turned */
    get sceneSize() {
        return this.quarters % 2 ? turnSize(this.size) : { ...this.size };
    }

    /** @returns {number} 0 to 3: how many quarter turns the picture has */
    get quarters() {
        return ((Math.round(this.image.angle / 90) % 4) + 4) % 4;
    }

    /** Where the picture lies: enough to put it back. */
    placement() {
        const { x, y } = this.image.getCenterPoint();
        const { angle, flipX, flipY } = this.image;
        return { angle, flipX, flipY, cx: x, cy: y };
    }

    place({ angle, flipX, flipY, cx, cy }) {
        this.image.set({ angle, flipX, flipY });
        this.image.setPositionByOrigin(new Point(cx, cy), "center", "center");
        this.image.setCoords();
    }

    /** The picture as it is when nothing is turned: in the corner, upright. */
    resetPlacement() {
        this.place({ angle: 0, flipX: false, flipY: false, cx: this.size.width / 2, cy: this.size.height / 2 });
    }

    /** Applies the filters of the settings to the picture that is shown. */
    setFilters(settings) {
        this.image.filters = buildFilters(window.fabric.filters, settings);
        this.refilter();
    }

    refilter() {
        this.image.applyFilters();
        this.image.filterVersion += 1;
        this.image.dirty = true;
    }

    /**
     * Shows the picture in full, or the small copy again. The filters run again on the other one.
     * @param {boolean} full
     */
    show(full) {
        this.showElement(full ? this.full : this.work, full ? 1 : this.scale);
    }

    /**
     * Shows `element`, a copy of the picture that has `factor` of its size, in place of the one
     * that is shown. The filters run again on it.
     */
    showElement(element, factor) {
        const { image } = this;
        if (this.shown.element === element && this.shown.factor === factor) {
            return;
        }
        this.shown = { element, factor };
        const center = image.getCenterPoint();
        image.setElement(element);
        image.set({ scaleX: 1 / factor, scaleY: 1 / factor });
        image.setPositionByOrigin(center, "center", "center");
        image.setCoords();
        this.refilter();
    }
}
