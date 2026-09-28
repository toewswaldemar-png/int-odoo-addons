/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {humanFileSize} from "./size_field.js";

// The list of uploads at the bottom right: progress per file, and what can be done with
// each (pause, continue, retry, rename after a name conflict, cancel).
export class IntFilemanagerV2UploadPanel extends Component {
  static template = "int_filemanager.v2.UploadPanel";
  static props = {
    items: Array,
    unfinishedCount: Number,
    onPause: Function,
    onRetry: Function,
    onRename: Function,
    onCancel: Function,
    onClear: Function,
    onDiscard: Function,
  };

  setup() {
    this.ui = useState({collapsed: false});
  }

  get visibleItems() {
    return this.props.items.filter((item) => item.state !== "cancelled");
  }

  get activeCount() {
    return this.visibleItems.filter((item) =>
      ["queued", "running", "finishing"].includes(item.state)
    ).length;
  }

  get title() {
    const active = this.activeCount;
    return active
      ? `${active} / ${this.visibleItems.length}`
      : String(this.visibleItems.length);
  }

  get unfinishedMessage() {
    return _t(
      "%s earlier upload(s) were interrupted. Select the same file(s) again to continue where they stopped.",
      this.props.unfinishedCount
    );
  }

  percent(item) {
    if (!item.size) {
      return item.state === "done" ? 100 : 0;
    }
    return Math.min(100, Math.round((item.sent / item.size) * 100));
  }

  formatSize(value) {
    return humanFileSize(value) || "0 Bytes";
  }

  canPause(item) {
    return item.state === "running" && item.size > 0;
  }

  canRetry(item) {
    return ["paused", "interrupted", "failed"].includes(item.state);
  }

  canRename(item) {
    return item.state === "failed" && /exists/i.test(item.error || "");
  }

  canCancel(item) {
    return !["done", "cancelled"].includes(item.state);
  }

  get toggleLabel() {
    return this.ui.collapsed ? _t("Expand") : _t("Collapse");
  }

  toggle() {
    this.ui.collapsed = !this.ui.collapsed;
  }
}
