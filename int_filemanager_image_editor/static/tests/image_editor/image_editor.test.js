import { beforeAll, describe, expect, test } from "@odoo/hoot";
import { loadBundle } from "@web/core/assets";

// The editor and Fabric are a bundle of their own, loaded at the first click on "Edit": the tests
// load it the same way and take the modules from the loader.
const BUNDLE = "int_filemanager_image_editor.assets_image_editor";
let load;

beforeAll(async () => {
    await loadBundle(BUNDLE);
    load = (name) => odoo.loader.modules.get(`@int_filemanager_image_editor/image_editor/${name}`);
});

const near = (a, b, epsilon = 1e-6) => Math.abs(a - b) < epsilon;

/** A canvas with a picture of 1000 x 600 as its background, as the editor sets it up. */
function setup(Picture) {
    const source = document.createElement("canvas");
    source.width = 1000;
    source.height = 600;
    const picture = new Picture(source, 500);
    picture.resetPlacement();
    const canvas = new window.fabric.Canvas(document.createElement("canvas"), {
        width: 800,
        height: 500,
        renderOnAddRemove: false,
    });
    canvas.backgroundImage = picture.image;
    return { picture, canvas };
}

describe("geometry", () => {
    test("a quarter turn takes the point to (height - y, x) and swaps the size", () => {
        const { turnPoint, turnSize } = load("geometry");
        expect(turnPoint({ x: 100, y: 40 }, { width: 1000, height: 600 })).toEqual({ x: 560, y: 100 });
        expect(turnSize({ width: 1000, height: 600 })).toEqual({ width: 600, height: 1000 });
    });

    test("four quarter turns bring a rectangle back", () => {
        const { turnRect, turnSize } = load("geometry");
        let size = { width: 1000, height: 600 };
        let rect = { left: 10, top: 20, width: 300, height: 100 };
        for (let turn = 0; turn < 4; turn++) {
            rect = turnRect(rect, size);
            size = turnSize(size);
        }
        expect(rect).toEqual({ left: 10, top: 20, width: 300, height: 100 });
    });

    test("the largest rectangle of a ratio fits and is centered", () => {
        const { ratioRect } = load("geometry");
        const rect = ratioRect({ width: 1000, height: 600 }, 1);
        expect(rect).toEqual({ left: 200, top: 0, width: 600, height: 600 });
    });

    test("a point that has no line near stays where it is", () => {
        const { nearest } = load("geometry");
        expect(nearest(50, [10, 20], 5)).toBe(null);
        expect(nearest(12, [10, 20], 5)).toBe(10);
    });
});

describe("history", () => {
    test("undo and redo walk the entries, a new entry cuts what could be redone", () => {
        const { History } = load("history");
        const history = new History(3);
        history.reset("a");
        history.push("b");
        history.push("c");
        expect(history.undo()).toBe("b");
        expect(history.canRedo).toBe(true);
        history.push("d");
        expect(history.canRedo).toBe(false);
        expect(history.push("d")).toBe(false);
    });

    test("only the newest entries are kept", () => {
        const { History } = load("history");
        const history = new History(2);
        history.reset("a");
        history.push("b");
        history.push("c");
        expect(history.entries).toEqual(["b", "c"]);
    });
});

describe("filters", () => {
    test("a value that is neutral again is dropped from the settings", () => {
        const { withSetting } = load("filters");
        let settings = withSetting({}, "brightness", 0.4);
        expect(settings).toEqual({ brightness: 0.4 });
        settings = withSetting(settings, "brightness", 0);
        expect(settings).toEqual({});
    });

    test("the settings make the Fabric filters in a fixed order", () => {
        const { buildFilters } = load("filters");
        const filters = buildFilters(window.fabric.filters, { sepia: true, brightness: 0.2, blendcolor: {} });
        expect(filters.map((filter) => filter.constructor.type)).toEqual(["Brightness", "Sepia", "BlendColor"]);
    });

    test("stored settings are cleaned: unknown keys go, values are held in range", () => {
        const { cleanSettings } = load("filters");
        const clean = cleanSettings({ brightness: 99, nothing: 1, sepia: "yes", grayscale: true });
        expect(clean).toEqual({ brightness: 1, grayscale: true });
    });
});

describe("snapping", () => {
    test("a mark snaps to the edge of another mark within the distance", () => {
        const { snapMove } = load("snapping");
        const { dx, guides } = snapMove(
            { left: 103, top: 500, width: 50, height: 50 },
            {
                others: [{ left: 100, top: 0, width: 80, height: 80 }],
                region: { left: 0, top: 0, width: 1000, height: 600 },
                distance: 5,
                grid: null,
                objects: true,
            }
        );
        expect(dx).toBe(-3);
        expect(guides[0]).toEqual({ x: 100 });
    });

    test("a mark snaps to the grid", () => {
        const { snapMove } = load("snapping");
        const { dx, dy } = snapMove(
            { left: 48, top: 103, width: 10, height: 10 },
            { others: [], region: { left: 0, top: 0, width: 1000, height: 600 }, distance: 5, grid: 50, objects: false }
        );
        expect([dx, dy]).toEqual([2, -3]);
    });
});

describe("the state of an edit", () => {
    test("a state of another picture or version is not read", () => {
        const { readState } = load("edit_state");
        const state = { version: 1, source: { width: 10, height: 10 }, base: { angle: 0, cx: 5, cy: 5 }, objects: [] };
        expect(readState(state, { width: 10, height: 10 })).not.toBe(null);
        expect(readState(state, { width: 11, height: 10 })).toBe(null);
        expect(readState({ ...state, version: 2 }, { width: 10, height: 10 })).toBe(null);
    });

    test("objects that the editor does not make, and pictures that point away, are dropped", () => {
        const { cleanObjects } = load("edit_state");
        const clean = cleanObjects([
            { type: "Bogus" },
            { type: "Image", src: "https://example.com/x.png" },
            { type: "Image", src: "data:image/png;base64,AAAA" },
            { type: "Rect", width: 5, height: 5, clipPath: { type: "Image", src: "https://example.com/y.png" } },
            { type: "Rect", width: 5, height: 5, fill: { type: "pattern", source: "https://example.com/p.png" } },
        ]);
        expect(clean.map((object) => object.type)).toEqual(["Image", "Rect", "Rect"]);
        expect("clipPath" in clean[1]).toBe(false);
        expect(clean[2].fill).toBe(null);
    });

    test("marks, filters and crop make a state that is read back as it was", async () => {
        const { Picture } = load("picture");
        const { buildState, readState, reviveObjects } = load("edit_state");
        const { createDraft, updateDraft, DEFAULT_STYLE } = load("marks");
        const { picture, canvas } = setup(Picture);
        const rect = createDraft("rect", { x: 100, y: 100 }, DEFAULT_STYLE, 1);
        updateDraft("rect", rect, { x: 100, y: 100 }, { x: 300, y: 220 }, false);
        canvas.add(rect);
        const state = buildState({ picture, canvas, filters: { sepia: true }, crop: { left: 1, top: 2, width: 300, height: 200 } });
        const read = readState(JSON.parse(JSON.stringify(state)), picture.size);
        expect(read.filters).toEqual({ sepia: true });
        expect(read.crop.width).toBe(300);
        const [revived] = await reviveObjects(read.objects);
        expect(revived.type).toBe("rect");
        expect(near(revived.width, 200, 0.5)).toBe(true);
    });
});

describe("pictures that are put on the picture", () => {
    test("a drawing loses what reaches out of it before it is read", () => {
        const { sanitizeSvg } = load("import_image");
        const text = sanitizeSvg(
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" onload="x()">' +
                '<script>x()</script><image xlink:href="https://example.com/x.png"/>' +
                '<image href="data:image/png;base64,AAAA"/><use xlink:href="#a"/>' +
                '<rect id="a" fill="url(https://example.com/g.svg#x)" stroke="url(#local)"/></svg>'
        );
        expect(text.includes("example.com")).toBe(false);
        expect(text.includes("<script")).toBe(false);
        expect(text.includes("onload")).toBe(false);
        expect(text.includes("data:image/png")).toBe(true);
        expect(text.includes("url(#local)")).toBe(true);
    });
});

describe("marks and the scene", () => {
    test("the style of a mark is read back as it was set", () => {
        const { createDraft, updateDraft, applyStyle, readStyle, DEFAULT_STYLE } = load("marks");
        const rect = createDraft("rect", { x: 0, y: 0 }, DEFAULT_STYLE, 1);
        updateDraft("rect", rect, { x: 0, y: 0 }, { x: 50, y: 50 }, false);
        const style = { ...DEFAULT_STYLE, stroke: "#00AA00", width: 10, dash: "dashed", radius: 8 };
        applyStyle(rect, { stroke: "#00AA00", width: 10, dash: "dashed", radius: 8 }, style, 1);
        const read = readStyle(rect, 1);
        expect([read.stroke, read.width, read.dash, read.radius]).toEqual(["#00AA00", 10, "dashed", 8]);
    });

    test("an arrow keeps its parts and takes a new colour as one mark", () => {
        const { createArrow, applyStyle, kindOf, DEFAULT_STYLE } = load("marks");
        const arrow = createArrow({ x: 0, y: 0 }, { x: 100, y: 0 }, DEFAULT_STYLE, 1);
        expect(kindOf(arrow)).toBe("arrow");
        applyStyle(arrow, { stroke: "#112233" }, { ...DEFAULT_STYLE, stroke: "#112233" }, 1);
        const [line, tip] = arrow.getObjects();
        expect([line.stroke, tip.fill]).toEqual(["#112233", "#112233"]);
    });

    test("four turns of the scene bring every mark and the picture back", () => {
        const { Picture } = load("picture");
        const { turnScene } = load("scene_ops");
        const { createDraft, updateDraft, DEFAULT_STYLE } = load("marks");
        const { picture, canvas } = setup(Picture);
        const rect = createDraft("rect", { x: 100, y: 100 }, DEFAULT_STYLE, 1);
        updateDraft("rect", rect, { x: 100, y: 100 }, { x: 300, y: 220 }, false);
        canvas.add(rect);
        const before = rect.getCenterPoint();
        turnScene(canvas, picture, null);
        expect(picture.sceneSize).toEqual({ width: 600, height: 1000 });
        for (let turn = 0; turn < 3; turn++) {
            turnScene(canvas, picture, null);
        }
        const after = rect.getCenterPoint();
        expect(near(after.x, before.x) && near(after.y, before.y)).toBe(true);
        expect(picture.sceneSize).toEqual({ width: 1000, height: 600 });
    });

    test("grouping and ungrouping put the marks back where they were", () => {
        const { Picture } = load("picture");
        const { group, ungroup, select } = load("arrange");
        const { createDraft, updateDraft, DEFAULT_STYLE } = load("marks");
        const { canvas } = setup(Picture);
        const first = createDraft("rect", { x: 200, y: 200 }, DEFAULT_STYLE, 1);
        updateDraft("rect", first, { x: 200, y: 200 }, { x: 400, y: 320 }, false);
        const second = createDraft("ellipse", { x: 600, y: 300 }, DEFAULT_STYLE, 1);
        updateDraft("ellipse", second, { x: 600, y: 300 }, { x: 700, y: 400 }, false);
        canvas.add(first, second);
        select(canvas, [first, second]);
        group(canvas);
        expect(canvas.getObjects().length).toBe(1);
        ungroup(canvas);
        canvas.discardActiveObject();
        expect(canvas.getObjects().length).toBe(2);
        expect(near(first.left, 200)).toBe(true);
    });
});

describe("texts", () => {
    test("the scale that a handle gave a text becomes its font size", () => {
        const { bakeTextScale } = load("marks");
        const text = new window.fabric.IText("Text", { left: 10, top: 10, fontSize: 40, scaleX: 2.5, scaleY: 2.5 });
        bakeTextScale(text);
        expect([text.fontSize, text.scaleX, text.scaleY]).toEqual([100, 1, 1]);
    });

    test("a text box grows in width by the same factor", () => {
        const { bakeTextScale } = load("marks");
        const box = new window.fabric.Textbox("Text", { left: 0, top: 0, fontSize: 40, width: 200, scaleX: 2, scaleY: 2 });
        bakeTextScale(box);
        expect([box.fontSize, box.width, box.scaleX]).toEqual([80, 400, 1]);
    });

    test("the handles that would stretch a text are hidden", () => {
        const { setTextHandles } = load("controls");
        const line = new window.fabric.IText("Text");
        const box = new window.fabric.Textbox("Text", { width: 100 });
        setTextHandles(line);
        setTextHandles(box);
        expect(["ml", "mr", "mt", "mb"].map((key) => line.isControlVisible(key))).toEqual([false, false, false, false]);
        expect(["ml", "mr", "mt", "mb"].map((key) => box.isControlVisible(key))).toEqual([true, true, false, false]);
    });

    test("the corner of a wide mark has a diagonal cursor", () => {
        const { cornerCursor } = load("controls");
        expect(cornerCursor({ x: -0.5, y: -0.5 }, 0)).toBe("nw-resize");
        expect(cornerCursor({ x: 0.5, y: -0.5 }, 90)).toBe("se-resize");
    });
});

describe("the picture", () => {
    test("a big picture is shown by a smaller copy and put back in full for the file", () => {
        const { Picture } = load("picture");
        const { picture } = setup(Picture);
        expect(picture.scale).toBe(0.5);
        expect(picture.shown.element).toBe(picture.work);
        picture.show(true);
        expect(picture.shown.element).toBe(picture.full);
        picture.show(false);
        expect(picture.image.scaleX).toBe(2);
    });

    test("the file has the size of the part and the scale, whatever the zoom of the screen is", async () => {
        const { Picture } = load("picture");
        const { renderBlob } = load("export");
        const { Viewport } = load("viewport");
        const { picture, canvas } = setup(Picture);
        const stage = document.createElement("div");
        Object.defineProperty(stage, "clientWidth", { value: 800 });
        Object.defineProperty(stage, "clientHeight", { value: 500 });
        const viewport = new Viewport(canvas, stage);
        viewport.setRegion({ left: 0, top: 0, width: 1000, height: 600 });
        viewport.zoomBy(2);
        const blob = await renderBlob({
            canvas,
            picture,
            region: { left: 100, top: 100, width: 400, height: 300 },
            scale: 0.5,
            mimetype: "image/png",
            quality: 1,
        });
        const url = URL.createObjectURL(blob);
        const image = new Image();
        await new Promise((resolve) => {
            image.onload = resolve;
            image.src = url;
        });
        expect([image.naturalWidth, image.naturalHeight]).toEqual([200, 150]);
        URL.revokeObjectURL(url);
    });
});
