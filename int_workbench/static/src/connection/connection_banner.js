import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

/**
 * The strip above a list of controller data when the line to one of its controllers is not good: the values on the screen may be old.
 * Nothing is shown while all is well. (Like the dashboards that Odoo puts above its lists, a component before the renderer.)
 */
export class ConnectionBanner extends Component {
    static template = "int_workbench.ConnectionBanner";
    static props = { list: Object };

    setup() {
        this.connections = useState(useService("int_workbench_connection").state);
    }

    /** The ids of the controllers whose rows the list shows. */
    get deviceIds() {
        return new Set(this.props.list.records.map((record) => record.data.device_id?.id).filter(Boolean));
    }

    /** The messages, one for each controller of the list whose line is not good. */
    get messages() {
        const messages = [];
        const shown = this.deviceIds;
        for (const device of this.connections.devices) {
            if (!shown.has(device.id)) {
                continue;
            }
            if (device.connection_state === "disconnected") {
                messages.push(_t("%s: the service has no line to the controller. The values shown may be old.", device.name));
            } else if (device.connection_state === "silent") {
                messages.push(_t("%s: the service has not reported for a while. The values shown may be old.", device.name));
            }
        }
        return messages;
    }
}
