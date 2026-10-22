/** @odoo-module **/

/**
 * Send setting changes one request at a time, merging what piles up meanwhile.
 *
 * A slider produces dozens of values a second; only the newest value of each setting
 * has to reach the server.
 */
export class SettingsQueue {
    /** @param {(values: object) => Promise<void>} send */
    constructor(send) {
        this.send = send;
        this.pending = null;
        this.running = null;
    }

    /** Tell whether a change is waiting or on its way. */
    get busy() {
        return this.pending !== null || this.running !== null;
    }

    /** Queue one change; resolves when the queue is empty again. */
    push(key, value) {
        this.pending = { ...this.pending, [key]: value };
        if (!this.running) {
            this.running = this.drain();
        }
        return this.running;
    }

    async drain() {
        try {
            while (this.pending !== null) {
                const values = this.pending;
                this.pending = null;
                await this.send(values);
            }
        } finally {
            this.running = null;
        }
    }
}
