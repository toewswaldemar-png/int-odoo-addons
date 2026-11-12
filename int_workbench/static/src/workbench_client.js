// What the page knows of a controller comes from Odoo, not from the controller service: the service reports to Odoo
// (int.workbench.device.service_sync, JSON-2), and the page reads that report. Nothing here calls the service. No import from
// Odoo, so that the file can be run on its own (tools/int_workbench/workbench_client.test.mjs); the ORM service is handed in.
//
// How a clamp ends is told by the bus of Odoo (a small message, sent when Odoo has the result): the page does not ask for it every
// few hundred milliseconds. It looks in Odoo now and then all the same, for a message that did not come.

/** No usable report: the service is gone, it has not reported, or Odoo cannot be reached: status 0 for all of them. */
export class ServiceError extends Error {
    constructor(status, message, body = null) {
        super(message);
        this.status = status; // 0: no usable report
        this.body = body;
    }
}

/** The part of the report that answers each route of the service that the views of the page read (the process values and the clamps are rows of int.workbench.parameter). */
const REPORT_KEYS = {
    "/status": "status",
    "/errors": "errors",
    "/errors/memory": "errors_memory",
    "/clock": "clock",
};

/**
 * The service is gone if it has not asked Odoo for this many seconds. It asks every two seconds when nobody looks and the page
 * says every ten seconds that somebody does, so the time is generous.
 */
export const SERVICE_GONE_SECONDS = 20;
/** A report older than this is shown as old (the service is asked for a new one as soon as the page is open). */
export const REPORT_OLD_SECONDS = 10;
/** How long a clamp request is waited for. Odoo lets a request expire after 15 s, so the answer is always there before this. */
export const COMMAND_WAIT_MS = 20000;
/** The first look in Odoo for the end of a request, in case its message came before the page was ready for it, and the ones after. */
export const FIRST_CHECK_MS = 400;
export const SAFETY_CHECK_MS = 1500;
/** The views read the report one by one; they get the same answer when they ask within this time. */
export const SHARE_MS = 500;
const FINISHED = ["done", "failed", "unconfirmed", "unknown", "expired"];

export class OdooClient {
    /**
     * @param {object} orm the ORM service of Odoo (read, create)
     * @param {{id: number}} device the record of the controller
     */
    constructor(orm, device, { now = () => Date.now(), sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)) } = {}) {
        this.orm = orm;
        this.id = device.id;
        this.now = now;
        this.sleep = sleep;
        this.reportAge = null; // seconds, by the clock of the server, of the report that was read last
        this._readAt = -Infinity;
        this._read = null;
        this._waiting = new Map(); // id of a request -> what to call when its end is told
        this._ended = new Map(); // id of a request that is waited for -> how it ended, if that was told before the wait began
    }

    /** The last report of the service; one read of Odoo serves all views that ask within SHARE_MS. */
    report() {
        if (this._read && this.now() - this._readAt < SHARE_MS) {
            return this._read;
        }
        this._readAt = this.now();
        this._read = this._load();
        return this._read;
    }

    async _load() {
        let rows;
        try {
            rows = await this.orm.read("int.workbench.device", [this.id], ["snapshot", "snapshot_at", "report_age", "seen_age"]);
        } catch (error) {
            throw new ServiceError(0, error?.message || "Odoo cannot be reached.");
        }
        const row = rows[0];
        if (!row) {
            throw new ServiceError(404, "This controller does not exist any more.");
        }
        if (!(row.seen_age >= 0) || row.seen_age > SERVICE_GONE_SECONDS) {
            const seen = row.seen_age >= 0 ? `not been seen for ${Math.round(row.seen_age)} s` : "never been seen";
            throw new ServiceError(0, `The controller service has ${seen}.`);
        }
        if (!row.snapshot_at || !row.snapshot) {
            throw new ServiceError(0, "The controller service has not reported yet.");
        }
        this.reportAge = row.report_age;
        return row.snapshot;
    }

    /** The part of the report for a route of the service ("/status", "/values", "/clamps" ...). */
    async get(path) {
        const key = REPORT_KEYS[path];
        if (!key) {
            throw new ServiceError(404, `The report has nothing for ${path}.`);
        }
        const report = await this.report();
        if (!(key in report)) {
            throw new ServiceError(404, `The report has nothing for ${path}.`);
        }
        return report[key];
    }

    /** The bus of Odoo tells how a request ended: {id, state, message}. Called for every such message; only the ones waited for count. */
    settle(payload) {
        if (!this._ended.has(payload.id) && !this._waiting.has(payload.id)) {
            return;
        }
        this._ended.set(payload.id, payload);
        this._waiting.get(payload.id)?.();
    }

    /**
     * Clamps or releases a row: makes a request (int.workbench.command) and waits until the service has carried it out (or Odoo says
     * why it was not). `path` is "/clamps/<row>", `body` {"action": "set", "value": 1} or {"action": "release"}, as for the service.
     * @returns {{confirmed: boolean, error: string}} like the answer of the service to a clamp
     */
    async post(path, body) {
        const match = /^\/clamps\/([^/]+)$/.exec(path);
        if (!match) {
            throw new ServiceError(404, `Nothing can be sent to ${path}.`);
        }
        const [id] = await this.orm.create("int.workbench.command", [
            { device_id: this.id, code: decodeURIComponent(match[1]), action: body.action, value: body.value ?? 0 },
        ]);
        this._ended.set(id, undefined); // from now on a message about this request is kept
        try {
            return await this._result(id);
        } finally {
            this._ended.delete(id);
            this._waiting.delete(id);
        }
    }

    async _result(id) {
        const deadline = this.now() + COMMAND_WAIT_MS;
        let wait = FIRST_CHECK_MS;
        while (this.now() < deadline) {
            if (this._ended.get(id)) {
                return this._answer(this._ended.get(id));
            }
            const told = new Promise((resolve) => this._waiting.set(id, resolve));
            await Promise.race([told, this.sleep(wait)]);
            this._waiting.delete(id);
            wait = SAFETY_CHECK_MS;
            if (this._ended.get(id)) {
                return this._answer(this._ended.get(id));
            }
            const [command] = await this.orm.read("int.workbench.command", [id], ["state", "message"]);
            if (FINISHED.includes(command.state)) {
                this._read = null; // what the views read next is read afresh: the report that came with the answer
                return this._answer(command);
            }
        }
        throw new ServiceError(504, "Nobody answered the request in time. It is in the clamp log.");
    }

    _answer(command) {
        this._read = null;
        return { confirmed: command.state === "done", error: command.state === "done" ? "" : command.message || command.state };
    }
}
