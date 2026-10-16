// SPIKE (throw-away): the `orm` service of the guest page. Same class and methods as the core's,
// only the transport differs: the gateway of the module instead of /web/dataset/call_kw.
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { ORM, ormService } from "@web/core/orm_service";

export const GATEWAY_ROUTE = "/int_filemanager/spike/rpc";

/**
 * The core's `ORM.call` builds `/web/dataset/call_kw/<model>/<method>` and the parameters
 * `{model, method, args, kwargs}`; the url is dropped and the token of the link added.
 */
export function guestRpc(url, params, settings) {
    return rpc(GATEWAY_ROUTE, { token: odoo.int_filemanager_token, ...params }, settings);
}

export class GuestORM extends ORM {
    constructor() {
        super();
        this.rpc = guestRpc;
    }
}

registry.category("services").add(
    "orm",
    {
        ...ormService,
        start() {
            return new GuestORM();
        },
    },
    { force: true }
);
