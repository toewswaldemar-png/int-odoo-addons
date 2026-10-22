const url = document.getElementById("odooUrl");
const token = document.getElementById("token");
const state = document.getElementById("state");

chrome.storage.local.get(["odooUrl", "token"]).then((saved) => {
    url.value = saved.odooUrl || "";
    token.value = saved.token || "";
});

document.getElementById("save").addEventListener("click", async () => {
    const odooUrl = url.value.trim().replace(/\/+$/, "");
    // the grey text in the empty field is only a hint, not a value
    if (!/^https?:\/\/[^/\s]+$/.test(odooUrl)) {
        state.textContent = "Bitte die Adresse von Odoo eintragen, zum Beispiel http://odoo.example:8069 (mit http://, ohne Pfad).";
        return;
    }
    if (!token.value.trim()) {
        state.textContent = "Bitte das Token der Liste eintragen.";
        return;
    }
    await chrome.storage.local.set({ odooUrl, token: token.value.trim() });
    state.textContent = "Gespeichert. Prüfe die Verbindung …";
    try {
        const response = await fetch(`${odooUrl}/int_keepass/aida_users?token=${encodeURIComponent(token.value.trim())}`, { cache: "no-store" });
        if (!response.ok) {
            state.textContent = `Odoo antwortet mit ${response.status}: Adresse oder Token stimmen nicht.`;
            return;
        }
        const { users } = await response.json();
        state.textContent = `Verbindung in Ordnung: ${users.length} Namen in der Liste.`;
    } catch (error) {
        state.textContent = `Odoo ist nicht erreichbar (${error.message}).`;
    }
});
