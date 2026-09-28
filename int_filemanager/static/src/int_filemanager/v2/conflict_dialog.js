/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {CONFLICT_ACTIONS} from "./upload_plan.js";

// One question for the whole drop: what to do with each file whose name is taken.
// "Replace" stores a new version of the existing file (the old one stays in its history);
// it does not exist for a name held by a folder.
export class IntFilemanagerV2ConflictDialog extends Component {
  static template = "int_filemanager.v2.ConflictDialog";
  static components = {Dialog};
  static props = {
    conflicts: Array, // [{name, isDir, file}]
    confirm: Function, // Called with Map(file -> action)
    cancel: Function,
    close: Function,
  };

  setup() {
    this.actions = CONFLICT_ACTIONS;
    this.state = useState({
      choices: this.props.conflicts.map(() => CONFLICT_ACTIONS.keepBoth),
    });
  }

  setChoice(index, action) {
    this.state.choices[index] = action;
  }

  setAll(action) {
    this.state.choices = this.props.conflicts.map((conflict) =>
      conflict.isDir && action === CONFLICT_ACTIONS.replace
        ? CONFLICT_ACTIONS.keepBoth
        : action
    );
  }

  onConfirm() {
    const decisions = new Map();
    this.props.conflicts.forEach((conflict, index) => {
      decisions.set(conflict.file, this.state.choices[index]);
    });
    this.props.confirm(decisions);
    this.props.close();
  }

  onCancel() {
    this.props.cancel();
    this.props.close();
  }
}
