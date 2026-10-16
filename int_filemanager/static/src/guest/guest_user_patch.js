// SPIKE (throw-away): `user` is a module, not a service; its group and access checks call
// /web/dataset/call_kw, which needs a login. A guest has no groups and may only read.
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";

patch(user, {
    hasGroup() {
        return Promise.resolve(false);
    },
    checkAccessRight(model, operation) {
        return Promise.resolve(operation === "read");
    },
    setUserSettings() {
        return Promise.resolve();
    },
});
