// The filters of the picture: what the user sets (`settings`, a plain object that is stored with
// the picture) and the Fabric filters that it makes. The labels are in the editor, not here.

const SHARPEN = [0, -1, 0, -1, 5, -1, 0, -1, 0];
const EMBOSS = [1, 1, 1, 1, 0.7, -1, -1, -1, -1];

/**
 * The adjustments with a slider. `build` makes the Fabric filter for a value that is not the
 * neutral one; the filters are applied in the order of this list.
 */
export const SLIDERS = [
    { id: "brightness", min: -1, max: 1, step: 0.01, neutral: 0, build: (f, v) => new f.Brightness({ brightness: v }) },
    { id: "contrast", min: -1, max: 1, step: 0.01, neutral: 0, build: (f, v) => new f.Contrast({ contrast: v }) },
    { id: "saturation", min: -1, max: 1, step: 0.01, neutral: 0, build: (f, v) => new f.Saturation({ saturation: v }) },
    { id: "vibrance", min: -1, max: 1, step: 0.01, neutral: 0, build: (f, v) => new f.Vibrance({ vibrance: v }) },
    { id: "gamma", min: 0.2, max: 2.2, step: 0.01, neutral: 1, build: (f, v) => new f.Gamma({ gamma: [v, v, v] }) },
    { id: "hue", min: -1, max: 1, step: 0.01, neutral: 0, build: (f, v) => new f.HueRotation({ rotation: v }) },
    { id: "blur", min: 0, max: 1, step: 0.01, neutral: 0, build: (f, v) => new f.Blur({ blur: v }) },
    { id: "noise", min: 0, max: 1000, step: 10, neutral: 0, build: (f, v) => new f.Noise({ noise: v }) },
    // The size of a block in pixels of the picture on the screen; one is no change.
    { id: "pixelate", min: 1, max: 48, step: 1, neutral: 1, build: (f, v) => new f.Pixelate({ blocksize: v }) },
];

/** The looks and the kernels: on or off. */
export const TOGGLES = [
    { id: "grayscale", build: (f) => new f.Grayscale() },
    { id: "blackwhite", build: (f) => new f.BlackWhite() },
    { id: "sepia", build: (f) => new f.Sepia() },
    { id: "invert", build: (f) => new f.Invert() },
    { id: "vintage", build: (f) => new f.Vintage() },
    { id: "polaroid", build: (f) => new f.Polaroid() },
    { id: "kodachrome", build: (f) => new f.Kodachrome() },
    { id: "technicolor", build: (f) => new f.Technicolor() },
    { id: "brownie", build: (f) => new f.Brownie() },
    { id: "sharpen", build: (f) => new f.Convolute({ matrix: SHARPEN }) },
    { id: "emboss", build: (f) => new f.Convolute({ matrix: EMBOSS }) },
];

/** The ways a colour is put over the picture (the names of Fabric's `BlendColor`). */
export const BLEND_MODES = ["multiply", "add", "difference", "screen", "subtract", "darken", "lighten", "overlay", "exclusion", "tint"];

export const REMOVE_COLOR_DEFAULT = { color: "#ffffff", distance: 0.2 };
export const BLEND_COLOR_DEFAULT = { color: "#ff0000", mode: "tint", alpha: 0.3 };

const BY_ID = new Map([...SLIDERS, ...TOGGLES].map((entry) => [entry.id, entry]));

/** @returns {Object} the settings of a picture with no filter at all */
export function noFilters() {
    return {};
}

/** @returns {number} the value of a slider in `settings`, the neutral one if it is not set */
export function sliderValue(settings, id) {
    const slider = BY_ID.get(id);
    return id in settings ? settings[id] : slider.neutral;
}

/**
 * Sets one entry; an entry that is back at its neutral value is dropped, so that two pictures
 * that look alike have equal settings.
 * @returns {Object} new settings
 */
export function withSetting(settings, id, value) {
    const next = { ...settings };
    const entry = BY_ID.get(id);
    const isNeutral = entry?.neutral !== undefined ? value === entry.neutral : value === false || value === null;
    if (isNeutral) {
        delete next[id];
    } else {
        next[id] = value;
    }
    return next;
}

/** @returns {boolean} whether any filter is on */
export function hasFilters(settings) {
    return Object.keys(settings).length > 0;
}

/**
 * The Fabric filters of the settings, in a fixed order (so that equal settings give the same
 * picture). Anything unknown in `settings` (a state of a later version) is left out.
 * @param {Object} fabricFilters `fabric.filters`
 * @param {Object} settings
 */
export function buildFilters(fabricFilters, settings) {
    const filters = [];
    for (const slider of SLIDERS) {
        if (slider.id in settings && settings[slider.id] !== slider.neutral) {
            filters.push(slider.build(fabricFilters, settings[slider.id]));
        }
    }
    for (const toggle of TOGGLES) {
        if (settings[toggle.id]) {
            filters.push(toggle.build(fabricFilters));
        }
    }
    if (settings.removecolor) {
        filters.push(new fabricFilters.RemoveColor({ ...REMOVE_COLOR_DEFAULT, ...settings.removecolor }));
    }
    if (settings.blendcolor) {
        filters.push(new fabricFilters.BlendColor({ ...BLEND_COLOR_DEFAULT, ...settings.blendcolor }));
    }
    return filters;
}

/**
 * Settings from a stored state, with only what this version knows and in the right type: a
 * state from outside is no more trusted than the form the user fills.
 */
export function cleanSettings(raw) {
    const clean = {};
    if (!raw || typeof raw !== "object") {
        return clean;
    }
    for (const slider of SLIDERS) {
        const value = raw[slider.id];
        if (typeof value === "number" && Number.isFinite(value) && value !== slider.neutral) {
            clean[slider.id] = Math.min(Math.max(value, slider.min), slider.max);
        }
    }
    for (const toggle of TOGGLES) {
        if (raw[toggle.id] === true) {
            clean[toggle.id] = true;
        }
    }
    if (raw.removecolor && typeof raw.removecolor === "object") {
        clean.removecolor = {
            color: colorOr(raw.removecolor.color, REMOVE_COLOR_DEFAULT.color),
            distance: numberIn(raw.removecolor.distance, 0, 1, REMOVE_COLOR_DEFAULT.distance),
        };
    }
    if (raw.blendcolor && typeof raw.blendcolor === "object") {
        clean.blendcolor = {
            color: colorOr(raw.blendcolor.color, BLEND_COLOR_DEFAULT.color),
            mode: BLEND_MODES.includes(raw.blendcolor.mode) ? raw.blendcolor.mode : BLEND_COLOR_DEFAULT.mode,
            alpha: numberIn(raw.blendcolor.alpha, 0, 1, BLEND_COLOR_DEFAULT.alpha),
        };
    }
    return clean;
}

function colorOr(value, fallback) {
    return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value) ? value : fallback;
}

function numberIn(value, low, high, fallback) {
    return typeof value === "number" && Number.isFinite(value) ? Math.min(Math.max(value, low), high) : fallback;
}
