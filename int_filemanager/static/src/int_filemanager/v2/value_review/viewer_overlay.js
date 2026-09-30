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

import {wordBox} from "./value_review_geometry.js";

const POLL_MS = 100;
const READY_TIMEOUT_MS = 20000;
const SCROLL_RETRY_MS = 300;

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
   */
  constructor(iframe, {onSelect, loadWords, pageSize, onPick} = {}) {
    this.iframe = iframe;
    this.onSelect = onSelect;
    this.loadWords = loadWords;
    this.pageSize = pageSize;
    this.onPick = onPick;
    this.wordMode = false;
    this.words = new Map();
    this.anchor = null;
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
  }

  /** Scrolls the box of a field to the middle of the viewer, also on a page not drawn yet. */
  scrollTo(fieldId, retry = true) {
    const marker = this.markers.find((m) => m.fieldId === fieldId);
    const doc = this.iframe.contentDocument;
    if (!marker || !doc) {
      return;
    }
    const box = doc.querySelector(`.o_int_fm_review_box[data-field-id="${fieldId}"]`);
    if (box) {
      box.scrollIntoView({block: "center", behavior: "smooth"});
    } else if (retry && this.app) {
      this.app.pdfViewer.scrollPageIntoView({pageNumber: marker.box.page});
      this._later(() => this.scrollTo(fieldId, false), SCROLL_RETRY_MS);
    }
  }

  destroy() {
    this.destroyed = true;
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
    if (this.destroyed || pageDiv.querySelector(":scope > .o_int_fm_review_layer")) {
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
      element.dataset.start = String(word[4]);
      element.dataset.end = String(word[5]);
      const {left, top, width, height} = wordBox(word, size);
      Object.assign(element.style, {
        left: `${left * 100}%`,
        top: `${top * 100}%`,
        width: `${width * 100}%`,
        height: `${height * 100}%`,
      });
      return element;
    });
    container.replaceChildren(...elements);
    this._listenToWords(container);
  }

  // A click is a drag from one word to the same one.
  _listenToWords(container) {
    const range = (from, to) => {
      const all = [...container.children];
      const [a, b] = [all.indexOf(from), all.indexOf(to)].sort((x, y) => x - y);
      return all.slice(a, b + 1);
    };
    const mark = (elements) =>
      [...container.children].forEach((el) =>
        el.classList.toggle("o_picking", elements.includes(el))
      );
    container.addEventListener("pointerdown", (event) => {
      if (event.target.classList.contains("o_int_fm_review_word")) {
        this.anchor = event.target;
        mark([event.target]);
        event.preventDefault();
      }
    });
    container.addEventListener("pointerover", (event) => {
      if (this.anchor && event.target.classList.contains("o_int_fm_review_word")) {
        mark(range(this.anchor, event.target));
      }
    });
    container.addEventListener("pointerup", (event) => {
      const anchor = this.anchor;
      this.anchor = null;
      mark([]);
      if (anchor && event.target.classList.contains("o_int_fm_review_word")) {
        const picked = range(anchor, event.target);
        this.onPick?.({
          start: Math.min(...picked.map((el) => Number(el.dataset.start))),
          end: Math.max(...picked.map((el) => Number(el.dataset.end))),
        });
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
        const {left, top, width, height} = marker.box;
        Object.assign(element.style, {
          left: `${left * 100}%`,
          top: `${top * 100}%`,
          width: `${width * 100}%`,
          height: `${height * 100}%`,
        });
        element.addEventListener("click", () => this.onSelect?.(marker.fieldId));
        return element;
      });
    layer.querySelector(".o_int_fm_review_boxes").replaceChildren(...boxes);
  }
}
