/** @odoo-module ignore **/
// The page that asks for the password of a share (a plain script: the page has no Odoo
// framework). The key that the server gives for the right password stays in the
// ``sessionStorage`` of the tab, never in a cookie or an address; a reload of the page finds it
// there and opens the share again without asking. The page of the share comes as a whole
// document from ``POST .../page`` (it needs the key) and replaces this one.
(function () {
    "use strict";
    const form = document.getElementById("o_share_password");
    if (!form) {
        return;
    }
    const base = "/int_filemanager/share/" + encodeURIComponent(form.dataset.token);
    const storageName = "int_filemanager.share_key." + form.dataset.token;
    const message = form.querySelector(".o_share_message");
    const MESSAGES = {
        403: "The password is wrong.",
        410: "This link is not valid any more.",
        429: "Too many tries. Try again later.",
    };

    function say(status) {
        message.textContent = MESSAGES[status] || "Something went wrong. Try again.";
    }

    async function open(key) {
        const response = await fetch(base + "/page", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ k: key }),
        });
        if (!response.ok) {
            sessionStorage.removeItem(storageName);
            say(response.status);
            return;
        }
        const html = await response.text();
        document.open();
        document.write(html);
        document.close();
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        message.textContent = "";
        const response = await fetch(base + "/unlock", {
            method: "POST",
            body: new URLSearchParams({ password: form.elements.password.value }),
        });
        if (!response.ok) {
            say(response.status);
            return;
        }
        const { key } = await response.json();
        sessionStorage.setItem(storageName, key);
        await open(key);
    });

    const stored = sessionStorage.getItem(storageName);
    if (stored) {
        open(stored);
    }
})();
