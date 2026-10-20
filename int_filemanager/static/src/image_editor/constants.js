// The version of the state that is stored with a picture (see `edit_state.js`).
export const STATE_VERSION = 1;
// The longest side of the picture the editor works on. A bigger picture is drawn smaller on the
// screen (the filters and the redaction run on that copy) and in full only when it is stored.
export const WORK_EDGE = 2048;
// Pictures that are put into the editor (stamps, marks) are made this small first, so that the
// state that is stored with the picture stays small.
export const EMBED_EDGE = 1024;
// The state is refused by the server above this (see `EDIT_STATE_MAX_SIZE` in the model).
export const STATE_MAX_SIZE = 8 * 1024 ** 2;
export const HISTORY_LIMIT = 50;
// The marks are sized against the picture, so that they look alike on a photo and on an icon.
export const UNIT_PER_PIXEL = 1 / 1000;
// Smaller than this (in units of the picture) a drag does not make a mark.
export const MIN_MARK = 2;
export const HIGHLIGHT_ALPHA = 0.4;
export const ARROW_HEAD_FACTOR = 4;
// The zoom of the view: the limits in screen pixels per picture pixel, and the step of a button.
export const ZOOM_MIN = 0.02;
export const ZOOM_MAX = 32;
export const ZOOM_STEP = 1.25;
// The space around the picture when it is fitted to the stage, in screen pixels.
export const STAGE_MARGIN = 16;
// The grid and the snapping, in units of the picture.
export const GRID_STEPS = [10, 25, 50, 100];
export const SNAP_DISTANCE = 8;
// The saved formats: the browser's names, the extension, the quality that is offered.
export const FORMATS = {
    "image/png": { format: "png", extension: "png", lossy: false },
    "image/jpeg": { format: "jpeg", extension: "jpg", lossy: true },
    "image/webp": { format: "webp", extension: "webp", lossy: true },
};
export const DEFAULT_QUALITY = 0.92;
// What a picture of each type is stored as by default (a lossless one stays lossless).
export const DEFAULT_FORMAT = "image/png";
// The scales the editor tries when the browser cannot make a canvas as large as the picture.
export const EXPORT_SCALES = [1, 0.75, 0.5, 0.35, 0.25, 0.15, 0.1];
export const FONTS = [
    "sans-serif",
    "serif",
    "monospace",
    "Arial",
    "Georgia",
    "Times New Roman",
    "Courier New",
    "Verdana",
    "Trebuchet MS",
    "Impact",
    "Comic Sans MS",
];
// The properties of a mark that a stored state carries on top of Fabric's own (see `marks.js`).
export const MARK_PROPS = ["mark", "mode", "strength", "locked", "dashKind", "gradientKind"];
// How the handles and the frame of a mark look: Fabric's own light blue, a little darker where the
// picture is bright, with the squares filled so that they show on every picture.
export const CONTROL_LOOK = {
    cornerColor: "rgb(178, 204, 255)",
    cornerStrokeColor: "rgb(107, 143, 214)",
    borderColor: "rgb(107, 143, 214)",
    cornerStyle: "rect",
    transparentCorners: false,
};
