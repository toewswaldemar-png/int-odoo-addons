// `user` is a module, not a service: its checks call /web/dataset/call_kw, which needs a login.
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
