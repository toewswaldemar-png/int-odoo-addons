import { Component, onMounted, onWillDestroy, useExternalListener, useRef, useState } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { DocumentFile, MODEL } from "@int_filemanager/int_filemanager/document_file";
import { UPLOAD_ROUTE } from "@int_filemanager/int_filemanager/views/list/document_list_controller";
import { attachPinch } from "@int_filemanager/int_filemanager/touch/pinch";
import * as arrange from "./arrange";
import { ColorField } from "./color_field";
import {
    DEFAULT_FORMAT,
    FONTS,
    FORMATS,
    GRID_STEPS,
    HISTORY_LIMIT,
    SNAP_DISTANCE,
    STATE_MAX_SIZE,
    UNIT_PER_PIXEL,
    WORK_EDGE,
    ZOOM_STEP,
} from "./constants";
import { styleHandles } from "./controls";
import { ASPECTS, CropTool } from "./crop_tool";
import { BRUSHES, createBrush, DrawingTools } from "./drawing";
import { buildState, captureModel, readState, reviveObjects } from "./edit_state";
import { renderBlob, renderSvg } from "./export";
import {
    BLEND_COLOR_DEFAULT,
    BLEND_MODES,
    hasFilters,
    REMOVE_COLOR_DEFAULT,
    SLIDERS,
    sliderValue,
    TOGGLES,
    withSetting,
} from "./filters";
import { clamp } from "./geometry";
import { History } from "./history";
import { importFile, isImportable, placeInMiddle } from "./import_image";
import { applyStyle, bakeTextScale, DEFAULT_STYLE, drawDirectly, kindOf, readStyle } from "./marks";
import { drawOverlay } from "./overlay";
import { canvasFits, largestExportScale, loadPicture, Picture } from "./picture";
import { REDACT_DEFAULT, REDACT_MODES } from "./redact_mark";
import { SaveDialog } from "./save_dialog";
import { flipScene, turnScene } from "./scene_ops";
import { snapMove } from "./snapping";
import { Viewport } from "./viewport";

const { Canvas, Rect } = window.fabric;

// `separated`: a line above the button, to set the groups of tools apart.
const TOOLS = [
    { id: "select", icon: "fa-mouse-pointer", title: _t("Select (V)") },
    { id: "hand", icon: "fa-hand-paper-o", title: _t("Move the view (H, or hold Space)") },
    { id: "pen", icon: "fa-pencil", title: _t("Pen (P)"), separated: true },
    { id: "highlight", icon: "fa-paint-brush", title: _t("Highlight (M)") },
    { id: "text", icon: "fa-font", title: _t("Text (T)"), separated: true },
    { id: "textbox", icon: "fa-align-left", title: _t("Text box") },
    { id: "line", icon: "fa-minus", title: _t("Line (L)"), separated: true },
    { id: "arrow", icon: "fa-long-arrow-right", title: _t("Arrow (A)") },
    { id: "rect", icon: "fa-square-o", title: _t("Rectangle (R)") },
    { id: "ellipse", icon: "fa-circle-o", title: _t("Ellipse (E)") },
    { id: "circle", icon: "fa-dot-circle-o", title: _t("Circle") },
    { id: "triangle", icon: "fa-play fa-rotate-270", title: _t("Triangle") },
    { id: "polygon", icon: "fa-diamond", title: _t("Polygon (click each point)") },
    { id: "polyline", icon: "fa-line-chart", title: _t("Polyline (click each point)") },
    { id: "redact", icon: "fa-eye-slash", title: _t("Hide a part (X)"), separated: true },
    { id: "crop", icon: "fa-crop", title: _t("Crop and turn (C)"), separated: true },
    { id: "adjust", icon: "fa-sliders", title: _t("Adjust the picture (F)") },
];
// The tools that belong together are one button with a dropdown; the rest are single buttons.
const TOOL_GROUPS = [
    { id: "draw", title: _t("Draw"), tools: ["pen", "highlight"] },
    { id: "text", title: _t("Text"), tools: ["text", "textbox"] },
    {
        id: "shape",
        title: _t("Shapes"),
        tools: ["line", "arrow", "rect", "ellipse", "circle", "triangle", "polygon", "polyline"],
    },
];
const TOOL_KEYS = {
    v: "select",
    h: "hand",
    p: "pen",
    m: "highlight",
    t: "text",
    l: "line",
    a: "arrow",
    r: "rect",
    e: "ellipse",
    x: "redact",
    c: "crop",
    f: "adjust",
};
// The kind of mark that a tool makes, for the controls that it shows.
const TOOL_KIND = {
    pen: "path",
    highlight: "highlight",
    text: "text",
    textbox: "text",
    line: "line",
    arrow: "arrow",
    rect: "rect",
    ellipse: "ellipse",
    circle: "circle",
    triangle: "triangle",
    polygon: "polygon",
    polyline: "polyline",
    redact: "redact",
};
const TOOLS_THAT_FIND_MARKS = ["select", "adjust", "text", "textbox"];
const LINE_KINDS = ["line", "arrow", "rect", "ellipse", "circle", "triangle", "polygon", "polyline", "path", "group", "mixed"];
const COLOR_KINDS = [...LINE_KINDS, "text", "highlight"];
const FILL_KINDS = ["rect", "ellipse", "circle", "triangle", "polygon"];
const NO_EFFECT_KINDS = ["redact"];
const HINTS = {
    hand: _t("Drag to move the picture. The wheel zooms."),
    polygon: _t("Click each point. Click the first point, double-click or press Enter to finish."),
    polyline: _t("Click each point. Double-click or press Enter to finish."),
    text: _t("Click on the picture and type."),
    textbox: _t("Click on the picture and type. Drag a handle to set the width."),
    redact: _t("Drag over what is to be hidden."),
    crop: _t("Drag the frame and its handles; then apply."),
};
const ANGLE_STEP = 15;
const NUDGE = 1;
const NUDGE_BIG = 10;
const COPY_OFFSET = 20;
const IMPORT_ACCEPT = "image/png,image/jpeg,image/webp,image/gif,image/svg+xml";

/** @returns {Object} a plain copy of `value` (the state is reactive, Fabric wants no proxies) */
function plain(value) {
    return JSON.parse(JSON.stringify(value));
}

/** @returns {{clientX: number, clientY: number}} where a mouse or a touch event is */
function pointOf(event) {
    return event.touches?.[0] || event.changedTouches?.[0] || event;
}

/**
 * Draws on a picture of a document and works on its looks. The picture is the background of a
 * Fabric canvas that has the size of the picture (the screen only zooms it); what is put on it
 * are objects that can be moved and changed until the picture is stored. It is stored as a new
 * document in the folder of the old one, which stays as it is, and the state of the editor
 * (marks, filters, crop) is kept with it, so that the next edit finds the marks as objects again.
 */
export class DocumentImageEditor extends Component {
    static template = "int_filemanager.DocumentImageEditor";
    static components = { ColorField, Dropdown, DropdownItem };
    static props = { file: Object, close: Function };

    setup() {
        this.tools = TOOLS;
        this.toolEntries = this.makeToolEntries();
        this.fonts = FONTS;
        this.brushes = BRUSHES;
        this.sliders = SLIDERS;
        this.toggles = TOGGLES;
        this.blendModes = BLEND_MODES;
        this.redactModes = REDACT_MODES;
        this.aspects = ASPECTS;
        this.gridSteps = GRID_STEPS;
        this.acceptedPictures = IMPORT_ACCEPT;
        this.labels = this.makeLabels();
        this.rootRef = useRef("root");
        this.canvasRef = useRef("canvas");
        this.stageRef = useRef("stage");
        this.importRef = useRef("import");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.action = useService("action");
        this.fileUpload = useService("file_upload");
        this.orm = useService("orm");
        this.ui = useService("ui");
        this.state = useState({
            tool: "select",
            style: plain(DEFAULT_STYLE),
            redact: { ...REDACT_DEFAULT },
            selection: { count: 0, kind: null, locked: false, canGroup: false, canUngroup: false },
            filters: {},
            cropped: false,
            aspect: "free",
            grid: false,
            gridStep: GRID_STEPS[1],
            snap: "off",
            zoom: 100,
            panel: !this.ui.isSmall,
            // The tool that each dropdown of tools shows: the one that was used last.
            lastOfGroup: Object.fromEntries(TOOL_GROUPS.map((group) => [group.id, group.tools[0]])),
            hasClipboard: false,
            canUndo: false,
            canRedo: false,
            ready: false,
            saving: false,
        });
        this.canvas = null;
        this.picture = null;
        this.viewport = null;
        this.drawing = new DrawingTools(this);
        this.cropTool = new CropTool(this);
        this.history = new History(HISTORY_LIMIT);
        /** the part of the scene that is stored: `null` is all of it */
        this.crop = null;
        this.scene = { width: 1, height: 1 };
        this.unit = 1;
        this.sourceFile = this.props.file;
        this.guides = [];
        this.clipboard = [];
        this.panning = null;
        this.spaceDown = false;
        this.exporting = false;
        this.busy = false;
        this.filterFrame = null;
        this.frozen = [];
        this.resizeObserver = null;
        this.detachPinch = null;
        useExternalListener(window, "beforeunload", (ev) => {
            if (this.history.changed) {
                ev.preventDefault();
            }
        });
        onMounted(() => {
            this.rootRef.el.focus(); // the keys of the editor work from the start
            this.start();
        });
        onWillDestroy(() => {
            this.resizeObserver?.disconnect();
            this.detachPinch?.();
            cancelAnimationFrame(this.filterFrame);
            this.canvas?.dispose();
        });
    }

    /** @returns {Object[]} the buttons of the column: a tool, or a group `{id, title, tools}` of them */
    makeToolEntries() {
        const byId = new Map(TOOLS.map((tool) => [tool.id, tool]));
        const entries = [];
        const done = new Set();
        for (const tool of TOOLS) {
            if (done.has(tool.id)) {
                continue;
            }
            const group = TOOL_GROUPS.find((candidate) => candidate.tools[0] === tool.id);
            if (group) {
                group.tools.forEach((id) => done.add(id));
                entries.push({
                    id: group.id,
                    title: group.title,
                    separated: tool.separated,
                    tools: group.tools.map((id) => byId.get(id)),
                });
            } else {
                entries.push(tool);
            }
        }
        return entries;
    }

    get menuPosition() {
        // Beside the column; over a small screen the tools lie in a row and the menu opens under it.
        return this.ui.isSmall ? "bottom-start" : "right-start";
    }

    isGroupActive(entry) {
        return entry.tools.some((tool) => tool.id === this.state.tool);
    }

    /** @returns {string} the icon of the tool that the dropdown shows (the one used last) */
    groupIcon(entry) {
        const id = this.state.lastOfGroup[entry.id];
        return entry.tools.find((tool) => tool.id === id).icon;
    }

    makeLabels() {
        return {
            brightness: _t("Brightness"),
            contrast: _t("Contrast"),
            saturation: _t("Saturation"),
            vibrance: _t("Vibrance"),
            gamma: _t("Gamma"),
            hue: _t("Hue"),
            blur: _t("Blur"),
            noise: _t("Noise"),
            pixelate: _t("Pixelate"),
            grayscale: _t("Grayscale"),
            blackwhite: _t("Black and white"),
            sepia: _t("Sepia"),
            invert: _t("Invert"),
            vintage: _t("Vintage"),
            polaroid: _t("Polaroid"),
            kodachrome: _t("Kodachrome"),
            technicolor: _t("Technicolor"),
            brownie: _t("Brownie"),
            sharpen: _t("Sharpen"),
            emboss: _t("Emboss"),
            pencil: _t("Pencil"),
            spray: _t("Spray"),
            circles: _t("Circles"),
            pattern: _t("Pattern"),
            color: _t("Color"),
            fillColor: _t("Fill color"),
            gradientFrom: _t("Gradient: from"),
            gradientTo: _t("Gradient: to"),
            shadowColor: _t("Shadow color"),
            pixelateMode: _t("Pixels"),
            blurMode: _t("Blur"),
            blackMode: _t("Black"),
            free: _t("Free"),
            original: _t("As the picture"),
            multiply: _t("Multiply"),
            add: _t("Add"),
            difference: _t("Difference"),
            screen: _t("Screen"),
            subtract: _t("Subtract"),
            darken: _t("Darken"),
            lighten: _t("Lighten"),
            overlay: _t("Overlay"),
            exclusion: _t("Exclusion"),
            tint: _t("Tint"),
        };
    }

    //--------------------------------------------------------------------------
    // Start
    //--------------------------------------------------------------------------

    async start() {
        const { file } = this.props;
        let sourceFile = file;
        let saved = null;
        try {
            // A picture that the editor stored before comes with the state it was made in, and the
            // picture it was made on (if the user may read that).
            const session = await this.orm.call(MODEL, "get_edit_session", [[file.id]]);
            if (session.source && new DocumentFile(session.source).isImage) {
                sourceFile = new DocumentFile({ ...session.source, folder_id: file.folder_id });
                saved = session.state;
            }
        } catch {
            // The editor starts from the picture as it is.
        }
        let element;
        try {
            element = await loadPicture(sourceFile.defaultSource);
        } catch {
            if (sourceFile === file) {
                this.fail();
                return;
            }
            // The picture it was made on is gone: the flat one is all that is left.
            sourceFile = file;
            saved = null;
            try {
                element = await loadPicture(file.defaultSource);
            } catch {
                this.fail();
                return;
            }
        }
        if (!this.canvasRef.el) {
            return; // closed while the picture was loading
        }
        this.sourceFile = sourceFile;
        this.picture = new Picture(element, WORK_EDGE);
        this.picture.resetPlacement();
        const { width, height } = this.picture.size;
        this.unit = Math.max(Math.max(width, height) * UNIT_PER_PIXEL, 1);
        this.scene = this.picture.sceneSize;
        const stage = this.stageRef.el;
        this.canvas = new Canvas(this.canvasRef.el, {
            width: stage.clientWidth || 1,
            height: stage.clientHeight || 1,
            preserveObjectStacking: true,
            stopContextMenu: true,
            fireRightClick: false,
            fireMiddleClick: true,
            selectionKey: "shiftKey",
            // No key turns the scaling by a corner into a stretch: a text would be pulled out of shape.
            uniScaleKey: null,
        });
        this.canvas.backgroundImage = this.picture.image;
        this.viewport = new Viewport(this.canvas, stage, () => {
            this.state.zoom = Math.round(this.viewport.zoom * 100);
        });
        this.bindEvents();
        this.resizeObserver = new ResizeObserver(() => this.viewport.resize());
        this.resizeObserver.observe(stage);
        this.detachPinch = attachPinch(stage, {
            onPinch: ({ factor, x, y, previous }) => this.onPinch(factor, x, y, previous),
        });
        const model = readState(saved, this.picture.size);
        if (model) {
            await this.applyModel(model);
        } else {
            this.updateRegion();
        }
        this.history.reset(this.snapshot());
        this.syncHistory();
        this.applyToolSettings();
        this.state.ready = true;
        if (!canvasFits(width, height)) {
            this.notification.add(
                _t("This picture is larger than your browser can store at full size. The file can be made smaller only."),
                { type: "warning" }
            );
        }
    }

    fail() {
        this.notification.add(_t("The picture could not be loaded."), { type: "danger" });
        this.props.close();
    }

    bindEvents() {
        this.canvas.on({
            "mouse:down": (ev) => this.onMouseDown(ev),
            "mouse:move": (ev) => this.onMouseMove(ev),
            "mouse:up": () => this.onMouseUp(),
            "mouse:dblclick": () => this.drawing.finishPoly(),
            "mouse:wheel": (ev) => this.onWheel(ev),
            "object:added": ({ target }) => this.styleControls(target),
            "object:modified": (ev) => this.onObjectModified(ev),
            "object:moving": (ev) => this.onObjectMoving(ev),
            "object:rotating": (ev) => this.onObjectRotating(ev),
            "path:created": ({ path }) => this.onPathCreated(path),
            "text:editing:exited": ({ target }) => this.onTextEdited(target),
            "selection:created": () => this.onSelection(),
            "selection:updated": () => this.onSelection(),
            "selection:cleared": () => this.syncSelection(),
            "after:render": ({ ctx }) => this.paintOverlay(ctx),
        });
    }

    //--------------------------------------------------------------------------
    // Tools
    //--------------------------------------------------------------------------

    setTool(tool) {
        if (!this.canvas) {
            return;
        }
        const leavingCrop = this.cropTool.active && tool !== "crop";
        this.drawing.abort();
        if (leavingCrop) {
            this.cancelCrop();
        }
        this.state.tool = tool;
        const group = TOOL_GROUPS.find((candidate) => candidate.tools.includes(tool));
        if (group) {
            this.state.lastOfGroup[group.id] = tool;
        }
        this.canvas.discardActiveObject();
        // The keys of the tools work from where the click was.
        this.rootRef.el.focus();
        if (tool === "crop" && !this.cropTool.active) {
            this.startCrop();
        }
        this.applyToolSettings();
    }

    /** Sets the canvas up for the tool that is on (and for a held Space, which moves the view). */
    applyToolSettings() {
        const { canvas } = this;
        const { tool, style } = this.state;
        const grabbing = this.spaceDown || tool === "hand";
        canvas.isDrawingMode = !grabbing && tool === "pen";
        if (canvas.isDrawingMode) {
            canvas.freeDrawingBrush = createBrush(canvas, plain(style), this.unit);
        }
        canvas.selection = !grabbing && ["select", "adjust"].includes(tool);
        canvas.skipTargetFind = grabbing || !(TOOLS_THAT_FIND_MARKS.includes(tool) || tool === "crop");
        canvas.defaultCursor = grabbing ? "grab" : tool === "select" || tool === "adjust" ? "default" : "crosshair";
        canvas.hoverCursor = grabbing ? "grab" : "move";
        canvas.requestRenderAll();
    }

    syncBrush() {
        if (this.canvas?.isDrawingMode) {
            this.canvas.freeDrawingBrush = createBrush(this.canvas, plain(this.state.style), this.unit);
        }
    }

    get hint() {
        return HINTS[this.state.tool] || "";
    }

    //--------------------------------------------------------------------------
    // The pointer
    //--------------------------------------------------------------------------

    onMouseDown(ev) {
        if (ev.e.button === 1 || this.spaceDown || this.state.tool === "hand") {
            const { clientX, clientY } = pointOf(ev.e);
            this.panning = { x: clientX, y: clientY };
            this.canvas.setCursor("grabbing");
            return;
        }
        this.drawing.onMouseDown(ev);
    }

    onMouseMove(ev) {
        if (this.panning) {
            const { clientX, clientY } = pointOf(ev.e);
            this.viewport.panBy(clientX - this.panning.x, clientY - this.panning.y);
            this.panning = { x: clientX, y: clientY };
            return;
        }
        this.drawing.onMouseMove(ev);
    }

    onMouseUp() {
        if (this.panning) {
            this.panning = null;
            this.applyToolSettings();
            return;
        }
        this.drawing.onMouseUp();
        if (this.guides.length) {
            this.guides = [];
            this.canvas.requestRenderAll();
        }
    }

    onWheel({ e }) {
        e.preventDefault();
        e.stopPropagation();
        const { x, y } = this.canvas.getViewportPoint(e);
        this.viewport.zoomBy(Math.pow(1.0015, -e.deltaY), { x, y });
    }

    onPinch(factor, x, y, previous) {
        // Two fingers are no drawing: what the first one began is given up.
        this.drawing.abort();
        const box = this.stageRef.el.getBoundingClientRect();
        this.viewport.panBy(x - previous.x, y - previous.y);
        this.viewport.zoomBy(factor, { x: x - box.left, y: y - box.top });
    }

    /**
     * What a mark gets when it comes onto the canvas (drawn, pasted, brought back by the undo or
     * by a stored state): the look and the cursors of its handles (`controls.js`), and no cache.
     */
    styleControls(object) {
        styleHandles(object);
        drawDirectly(object);
    }

    onObjectModified({ target }) {
        if (target === this.cropTool.rect) {
            this.cropTool.normalize();
            this.canvas.requestRenderAll();
            return;
        }
        this.guides = [];
        bakeTextScale(target);
        // A mark that was made larger or turned may reach out; it is brought back.
        this.keepMarkInside(target);
        this.commit();
    }

    /**
     * Moves a mark (or the selection) so that it lies inside the part that is stored. One that is
     * larger than that part is kept covering it: a mark that is wholly outside cannot be got at.
     */
    keepMarkInside(object) {
        const { left, top, width, height } = this.regionBox;
        const box = this.freshBox(object);
        const shift = (start, length, from, size) => {
            const low = Math.min(from, from + size - length);
            const high = Math.max(from, from + size - length);
            return clamp(start, low, high) - start;
        };
        const dx = shift(box.left, box.width, left, width);
        const dy = shift(box.top, box.height, top, height);
        if (dx || dy) {
            object.set({ left: object.left + dx, top: object.top + dy });
            object.setCoords();
        }
    }

    /**
     * The box of a mark as it is now. While a mark is dragged Fabric fires `object:moving` before it
     * works out the coordinates of the new place (it does that after the handlers ran), so what
     * `getBoundingRect` reads is one step old; a correction made from it jumps back and forth.
     */
    freshBox(object) {
        object.setCoords();
        return object.getBoundingRect();
    }

    onObjectMoving({ target }) {
        if (target === this.cropTool.rect) {
            this.cropTool.constrainMoving();
            return;
        }
        if (this.state.snap !== "off") {
            this.snapMoving(target);
        }
        this.keepMarkInside(target);
    }

    snapMoving(target) {
        const members = target.getObjects?.() || [];
        const others = this.canvas
            .getObjects()
            .filter((object) => object !== target && !members.includes(object) && !object.helper)
            .map((object) => object.getBoundingRect());
        const { dx, dy, guides } = snapMove(this.freshBox(target), {
            others,
            region: this.regionBox,
            distance: SNAP_DISTANCE / this.viewport.zoom,
            grid: this.state.snap === "grid" ? this.state.gridStep * this.unit : null,
            objects: this.state.snap === "objects",
        });
        if (dx || dy) {
            target.set({ left: target.left + dx, top: target.top + dy });
            target.setCoords();
        }
        this.guides = guides;
    }

    onObjectRotating({ target }) {
        if (this.state.snap !== "off") {
            target.set({ angle: Math.round(target.angle / ANGLE_STEP) * ANGLE_STEP });
        }
    }

    onPathCreated(path) {
        // A stroke that began and ended outside the picture is nothing.
        const { left, top, width, height } = this.regionBox;
        const box = path.getBoundingRect();
        if (box.left > left + width || box.top > top + height || box.left + box.width < left || box.top + box.height < top) {
            this.canvas.remove(path);
            return;
        }
        if (path.type === "path") {
            path.set({ strokeUniform: true, dashKind: this.state.style.dash });
        }
        this.commit();
    }

    onTextEdited(text) {
        if (!text.text.trim()) {
            this.canvas.remove(text);
        }
        this.commit();
    }

    /** What is drawn over the picture and does not go into the file. */
    paintOverlay(ctx) {
        // Fabric fires `after:render` for the upper layer as well (selection, brush); what is drawn
        // there is not cleared when the view changes, and stays behind at the old place. The
        // overlay belongs on the lower layer only, which is drawn anew with every change.
        if (this.exporting || !this.viewport || ctx !== this.canvas.getContext()) {
            return;
        }
        drawOverlay(ctx, this.canvas.viewportTransform, {
            region: this.regionBox,
            zoom: this.viewport.zoom,
            grid: this.state.grid ? { step: this.state.gridStep * this.unit } : null,
            guides: this.guides,
            shade: this.cropTool.active ? this.cropTool.box : null,
            poly: this.drawing.polyOverlay(),
        });
    }

    //--------------------------------------------------------------------------
    // The selection and the style
    //--------------------------------------------------------------------------

    get selectedObjects() {
        return this.canvas ? this.canvas.getActiveObjects().filter((object) => !object.helper) : [];
    }

    onSelection() {
        // A selection of several marks is an object of its own, which is not added to the canvas.
        const selected = this.canvas.getActiveObject();
        if (selected?.type === "activeselection") {
            this.styleControls(selected);
        }
        this.syncSelection();
    }

    syncSelection() {
        const objects = this.selectedObjects;
        if (!objects.length) {
            Object.assign(this.state.selection, { count: 0, kind: null, locked: false, canGroup: false, canUngroup: false });
            return;
        }
        const kinds = new Set(objects.map(kindOf));
        const kind = kinds.size === 1 ? [...kinds][0] : "mixed";
        Object.assign(this.state.selection, {
            count: objects.length,
            kind,
            locked: objects.every(arrange.isLocked),
            canGroup: arrange.canGroup(this.canvas),
            canUngroup: arrange.canUngroup(this.canvas),
        });
        // The controls show the first mark; a change goes to all of them.
        Object.assign(this.state.style, readStyle(objects[0], this.unit));
        if (kind === "redact") {
            Object.assign(this.state.redact, {
                mode: objects[0].mode,
                strength: Math.round(objects[0].strength / this.unit),
            });
        }
    }

    /** The kind of mark that the controls are for: the selected one, else what the tool makes. */
    get kind() {
        const { selection, tool } = this.state;
        return selection.count ? selection.kind : TOOL_KIND[tool] || null;
    }

    get hasColor() {
        return COLOR_KINDS.includes(this.kind);
    }

    get hasLine() {
        return LINE_KINDS.includes(this.kind);
    }

    get hasFill() {
        return FILL_KINDS.includes(this.kind);
    }

    get hasRadius() {
        return this.kind === "rect";
    }

    get isTextKind() {
        return this.kind === "text";
    }

    get isRedact() {
        return this.kind === "redact";
    }

    get hasEffects() {
        const { kind } = this;
        return Boolean(kind) && !NO_EFFECT_KINDS.includes(kind);
    }

    get isPen() {
        return this.state.tool === "pen" && !this.state.selection.count;
    }

    get hasSelection() {
        return this.state.selection.count > 0;
    }

    get isCropTool() {
        return this.state.tool === "crop";
    }

    get isAdjustTool() {
        return this.state.tool === "adjust";
    }

    /**
     * Sets keys of the style for what is made next and for the marks that are selected.
     * @param {Object} patch
     * @param {boolean} [live] true while a slider moves: the history gets the end of it only
     */
    setStyle(patch, { live = false } = {}) {
        Object.assign(this.state.style, patch);
        this.syncBrush();
        const objects = this.selectedObjects;
        if (!objects.length) {
            return;
        }
        const style = plain(this.state.style);
        for (const object of objects) {
            applyStyle(object, patch, style, this.unit);
        }
        this.canvas.requestRenderAll();
        if (!live) {
            this.commit();
        }
    }

    // The templates of Owl have no `Number` or `String` of their own: the handlers read the values.
    onStyleInput(key, ev) {
        this.setStyle({ [key]: Number(ev.target.value) }, { live: true });
    }

    /** A choice from a list (a text). */
    onStyleChoice(key, ev) {
        this.setStyle({ [key]: ev.target.value });
    }

    onNestedInput(key, field, ev) {
        this.setStyle({ [key]: { ...this.state.style[key], [field]: Number(ev.target.value) } }, { live: true });
    }

    onGradientColor(field, color) {
        this.setStyle({ gradient: { ...this.state.style.gradient, [field]: color } });
    }

    onShadowColor(color) {
        this.setStyle({ shadow: { ...this.state.style.shadow, color } });
    }

    onShadowToggle(ev) {
        this.setStyle({ shadow: { ...this.state.style.shadow, on: ev.target.checked } });
    }

    onCommitInput() {
        this.commit();
    }

    toggleStyle(key) {
        this.setStyle({ [key]: !this.state.style[key] });
    }

    onRedactMode(ev) {
        this.setRedact({ mode: ev.target.value });
    }

    onRedactStrength(ev) {
        this.setRedact({ strength: Number(ev.target.value) }, { live: true });
    }

    setRedact(patch, { live = false } = {}) {
        Object.assign(this.state.redact, patch);
        const marks = this.selectedObjects.filter((object) => object.mark === "redact");
        for (const mark of marks) {
            mark.set({ mode: this.state.redact.mode, strength: this.state.redact.strength * this.unit });
            mark.dirty = true;
        }
        this.canvas.requestRenderAll();
        if (marks.length && !live) {
            this.commit();
        }
    }

    //--------------------------------------------------------------------------
    // Marks that are there
    //--------------------------------------------------------------------------

    order(how) {
        arrange.order(this.canvas, how);
        this.commit();
    }

    group() {
        arrange.group(this.canvas);
        this.commit();
    }

    ungroup() {
        arrange.ungroup(this.canvas);
        this.commit();
    }

    async duplicate() {
        await arrange.duplicate(this.canvas, COPY_OFFSET * this.unit);
        this.commit();
    }

    async copy() {
        const objects = this.selectedObjects;
        if (objects.length) {
            this.clipboard = await arrange.cloneAll(objects);
            this.state.hasClipboard = true;
        }
    }

    async paste() {
        if (!this.clipboard.length) {
            return;
        }
        this.canvas.discardActiveObject();
        const copies = await arrange.addCopies(this.canvas, this.clipboard, COPY_OFFSET * this.unit);
        // The next paste goes a step further, so that copies do not lie on each other.
        this.clipboard = await arrange.cloneAll(copies);
        this.commit();
    }

    align(how) {
        arrange.align(this.canvas, how, this.regionBox);
        this.commit();
    }

    distribute(axis) {
        arrange.distribute(this.canvas, axis);
        this.commit();
    }

    mirrorSelection(axis) {
        arrange.mirror(this.canvas, axis);
        this.commit();
    }

    toggleLock() {
        const objects = this.selectedObjects;
        const lock = !objects.every(arrange.isLocked);
        for (const object of objects) {
            arrange.setLocked(object, lock);
        }
        this.syncSelection();
        this.canvas.requestRenderAll();
        this.commit();
    }

    deleteSelection() {
        const objects = this.selectedObjects;
        if (!objects.length) {
            return;
        }
        this.canvas.discardActiveObject();
        this.canvas.remove(...objects);
        this.canvas.requestRenderAll();
        this.commit();
    }

    selectAll() {
        arrange.selectAll(this.canvas);
    }

    //--------------------------------------------------------------------------
    // The filters of the picture
    //--------------------------------------------------------------------------

    get hasFilters() {
        return hasFilters(this.state.filters);
    }

    filterValue(id) {
        return sliderValue(this.state.filters, id);
    }

    setFilter(id, value) {
        this.state.filters = withSetting(this.state.filters, id, value);
        this.scheduleFilters();
    }

    onFilterInput(id, ev) {
        this.setFilter(id, Number(ev.target.value));
    }

    onFilterChange(id, ev) {
        this.setFilter(id, Number(ev.target.value));
        this.commit();
    }

    toggleFilter(id) {
        this.setFilter(id, !this.state.filters[id]);
        this.commit();
    }

    /** Applies a colour filter with its settings; `null` turns it off. */
    setColorFilter(id, value) {
        const next = { ...this.state.filters };
        if (value) {
            next[id] = value;
        } else {
            delete next[id];
        }
        this.state.filters = next;
        this.scheduleFilters();
    }

    toggleColorFilter(id, defaults) {
        this.setColorFilter(id, this.state.filters[id] ? null : { ...defaults });
        this.commit();
    }

    onColorFilterRange(id, key, ev) {
        this.onColorFilterChange(id, key, Number(ev.target.value), { live: true });
    }

    onColorFilterChoice(id, key, ev) {
        this.onColorFilterChange(id, key, ev.target.value);
    }

    onColorFilterChange(id, key, value, { live = false } = {}) {
        this.setColorFilter(id, { ...this.state.filters[id], [key]: value });
        if (!live) {
            this.commit();
        }
    }

    resetFilters() {
        this.state.filters = {};
        this.scheduleFilters();
        this.commit();
    }

    get removeColorDefaults() {
        return REMOVE_COLOR_DEFAULT;
    }

    get blendColorDefaults() {
        return BLEND_COLOR_DEFAULT;
    }

    /** The filters run once per frame, however fast a slider moves. */
    scheduleFilters() {
        if (this.filterFrame) {
            return;
        }
        this.filterFrame = requestAnimationFrame(() => {
            this.filterFrame = null;
            this.applyFilters();
        });
    }

    applyFilters() {
        this.picture.setFilters(plain(this.state.filters));
        this.canvas.requestRenderAll();
    }

    //--------------------------------------------------------------------------
    // Crop and turn
    //--------------------------------------------------------------------------

    /** The part of the scene that the view shows and the file holds. */
    get regionBox() {
        if (this.crop && !this.cropTool.active) {
            return this.crop;
        }
        return { left: 0, top: 0, ...this.scene };
    }

    updateRegion() {
        this.scene = this.picture.sceneSize;
        // Nothing is drawn outside the part that is stored: what lies beyond it is cut off on the
        // screen as it is in the file.
        const region = this.regionBox;
        this.canvas.clipPath = new Rect({ ...region, originX: "left", originY: "top", absolutePositioned: true });
        this.viewport.setRegion(region);
    }

    startCrop() {
        this.freezeMarks(true);
        this.updateRegion();
        this.cropTool.start();
        this.state.aspect = this.cropTool.aspect;
    }

    cancelCrop() {
        this.cropTool.cancel();
        this.freezeMarks(false);
        this.updateRegion();
    }

    /** While the frame is chosen the marks are not to be grabbed. */
    freezeMarks(freeze) {
        if (freeze) {
            this.frozen = this.canvas.getObjects().map((object) => [object, object.selectable, object.evented]);
            this.frozen.forEach(([object]) => object.set({ selectable: false, evented: false }));
        } else {
            this.frozen.forEach(([object, selectable, evented]) => object.set({ selectable, evented }));
            this.frozen = [];
        }
    }

    setAspect(id) {
        this.state.aspect = id;
        this.cropTool.setAspect(id);
    }

    onAspect(ev) {
        this.setAspect(ev.target.value);
    }

    applyCrop() {
        if (!this.cropTool.active) {
            return;
        }
        const box = this.cropTool.normalize();
        const { width, height } = this.scene;
        const whole = box.left <= 0 && box.top <= 0 && box.width >= width && box.height >= height;
        this.crop = whole ? null : { ...box };
        this.state.cropped = Boolean(this.crop);
        this.setTool("select");
        this.commit();
    }

    resetCrop() {
        this.crop = null;
        this.state.cropped = false;
        if (this.cropTool.active) {
            this.cropTool.cancel();
            this.freezeMarks(false);
            this.startCrop();
        } else {
            this.updateRegion();
            this.commit();
        }
    }

    rotate(clockwise = true) {
        for (let turn = 0; turn < (clockwise ? 1 : 3); turn++) {
            this.crop = turnScene(this.canvas, this.picture, this.crop);
        }
        this.afterSceneChange();
    }

    flip(horizontal) {
        this.crop = flipScene(this.canvas, this.picture, this.crop, horizontal);
        this.afterSceneChange();
    }

    afterSceneChange() {
        this.state.cropped = Boolean(this.crop);
        this.scene = this.picture.sceneSize;
        if (this.cropTool.active) {
            this.cropTool.normalize();
        }
        this.updateRegion();
        this.canvas.requestRenderAll();
        this.commit();
    }

    //--------------------------------------------------------------------------
    // The view
    //--------------------------------------------------------------------------

    zoomIn() {
        this.viewport.zoomBy(ZOOM_STEP);
    }

    zoomOut() {
        this.viewport.zoomBy(1 / ZOOM_STEP);
    }

    zoomFit() {
        this.viewport.fit();
    }

    /** One screen pixel to one pixel of the picture. */
    zoomActual() {
        this.viewport.zoomTo(1);
    }

    togglePanel() {
        this.state.panel = !this.state.panel;
    }

    onGrid(ev) {
        this.state.grid = ev.target.checked;
        this.canvas.requestRenderAll();
    }

    onGridStep(ev) {
        this.state.gridStep = Number(ev.target.value);
        this.canvas.requestRenderAll();
    }

    onSnap(ev) {
        this.state.snap = ev.target.value;
    }

    //--------------------------------------------------------------------------
    // Pictures that are put on the picture
    //--------------------------------------------------------------------------

    chooseImport() {
        this.importRef.el.click();
    }

    async onImportChosen(ev) {
        const [file] = ev.target.files;
        ev.target.value = "";
        if (file) {
            await this.addPicture(file);
        }
    }

    async onPaste(ev) {
        if (this.canvas?.getActiveObject()?.isEditing) {
            return;
        }
        const file = [...(ev.clipboardData?.files || [])].find(isImportable);
        if (file) {
            ev.preventDefault();
            await this.addPicture(file);
        } else if (this.clipboard.length) {
            ev.preventDefault();
            await this.paste();
        }
    }

    async addPicture(file) {
        if (!isImportable(file)) {
            this.notification.add(_t("This kind of file cannot be put on a picture."), { type: "warning" });
            return;
        }
        try {
            const object = await importFile(file);
            placeInMiddle(object, this.regionBox);
            this.setTool("select");
            this.canvas.add(object);
            this.canvas.setActiveObject(object);
            this.commit();
        } catch {
            this.notification.add(_t("The file could not be put on the picture."), { type: "danger" });
        }
    }

    //--------------------------------------------------------------------------
    // History
    //--------------------------------------------------------------------------

    /** @returns {string} the edit as JSON text, as the history keeps it */
    snapshot() {
        return JSON.stringify(
            captureModel({
                picture: this.picture,
                canvas: this.canvas,
                filters: plain(this.state.filters),
                crop: this.crop,
            })
        );
    }

    commit() {
        if (this.history.push(this.snapshot())) {
            this.syncHistory();
        }
    }

    syncHistory() {
        this.state.canUndo = this.history.canUndo;
        this.state.canRedo = this.history.canRedo;
    }

    get changed() {
        return this.history.changed;
    }

    async undo() {
        await this.step(() => this.history.undo());
    }

    async redo() {
        await this.step(() => this.history.redo());
    }

    async step(move) {
        if (this.busy || !this.state.ready) {
            return;
        }
        this.busy = true;
        try {
            this.drawing.abort();
            if (this.cropTool.active) {
                this.setTool("select");
            }
            const entry = move();
            if (entry !== undefined) {
                await this.applyModel(JSON.parse(entry));
            }
            this.syncHistory();
        } finally {
            this.busy = false;
        }
    }

    /** Puts the picture, the filters, the crop and the marks of a state onto the canvas. */
    async applyModel(model) {
        const objects = await reviveObjects(model.objects);
        const { canvas } = this;
        canvas.discardActiveObject();
        canvas.remove(...canvas.getObjects());
        this.picture.place(model.base);
        this.state.filters = { ...model.filters };
        this.picture.setFilters(plain(this.state.filters));
        this.crop = model.crop;
        this.state.cropped = Boolean(model.crop);
        for (const object of objects) {
            if (object.locked) {
                arrange.setLocked(object, true);
            }
        }
        if (objects.length) {
            canvas.add(...objects);
        }
        this.updateRegion();
        this.syncSelection();
        canvas.requestRenderAll();
    }

    //--------------------------------------------------------------------------
    // Keys
    //--------------------------------------------------------------------------

    onKeydown(ev) {
        const active = this.canvas?.getActiveObject();
        if (active?.isEditing) {
            return; // the text takes the keys
        }
        const inField = ev.target.matches?.("input, select, textarea");
        if (ev.key === "Escape") {
            this.onEscape();
            return;
        }
        if (inField || !this.state.ready) {
            return;
        }
        const withCtrl = ev.ctrlKey || ev.metaKey;
        const key = ev.key.toLowerCase();
        // A button that has the focus keeps Space and Enter: they press it.
        if ((key === " " || key === "enter") && ev.target.matches?.("button, a, summary")) {
            return;
        }
        if (key === " " && !this.spaceDown) {
            ev.preventDefault();
            this.spaceDown = true;
            this.applyToolSettings();
        } else if (key === "delete" || key === "backspace") {
            ev.preventDefault();
            this.deleteSelection();
        } else if (key === "enter") {
            ev.preventDefault();
            this.onEnter();
        } else if (withCtrl) {
            this.onShortcut(ev, key);
        } else if (key.startsWith("arrow")) {
            ev.preventDefault();
            const step = (ev.shiftKey ? NUDGE_BIG : NUDGE) * this.unit;
            arrange.nudge(this.canvas, key === "arrowleft" ? -step : key === "arrowright" ? step : 0, key === "arrowup" ? -step : key === "arrowdown" ? step : 0);
            const moved = this.canvas.getActiveObject();
            if (moved && !moved.helper) {
                this.keepMarkInside(moved);
            }
            this.commit();
        } else if (key === "+" || key === "=") {
            this.zoomIn();
        } else if (key === "-") {
            this.zoomOut();
        } else if (key === "0") {
            this.zoomFit();
        } else if (key === "1") {
            this.zoomActual();
        } else if (!ev.altKey && TOOL_KEYS[key]) {
            this.setTool(TOOL_KEYS[key]);
        }
    }

    onShortcut(ev, key) {
        const actions = {
            z: () => (ev.shiftKey ? this.redo() : this.undo()),
            y: () => this.redo(),
            a: () => this.selectAll(),
            c: () => this.copy(),
            x: async () => {
                await this.copy();
                this.deleteSelection();
            },
            d: () => this.duplicate(),
            g: () => (ev.shiftKey ? this.ungroup() : this.group()),
        };
        if (actions[key]) {
            ev.preventDefault();
            actions[key]();
        }
    }

    onKeyup(ev) {
        if (ev.key === " " && this.spaceDown) {
            this.spaceDown = false;
            this.applyToolSettings();
        }
    }

    onEnter() {
        if (this.drawing.poly) {
            this.drawing.finishPoly();
        } else if (this.cropTool.active) {
            this.applyCrop();
        }
    }

    onEscape() {
        if (this.drawing.busy) {
            this.drawing.abort();
        } else if (this.cropTool.active) {
            this.setTool("select");
        } else if (this.selectedObjects.length) {
            this.canvas.discardActiveObject();
            this.canvas.requestRenderAll();
        } else {
            this.cancel();
        }
    }

    //--------------------------------------------------------------------------
    // Leave
    //--------------------------------------------------------------------------

    cancel() {
        if (!this.changed) {
            this.props.close();
            return;
        }
        // The wording and the buttons of Odoo's own question when a form is left with changes.
        this.dialog.add(ConfirmationDialog, {
            title: _t("Discard the changes?"),
            body: _t("Your changes will be lost if you close the editor without saving."),
            confirmLabel: _t("Discard changes"),
            cancelLabel: _t("Stay here"),
            confirm: () => this.props.close(),
            cancel: () => {},
        });
    }

    /** @returns {string} the name that is offered: `name (edited)`, without the extension */
    get offeredName() {
        const { name } = this.props.file;
        const dot = name.lastIndexOf(".");
        const stem = dot > 0 ? name.slice(0, dot) : name;
        const mark = _t("(edited)");
        return stem.endsWith(mark) ? stem : `${stem} ${mark}`;
    }

    openSave() {
        if (this.state.saving || !this.state.ready) {
            return;
        }
        this.drawing.abort();
        if (this.cropTool.active) {
            this.applyCrop();
        }
        const size = { width: this.regionBox.width, height: this.regionBox.height };
        const maxScale = largestExportScale(size);
        if (!maxScale) {
            this.notification.add(_t("Your browser cannot make a file of this picture."), { type: "danger" });
            return;
        }
        const { mimetype } = this.props.file;
        this.dialog.add(SaveDialog, {
            name: this.offeredName,
            mimetype: FORMATS[mimetype] ? mimetype : DEFAULT_FORMAT,
            size,
            maxScale,
            canKeepState: this.stateJson().length <= STATE_MAX_SIZE,
            onSave: (options) => this.save(options),
        });
    }

    stateJson() {
        return JSON.stringify(
            buildState({
                picture: this.picture,
                canvas: this.canvas,
                filters: plain(this.state.filters),
                crop: this.crop,
            })
        );
    }

    async save({ mimetype, quality, scale, name, keepState }) {
        this.state.saving = true;
        this.exporting = true;
        try {
            this.canvas.discardActiveObject();
            const parts = { canvas: this.canvas, picture: this.picture, region: this.regionBox, scale };
            const blob =
                mimetype === "image/svg+xml"
                    ? await renderSvg(parts)
                    : await renderBlob({ ...parts, mimetype, quality });
            const extension = mimetype === "image/svg+xml" ? "svg" : FORMATS[mimetype].extension;
            const file = new File([blob], `${name}.${extension}`, { type: blob.type });
            const state = keepState ? this.stateJson() : null;
            const { folder_id } = this.props.file;
            const upload = await this.fileUpload.upload(UPLOAD_ROUTE, [file], {
                buildFormData: (formData) => {
                    formData.append("folder_id", folder_id);
                    if (state) {
                        formData.append("edit_state", state);
                        formData.append("edit_source_id", this.sourceFile.id);
                    }
                },
            });
            await this.waitForEnd(upload);
            if (upload.state !== "loaded") {
                return; // the service has told the user
            }
            this.onStored(JSON.parse(upload.xhr.responseText));
        } catch {
            this.notification.add(_t("The picture could not be stored."), { type: "danger" });
        } finally {
            this.exporting = false;
            this.state.saving = false;
            this.canvas.requestRenderAll();
        }
    }

    waitForEnd(upload) {
        const bus = this.fileUpload.bus;
        return new Promise((resolve) => {
            if (["loaded", "error"].includes(upload.state)) {
                resolve();
                return;
            }
            const onEnd = ({ detail }) => {
                if (detail.upload !== upload) {
                    return;
                }
                bus.removeEventListener("FILE_UPLOAD_LOADED", onEnd);
                bus.removeEventListener("FILE_UPLOAD_ERROR", onEnd);
                resolve();
            };
            bus.addEventListener("FILE_UPLOAD_LOADED", onEnd);
            bus.addEventListener("FILE_UPLOAD_ERROR", onEnd);
        });
    }

    onStored({ id, name }) {
        this.notification.add(_t("Stored as a new document: %(name)s", { name }), {
            type: "success",
            buttons: [
                {
                    name: _t("Open"),
                    primary: true,
                    onClick: () =>
                        this.action.doAction({
                            type: "ir.actions.act_window",
                            res_model: MODEL,
                            res_id: id,
                            views: [[false, "form"]],
                        }),
                },
            ],
        });
        // The list or the board of cards behind the editor shows the new document at once.
        if (["list", "kanban"].includes(this.action.currentController?.props?.type)) {
            this.action.doAction("soft_reload");
        }
        this.props.close();
    }
}

registry
    .category("lazy_components")
    .add("int_filemanager.DocumentImageEditor", DocumentImageEditor);
