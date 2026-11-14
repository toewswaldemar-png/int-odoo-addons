import { onMounted, onWillDestroy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";

/**
 * The form of a request to a controller (what the console opens): the answer of the controller comes some seconds after the request,
 * when the service has carried it out. The bus tells the user who asked that the request ended ({id, state}, the message
 * "int_workbench/request" goes to the user, so it comes wherever he is); if it is the request on the screen, the form loads it again and
 * shows the answer.
 */
export class CommandFormController extends FormController {
    setup() {
        super.setup(...arguments);
        this.bus = useService("bus_service");
        this.onRequest = ({ id } = {}) => {
            const root = this.model.root;
            if (id && root.resId === id && !root.dirty) {
                root.load();
            }
        };
        onMounted(() => this.bus.subscribe("int_workbench/request", this.onRequest));
        onWillDestroy(() => this.bus.unsubscribe("int_workbench/request", this.onRequest));
    }
}

export const commandFormView = { ...formView, Controller: CommandFormController };

registry.category("views").add("int_workbench.command_form", commandFormView);
