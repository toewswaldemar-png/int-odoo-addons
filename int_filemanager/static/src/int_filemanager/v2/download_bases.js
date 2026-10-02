/** @odoo-module **/

// "Edit locally": the revision a file was downloaded from, so that the upload of the edited
// copy carries it as its base and a change made by somebody else in between is reported
// instead of overwritten. Logic only - the storage is injected, tested with plain Node.

const KEEP_MS = 30 * 24 * 60 * 60 * 1000;

export class DownloadBases {
    /**
     * @param {{load: Function, save: Function}} storage  a plain object of remembered bases
     * @param {Function} [now]
     */
    constructor(storage, now = Date.now) {
        this.storage = storage;
        this.now = now;
    }

    remember(nodeId, revisionId) {
        if (!revisionId) {
            return;
        }
        const bases = this.storage.load();
        bases[nodeId] = {revisionId, at: this.now()};
        this.storage.save(bases);
    }

    /** The remembered revision of the node, once; false if none or too old. */
    take(nodeId) {
        const bases = this.storage.load();
        const entry = bases[nodeId];
        if (!entry) {
            return false;
        }
        delete bases[nodeId];
        this.storage.save(bases);
        return this.now() - entry.at > KEEP_MS ? false : entry.revisionId;
    }
}
