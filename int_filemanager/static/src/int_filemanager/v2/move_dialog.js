/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {IntFilemanagerV2FolderTree} from "./folder_tree.js";

// Pick a destination folder for "Move to..." and "Copy to...": the sidebar tree in a
// dialog. "All folders" (the top) is not a destination.
export class IntFilemanagerV2MoveDialog extends Component {
  static template = "int_filemanager.v2.MoveDialog";
  static components = {Dialog, FolderTree: IntFilemanagerV2FolderTree};
  static props = {
    title: String,
    confirmLabel: String,
    startFolderId: {type: [Number, Boolean], optional: true},
    confirm: Function, // Called with the chosen folder id
    close: Function,
  };

  setup() {
    this.state = useState({target: this.props.startFolderId || false});
  }

  onSelectFolder(folderId) {
    this.state.target = folderId;
  }

  onConfirm() {
    if (!this.state.target) {
      return;
    }
    this.props.confirm(this.state.target);
    this.props.close();
  }
}
