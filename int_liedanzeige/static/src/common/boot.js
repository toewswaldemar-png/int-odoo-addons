/** @odoo-module **/

import { mount, whenReady } from "@odoo/owl";
import { appTranslateFn } from "@web/core/l10n/translation";
import { getTemplate } from "@web/core/templates";
import { makeEnv, startServices } from "@web/env";

import { IntLiedanzeigeConductor } from "../conductor/conductor";
import { IntLiedanzeigeControl } from "../control/control";
import { IntLiedanzeigeDisplay } from "../display/display";

const PAGES = {
    display: IntLiedanzeigeDisplay,
    control: IntLiedanzeigeControl,
    conductor: IntLiedanzeigeConductor,
};

(async function boot() {
    await whenReady();
    const config = odoo.int_liedanzeige;
    const env = makeEnv();
    await startServices(env);
    odoo.isReady = true;
    await mount(PAGES[config.page], document.body, {
        env,
        getTemplate,
        dev: env.debug,
        props: { config },
        translatableAttributes: ["data-tooltip"],
        translateFn: appTranslateFn,
    });
})();
