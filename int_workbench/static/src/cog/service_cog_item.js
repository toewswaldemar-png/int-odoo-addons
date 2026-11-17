import { Component } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";

/**
 * "Service" in the gear menu of a device: opens the settings of its service in a dialog, with an icon like the other entries.
 */
export class ServiceCogItem extends Component {
    static template = "int_workbench.ServiceCogItem";
    static components = { DropdownItem };
    static props = {};

    async openService() {
        // the click closes the menu and this component with it: the services of the environment go on, those of useService would not
        const { orm, action } = this.env.services;
        const dialog = await orm.call("int.workbench.device", "action_open_service", [[this.env.model.root.resId]]);
        await action.doAction(dialog);
    }
}

registry.category("cogMenu").add(
    "int-workbench-service",
    {
        Component: ServiceCogItem,
        groupNumber: ACTIONS_GROUP_NUMBER,
        isDisplayed: async (env) =>
            env.config.viewType === "form" && env.model.root?.resModel === "int.workbench.device" && Boolean(env.model.root.resId),
    },
    { sequence: 50 }
);
