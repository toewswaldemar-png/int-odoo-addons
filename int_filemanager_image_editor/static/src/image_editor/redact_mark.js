// A rectangle that hides what is under it: the picture as blocks (pixelated), blurred, or a
// black area. It is drawn from the picture of the canvas, not stored as pixels: the state keeps
// only the place, the mode and the strength, and the hidden part is made anew each time.
//
// The part is gone from the picture that is stored as a file, but not from the original: the
// editor keeps that as the source of the edit, as long as somebody may read it.

const { Rect, classRegistry, util } = window.fabric;

export const REDACT_MODES = ["pixelate", "blur", "black"];
export const REDACT_DEFAULT = { mode: "pixelate", strength: 12 };

export class RedactMark extends Rect {
    static type = "RedactMark";

    static ownDefaults = {
        mark: "redact",
        mode: REDACT_DEFAULT.mode,
        // Pixelate: the size of a block; blur: the reach of the blur; both in units of the scene.
        strength: REDACT_DEFAULT.strength,
        fill: "rgba(0,0,0,0)",
        strokeWidth: 0,
        lockRotation: true,
        objectCaching: false,
    };

    constructor(options) {
        // Fabric applies the defaults of the base classes only; ours go in as options.
        super({ ...RedactMark.ownDefaults, ...options });
    }

    /**
     * Draws what lies under the rectangle. `this.canvas` has the picture as its background; the
     * picture is read at the size it has now (small on the screen, full when it is stored).
     */
    _render(ctx) {
        const base = this.canvas?.backgroundImage;
        const width = this.width;
        const height = this.height;
        if (!base || !(width > 0 && height > 0)) {
            return;
        }
        if (this.mode === "black") {
            ctx.fillStyle = "#000";
            ctx.fillRect(-width / 2, -height / 2, width, height);
            return;
        }
        const element = base.getElement();
        const source = this.smallCopy(element, base);
        ctx.save();
        ctx.beginPath();
        ctx.rect(-width / 2, -height / 2, width, height);
        ctx.clip();
        // From the space of the mark back to the space of the picture, then into the picture.
        ctx.transform(...util.invertTransform(this.calcTransformMatrix()));
        ctx.transform(...base.calcTransformMatrix());
        ctx.imageSmoothingEnabled = this.mode === "blur";
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(source, -base.width / 2, -base.height / 2, base.width, base.height);
        ctx.restore();
    }

    /**
     * The picture, drawn at a small size and kept; drawn large again it gives blocks (no
     * smoothing) or a blur (smoothing). Made anew when the picture, the filters or the strength
     * change.
     */
    smallCopy(element, base) {
        // `strength` is in units of the scene (pixels of the full picture); the element of the
        // picture has `1 / scaleX` of its own pixels per unit while it is the small copy.
        const block = Math.max(this.strength / Math.abs(base.scaleX), 1);
        const key = `${block.toFixed(3)}|${base.width}|${base.height}|${this.mode}`;
        const cached = this._small;
        if (cached?.element === element && cached.key === key && cached.version === base.filterVersion) {
            return cached.canvas;
        }
        const factor = this.mode === "blur" ? block * 2 : block;
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.ceil(base.width / factor));
        canvas.height = Math.max(1, Math.ceil(base.height / factor));
        const small = canvas.getContext("2d");
        small.imageSmoothingEnabled = true;
        small.imageSmoothingQuality = "high";
        small.drawImage(element, 0, 0, canvas.width, canvas.height);
        this._small = { element, key, version: base.filterVersion, canvas };
        return canvas;
    }

    toObject(propertiesToInclude = []) {
        return super.toObject(["mark", "mode", "strength", ...propertiesToInclude]);
    }
}

classRegistry.setClass(RedactMark);
