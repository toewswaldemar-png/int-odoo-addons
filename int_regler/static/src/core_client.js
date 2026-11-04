// The browser side of the controller service: its address, its sign-in and its routes. No import from Odoo, so
// that the file can be run on its own (tools/int_regler/core_client.test.mjs).

const TOKEN_PREFIX = "int_regler.token:";

export class CoreError extends Error {
    constructor(status, message, body = null) {
        super(message);
        this.status = status; // 0: the service could not be reached
        this.body = body;
    }
}

/** The base of every route of one controller: ".../api/v1/devices/<id>". */
export function deviceBase(coreUrl, deviceRef) {
    return `${String(coreUrl).replace(/\/+$/, "")}/api/v1/devices/${encodeURIComponent(deviceRef)}`;
}

export class CoreClient {
    /**
     * @param {{core_url: string, device_ref: string}} device
     * @param {{storage?: Storage|null, fetchImpl?: typeof fetch}} [options] the token lives in the session storage
     *      of the tab: it is gone when the tab is closed and is never sent to Odoo.
     */
    constructor(device, { storage = globalThis.sessionStorage, fetchImpl = globalThis.fetch } = {}) {
        this.root = String(device.core_url).replace(/\/+$/, "");
        this.base = deviceBase(device.core_url, device.device_ref);
        this.storage = storage;
        this.fetchImpl = (...args) => fetchImpl(...args);
        this.tokenKey = TOKEN_PREFIX + this.root;
    }

    get token() {
        try {
            return this.storage?.getItem(this.tokenKey) || null;
        } catch {
            return null; // a private window or blocked site data: the sign-in then lasts until the page is closed
        }
    }

    set token(value) {
        try {
            if (value) {
                this.storage?.setItem(this.tokenKey, value);
            } else {
                this.storage?.removeItem(this.tokenKey);
            }
        } catch {
            // no storage, nothing to remember
        }
    }

    async request(url, init = {}) {
        const headers = { ...(init.headers || {}) };
        if (this.token) {
            headers.Authorization = `Bearer ${this.token}`;
        }
        if (init.body) {
            headers["Content-Type"] = "application/json";
        }
        let response;
        try {
            response = await this.fetchImpl(url, { ...init, headers });
        } catch (error) {
            if (error?.name === "AbortError") {
                throw error;
            }
            throw new CoreError(0, "The controller service cannot be reached.");
        }
        let body = null;
        try {
            body = await response.json();
        } catch {
            // an answer without a JSON body
        }
        if (!response.ok) {
            throw new CoreError(response.status, body?.error || response.statusText, body);
        }
        return body;
    }

    /** GET a route of this controller ("/status", "/pages/1"). */
    get(path, signal) {
        return this.request(this.base + path, { signal });
    }

    /** POST to a route of this controller; `body` is sent as JSON. */
    post(path, body) {
        return this.request(this.base + path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
    }

    /** Who the service thinks we are: the read-only local principal until we sign in. */
    me() {
        return this.request(`${this.root}/api/v1/me`);
    }

    async login(name, password) {
        const answer = await this.request(`${this.root}/api/v1/login`, {
            method: "POST",
            body: JSON.stringify({ name, password }),
        });
        this.token = answer.token;
        return answer.user;
    }

    async logout() {
        try {
            await this.request(`${this.root}/api/v1/logout`, { method: "POST" });
        } finally {
            this.token = null;
        }
    }
}
