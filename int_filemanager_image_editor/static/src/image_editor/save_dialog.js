import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { DEFAULT_QUALITY, EXPORT_SCALES, FORMATS } from "./constants";

/** What the user chooses before the picture is stored: the format, the size, the name. */
export class SaveDialog extends Component {
    static template = "int_filemanager_image_editor.ImageEditorSaveDialog";
    static components = { Dialog };
    static props = {
        // The name without the extension, and the type it starts with.
        name: String,
        mimetype: String,
        // The part that is stored, at the size of the picture; `maxScale` is the largest scale that
        // the browser can make a canvas for.
        size: Object,
        maxScale: Number,
        // Whether the state of the editor can be kept with the picture (it may be too large).
        canKeepState: Boolean,
        // `onSave({mimetype, quality, scale, name, keepState})`
        onSave: Function,
        close: Function,
    };

    setup() {
        this.formats = [
            { mimetype: "image/png", label: "PNG" },
            { mimetype: "image/jpeg", label: "JPEG" },
            { mimetype: "image/webp", label: "WebP" },
            { mimetype: "image/svg+xml", label: _t("SVG (marks as vectors, with the picture)") },
        ];
        this.scales = EXPORT_SCALES.filter((scale) => scale <= this.props.maxScale);
        this.state = useState({
            mimetype: this.props.mimetype,
            quality: DEFAULT_QUALITY,
            scale: this.scales[0] ?? 0,
            name: this.props.name,
            keepState: this.props.canKeepState,
        });
    }

    get title() {
        return _t("Save as new document");
    }

    get isLossy() {
        return Boolean(FORMATS[this.state.mimetype]?.lossy);
    }

    get extension() {
        return this.state.mimetype === "image/svg+xml" ? "svg" : FORMATS[this.state.mimetype].extension;
    }

    get outputSize() {
        const { width, height } = this.props.size;
        return {
            width: Math.max(1, Math.round(width * this.state.scale)),
            height: Math.max(1, Math.round(height * this.state.scale)),
        };
    }

    get isReduced() {
        return this.props.maxScale < 1;
    }

    scaleLabel(scale) {
        return `${Math.round(scale * 100)} %`;
    }

    get canSave() {
        return this.state.name.trim() !== "" && this.state.scale > 0;
    }

    onMimetype(ev) {
        this.state.mimetype = ev.target.value;
    }

    onQuality(ev) {
        this.state.quality = Number(ev.target.value);
    }

    onScale(ev) {
        this.state.scale = Number(ev.target.value);
    }

    onName(ev) {
        this.state.name = ev.target.value;
    }

    onKeepState(ev) {
        this.state.keepState = ev.target.checked;
    }

    save() {
        if (!this.canSave) {
            return;
        }
        const { mimetype, quality, scale, name, keepState } = this.state;
        this.props.close();
        this.props.onSave({ mimetype, quality, scale, name: name.trim(), keepState: keepState && this.props.canKeepState });
    }
}
