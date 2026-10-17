// The `orm` service of the page of the guests. The class and its methods are the core's; only
// the transport differs: the gateway of the share instead of /web/dataset/call_kw. The gateway
// answers with a status and a short text (not JSON-RPC), and that becomes an error here.
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { RPCError } from "@web/core/network/rpc";
import { ORM, ormService } from "@web/core/orm_service";
import { registry } from "@web/core/registry";
import { shareKey, shareUrl } from "./guest_share";

function messageOf(status) {
    switch (status) {
        case 403:
            return _t("This link does not allow that.");
        case 410:
            return _t("This link is not valid any more.");
        case 429:
            return _t("Too many requests. Try again in a minute.");
        default:
            return _t("Something went wrong. Try again.");
    }
}

/**
 * The core's `ORM.call` builds `/web/dataset/call_kw/<model>/<method>` and the parameters
 * `{model, method, args, kwargs}`; the address is dropped and the gateway of the share is called
 * with the parameters and the key.
 */
export function guestRpc(url, params) {
    const controller = new AbortController();
    const request = (async () => {
        const response = await browser.fetch(shareUrl("rpc"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ k: shareKey(), ...params }),
            signal: controller.signal,
        });
        if (!response.ok) {
            const error = new RPCError(messageOf(response.status));
            error.code = response.status;
            error.data = { message: error.message };
            throw error;
        }
        return response.json();
    })();
    request.abort = () => controller.abort();
    return request;
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
