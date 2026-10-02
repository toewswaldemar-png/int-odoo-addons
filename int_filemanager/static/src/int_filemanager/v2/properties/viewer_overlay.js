/** @odoo-module **/

// Outlines of the found values over the pages of Odoo's own pdf.js viewer (the viewer.html
// in an iframe, same origin). pdf.js throws away every child of a page it did not make
// when it draws the page again (zoom, scrolling far away and back), so a MutationObserver
// puts the layer back at once. The boxes are placed in percent of the page, which follows
// every zoom without a repaint.
//
// Words to click on lie in a second layer, loaded per page when the page gets its layer
// and only reacting while a field is chosen (word mode); then a click or a drag over
// several words says which text of the file was meant.
//
// The viewer's document has none of Odoo's stylesheets, and Odoo's page defines no color
// variables at run time: the two colors are read from Odoo's own classes (the action color
// and the muted text color) on a hidden element and copied into the frame.

import {boxStyle, outlineBox, selectWords, wordBox} from "./value_geometry.js";

const POLL_MS = 100;
const READY_TIMEOUT_MS = 20000;
// The viewer shows this much of the page width around a box: a few times the width of the
// box, but neither less than a third of the page (a short number would fill the screen) nor
// more than four fifths of it.
const REGION_PER_BOX_WIDTH = 4;
const REGION_MIN_SHARE = 0.3;
const REGION_MAX_SHARE = 0.8;

const STYLE = `
.o_int_fm_review_layer { position: absolute; inset: 0; pointer-events: none; z-index: 5; }
.o_int_fm_review_box {
  position: absolute; box-sizing: border-box; pointer-events: auto; cursor: pointer;
  border: 1px solid var(--o-int-border); border-radius: 2px;
}
.o_int_fm_review_words { position: absolute; inset: 0; }
.o_int_fm_review_word { position: absolute; pointer-events: none; }
.o_word_mode .o_int_fm_review_word { pointer-events: auto; cursor: crosshair; }
.o_word_mode .o_int_fm_review_box { pointer-events: none; }
.o_int_fm_review_word:hover, .o_int_fm_review_word.o_picking {
  background: color-mix(in srgb, var(--o-int-accent) 20%, transparent);
}
.o_int_fm_review_box:hover { border-color: var(--o-int-accent); }
.o_int_fm_review_box.o_active {
  border: 2px solid var(--o-int-accent);
  background: color-mix(in srgb, var(--o-int-accent) 12%, transparent);
}
`;

/** The action color and the quiet color of Odoo, as the page shows them. */
function themeColors() {
    const colorOf = (className) => {
        const probe = document.createElement("span");
        probe.className = className;
        probe.style.display = "none";
        document.body.appendChild(probe);
        const color = getComputedStyle(probe).color;
        probe.remove();
        return color;
    };
    return {accent: colorOf("text-action"), quiet: colorOf("text-muted")};
}

export class ViewerOverlay {
    /**
     * @param {HTMLIFrameElement} iframe the pdf.js viewer
     * @param {Object} [options]
     * @param {Function} [options.onSelect] ``onSelect(fieldId)`` when a box is clicked
     * @param {Function} [options.loadWords] ``loadWords(page)`` resolves to the words of a
     *   page: ``[x0, top, x1, bottom, start, end]`` each
     * @param {Function} [options.pageSize] ``pageSize(page)``: width and height of a page
     * @param {Function} [options.onPick] ``onPick({start, end})`` when words were clicked
     * @param {Function} [options.onCancel] ``onCancel()`` when Esc is pressed in word mode;
     *   the key goes to the frame, not to the page around it
     */
    constructor(iframe, {onSelect, loadWords, pageSize, onPick, onCancel} = {}) {
        this.iframe = iframe;
        this.onSelect = onSelect;
        this.loadWords = loadWords;
        this.pageSize = pageSize;
        this.onPick = onPick;
        this.onCancel = onCancel;
        this._onKeydown = (event) => {
            if (event.key === "Escape" && this.wordMode) {
                event.preventDefault();
                this.onCancel?.();
            }
        };
        this.wordMode = false;
        this.words = new Map();
        // The index of the word a drag began on, and the page layer it lies in.
        this.anchor = null;
        this.anchorLayer = null;
        this.markers = [];
        this.activeFieldId = null;
        this.observers = [];
        this.timers = new Set();
        this.destroyed = false;
    }

    get app() {
        const win = this.iframe && this.iframe.contentWindow;
        return win && win.PDFViewerApplication;
    }

    /**
     * Waits until the viewer knows its pages, then puts a layer on each of them.
     * @returns {Promise<boolean>} false when the viewer did not come up in time
     */
    async attach() {
        const ready = await this._until(() => {
            const viewer = this.app && this.app.pdfViewer;
            return Boolean(viewer && viewer.pagesCount && viewer.getPageView(0));
        });
        if (!ready || this.destroyed) {
            return false;
        }
        this._injectStyle();
        const viewer = this.app.pdfViewer;
        for (let i = 0; i < viewer.pagesCount; i++) {
            this._watch(viewer.getPageView(i).div);
        }
        return true;
    }

    setMarkers(markers) {
        this.markers = markers;
        this._paintAll();
    }

    setActive(fieldId) {
        this.activeFieldId = fieldId;
        this._paintAll();
    }

    /** Words react to the mouse only while a field waits for a value. */
    setWordMode(enabled) {
        this.wordMode = enabled;
        const doc = this.iframe.contentDocument;
        for (const layer of doc ? doc.querySelectorAll(".o_int_fm_review_layer") : []) {
            layer.classList.toggle("o_word_mode", enabled);
        }
        if (doc) {
            doc.removeEventListener("keydown", this._onKeydown);
            if (enabled) {
                doc.addEventListener("keydown", this._onKeydown);
                this._loadMissingWords(doc);
            }
        }
    }

    /**
     * Brings the box of a field to the middle of the viewer and zooms to it, with pdf.js's own
     * destination "FitR" (the way a link inside a PDF goes to a place). The region has the
     * shape of the viewer and is centred on the box, so the value stands in the middle with
     * its surroundings, also on a page that is not drawn yet.
     */
    scrollTo(fieldId) {
        const marker = this.markers.find((m) => m.fieldId === fieldId);
        const viewer = this.app && this.app.pdfViewer;
        const pageView = marker && viewer && viewer.getPageView(marker.box.page - 1);
        if (!pageView || pageView.rotation % 360 !== 0) {
            return;
        }
        // The page in PDF units, origin at the lower left; the box was given from the top left.
        const [x0, y0, x1, y1] = pageView.viewport.viewBox;
        const pageWidth = x1 - x0;
        const pageHeight = y1 - y0;
        const {left, top, width, height} = marker.box;
        const centerX = x0 + (left + width / 2) * pageWidth;
        const centerY = y1 - (top + height / 2) * pageHeight;
        const regionWidth = Math.min(
            Math.max(
                width * pageWidth * REGION_PER_BOX_WIDTH,
                pageWidth * REGION_MIN_SHARE
            ),
            pageWidth * REGION_MAX_SHARE
        );
        const regionHeight =
            (regionWidth * viewer.container.clientHeight) /
            viewer.container.clientWidth;
        viewer.scrollPageIntoView({
            pageNumber: marker.box.page,
            destArray: [
                null,
                {name: "FitR"},
                centerX - regionWidth / 2,
                centerY - regionHeight / 2,
                centerX + regionWidth / 2,
                centerY + regionHeight / 2,
            ],
        });
    }

    destroy() {
        this.destroyed = true;
        const doc = this.iframe && this.iframe.contentDocument;
        if (doc) {
            doc.removeEventListener("keydown", this._onKeydown);
        }
        this.observers.forEach((observer) => observer.disconnect());
        this.observers = [];
        this.timers.forEach((timer) => clearTimeout(timer));
        this.timers.clear();
    }

    // ---------------------------------------------------------------- internals

    _until(condition) {
        return new Promise((resolve) => {
            const started = Date.now();
            const check = () => {
                let ok = false;
                try {
                    ok = condition();
                } catch {
                    // The frame is still loading.
                }
                if (ok || this.destroyed || Date.now() - started > READY_TIMEOUT_MS) {
                    resolve(ok);
                } else {
                    this._later(check, POLL_MS);
                }
            };
            check();
        });
    }

    _later(callback, delay) {
        const timer = setTimeout(() => {
            this.timers.delete(timer);
            callback();
        }, delay);
        this.timers.add(timer);
    }

    _injectStyle() {
        const doc = this.iframe.contentDocument;
        if (doc.getElementById("o_int_fm_review_style")) {
            return;
        }
        const colors = themeColors();
        const style = doc.createElement("style");
        style.id = "o_int_fm_review_style";
        style.textContent = `:root { --o-int-accent: ${colors.accent}; --o-int-border: ${colors.quiet}; }${STYLE}`;
        doc.head.appendChild(style);
    }

    _watch(pageDiv) {
        const observer = new this.iframe.contentWindow.MutationObserver(() =>
            this._ensureLayer(pageDiv)
        );
        observer.observe(pageDiv, {childList: true});
        this.observers.push(observer);
        this._ensureLayer(pageDiv);
    }

    _ensureLayer(pageDiv) {
        if (
            this.destroyed ||
            pageDiv.querySelector(":scope > .o_int_fm_review_layer")
        ) {
            return;
        }
        const doc = this.iframe.contentDocument;
        const layer = doc.createElement("div");
        layer.className = "o_int_fm_review_layer";
        layer.classList.toggle("o_word_mode", this.wordMode);
        const words = doc.createElement("div");
        words.className = "o_int_fm_review_words";
        const boxes = doc.createElement("div");
        boxes.className = "o_int_fm_review_boxes";
        layer.append(words, boxes);
        pageDiv.appendChild(layer);
        const pageNumber = Number(pageDiv.dataset.pageNumber);
        this._paint(layer, pageNumber);
        this._paintWords(words, pageNumber);
    }

    /** Pages whose words were not there when they were drawn (the text was still being read). */
    _loadMissingWords(doc) {
        for (const layer of doc.querySelectorAll(".o_int_fm_review_layer")) {
            const container = layer.querySelector(".o_int_fm_review_words");
            if (!container.hasChildNodes()) {
                this._paintWords(
                    container,
                    Number(layer.parentElement.dataset.pageNumber)
                );
            }
        }
    }

    async _paintWords(container, pageNumber) {
        if (!this.loadWords) {
            return;
        }
        if (!this.words.has(pageNumber)) {
            this.words.set(pageNumber, this.loadWords(pageNumber));
        }
        const words = await this.words.get(pageNumber).catch(() => null);
        if (!words) {
            this.words.delete(pageNumber);
            return;
        }
        if (this.destroyed || !container.isConnected) {
            return;
        }
        const doc = this.iframe.contentDocument;
        const size = this.pageSize ? this.pageSize(pageNumber) : [595, 842];
        const elements = words.map((word) => {
            const element = doc.createElement("div");
            element.className = "o_int_fm_review_word";
            element.style.cssText = boxStyle(wordBox(word, size));
            return element;
        });
        container.replaceChildren(...elements);
        if (elements.length) {
            this._listenToWords(container, words);
        }
    }

    // A click is a drag from one word to the same one.
    _listenToWords(container, words) {
        const isWord = (element) => element.classList.contains("o_int_fm_review_word");
        const indexOf = (element) => [...container.children].indexOf(element);
        const mark = (range) =>
            [...container.children].forEach((el, index) =>
                el.classList.toggle(
                    "o_picking",
                    Boolean(range) && index >= range.first && index <= range.last
                )
            );
        container.addEventListener("pointerdown", (event) => {
            if (isWord(event.target)) {
                this.anchor = indexOf(event.target);
                this.anchorLayer = container;
                mark(selectWords(words, this.anchor, this.anchor));
                event.preventDefault();
            }
        });
        container.addEventListener("pointerover", (event) => {
            if (this.anchorLayer === container && isWord(event.target)) {
                mark(selectWords(words, this.anchor, indexOf(event.target)));
            }
        });
        container.addEventListener("pointerup", (event) => {
            const anchor = this.anchorLayer === container ? this.anchor : null;
            this.anchor = null;
            this.anchorLayer = null;
            mark(null);
            if (anchor !== null && isWord(event.target)) {
                const {start, end} = selectWords(words, anchor, indexOf(event.target));
                this.onPick?.({start, end});
            }
        });
    }

    _paintAll() {
        const doc = this.iframe.contentDocument;
        if (!doc) {
            return;
        }
        for (const layer of doc.querySelectorAll(".o_int_fm_review_layer")) {
            this._paint(layer, Number(layer.parentElement.dataset.pageNumber));
        }
    }

    _paint(layer, pageNumber) {
        const doc = this.iframe.contentDocument;
        const boxes = this.markers
            .filter((marker) => marker.box.page === pageNumber)
            .map((marker) => {
                const element = doc.createElement("div");
                element.className = "o_int_fm_review_box";
                if (marker.fieldId === this.activeFieldId) {
                    element.classList.add("o_active");
                }
                element.dataset.fieldId = String(marker.fieldId);
                element.title = marker.name;
                const size = this.pageSize ? this.pageSize(pageNumber) : [595, 842];
                element.style.cssText = boxStyle(outlineBox(marker.box, size));
                element.addEventListener("click", () =>
                    this.onSelect?.(marker.fieldId)
                );
                return element;
            });
        layer.querySelector(".o_int_fm_review_boxes").replaceChildren(...boxes);
    }
}
