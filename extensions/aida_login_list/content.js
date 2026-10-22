// Offers the user names of AIDA-Web as a list in the field of the login. The names come from
// Odoo (int_keepass, /int_keepass/aida_users); only the password is typed.
//
// The login of AIDA is an AngularJS form that appears after the page has loaded, so the field is
// waited for. A choice from the list fires an `input` event, which AngularJS takes into its model.
(function () {
    "use strict";

    const USERNAME_SELECTOR = 'input[ng-model="$root.login.UserName"]';
    const PASSWORD_ID = "passwordFieldDirective";
    const LIST_ID = "aida-login-list";
    const CACHE_KEY = "aidaLoginUsers";
    const TIMEOUT_MS = 5000;

    /** The settings: the policy of the administrator wins over what is saved in the options. */
    async function loadConfig(storage) {
        const read = async (area) => {
            try {
                return (await area.get(["odooUrl", "token"])) || {};
            } catch {
                return {};
            }
        };
        const managed = await read(storage.managed);
        const local = await read(storage.local);
        const odooUrl = managed.odooUrl || local.odooUrl;
        const token = managed.token || local.token;
        return odooUrl && token ? { odooUrl: odooUrl.replace(/\/+$/, ""), token } : null;
    }

    /** The names from Odoo; throws when Odoo does not answer with a list. */
    async function fetchUsers(config, fetchFn, timeoutMs = TIMEOUT_MS) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
        try {
            const url = `${config.odooUrl}/int_keepass/aida_users?token=${encodeURIComponent(config.token)}`;
            const response = await fetchFn(url, { signal: controller.signal, cache: "no-store" });
            if (!response.ok) {
                throw new Error(`Odoo answered ${response.status}`);
            }
            const data = await response.json();
            if (!data || !Array.isArray(data.users) || !data.users.every((name) => typeof name === "string")) {
                throw new Error("Odoo did not send a list of names");
            }
            return data.users;
        } finally {
            clearTimeout(timer);
        }
    }

    /** The names of Odoo; if Odoo is not there, the names of the last time. */
    async function getUsers(config, storage, fetchFn) {
        try {
            const users = await fetchUsers(config, fetchFn);
            try {
                await storage.local.set({ [CACHE_KEY]: users });
            } catch {
                // a full or blocked storage must not take the list away
            }
            return users;
        } catch {
            const cached = (await storage.local.get([CACHE_KEY]).catch(() => ({})))[CACHE_KEY];
            return Array.isArray(cached) ? cached : [];
        }
    }

    /** Puts the names as a list (a `datalist`) at the field; safe to call again for the same field. */
    function attachList(input, users) {
        const doc = input.ownerDocument;
        let list = doc.getElementById(LIST_ID);
        if (!list) {
            list = doc.createElement("datalist");
            list.id = LIST_ID;
            input.insertAdjacentElement("afterend", list);
        }
        list.replaceChildren(
            ...users.map((name) => {
                const option = doc.createElement("option");
                option.value = name;
                return option;
            })
        );
        input.setAttribute("list", LIST_ID);
        // the box of the browser's own saved logins would cover this list
        input.setAttribute("autocomplete", "off");
        input.aidaLoginUsers = new Set(users);
        if (!input.dataset.aidaLoginList) {
            input.dataset.aidaLoginList = "1";
            input.addEventListener("input", onInput);
        }
    }

    /** After a choice from the list the cursor goes to the password; typing the name letter by letter does not. */
    function onInput(event) {
        const input = event.target;
        const chosen = !event.inputType || event.inputType === "insertReplacementText";
        if (chosen && input.aidaLoginUsers?.has(input.value)) {
            input.ownerDocument.getElementById(PASSWORD_ID)?.focus();
        }
    }

    /** Calls `onField` for the field now and every time AngularJS draws it again (login, logout). */
    function watchField(doc, onField) {
        const check = () => {
            const input = doc.querySelector(USERNAME_SELECTOR);
            if (input && !input.dataset.aidaLoginList) {
                onField(input);
            }
        };
        check();
        const observer = new doc.defaultView.MutationObserver(check);
        observer.observe(doc.documentElement, { childList: true, subtree: true });
        return observer;
    }

    async function main(chromeApi, doc, fetchFn) {
        const config = await loadConfig(chromeApi.storage);
        if (!config) {
            return null;
        }
        const users = await getUsers(config, chromeApi.storage, fetchFn);
        return watchField(doc, (input) => attachList(input, users));
    }

    if (typeof module !== "undefined" && module.exports) {
        module.exports = { loadConfig, fetchUsers, getUsers, attachList, watchField, main, USERNAME_SELECTOR, LIST_ID, PASSWORD_ID, CACHE_KEY };
    } else {
        main(chrome, document, (...args) => fetch(...args));
    }
})();
