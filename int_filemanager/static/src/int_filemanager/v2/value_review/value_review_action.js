/** @odoo-module **/

// The value review: one file at a time, its document on the left (Odoo's pdf.js viewer)
// and the values found in it on the right, in the header the pager of the chosen files.
// A client action, not a dialog: the document needs the room.
import {Component, onWillUnmount, useEffect, useRef, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {ResizablePanel} from "@web/core/resizable_panel/resizable_panel";
import {useService} from "@web/core/utils/hooks";
import {Layout} from "@web/search/layout";
import {usePager} from "@web/search/pager_hook";
import {downloadUrl, errorMessage} from "../utils.js";
import {ViewerOverlay} from "./viewer_overlay.js";
import {markers, shownFields, wrapIndex} from "./value_review_geometry.js";

const NODE_MODEL = "int_filemanager.node";
const VIEWER_URL = "/web/static/lib/pdfjs/web/viewer.html";
const POLL_PENDING_MS = 3000;
const MAX_POLLS = 40;
const DOCUMENT_WIDTH = 640;

function isPdf(name) {
  return /\.pdf$/i.test(name || "");
}

export class IntFilemanagerV2ValueReview extends Component {
  static template = "int_filemanager.v2.ValueReview";
  static components = {Layout, ResizablePanel};
  static props = ["*"];

  setup() {
    this.orm = useService("orm");
    this.notification = useService("notification");
    const params = (this.props.action && this.props.action.params) || {};
    this.nodeIds = params.node_ids || [];
    this.display = {controlPanel: {}};
    this.viewerRef = useRef("viewer");
    this.state = useState({
      index: wrapIndex(params.index || 0, this.nodeIds.length),
      status: "loading", // Loading | ready | pending | none | error
      name: "",
      message: "",
      data: null,
      activeFieldId: null,
      tab: "document",
    });
    this.overlay = null;
    this.loadToken = 0;
    this.pollTimer = null;

    usePager(() => ({
      offset: this.state.index,
      limit: 1,
      total: this.nodeIds.length,
      onUpdate: ({offset}) => {
        this.state.index = wrapIndex(offset, this.nodeIds.length);
      },
    }));
    useEffect(
      () => {
        this.load();
      },
      () => [this.state.index]
    );
    useEffect(
      () => {
        this.mountViewer();
      },
      () => [this.viewerSrc]
    );
    useEffect(
      () => {
        if (this.overlay) {
          this.overlay.setMarkers(this.markers);
        }
      },
      () => [this.state.data]
    );
    useEffect(
      () => {
        if (this.overlay) {
          this.overlay.setActive(this.state.activeFieldId);
        }
      },
      () => [this.state.activeFieldId]
    );
    onWillUnmount(() => {
      this.loadToken++;
      clearTimeout(this.pollTimer);
      this.destroyOverlay();
    });
  }

  // ---------------------------------------------------------------- state

  get nodeId() {
    return this.nodeIds[this.state.index];
  }

  get isEmpty() {
    return !this.nodeIds.length;
  }

  get hasViewer() {
    return isPdf(this.state.name) && this.state.status !== "error";
  }

  get viewerSrc() {
    if (!this.hasViewer || !this.nodeId) {
      return "";
    }
    const file = encodeURIComponent(downloadUrl(this.nodeId, {inline: true}));
    return `${VIEWER_URL}?file=${file}#pagemode=none`;
  }

  get fields() {
    return this.state.data ? shownFields(this.state.data.fields) : [];
  }

  get markers() {
    const data = this.state.data;
    return data ? markers(data.fields, data.page_sizes) : [];
  }

  get panelWidth() {
    return DOCUMENT_WIDTH;
  }

  get documentClass() {
    const hidden = this.env.isSmall && this.state.tab !== "document";
    return `o_int_filemanager_review_document${hidden ? " d-none" : ""}`;
  }

  valueText(field) {
    if (field.confirmed) {
      return field.confirmed;
    }
    const best = field.suggestions[0];
    return best ? best.value.value_text : "";
  }

  originText(field) {
    if (field.confirmed) {
      return _t("Confirmed value");
    }
    const best = field.suggestions[0];
    if (!best) {
      return "";
    }
    const how = {
      hint: _t("learned for this sender"),
      regex: _t("rule"),
      before: _t("label before"),
      left: _t("label to the left"),
      above: _t("label above"),
      below: _t("label below"),
      unlabelled: _t("no label"),
    }[best.direction];
    return best.label ? `${best.label} (${how})` : how || "";
  }

  otherCount(field) {
    return Math.max(field.suggestions.length - 1, 0);
  }

  // ---------------------------------------------------------------- loading

  async load(polls = 0) {
    const token = ++this.loadToken;
    clearTimeout(this.pollTimer);
    if (!this.nodeId) {
      return;
    }
    if (polls === 0) {
      Object.assign(this.state, {
        status: "loading",
        data: null,
        activeFieldId: null,
        message: "",
      });
    }
    try {
      const [record] = await this.orm.read(NODE_MODEL, [this.nodeId], ["name"]);
      const data = await this.orm.call(NODE_MODEL, "suggest_field_values", [
        this.nodeId,
      ]);
      if (token !== this.loadToken) {
        return;
      }
      this.state.name = record ? record.name : "";
      this.env.config.setDisplayName?.(this.state.name);
      this.state.status = data.state;
      this.state.data = data.state === "ready" ? data : null;
      if (data.state === "pending" && polls < MAX_POLLS) {
        this.pollTimer = setTimeout(() => this.load(polls + 1), POLL_PENDING_MS);
      }
    } catch (error) {
      if (token === this.loadToken) {
        this.state.status = "error";
        this.state.message = errorMessage(error);
      }
    }
  }

  // ---------------------------------------------------------------- viewer

  destroyOverlay() {
    if (this.overlay) {
      this.overlay.destroy();
      this.overlay = null;
    }
  }

  async mountViewer() {
    this.destroyOverlay();
    const iframe = this.viewerRef.el;
    if (!iframe || !this.viewerSrc) {
      return;
    }
    const overlay = new ViewerOverlay(iframe, {
      onSelect: (fieldId) => this.onSelectField(fieldId, {scroll: false}),
    });
    this.overlay = overlay;
    // The frame loads the new file after the src changed; attach() waits for its pages.
    if (await overlay.attach()) {
      overlay.setMarkers(this.markers);
      overlay.setActive(this.state.activeFieldId);
    }
  }

  // ---------------------------------------------------------------- events

  onSelectField(fieldId, {scroll = true} = {}) {
    this.state.activeFieldId = fieldId;
    if (scroll && this.overlay) {
      this.state.tab = "document";
      this.overlay.scrollTo(fieldId);
    }
  }

  onSelectTab(tab) {
    this.state.tab = tab;
  }
}

registry
  .category("actions")
  .add("int_filemanager.value_review", IntFilemanagerV2ValueReview);
