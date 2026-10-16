// SPIKE (throw-away): starts the Owl app of the guest page, as `mail/.../public/boot.js` does for
// the public discuss page: environment, services, and the container of the main components.
import { mount, whenReady } from "@odoo/owl";
import { getTemplate } from "@web/core/templates";
import { appTranslateFn } from "@web/core/l10n/translation";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { registry } from "@web/core/registry";
import { customDirectives, globalValues, makeEnv, startServices } from "@web/env";
import { GuestApp } from "./guest_app";

(async function boot() {
    await whenReady();
    registry.category("main_components").add("GuestApp", { Component: GuestApp });
    const env = makeEnv();
    await startServices(env);
    odoo.isReady = true;
    const root = await mount(MainComponentsContainer, document.body, {
        env,
        getTemplate,
        dev: env.debug,
        translatableAttributes: ["data-tooltip"],
        translateFn: appTranslateFn,
        customDirectives,
        globalValues,
    });
    odoo.__WOWL_DEBUG__ = { root };
})();
