// The marks of the editor: what is made when the user drags, clicks or types, and how the style
// of a mark is read and set. The style is one plain object (`DEFAULT_STYLE`) that the controls
// of the editor show; sizes in it are in steps of the unit of the picture (see `UNIT_PER_PIXEL`).
import { ARROW_HEAD_FACTOR, HIGHLIGHT_ALPHA } from "./constants";
import { snapAngle, squareTo } from "./geometry";
import { REDACT_DEFAULT, RedactMark } from "./redact_mark";

const { Circle, Color, Ellipse, Gradient, Group, IText, Line, Pattern, Polygon, Polyline, Rect, Shadow, Textbox, Triangle } =
    window.fabric;

export const DEFAULT_STYLE = {
    stroke: "#FF0000",
    width: 4,
    dash: "solid",
    fillMode: "none",
    fill: "#FF0000",
    gradient: { from: "#FF0000", to: "#0000FF", angle: 0 },
    opacity: 1,
    shadow: { on: false, color: "#000000", blur: 10, offset: 6 },
    radius: 0,
    font: "sans-serif",
    textSize: 24,
    bold: false,
    italic: false,
    underline: false,
    linethrough: false,
    align: "left",
    lineHeight: 1.16,
    spacing: 0,
    brush: "pencil",
    density: 20,
};

/** The marks that are dragged out: the box or the line is made while the pointer moves. */
export const DRAG_KINDS = ["line", "arrow", "rect", "ellipse", "circle", "triangle", "highlight", "redact"];
/** The marks made by a click for each point. */
export const POINT_KINDS = ["polygon", "polyline"];
export const TEXT_KINDS = ["text", "textbox"];
/** The marks that have an inside to fill. */
const CLOSED = ["rect", "ellipse", "circle", "triangle", "polygon"];
const TEXT_TYPES = ["i-text", "textbox", "text"];

//------------------------------------------------------------------------------
// Kinds
//------------------------------------------------------------------------------

/** @returns {string|null} what a mark is, in the words of the editor */
export function kindOf(object) {
    if (!object) {
        return null;
    }
    if (object.mark) {
        return object.mark;
    }
    if (TEXT_TYPES.includes(object.type)) {
        return "text";
    }
    return object.type;
}

export function isText(object) {
    return TEXT_TYPES.includes(object?.type);
}

/**
 * Takes the scale that a handle gave a text into its size: the font size is that much larger (a
 * text box is also that much wider) and the scale is 1 again, so that what the controls show is the
 * size that the text has. The corners scale both ways alike (the canvas does not let a key undo
 * that), so one factor is enough.
 */
export function bakeTextScale(object) {
    if (!isText(object) || (object.scaleX === 1 && object.scaleY === 1)) {
        return;
    }
    const factor = object.scaleY;
    const changes = { fontSize: object.fontSize * factor, scaleX: 1, scaleY: 1 };
    if (object.type === "textbox") {
        changes.width = object.width * object.scaleX;
    }
    object.set(changes);
    object.initDimensions();
    object.setCoords();
}

/** @returns {boolean} whether the mark has an inside that takes a fill */
export function isClosed(object) {
    return CLOSED.includes(kindOf(object));
}

/**
 * Makes Fabric draw a mark from its shape every time, not from a bitmap that it keeps for it (the
 * cache of the object). The bitmap has the size that the mark had when it was made, or that it has
 * on the screen: while a handle scales a mark it is not made anew (`noScaleCache`, the default of
 * Fabric for most objects), so a small text pulled large is a small bitmap pulled large; and it is
 * never larger than about two million pixels, so a large mark is drawn from a smaller bitmap, on
 * the screen when it is zoomed and in the file when it is stored. A mark drawn directly is sharp at
 * every size, and the marks are few.
 */
export function drawDirectly(object) {
    object.set({ objectCaching: false });
    if (object.type === "group") {
        object.getObjects().forEach(drawDirectly);
    }
}

/** @returns {Object[]} the parts of a mark that carry its style (a group by its parts, deeply) */
export function leaves(object) {
    if (object.type === "group") {
        return object.getObjects().flatMap((part) => leaves(part));
    }
    return [object];
}

//------------------------------------------------------------------------------
// Style to Fabric
//------------------------------------------------------------------------------

/** @returns {string|null} the colour as `#RRGGBB`, `null` if it has none */
export function toHex(value) {
    if (typeof value !== "string" || !value || value === "transparent") {
        return null;
    }
    try {
        return `#${new Color(value).toHex().toUpperCase()}`;
    } catch {
        return null;
    }
}

export function withAlpha(color, alpha) {
    const [red, green, blue] = [1, 3, 5].map((from) => parseInt(color.slice(from, from + 2), 16));
    return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

export function dashArray(dash, width) {
    if (dash === "dashed") {
        return [width * 3, width * 2];
    }
    if (dash === "dotted") {
        return [width * 0.1, width * 2];
    }
    return null;
}

export function gradientFor({ from, to, angle }) {
    const radians = (angle * Math.PI) / 180;
    const [cos, sin] = [Math.cos(radians) / 2, Math.sin(radians) / 2];
    return new Gradient({
        type: "linear",
        gradientUnits: "percentage",
        coords: { x1: 0.5 - cos, y1: 0.5 - sin, x2: 0.5 + cos, y2: 0.5 + sin },
        colorStops: [
            { offset: 0, color: from },
            { offset: 1, color: to },
        ],
    });
}

/** Diagonal stripes in the colour, as a canvas that is repeated (a fill, or the source of a brush). */
export function stripeSource(color, size) {
    const side = Math.max(Math.round(size), 4);
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = side;
    const context = canvas.getContext("2d");
    context.strokeStyle = color;
    context.lineWidth = Math.max(side / 4, 1);
    context.beginPath();
    context.moveTo(0, side);
    context.lineTo(side, 0);
    context.moveTo(-side / 2, side / 2);
    context.lineTo(side / 2, -side / 2);
    context.moveTo(side / 2, side * 1.5);
    context.lineTo(side * 1.5, side / 2);
    context.stroke();
    return canvas;
}

// The size of the stripes of the pattern fill, in units of the picture.
const PATTERN_SIZE = 12;

/** @returns {string|Gradient|Pattern} the fill that the style asks for (transparent: none) */
export function fillFor(style, unit = 1) {
    if (style.fillMode === "gradient") {
        return gradientFor(style.gradient);
    }
    if (style.fillMode === "pattern") {
        return new Pattern({ source: stripeSource(style.fill, PATTERN_SIZE * unit), repeat: "repeat" });
    }
    return style.fillMode === "solid" ? style.fill : "transparent";
}

export function shadowFor({ on, color, blur, offset }, unit) {
    return on ? new Shadow({ color, blur: blur * unit, offsetX: offset * unit, offsetY: offset * unit }) : null;
}

/** The properties that every new outlined mark gets from the style. */
export function shapeProps(style, unit) {
    const width = style.width * unit;
    return {
        stroke: style.stroke,
        strokeWidth: width,
        strokeUniform: true,
        strokeDashArray: dashArray(style.dash, width),
        strokeLineCap: style.dash === "dotted" ? "round" : "butt",
        dashKind: style.dash,
        opacity: style.opacity,
        shadow: shadowFor(style.shadow, unit),
    };
}

//------------------------------------------------------------------------------
// New marks
//------------------------------------------------------------------------------

/**
 * The start of a mark that is dragged out; `updateDraft` grows it.
 * @param {string} kind one of `DRAG_KINDS`
 * @param {{x: number, y: number}} point where the drag starts
 * @param {{mode: string, strength: number}} redact the mode and the strength of a redaction
 */
export function createDraft(kind, point, style, unit, redact = REDACT_DEFAULT) {
    const common = { originX: "left", originY: "top", left: point.x, top: point.y };
    const props = shapeProps(style, unit);
    switch (kind) {
        case "line":
        case "arrow":
            return new Line([point.x, point.y, point.x, point.y], props);
        case "highlight":
            return new Rect({
                ...common,
                width: 0,
                height: 0,
                mark: "highlight",
                fill: withAlpha(style.stroke, HIGHLIGHT_ALPHA),
                strokeWidth: 0,
                opacity: style.opacity,
                strokeUniform: true,
            });
        case "redact":
            return new RedactMark({ ...common, width: 0, height: 0, mode: redact.mode, strength: redact.strength * unit });
        case "ellipse":
            return new Ellipse({ ...common, ...props, fill: fillFor(style, unit), rx: 0, ry: 0 });
        case "circle":
            return new Circle({ ...common, ...props, fill: fillFor(style, unit), radius: 0 });
        case "triangle":
            return new Triangle({ ...common, ...props, fill: fillFor(style, unit), width: 0, height: 0 });
        default:
            return new Rect({ ...common, ...props, fill: fillFor(style, unit), width: 0, height: 0, rx: style.radius * unit, ry: style.radius * unit });
    }
}

/**
 * Brings a draft to the pointer.
 * @param {boolean} constrain Shift: a square, a circle, a line at a multiple of 45 degrees
 */
export function updateDraft(kind, object, start, point, constrain) {
    if (kind === "line" || kind === "arrow") {
        const end = constrain ? snapAngle(start, point) : point;
        object.set({ x2: end.x, y2: end.y });
        return;
    }
    const end = constrain || kind === "circle" ? squareTo(start, point) : point;
    const left = Math.min(start.x, end.x);
    const top = Math.min(start.y, end.y);
    const width = Math.abs(end.x - start.x);
    const height = Math.abs(end.y - start.y);
    if (kind === "ellipse") {
        object.set({ left, top, rx: width / 2, ry: height / 2 });
    } else if (kind === "circle") {
        object.set({ left, top, radius: width / 2 });
    } else {
        object.set({ left, top, width, height });
    }
}

/** A line with a head, as one object: it is moved, turned and scaled as a whole. */
export function createArrow(from, to, style, unit) {
    const width = style.width * unit;
    const head = Math.max(width * ARROW_HEAD_FACTOR, unit * 4);
    const angle = Math.atan2(to.y - from.y, to.x - from.x);
    // The line ends in the middle of the head, so that its end is not seen beside the tip.
    const stop = { x: to.x - Math.cos(angle) * head * 0.5, y: to.y - Math.sin(angle) * head * 0.5 };
    const props = shapeProps(style, unit);
    const line = new Line([from.x, from.y, stop.x, stop.y], { ...props, mark: "arrowline" });
    const tip = new Triangle({
        left: to.x,
        top: to.y,
        width: head,
        height: head,
        originX: "center",
        originY: "center",
        angle: (angle * 180) / Math.PI + 90,
        fill: style.stroke,
        mark: "arrowhead",
    });
    return new Group([line, tip], {
        originX: "left",
        originY: "top",
        mark: "arrow",
        opacity: style.opacity,
        shadow: props.shadow,
    });
}

/** The polygon or the line through the points of a click-by-click mark. */
export function createPolyMark(kind, points, style, unit) {
    const props = shapeProps(style, unit);
    if (kind === "polygon") {
        return new Polygon(points, { ...props, fill: fillFor(style, unit), strokeLineJoin: "round" });
    }
    return new Polyline(points, { ...props, fill: "transparent", strokeLineJoin: "round" });
}

export function textProps(style, unit) {
    return {
        fontFamily: style.font,
        fontSize: style.textSize * unit,
        fontWeight: style.bold ? "bold" : "normal",
        fontStyle: style.italic ? "italic" : "normal",
        underline: style.underline,
        linethrough: style.linethrough,
        textAlign: style.align,
        lineHeight: style.lineHeight,
        charSpacing: style.spacing,
        fill: style.fillMode === "gradient" ? gradientFor(style.gradient) : style.stroke,
        opacity: style.opacity,
        shadow: shadowFor(style.shadow, unit),
        strokeUniform: true,
    };
}

/**
 * A text for a click: a line that grows with what is typed (`text`), or a box with a width
 * that wraps (`textbox`).
 */
export function createText(kind, point, label, style, unit, sceneWidth) {
    const common = { ...textProps(style, unit), left: point.x, top: point.y, originX: "left", originY: "top" };
    if (kind === "textbox") {
        return new Textbox(label, { ...common, width: Math.max(sceneWidth * 0.3, unit * 120) });
    }
    return new IText(label, common);
}

//------------------------------------------------------------------------------
// Style from Fabric
//------------------------------------------------------------------------------

function primaryLeaf(object) {
    const all = leaves(object);
    return all.find((leaf) => leaf.mark === "arrowline") || all[0];
}

/**
 * The style that a mark shows, as far as the style has a say in it: only the keys that the mark
 * has are in the answer, so that the controls keep the rest.
 */
export function readStyle(object, unit) {
    const leaf = primaryLeaf(object);
    const kind = kindOf(leaf);
    const style = { opacity: object.opacity ?? 1 };
    const shadow = object.shadow;
    style.shadow = shadow
        ? { on: true, color: toHex(shadow.color) || "#000000", blur: shadow.blur / unit, offset: shadow.offsetX / unit }
        : { ...DEFAULT_STYLE.shadow, on: false };
    if (isText(leaf)) {
        Object.assign(style, {
            font: leaf.fontFamily,
            textSize: Math.round(leaf.fontSize / unit),
            bold: leaf.fontWeight === "bold" || Number(leaf.fontWeight) >= 600,
            italic: leaf.fontStyle === "italic",
            underline: Boolean(leaf.underline),
            linethrough: Boolean(leaf.linethrough),
            align: leaf.textAlign,
            lineHeight: leaf.lineHeight,
            spacing: leaf.charSpacing,
        });
        const color = toHex(leaf.fill);
        if (color) {
            style.stroke = color;
        }
        return style;
    }
    if (kind === "highlight") {
        const color = toHex(leaf.fill);
        if (color) {
            style.stroke = color;
        }
        return style;
    }
    if (kind === "redact" || kind === "image") {
        return style;
    }
    const stroke = toHex(leaf.stroke);
    if (stroke) {
        style.stroke = stroke;
    }
    if (leaf.strokeWidth) {
        style.width = Math.max(Math.round((leaf.strokeWidth / unit) * 10) / 10, 0.5);
    }
    style.dash = leaf.dashKind || "solid";
    if (CLOSED.includes(kind)) {
        const fill = leaf.fill;
        if (fill instanceof Gradient) {
            const [first, last] = fill.colorStops;
            const { x1, y1, x2, y2 } = fill.coords;
            style.fillMode = "gradient";
            style.gradient = {
                from: toHex(first.color) || "#FF0000",
                to: toHex(last.color) || "#0000FF",
                angle: Math.round((Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI),
            };
        } else if (fill instanceof Pattern) {
            style.fillMode = "pattern";
        } else if (toHex(fill) && !isTransparent(fill)) {
            style.fillMode = "solid";
            style.fill = toHex(fill);
        } else {
            style.fillMode = "none";
        }
    }
    if (kind === "rect") {
        style.radius = Math.round((leaf.rx || 0) / unit);
    }
    return style;
}

function isTransparent(value) {
    try {
        return new Color(value).getAlpha() === 0;
    } catch {
        return false;
    }
}

//------------------------------------------------------------------------------
// Style onto marks
//------------------------------------------------------------------------------

/**
 * Sets the keys of `patch` (keys of the style) on a mark. `style` is the whole style after the
 * change, for the keys that go together (a gradient has two colours and an angle).
 */
export function applyStyle(object, patch, style, unit) {
    const keys = Object.keys(patch);
    const touches = (...names) => names.some((name) => keys.includes(name));
    for (const leaf of leaves(object)) {
        const kind = kindOf(leaf);
        if (touches("stroke")) {
            setColor(leaf, kind, style.stroke);
        }
        if (touches("width", "dash")) {
            setLine(leaf, kind, style, unit);
        }
        if (touches("fillMode", "fill", "gradient") && CLOSED.includes(kind)) {
            leaf.set({ fill: fillFor(style, unit) });
        }
        if (touches("radius") && kind === "rect") {
            leaf.set({ rx: style.radius * unit, ry: style.radius * unit });
        }
        if (isText(leaf)) {
            setText(leaf, keys, style, unit);
        }
        leaf.dirty = true;
    }
    if (touches("opacity")) {
        object.set({ opacity: style.opacity });
    }
    if (touches("shadow")) {
        object.set({ shadow: shadowFor(style.shadow, unit) });
    }
    if (object.type === "group") {
        object.triggerLayout?.();
        object.setCoords();
    }
    object.dirty = true;
}

function setColor(leaf, kind, color) {
    if (kind === "text") {
        leaf.set({ fill: color });
    } else if (kind === "highlight") {
        leaf.set({ fill: withAlpha(color, HIGHLIGHT_ALPHA) });
    } else if (kind === "arrowhead") {
        leaf.set({ fill: color });
    } else if (kind !== "redact" && kind !== "image") {
        leaf.set({ stroke: color });
    }
}

function setLine(leaf, kind, style, unit) {
    const width = style.width * unit;
    if (kind === "arrowhead") {
        const head = Math.max(width * ARROW_HEAD_FACTOR, unit * 4);
        leaf.set({ width: head, height: head });
    } else if (kind !== "text" && kind !== "highlight" && kind !== "redact" && kind !== "image") {
        leaf.set({
            strokeWidth: width,
            strokeDashArray: dashArray(style.dash, width),
            strokeLineCap: style.dash === "dotted" ? "round" : "butt",
            dashKind: style.dash,
        });
    }
}

function setText(leaf, keys, style, unit) {
    const map = {
        font: () => ({ fontFamily: style.font }),
        textSize: () => ({ fontSize: style.textSize * unit }),
        bold: () => ({ fontWeight: style.bold ? "bold" : "normal" }),
        italic: () => ({ fontStyle: style.italic ? "italic" : "normal" }),
        underline: () => ({ underline: style.underline }),
        linethrough: () => ({ linethrough: style.linethrough }),
        align: () => ({ textAlign: style.align }),
        lineHeight: () => ({ lineHeight: style.lineHeight }),
        spacing: () => ({ charSpacing: style.spacing }),
    };
    for (const key of keys) {
        if (map[key]) {
            leaf.set(map[key]());
        }
    }
    if (keys.some((key) => ["fillMode", "gradient"].includes(key)) && style.fillMode === "gradient") {
        leaf.set({ fill: gradientFor(style.gradient) });
    } else if (keys.includes("fillMode") && style.fillMode !== "gradient") {
        leaf.set({ fill: style.stroke });
    }
    leaf.initDimensions?.();
}
