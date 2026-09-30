/** @odoo-module **/

// The value review: one file at a time, its document on the left (Odoo's pdf.js viewer)
// and the values found in it on the right, in the header the pager of the chosen files.
// A client action, not a dialog: the document needs the room.
import {Component, onWillUnmount, useEffect, useRef, useState} from "@odoo/owl";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {Dropdown} from "@web/core/dropdown/dropdown";
import {DropdownItem} from "@web/core/dropdown/dropdown_item";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {ResizablePanel} from "@web/core/resizable_panel/resizable_panel";
import {useService} from "@web/core/utils/hooks";
import {useSetupAction} from "@web/search/action_hook";
import {Layout} from "@web/search/layout";
import {usePager} from "@web/search/pager_hook";
import {downloadUrl, errorMessage} from "../utils.js";
import {ViewerOverlay} from "./viewer_overlay.js";
import {
  chooseSuggestion,
  initialRows,
  isDirty,
  removeRow,
  rowMarkers,
  typeText,
  valuesToSave,
} from "./value_review_edits.js";
import {wrapIndex} from "./value_review_geometry.js";

const NODE_MODEL = "int_filemanager.node";
const VIEWER_URL = "/web/static/lib/pdfjs/web/viewer.html";
const POLL_PENDING_MS = 3000;
const MAX_POLLS = 40;
const DOCUMENT_WIDTH = 640;

function isPdf(name) {
  return /\.pdf$/i.test(name || "");
}

// The ids come as a list from the menu and as "3,4,5" from the address after a reload.
function parseIds(raw) {
  const list = Array.isArray(raw) ? raw : String(raw || "").split(",");
  return list.map(Number).filter((id) => id > 0);
}

export class IntFilemanagerV2ValueReview extends Component {
  static template = "int_filemanager.v2.ValueReview";
  static components = {Dropdown, DropdownItem, Layout, ResizablePanel};
  static props = ["*"];

  setup() {
    this.orm = useService("orm");
    this.notification = useService("notification");
    this.dialog = useService("dialog");
    const params = (this.props.action && this.props.action.params) || {};
    this.nodeIds = parseIds(params.node_ids);
    this.display = {controlPanel: {}};
    this.viewerRef = useRef("viewer");
    this.state = useState({
      index: wrapIndex(Number(params.index) || 0, this.nodeIds.length),
      status: "loading", // Loading | ready | pending | none | error
      name: "",
      message: "",
      data: null,
      rows: [],
      sender: null,
      changedSender: false,
      tags: [],
      changedTags: false,
      saving: false,
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
      // Going on saves what was changed first, like the form view of Odoo.
      onUpdate: async ({offset}) => {
        if (await this.saveIfChanged()) {
          this.state.index = wrapIndex(offset, this.nodeIds.length);
        }
      },
    }));
    useSetupAction({beforeLeave: (options) => this.confirmLeave(options)});
    useEffect(
      () => {
        this.load();
      },
      () => [this.state.index]
    );
    useEffect(
      () => {
        // A reload of the page comes back to the same files.
        this.props.updateActionState?.({
          node_ids: this.nodeIds.join(","),
          index: String(this.state.index),
        });
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
      () => [this.markerKey]
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

  get markers() {
    const data = this.state.data;
    return data ? rowMarkers(this.state.rows, data.page_sizes) : [];
  }

  // Changes when a box has to move, appear or go: what the overlay effect watches.
  get markerKey() {
    return this.markers.map((m) => `${m.fieldId}:${m.box.left}:${m.box.top}`).join("|");
  }

  get isChanged() {
    return isDirty(this.state.rows, {
      changedSender: this.state.changedSender,
      changedTags: this.state.changedTags,
    });
  }

  get visibleRows() {
    return this.state.rows.filter((row) => !row.removed);
  }

  get isReviewed() {
    return this.state.data && this.state.data.review_state !== "unreviewed";
  }

  get panelWidth() {
    return DOCUMENT_WIDTH;
  }

  get documentClass() {
    const hidden = this.env.isSmall && this.state.tab !== "document";
    return `o_int_filemanager_review_document${hidden ? " d-none" : ""}`;
  }

  originText(row) {
    if (row.touched && row.source === "manual") {
      return _t("typed");
    }
    if (row.confirmed && !row.touched) {
      return _t("Confirmed value");
    }
    const chosen = row.suggestions.find((s) => s.start === row.start);
    if (!chosen) {
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
    }[chosen.direction];
    return chosen.label ? `${chosen.label} (${how})` : how || "";
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
        rows: [],
        sender: null,
        changedSender: false,
        tags: [],
        changedTags: false,
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
      if (data.state === "ready") {
        this.state.rows = initialRows(data.fields);
        this.state.sender = data.partner || null;
        this.state.tags = data.tags || [];
      }
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

  onType(row, text) {
    typeText(row, text);
  }

  onChoose(row, suggestion) {
    chooseSuggestion(row, suggestion);
    this.onSelectField(row.fieldId);
  }

  onRemove(row) {
    removeRow(row);
  }

  onRemoveSender() {
    this.state.sender = null;
    this.state.changedSender = true;
  }

  onRemoveTag(tag) {
    this.state.tags = this.state.tags.filter((t) => t.id !== tag.id);
    this.state.changedTags = true;
  }

  onDiscard() {
    this.load();
  }

  async onSave() {
    if (await this.save()) {
      await this.load();
    }
  }

  // ---------------------------------------------------------------- saving

  /** Stores the rows; the server reads every text again with the type of its field. */
  async save() {
    const data = this.state.data;
    if (!data || this.state.saving) {
      return false;
    }
    this.state.saving = true;
    try {
      await this.orm.call(
        NODE_MODEL,
        "apply_field_values",
        [this.nodeId, data.revision_id, valuesToSave(this.state.rows)],
        {
          partner_id: this.state.sender ? this.state.sender.id : false,
          tag_ids: this.state.tags.map((tag) => tag.id),
        }
      );
    } catch (error) {
      this.notification.add(errorMessage(error), {type: "danger"});
      return false;
    } finally {
      this.state.saving = false;
    }
    this.notification.add(_t("Values saved."), {type: "success"});
    return true;
  }

  async saveIfChanged() {
    return this.isChanged ? this.save() : true;
  }

  /** Asks before leaving with changes that were not saved: "Stay here" or "Discard". */
  confirmLeave({forceLeave} = {}) {
    if (forceLeave || !this.isChanged) {
      return true;
    }
    return new Promise((resolve) => {
      let leave = false;
      this.dialog.add(
        ConfirmationDialog,
        {
          title: _t("Unsaved changes"),
          body: _t("The values you changed are not saved. Leave and discard them?"),
          confirmLabel: _t("Discard changes"),
          confirm: () => {
            leave = true;
          },
          cancelLabel: _t("Stay here"),
          cancel: () => {
            leave = false;
          },
        },
        {onClose: () => resolve(leave)}
      );
    });
  }
}

registry
  .category("actions")
  .add("int_filemanager.value_review", IntFilemanagerV2ValueReview);
