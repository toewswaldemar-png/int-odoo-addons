import { Component } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { MultiRecordViewButton } from "@web/views/view_button/multi_record_view_button";

/**
 * The menu of a right click on a row: the buttons of the head of the list, as the core's list
 * shows them in the dropdown of the small screen (`list_controller.xml`), and "View" for the
 * viewer, which is no button of the list. A button acts on the ticked rows, the row of the
 * click is one of them (see `DocumentListContextMenuRenderer`).
 */
export class DocumentListContextMenu extends Component {
    static template = "int_filemanager.DocumentListContextMenu";
    static components = { DropdownItem, MultiRecordViewButton };
    static props = {
        // From the popover.
        close: Function,
        list: Object,
        // The buttons of the head of the list that are visible.
        buttons: Array,
        domain: Array,
        // Shows the file in the viewer; missing for more than one row or a file that cannot be shown.
        onView: { type: Function, optional: true },
    };

    /**
     * The buttons and the item stop the click (`ViewButton`, `DropdownItem`): it does not reach
     * the menu in the bubbling phase. The menu closes when the action has been started, not
     * before (the action of a button is a call to the server, the page does not change).
     */
    onClickCapture() {
        browser.setTimeout(() => this.props.close());
    }
}
