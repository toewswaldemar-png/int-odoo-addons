/** @odoo-module **/

import { Component } from "@odoo/owl";

// Popover-Inhalt fuer das Rechtsklick-Kontextmenue (filemanager_controller_mixin.js:
// onWindowContextMenu()) - bewusst KEIN echtes <Dropdown>/<DropdownItem> (die brauchen einen
// echten Dropdown-Vorfahren fuer ihren useDropdownCloser()-Kontext, den es hier nicht gibt, ein
// per usePopover() an einem freien Punkt geoeffnetes Popover ist keiner), sondern dieselben
// CSS-Klassen, die Odoos eigene DropdownItem-Komponente selbst rendert (dropdown_item.xml:
// "o-dropdown-item dropdown-item o-navigable" auf dem Item, "o-dropdown--menu dropdown-menu
// show" fuer den Menue-Container, siehe dropdown.js) - optisch 1:1 identisch, ohne die
// Komponenten/Hooks selbst zu benoetigen.
export class IntFilemanagerContextMenu extends Component {
    static template = "int_filemanager.ContextMenu";
    static props = {
        items: Array,
        close: Function,
    };

    onItemClick(item) {
        this.props.close();
        item.callback();
    }
}
