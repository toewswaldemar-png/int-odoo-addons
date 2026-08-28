/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onWillUnmount } from "@odoo/owl";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

const BUS_CHANNEL = "int_repair_workshop";
const BUS_NOTIFICATION_TYPE = "int_repair_workshop.change";

export class RepairWorkshopListController extends ListController {
    setup() {
        super.setup();
        const busService = useService("bus_service");
        // Reload when anything changes repair.order server-side, whether from
        // this tab or another session (e.g. the shared workshop screen).
        // Debounced since a bulk change fires one notification per write.
        let reloadTimeout;
        const onChange = () => {
            clearTimeout(reloadTimeout);
            reloadTimeout = setTimeout(() => this.model.load(), 800);
        };
        busService.addChannel(BUS_CHANNEL);
        busService.subscribe(BUS_NOTIFICATION_TYPE, onChange);
        onWillUnmount(() => {
            clearTimeout(reloadTimeout);
            busService.unsubscribe(BUS_NOTIFICATION_TYPE, onChange);
        });
    }
}

registry.category("views").add("int_repair_workshop_list", {
    ...listView,
    Controller: RepairWorkshopListController,
});
