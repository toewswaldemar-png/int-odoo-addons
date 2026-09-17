/** @odoo-module **/

import { Component } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

// Popover-Inhalt fuer das Rechtsklick-Kontextmenue (filemanager_controller_mixin.js:
// onWindowContextMenu()) - echte Odoo-Komponente statt eigener Nachbildung: DropdownItem selbst
// braucht keinen echten <Dropdown>-Vorfahren zwingend (dropdown_item.js: useDropdownCloser()
// liest env[DROPDOWN_NESTING] nur optional-chained, ohne Dropdown-Kontext bleibt es ein
// folgenloses No-op statt eines Fehlers) - close() wird hier stattdessen explizit selbst
// aufgerufen. Die Popover-Einrichtung selbst (useNavigation fuer Hover/Pfeiltasten,
// usePopover-Optionen: arrow:false, popoverClass "o-dropdown--menu dropdown-menu mx-0", role
// "menu") ist 1:1 aus Odoos eigenem Dropdown (dropdown.js) uebernommen, siehe
// filemanager_controller_mixin.js - keine eigens erfundene CSS/Verhalten-Nachbildung mehr.
export class IntFilemanagerContextMenu extends Component {
    static template = "int_filemanager.ContextMenu";
    static components = { DropdownItem };
    static props = {
        items: Array,
        close: Function,
    };

    onItemSelected(item) {
        this.props.close();
        item.callback();
    }
}
