/** @odoo-module **/

import {Component, useEffect, useRef, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {extOf} from "./utils.js";

// Odoo's own mimetype icon set (web/static/img/mimetypes) is selected purely by CSS
// attribute selectors on data-mimetype ("&[data-mimetype*='spreadsheet']"), a substring
// is enough. The real mime type of a node is used when it is known; otherwise a rough
// stand-in is derived from the extension.
const EXT_TO_PSEUDO_MIMETYPE = {
  pdf: "application/pdf",
  doc: "application/msword",
  docx: "application/msword",
  odt: "application/msword",
  rtf: "application/msword",
  xls: "application/vnd.ms-excel",
  xlsx: "application/vnd.ms-excel",
  ods: "application/vnd.ms-excel",
  csv: "text/csv",
  ppt: "application/vnd.ms-powerpoint",
  pptx: "application/vnd.ms-powerpoint",
  odp: "application/vnd.ms-powerpoint",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  gif: "image/gif",
  webp: "image/webp",
  bmp: "image/bmp",
  svg: "image/svg+xml",
  mp4: "video/mp4",
  webm: "video/webm",
  avi: "video/avi",
  mov: "video/quicktime",
  mp3: "audio/mpeg",
  wav: "audio/wav",
  flac: "audio/flac",
  ogg: "audio/ogg",
  zip: "application/zip",
  rar: "application/x-rar",
  "7z": "application/x-7z-compressed",
  tar: "application/x-tar",
  gz: "application/gzip",
  txt: "text/plain",
  md: "text/plain",
  log: "text/plain",
  json: "text/plain",
  html: "text/html",
  htm: "text/html",
  css: "text/css",
};

// A folder icon is not part of that set (files only), so folders use the same fa-folder
// as the sidebar tree.
export class IntFilemanagerV2NameField extends Component {
  static template = "int_filemanager.v2.NameField";
  static props = {...standardFieldProps};

  setup() {
    // UseState() again on the already reactive rename state, not just reading it through
    // the env: owl binds change notifications to the callback the proxy was created with
    // (the controller's render), so without this the cell would never re-render.
    this.renameState = useState(this.env.filemanagerRename.state);
    this.renameInputRef = useRef("renameInput");
    // Which part of the name F2 selects: 0 = all, 1 = base name (on entry), 2 = extension.
    // Plain instance state: only the selection inside an open input depends on it.
    this.selectionMode = 1;
    useEffect(
      () => {
        if (this.isRenaming && this.renameInputRef.el) {
          this.selectionMode = 1;
          this.renameInputRef.el.focus();
          this._applySelection();
        }
      },
      () => [this.isRenaming]
    );
  }

  // By id, not by object: the cell's record is not necessarily the same object as the
  // controller's selection entry, although both mean the same row.
  get isRenaming() {
    return this.renameState.recordId === this.props.record.resId;
  }

  _applySelection() {
    const el = this.renameInputRef.el;
    const name = this.env.filemanagerRename.state.value;
    // Dot > 0: a leading dot (".gitignore") is no extension separator.
    const dot = name.lastIndexOf(".");
    const hasExt = !this.isDir && dot > 0;
    let start = 0;
    let end = name.length;
    let direction = "backward";
    if (hasExt && this.selectionMode === 1) {
      end = dot;
    } else if (hasExt && this.selectionMode === 2) {
      start = dot + 1;
      direction = "forward";
    }
    el.setSelectionRange(start, end, direction);
    el.scrollLeft = 0;
  }

  onRenameKeydown(ev) {
    // Keep the list's own keyboard navigation out of the input.
    ev.stopPropagation();
    if (ev.key === "Enter") {
      ev.preventDefault();
      this.renameInputRef.el.blur();
    } else if (ev.key === "Escape") {
      ev.preventDefault();
      this.env.filemanagerRename.cancel();
    } else if (ev.key === "F2") {
      // Another F2 does not leave the mode, it moves the selection on (Explorer
      // convention). preventDefault matters: the browser opens its own menu otherwise.
      ev.preventDefault();
      this.selectionMode = (this.selectionMode + 1) % 3;
      this._applySelection();
    }
  }

  // Blur commits (clicking away keeps the name, like the Explorer); Escape cancels first,
  // so the blur it causes finds nothing to commit.
  onRenameBlur() {
    this.env.filemanagerRename.commit(this.env.filemanagerRename.state.value);
  }

  get isDir() {
    return this.props.record.data.is_dir;
  }

  get value() {
    return this.props.record.data[this.props.name];
  }

  // The folder a hit lives in, shown under the name while a search is active: hits from
  // several folders need it. Plain folder navigation never touches searchModel.query.
  get showParent() {
    return Boolean(this.env.searchModel.query.length);
  }

  get parentName() {
    return this.props.record.data.parent_id?.display_name || "";
  }

  get pseudoMimetype() {
    return (
      this.props.record.data.mime ||
      EXT_TO_PSEUDO_MIMETYPE[extOf(this.value || "")] ||
      ""
    );
  }
}

export const intFilemanagerV2NameField = {
  component: IntFilemanagerV2NameField,
  supportedTypes: ["char"],
  // Odoo's column width hook shrinks columns to a hard minimum unless told otherwise.
  // A function so it follows the window: full width on a phone, at least 400px otherwise.
  listViewWidth: () => (window.innerWidth < 768 ? [window.innerWidth] : [400]),
};

registry.category("fields").add("int_filemanager_v2_name", intFilemanagerV2NameField);
