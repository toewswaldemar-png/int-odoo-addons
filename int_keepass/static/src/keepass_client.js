import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { wrapRpc } from "./keepass_header";

export const UNLOCK_ACTION = "int_keepass.int_keepass_unlock_action";
export const ENTRY_ACTION = "int_keepass.int_keepass_entry_action";

// The master password lives here and nowhere else: in the memory of this page. A reload of the
// page forgets it (the unlock screen asks again); it is in no storage, no URL and no context.
export const keepass = { password: null, email: null, onLocked: null };

rpc._rpc = wrapRpc(rpc._rpc, keepass);

registry.category("services").add("int_keepass", {
    dependencies: ["action"],
    start(env, { action }) {
        let opening = false;
        keepass.onLocked = () => {
            // the list, the search panel and the form may all call at once: one screen is enough
            if (opening) {
                return;
            }
            opening = true;
            action.doAction(UNLOCK_ACTION, { clearBreadcrumbs: true }).finally(() => {
                opening = false;
            });
        };
    },
});

// Reads the source afresh: the worker keeps what it read for a few minutes, a change made in
// Vaultwarden or KeePass in the meantime shows up after this.
registry.category("actions").add("int_keepass.refresh", async (env) => {
    if (!keepass.password) {
        return env.services.action.doAction(UNLOCK_ACTION, { clearBreadcrumbs: true });
    }
    await env.services.orm.call("int.keepass.entry", "action_refresh", []);
    return env.services.action.doAction(ENTRY_ACTION, { clearBreadcrumbs: true });
});

// Takes the user names of the AIDA entries over into Odoo (names only). Held back by the
// wrapper of the rpc until the password manager is unlocked, like every other call.
registry.category("actions").add("int_keepass.sync_aida", async (env) => {
    const result = await env.services.orm.call("int.keepass.entry", "action_sync_aida_users", []);
    env.services.notification.add(
        _t("%(total)s AIDA names found, %(added)s new, %(removed)s archived.", result),
        { type: "success" }
    );
});

registry.category("actions").add("int_keepass.lock", async (env) => {
    if (keepass.password) {
        try {
            await env.services.orm.call("int.keepass.entry", "action_lock", []);
        } catch {
            // the screen locks anyway; the worker forgets after a few minutes by itself
        }
    }
    keepass.password = null;
    keepass.email = null;
    return env.services.action.doAction(UNLOCK_ACTION, { clearBreadcrumbs: true });
});
