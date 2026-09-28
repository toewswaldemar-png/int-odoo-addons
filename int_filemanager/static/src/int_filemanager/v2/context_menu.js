/** @odoo-module **/

import {Component, onMounted} from "@odoo/owl";
import {DropdownItem} from "@web/core/dropdown/dropdown_item";

// Popover content of the right-click menu (controller_interaction.js). Built from real
// Odoo pieces (DropdownItem, the popover service, useNavigation) configured exactly like
// Odoo's own Dropdown; DropdownItem does not need a Dropdown ancestor, so close() is
// called explicitly here.
//
// navigator.update() on mount: useNavigation lives in the controller and only re-reads its
// items when the controller renders, which does not happen when a popover opens
// elsewhere. This component is created afresh on every open, so its own mount is the
// dependable moment to ask the navigator for a new item list (without it the hover
// highlight stays missing).
export class IntFilemanagerV2ContextMenu extends Component {
  static template = "int_filemanager.v2.ContextMenu";
  static components = {DropdownItem};
  static props = {
    items: Array,
    close: Function,
    navigator: Object,
  };

  setup() {
    onMounted(() => this.props.navigator.update());
  }

  onItemSelected(item) {
    this.props.close();
    item.callback();
  }
}
