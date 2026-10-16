// SPIKE (throw-away): a stand-in for the `action` service of the webclient. The views, the control
// panel and the search menus ask for it (`useService("action")`); a guest has no actions.
import { registry } from "@web/core/registry";

registry.category("services").add("action", {
    dependencies: ["notification"],
    start(env, { notification }) {
        return {
            currentController: null,
            doAction() {
                notification.add("Not available on this page.", { type: "warning" });
                return Promise.resolve();
            },
            doActionButton() {
                notification.add("Not available on this page.", { type: "warning" });
                return Promise.resolve();
            },
            switchView() {},
            restore() {},
            loadState() {},
        };
    },
});
