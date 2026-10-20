// The undo history: one entry per state of the edit, as JSON text (so that equal states are found
// equal, and an entry cannot be changed by later work).

export class History {
    /** @param {number} limit the most entries that are kept */
    constructor(limit) {
        this.limit = limit;
        this.entries = [];
        this.cursor = 0;
    }

    /** Starts over with one entry: the state the edit starts from. */
    reset(entry) {
        this.entries = [entry];
        this.cursor = 0;
    }

    get current() {
        return this.entries[this.cursor];
    }

    get canUndo() {
        return this.cursor > 0;
    }

    get canRedo() {
        return this.cursor < this.entries.length - 1;
    }

    /** Whether anything was done since the start (or the last `reset`). */
    get changed() {
        return this.entries.length > 1;
    }

    /**
     * Adds a state after the one on show; what could be redone is gone.
     * @returns {boolean} false if it equals the one on show (nothing is added)
     */
    push(entry) {
        if (entry === this.current) {
            return false;
        }
        this.entries = this.entries.slice(0, this.cursor + 1);
        this.entries.push(entry);
        if (this.entries.length > this.limit) {
            this.entries.shift();
        }
        this.cursor = this.entries.length - 1;
        return true;
    }

    /** @returns {string|undefined} the entry to show, `undefined` if there is none before */
    undo() {
        return this.canUndo ? this.entries[--this.cursor] : undefined;
    }

    redo() {
        return this.canRedo ? this.entries[++this.cursor] : undefined;
    }
}
