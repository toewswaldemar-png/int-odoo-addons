import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { OdooClient } from "./regler_client";

const OPERATOR_GROUP = "int_regler.group_regler_operator";

/**
 * Clamps and releases rows for the list of process values. A clamp is a request (int.regler.command) that the controller service
 * carries out; how it ended is told by the bus of Odoo. The view that listens to the bus hands each message to `settle`, so that
 * this service starts nothing of its own (it does not open the bus for a user who never looks at a controller).
 */
export const reglerClampingService = {
    dependencies: ["orm"],

    start(env, { orm }) {
        const clients = new Map(); // id of a controller -> the client that makes its requests
        let operator = null;

        function client(deviceId) {
            if (!clients.has(deviceId)) {
                clients.set(deviceId, new OdooClient(orm, { id: deviceId }));
            }
            return clients.get(deviceId);
        }

        return {
            /** May the user clamp? The server decides in the end (a request of a user who may not is refused there). */
            canClamp() {
                operator ??= user.hasGroup(OPERATOR_GROUP);
                return operator;
            },

            /** How a request ended, from the bus: {id, state, message}. Only the requests that are waited for count. */
            settle(payload) {
                for (const one of clients.values()) {
                    one.settle(payload);
                }
            },

            /**
             * @param {number} deviceId the controller
             * @param {string} code the row
             * @param {"set"|"release"} action
             * @param {number} [value] for "set"
             * @returns {Promise<{confirmed: boolean, error: string}>}
             */
            clamp(deviceId, code, action, value = 0) {
                return client(deviceId).post(`/clamps/${encodeURIComponent(code)}`, { action, value });
            },
        };
    },
};

registry.category("services").add("int_regler_clamping", reglerClampingService);
