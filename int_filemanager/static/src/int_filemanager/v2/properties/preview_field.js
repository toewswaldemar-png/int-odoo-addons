/** @odoo-module **/

// The document of a file, next to the values in the properties form: Odoo's pdf.js viewer for
// a PDF, the picture for an image. The button at its corner opens Odoo's viewer window.
//
// On a PDF the viewer gets the outlines of the values read from it, and the words of its
// pages when a field asks for a value from the document: the words react to the mouse, a
// click or a drag over several of them is read by the server as the value of that field.
// A picture whose text was read gets the same in a layer of its own (ImageWords).
import {Component, markRaw, useEffect, useRef, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {useFileViewer} from "@web/core/file_viewer/file_viewer_hook";
import {useHotkey} from "@web/core/hotkeys/hotkey_hook";
import {registry} from "@web/core/registry";
import {useBus, useService} from "@web/core/utils/hooks";
import {hidePDFJSButtons} from "@web/core/utils/pdfjs";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {canPreview, viewerFileOf} from "../controller_mutations.js";
import {errorMessage} from "../utils.js";
import {IntFilemanagerV2ImageWords} from "./image_words.js";
import {ViewerOverlay} from "./viewer_overlay.js";
import {pageSize} from "./value_geometry.js";
import {EVENTS} from "./events.js";

const NODE_MODEL = "int_filemanager.node";

export class IntFilemanagerV2PreviewField extends Component {
    static template = "int_filemanager.v2.PreviewField";
    static components = {IntFilemanagerV2ImageWords};
    static props = {...standardFieldProps};

    setup() {
        this.fileViewer = useFileViewer();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.iframeRef = useRef("iframe");
        this.state = useState({
            picking: null,
            markers: [],
            activeFieldId: null,
            // The sizes of the pages as the values last saw them; the form's own answer may be
            // older (the text was still being read when it opened).
            sizes: null,
            // Picture: width over height once it is loaded, and the words of it while choosing
            ratio: 0,
            words: null,
        });
        this.overlay = null;
        // The viewer shows its editing buttons, "open file" and the bookmark link otherwise;
        // Odoo's own previews hide them the same way.
        useEffect(
            (iframe) => {
                if (iframe) {
                    hidePDFJSButtons(iframe);
                }
            },
            () => [this.iframeRef.el]
        );
        useEffect(
            (iframe) => {
                if (!iframe) {
                    return;
                }
                const overlay = new ViewerOverlay(iframe, {
                    loadWords: (page) => this.loadWords(page),
                    pageSize: (page) => pageSize(this.pageSizes, page),
                    onPick: (range) => this.onPickWords(range),
                    onCancel: () => this.onCancelPick(),
                });
                this.overlay = overlay;
                overlay.attach().then((attached) => {
                    if (attached && this.overlay === overlay) {
                        overlay.setMarkers(this.state.markers);
                        overlay.setActive(this.state.activeFieldId);
                        overlay.setWordMode(Boolean(this.state.picking));
                        this.bus.trigger(EVENTS.PREVIEW_READY);
                    }
                });
                return () => {
                    overlay.destroy();
                    if (this.overlay === overlay) {
                        this.overlay = null;
                    }
                };
            },
            () => [this.iframeRef.el]
        );
        useBus(this.bus, EVENTS.PICK, (ev) => this.onStartPick(ev.detail));
        useBus(this.bus, EVENTS.PICK_CANCEL, () => this.endPick());
        useBus(this.bus, EVENTS.MARKERS, (ev) => {
            this.state.markers = markRaw(ev.detail.markers);
            this.state.sizes = markRaw(ev.detail.sizes || null);
            this.overlay?.setMarkers(this.state.markers);
        });
        useBus(this.bus, EVENTS.ACTIVE, (ev) => {
            this.state.activeFieldId = ev.detail.fieldId;
            this.overlay?.setActive(this.state.activeFieldId);
            this.overlay?.scrollTo(this.state.activeFieldId);
        });
        // Later registrations come first, so Esc ends the choosing before it closes the dialog.
        useHotkey("escape", () => this.onCancelPick(), {
            isAvailable: () => Boolean(this.state.picking),
            bypassEditableProtection: true,
        });
    }

    get bus() {
        return this.props.record.model.bus;
    }

    /** What the server answered about the values; its revision and page sizes. */
    get values() {
        return this.props.record.data.values_json || {};
    }

    get pageSizes() {
        return this.state.sizes || this.values.page_sizes || {};
    }

    get file() {
        return canPreview(this.props.record) ? viewerFileOf(this.props.record) : false;
    }

    onOpenWindow() {
        const file = this.file;
        this.fileViewer.open(file, [file]);
    }

    /** The answer of the server about the words of a page to click on. */
    fetchWords(page) {
        return this.orm.call(NODE_MODEL, "page_words", [
            this.props.record.resId,
            this.values.revision_id,
            page,
        ]);
    }

    /** The words of a page of the PDF; none while the text is not read, so it is asked again. */
    async loadWords(page) {
        const result = await this.fetchWords(page);
        return result.state === "ready" ? result.words : null;
    }

    async onStartPick({fieldId, name}) {
        if (this.file && this.file.isImage) {
            await this.startPickOnPicture({fieldId, name});
            return;
        }
        if (!this.overlay) {
            this.notification.add(_t("The document is not ready yet."), {
                type: "warning",
            });
            return;
        }
        this.state.picking = {fieldId, name};
        this.overlay.setWordMode(true);
    }

    async startPickOnPicture(picking) {
        try {
            const result = await this.fetchWords(1);
            if (result.state !== "ready") {
                this.notification.add(_t("The text of the picture is not ready yet."), {
                    type: "warning",
                });
                return;
            }
            this.state.words = markRaw(result.words);
            this.state.picking = picking;
        } catch (error) {
            this.notification.add(errorMessage(error), {type: "danger"});
        }
    }

    /** The picture is shown: its shape sizes the frame, and the values can draw their outlines. */
    onPictureLoad(event) {
        const {naturalWidth, naturalHeight} = event.target;
        this.state.ratio = naturalHeight ? naturalWidth / naturalHeight : 0;
        this.bus.trigger(EVENTS.PREVIEW_READY);
    }

    get isPicking() {
        return Boolean(this.state.picking);
    }

    get pictureSize() {
        return pageSize(this.pageSizes, 1);
    }

    get pictureMarkers() {
        return this.state.markers.filter((marker) => marker.box.page === 1);
    }

    onCancelPick() {
        this.bus.trigger(EVENTS.PICK_CANCEL);
    }

    endPick() {
        this.state.picking = null;
        this.state.words = null;
        this.overlay?.setWordMode(false);
    }

    /** Words were chosen: the server reads the text as the value of the field. */
    async onPickWords({start, end}) {
        const picking = this.state.picking;
        if (!picking) {
            return;
        }
        try {
            const result = await this.orm.call(NODE_MODEL, "read_selection", [
                this.props.record.resId,
                this.values.revision_id,
                picking.fieldId,
                start,
                end,
            ]);
            if (result.suggestion) {
                this.endPick();
                this.bus.trigger(EVENTS.PICKED, {
                    fieldId: picking.fieldId,
                    suggestion: result.suggestion,
                });
            } else {
                this.notification.add(
                    result.message ||
                        _t("This file changed. Open the properties again."),
                    {type: "warning"}
                );
            }
        } catch (error) {
            this.notification.add(errorMessage(error), {type: "danger"});
        }
    }
}

export const intFilemanagerV2PreviewField = {
    component: IntFilemanagerV2PreviewField,
    supportedTypes: ["many2one"],
    additionalClasses: ["w-100"],
};

registry
    .category("fields")
    .add("int_filemanager_v2_preview", intFilemanagerV2PreviewField);
