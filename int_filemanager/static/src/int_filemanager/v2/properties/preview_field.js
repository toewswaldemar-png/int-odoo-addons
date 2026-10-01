/** @odoo-module **/

// The document of a file, next to the values in the properties form: Odoo's pdf.js viewer for
// a PDF, the picture for an image. The button at its corner opens Odoo's viewer window.
//
// On a PDF the viewer gets the outlines of the values read from it, and the words of its
// pages when a field asks for a value from the document: the words react to the mouse, a
// click or a drag over several of them is read by the server as the value of that field.
import {Component, useEffect, useRef, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {useFileViewer} from "@web/core/file_viewer/file_viewer_hook";
import {useHotkey} from "@web/core/hotkeys/hotkey_hook";
import {registry} from "@web/core/registry";
import {useBus, useService} from "@web/core/utils/hooks";
import {hidePDFJSButtons} from "@web/core/utils/pdfjs";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {canPreview, viewerFileOf} from "../controller_mutations.js";
import {errorMessage} from "../utils.js";
import {ViewerOverlay} from "../value_review/viewer_overlay.js";
import {pageSize} from "../value_review/value_review_geometry.js";
import {EVENTS} from "./events.js";

const NODE_MODEL = "int_filemanager.node";

export class IntFilemanagerV2PreviewField extends Component {
  static template = "int_filemanager.v2.PreviewField";
  static props = {...standardFieldProps};

  setup() {
    this.fileViewer = useFileViewer();
    this.orm = useService("orm");
    this.notification = useService("notification");
    this.iframeRef = useRef("iframe");
    this.state = useState({picking: null});
    this.overlay = null;
    this.markers = [];
    this.activeFieldId = null;
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
            overlay.setMarkers(this.markers);
            overlay.setActive(this.activeFieldId);
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
      this.markers = ev.detail.markers;
      this.overlay?.setMarkers(this.markers);
    });
    useBus(this.bus, EVENTS.ACTIVE, (ev) => {
      this.activeFieldId = ev.detail.fieldId;
      this.overlay?.setActive(this.activeFieldId);
      this.overlay?.scrollTo(this.activeFieldId);
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
    return this.values.page_sizes || {};
  }

  get file() {
    return canPreview(this.props.record) ? viewerFileOf(this.props.record) : false;
  }

  onOpenWindow() {
    const file = this.file;
    this.fileViewer.open(file, [file]);
  }

  /** The words of a page to click on. */
  async loadWords(page) {
    const result = await this.orm.call(NODE_MODEL, "page_words", [
      this.props.record.resId,
      this.values.revision_id,
      page,
    ]);
    return result.words;
  }

  onStartPick({fieldId, name}) {
    if (!this.overlay) {
      this.notification.add(_t("The document is not ready yet."), {type: "warning"});
      return;
    }
    this.state.picking = {fieldId, name};
    this.overlay.setWordMode(true);
  }

  onCancelPick() {
    this.bus.trigger(EVENTS.PICK_CANCEL);
  }

  endPick() {
    this.state.picking = null;
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
          result.message || _t("This file changed. Open the properties again."),
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
