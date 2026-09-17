/** @odoo-module **/

import { Component, onMounted } from "@odoo/owl";
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
//
// navigator.update() im eigenen onMounted() (Nutzerreport 2026-09-17 "kein Hover-Hintergrund",
// Root-Cause statt Symptom behoben): useNavigation() sitzt im Controller-Setup, dessen
// useEffect(() => {...}, () => [containerRef.el]) laeuft aber nur bei einem Re-Render DES
// CONTROLLERS erneut - der Controller re-rendert nicht automatisch, nur weil das Popover an
// anderer Stelle oeffnet (dessen isOpen ist dort keine vom Controller-Template gelesene
// Reactivity). Bei Odoos echtem <Dropdown> funktioniert genau das nur, weil Dropdown selbst bei
// jedem Oeffnen/Schliessen ueber sein eigenes state.isOpen neu rendert. Diese Komponente hier
// mountet dagegen bei JEDEM Oeffnen frisch (der Popover-Service erzeugt sie neu) - ihr eigenes
// onMounted() ist deshalb der zuverlaessige Zeitpunkt, um den durchgereichten Navigator explizit
// aufzufordern, seine Item-Liste neu einzulesen, statt auf eine Reactivity-Kette zu vertrauen,
// die hier strukturell nicht existiert.
export class IntFilemanagerContextMenu extends Component {
    static template = "int_filemanager.ContextMenu";
    static components = { DropdownItem };
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
