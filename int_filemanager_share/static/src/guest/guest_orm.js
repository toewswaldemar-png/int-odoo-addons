// The `orm` service of the guest page: the core's ORM over the gateway of the share instead of
// /web/dataset/call_kw. The gateway answers with a status, not JSON-RPC.
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
 * Replaces the core's `rpc`: the address `ORM.call` builds is dropped, the share gateway is
 * called with its `{model, method, args, kwargs}` and the key.
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
