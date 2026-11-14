import { Component, useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { STATE_COLORS, stateLabels, worstState } from "./connection_service";

/**
 * The item of the systray: a coloured dot for the line to the controllers (the worst state of all of them), on every page of Odoo; a
 * click lists the controllers with their state. The way the attendance of HR does it: a dot in the navbar and a dropdown.
 */
export class ConnectionMenu extends Component {
    static template = "int_workbench.ConnectionMenu";
    static components = { Dropdown, DropdownItem };
    static props = [];

    setup() {
        // useState: the component is drawn again when the service reads a new state
        this.connections = useState(useService("int_workbench_connection").state);
        this.action = useService("action");
        this.labels = stateLabels();
    }

    get devices() {
        return this.connections.devices;
    }

    get worst() {
        return worstState(this.devices);
    }

    color(state) {
        return STATE_COLORS[state];
    }

    openControllers() {
        this.action.doAction("int_workbench.int_workbench_device_action");
    }
}

registry.category("systray").add("int_workbench.connection_menu", { Component: ConnectionMenu }, { sequence: 99 });
