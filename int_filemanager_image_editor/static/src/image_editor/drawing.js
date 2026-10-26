// What the pointer does on the canvas while a drawing tool is on: drag out a shape, click the
// points of a polygon, set down a text, draw freehand with a brush.
import { _t } from "@web/core/l10n/translation";
import { MIN_MARK } from "./constants";
import { clamp } from "./geometry";
import {
    createArrow,
    createDraft,
    createPolyMark,
    createText,
    dashArray,
    DRAG_KINDS,
    POINT_KINDS,
    shadowFor,
    stripeSource,
    TEXT_KINDS,
    updateDraft,
} from "./marks";

const { CircleBrush, PatternBrush, PencilBrush, SprayBrush } = window.fabric;

// A click this near to the first point (in pixels of the screen) closes a polygon.
const CLOSE_DISTANCE = 10;
const POINT_APART = 0.5;

export const BRUSHES = ["pencil", "spray", "circles", "pattern"];

/**
 * The brush of the style.
 * @returns {Object} a Fabric brush for `canvas.freeDrawingBrush`
 */
export function createBrush(canvas, style, unit) {
    const width = style.width * unit;
    let brush;
    if (style.brush === "spray") {
        brush = new SprayBrush(canvas);
        brush.width = width * 4;
        brush.density = style.density;
        brush.dotWidth = Math.max(width / 3, 1);
        brush.dotWidthVariance = brush.dotWidth / 2;
        brush.randomOpacity = true;
    } else if (style.brush === "circles") {
        brush = new CircleBrush(canvas);
        brush.width = width * 2;
    } else if (style.brush === "pattern") {
        brush = new PatternBrush(canvas);
        brush.source = stripeSource(style.stroke, width * 3);
        brush.width = width * 2;
    } else {
        brush = new PencilBrush(canvas);
        brush.width = width;
        brush.strokeDashArray = dashArray(style.dash, width);
        brush.strokeLineCap = "round";
    }
    brush.color = style.stroke;
    brush.shadow = shadowFor(style.shadow, unit);
    return brush;
}

export class DrawingTools {
    /** @param {Object} editor the editor: `canvas`, `state`, `unit`, `scene`, `viewport`, `commit()`, `setTool()` */
    constructor(editor) {
        this.editor = editor;
        this.draft = null;
        this.poly = null;
    }

    get canvas() {
        return this.editor.canvas;
    }

    get busy() {
        return Boolean(this.draft || this.poly);
    }

    /** Gives up what is being drawn. */
    abort() {
        if (this.draft) {
            this.canvas.remove(this.draft.object);
            this.draft = null;
        }
        this.poly = null;
        this.canvas.requestRenderAll();
    }

    /** @returns {{x: number, y: number}} `point` brought into the part that is stored */
    keepInside(point) {
        const { left, top, width, height } = this.editor.regionBox;
        return { x: clamp(point.x, left, left + width), y: clamp(point.y, top, top + height) };
    }

    isInside({ x, y }) {
        const { left, top, width, height } = this.editor.regionBox;
        return x >= left && x <= left + width && y >= top && y <= top + height;
    }

    onMouseDown({ e, target }) {
        const { tool } = this.editor.state;
        const point = this.canvas.getScenePoint(e);
        // A mark begins on the picture, not beside it.
        if (!this.isInside(point)) {
            return;
        }
        if (TEXT_KINDS.includes(tool)) {
            if (!target) {
                this.addText(tool, point);
            }
        } else if (POINT_KINDS.includes(tool)) {
            this.addPoint(tool, point);
        } else if (DRAG_KINDS.includes(tool) && !target) {
            const { style, redact } = this.editor.state;
            const object = createDraft(tool, point, style, this.editor.unit, redact);
            this.draft = { tool, start: point, end: point, object };
            this.canvas.add(object);
        }
    }

    onMouseMove({ e }) {
        // Dragged beyond the edge, a mark ends at the edge.
        const point = this.keepInside(this.canvas.getScenePoint(e));
        if (this.poly) {
            this.poly.hover = point;
            this.canvas.requestRenderAll();
            return;
        }
        if (!this.draft) {
            return;
        }
        const { tool, start, object } = this.draft;
        this.draft.end = point;
        updateDraft(tool, object, start, point, e.shiftKey);
        this.canvas.requestRenderAll();
    }

    onMouseUp() {
        if (!this.draft) {
            return;
        }
        const { tool, start, end, object } = this.draft;
        this.draft = null;
        // The way of the pointer decides, not the box (the line around a mark counts in that).
        if (Math.max(Math.abs(end.x - start.x), Math.abs(end.y - start.y)) < MIN_MARK * this.editor.unit) {
            this.canvas.remove(object);
            return;
        }
        if (tool === "arrow") {
            this.canvas.remove(object);
            this.canvas.add(
                createArrow(start, { x: object.x2, y: object.y2 }, this.editor.state.style, this.editor.unit)
            );
        }
        object.setCoords();
        this.editor.commit();
    }

    //--------------------------------------------------------------------------
    // Text and polygons
    //--------------------------------------------------------------------------

    addText(kind, point) {
        const { canvas, editor } = this;
        const text = createText(kind, point, _t("Text"), editor.state.style, editor.unit, editor.scene.width);
        canvas.add(text);
        // One text per click; the next click selects again.
        editor.setTool("select");
        canvas.setActiveObject(text);
        text.enterEditing();
        text.selectAll();
    }

    addPoint(kind, point) {
        const { poly } = this;
        if (!poly) {
            this.poly = { kind, points: [point], hover: point };
        } else {
            const [first] = poly.points;
            const near = CLOSE_DISTANCE / this.editor.viewport.zoom;
            if (kind === "polygon" && poly.points.length >= 3 && Math.hypot(point.x - first.x, point.y - first.y) <= near) {
                this.finishPoly();
                return;
            }
            poly.points.push(point);
            poly.hover = point;
        }
        this.canvas.requestRenderAll();
    }

    /** Makes the shape of the points that were clicked, if there are enough of them. */
    finishPoly() {
        const { poly } = this;
        this.poly = null;
        if (!poly) {
            return;
        }
        // A double click sets the last point twice.
        const points = poly.points.filter(
            (point, index, all) =>
                !index || Math.hypot(point.x - all[index - 1].x, point.y - all[index - 1].y) > POINT_APART
        );
        const enough = poly.kind === "polygon" ? points.length >= 3 : points.length >= 2;
        if (enough) {
            this.canvas.add(createPolyMark(poly.kind, points, this.editor.state.style, this.editor.unit));
            this.editor.commit();
        }
        this.canvas.requestRenderAll();
    }

    /** @returns {Object|null} the line of the polygon for the overlay */
    polyOverlay() {
        if (!this.poly) {
            return null;
        }
        const { style } = this.editor.state;
        return {
            points: [...this.poly.points, this.poly.hover],
            color: style.stroke,
            width: (style.width * this.editor.unit) / 2,
            closed: false,
        };
    }
}
