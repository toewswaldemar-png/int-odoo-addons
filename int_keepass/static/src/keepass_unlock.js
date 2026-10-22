import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { ENTRY_ACTION, keepass } from "./keepass_client";

export class KeepassUnlock extends Component {
    static template = "int_keepass.Unlock";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ password: "", email: "", withEmail: false, error: "", busy: false });
        useAutofocus({ refName: "password" });
        onWillStart(async () => {
            // asked first: the answer says whether the screen needs an e-mail address
            const info = await this.orm.call("int.keepass.entry", "get_source_info", []);
            this.state.withEmail = info.source === "vaultwarden";
            this.state.email = keepass.email || info.email || "";
        });
        // already unlocked in this page (the menu "Open" again): straight to the list
        onMounted(() => {
            if (keepass.password) {
                this.openList();
            }
        });
    }

    openList() {
        return this.action.doAction(ENTRY_ACTION, { clearBreadcrumbs: true });
    }

    async onSubmit() {
        if (!this.state.password || this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.error = "";
        keepass.password = this.state.password;
        keepass.email = this.state.withEmail ? this.state.email.trim() : null;
        try {
            await this.orm.call("int.keepass.entry", "action_unlock", []);
        } catch (error) {
            keepass.password = null;
            keepass.email = null;
            this.state.password = "";
            this.state.busy = false;
            this.state.error = error.data?.message || error.message;
            return;
        }
        this.state.password = "";
        await this.openList();
    }
}

registry.category("actions").add("int_keepass.unlock", KeepassUnlock);
