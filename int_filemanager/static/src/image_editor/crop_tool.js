// The crop: a frame on the picture that the user moves and resizes, with the rest shaded. The crop
// is not cut out of the picture; it is the part that is shown and stored, and it can be chosen
// anew, or taken away, until the picture is stored.
import { CONTROL_LOOK } from "./constants";
import { keepInside, ratioRect } from "./geometry";

const { Rect } = window.fabric;

/** The ratios offered; `ratio` is width / height, `"original"` that of the picture. */
export const ASPECTS = [
    { id: "free", ratio: null },
    { id: "original", ratio: "original" },
    { id: "1:1", ratio: 1 },
    { id: "4:3", ratio: 4 / 3 },
    { id: "3:2", ratio: 3 / 2 },
    { id: "16:9", ratio: 16 / 9 },
    { id: "3:4", ratio: 3 / 4 },
    { id: "2:3", ratio: 2 / 3 },
    { id: "9:16", ratio: 9 / 16 },
];
const SIDE_CONTROLS = ["ml", "mr", "mt", "mb"];

export class CropTool {
    /** @param {Object} editor the editor: `canvas`, `scene`, `crop`, `region` */
    constructor(editor) {
        this.editor = editor;
        this.rect = null;
        this.aspect = "free";
    }

    get active() {
        return Boolean(this.rect);
    }

    /** The frame as a rectangle of the scene, `null` if there is none. */
    get box() {
        return this.rect ? this.rect.getBoundingRect() : null;
    }

    start() {
        if (this.rect) {
            return;
        }
        const { canvas, editor } = this;
        const { left, top, width, height } = editor.crop || { left: 0, top: 0, ...editor.scene };
        this.rect = new Rect({
            left,
            top,
            width,
            height,
            originX: "left",
            originY: "top",
            fill: "rgba(0, 0, 0, 0.001)",
            strokeWidth: 0,
            helper: true,
            excludeFromExport: true,
            lockRotation: true,
            objectCaching: false,
            ...CONTROL_LOOK,
            // On the shade the frame is white.
            borderColor: "#ffffff",
            borderScaleFactor: 2,
        });
        this.rect.setControlVisible("mtr", false);
        canvas.add(this.rect);
        canvas.setActiveObject(this.rect);
        this.setAspect(this.aspect);
    }

    /** The size of a screen pixel in units of the scene, for the handles. */
    get scaleToScene() {
        return 1 / this.editor.viewport.zoom;
    }

    get canvas() {
        return this.editor.canvas;
    }

    /** Takes the frame away without keeping it. */
    cancel() {
        if (!this.rect) {
            return;
        }
        this.canvas.discardActiveObject();
        this.canvas.remove(this.rect);
        this.rect = null;
        this.canvas.uniformScaling = true;
        this.canvas.requestRenderAll();
    }

    /**
     * Sets the shape of the frame: the largest of the ratio that fits in the frame it has, in its
     * middle. A fixed ratio keeps the frame in that ratio (the handles on the sides go).
     * @param {string} id one of `ASPECTS`
     */
    setAspect(id) {
        this.aspect = id;
        if (!this.rect) {
            return;
        }
        const entry = ASPECTS.find((aspect) => aspect.id === id) || ASPECTS[0];
        const ratio = entry.ratio === "original" ? this.editor.scene.width / this.editor.scene.height : entry.ratio;
        this.canvas.uniformScaling = ratio !== null;
        for (const control of SIDE_CONTROLS) {
            this.rect.setControlVisible(control, ratio === null);
        }
        if (ratio !== null) {
            const now = this.normalize();
            const inner = ratioRect(now, ratio);
            this.place({ left: now.left + inner.left, top: now.top + inner.top, width: inner.width, height: inner.height });
        }
        this.canvas.requestRenderAll();
    }

    place({ left, top, width, height }) {
        this.rect.set({ left, top, width, height, scaleX: 1, scaleY: 1, angle: 0 });
        this.rect.setCoords();
    }

    /** While the frame is dragged: it does not leave the picture. */
    constrainMoving() {
        // Fabric works out the coordinates of the new place after this handler ran: they are brought
        // up to date first, or the frame jumps back and forth at the edge.
        this.rect.setCoords();
        const box = keepInside(this.rect.getBoundingRect(), this.editor.scene);
        this.rect.set({ left: box.left, top: box.top });
        this.rect.setCoords();
    }

    /**
     * After the frame was moved or resized: the scale goes into the size, the frame is inside the
     * picture, and a fixed ratio holds.
     * @returns {{left: number, top: number, width: number, height: number}} the frame
     */
    normalize() {
        let box = keepInside(this.rect.getBoundingRect(), this.editor.scene);
        const entry = ASPECTS.find((aspect) => aspect.id === this.aspect);
        const ratio = entry?.ratio === "original" ? this.editor.scene.width / this.editor.scene.height : entry?.ratio;
        if (ratio) {
            const height = Math.min(box.width / ratio, this.editor.scene.height);
            const width = height * ratio;
            box = keepInside({ left: box.left, top: box.top, width, height }, this.editor.scene);
        }
        this.place(box);
        return box;
    }
}
