const DIMMED_CLASS = "opacity-50";

/**
 * The documents that are dragged from the list or the cards to a folder of the search panel, and
 * the folder under the pointer. The two do not know each other: the panel shows `over` and the
 * rows set it (`searchModel.drag`, a reactive object).
 */
export class DocumentDragState {
    constructor() {
        this.resIds = [];
        this.over = null;
        this.dimmed = [];
    }

    get active() {
        return this.resIds.length > 0;
    }

    /**
     * @param {Object[]} records the records that are dragged
     * @param {Element} root the element that holds their rows or cards
     */
    start(records, root) {
        this.resIds = records.map((record) => record.resId);
        const dragged = new Set(records.map((record) => record.id));
        for (const element of root.querySelectorAll("[data-id]")) {
            if (dragged.has(element.dataset.id)) {
                element.classList.add(DIMMED_CLASS);
                this.dimmed.push(element);
            }
        }
    }

    end() {
        for (const element of this.dimmed) {
            element.classList.remove(DIMMED_CLASS);
        }
        this.dimmed = [];
        this.resIds = [];
        this.over = null;
    }
}
