// A stand-in for the `action` service of the webclient. The views, the control panel and the
// search menus ask for it (`useService("action")`); a guest has no actions.
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

registry.category("services").add("action", {
    dependencies: ["notification"],
    start(env, { notification }) {
        const notAvailable = () => {
            notification.add(_t("Not available on this page."), { type: "warning" });
            return Promise.resolve();
        };
        return {
            currentController: null,
            doAction: notAvailable,
            doActionButton: notAvailable,
            switchView() {},
            restore() {},
            loadState() {},
        };
    },
});
