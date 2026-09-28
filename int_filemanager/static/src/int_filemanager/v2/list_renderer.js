/** @odoo-module **/

// File-explorer behaviour on top of Odoo's list: a single click only selects, a double
// click opens, dragging over empty space draws a selection rectangle, touch users
// select with a long press. A real subclass registered as the view's "Renderer", so no
// other list in the system is touched.
//
// MouseEvent.detail tells the clicks apart on the handler Odoo already wires on the cell
// (1 = single, 2 = double, 0 = keyboard/programmatic, which keeps Odoo's original
// "open" so the list stays usable without a mouse).
import {onMounted, onWillUnmount} from "@odoo/owl";
import {ListRenderer} from "@web/views/list/list_renderer";

const LONG_PRESS_MS = 500;
const LONG_PRESS_MOVE_TOLERANCE_PX = 10;
const RUBBERBAND_THRESHOLD_PX = 4;

export class IntFilemanagerV2ListRenderer extends ListRenderer {
  setup() {
    super.setup();
    this._longPressSuppressClick = false;
    this._setupDeselectOnOutsideClick();
    this._setupRubberband();
    this._setupLongPress();
  }

  // A click outside the list (empty space below the rows, sidebar, navbar, search bar)
  // clears the selection, like an explorer. Deliberately NOT cleared: clicks on a row
  // (its own logic), on the selection box and its "Actions" button, on open dropdowns and
  // dialogs, on the chatter panel and its toggle, and on the table head (Odoo's
  // "select all" checkbox lives there - this capture-phase guard runs BEFORE Odoo's own
  // handler and would otherwise clear first, so "select all" could never deselect).
  _setupDeselectOnOutsideClick() {
    const onDocumentClick = (ev) => {
      // The click that follows a long press must be swallowed here, on the document in the
      // capture phase, before Odoo's row-level capture handler sees it and deselects the
      // row that was just selected.
      if (this._longPressSuppressClick) {
        this._longPressSuppressClick = false;
        ev.stopPropagation();
        ev.preventDefault();
        return;
      }
      if (this._rubberbandJustEnded) {
        this._rubberbandJustEnded = false;
        return;
      }
      if (!this.props.list.selection.length) {
        return;
      }
      const target = ev.target;
      if (
        target.closest("tr.o_data_row") ||
        target.closest(".o_selection_container") ||
        target.closest(".dropdown-menu, .o-dropdown--menu") ||
        target.closest(".modal, .o_dialog") ||
        target.closest(".o_int_filemanager_chatter_panel") ||
        target.closest(".o_int_filemanager_chatter_toggle") ||
        target.closest("thead")
      ) {
        return;
      }
      for (const record of this.props.list.records) {
        if (record.selected) {
          record.toggleSelection(false);
        }
      }
    };
    onMounted(() => document.addEventListener("click", onDocumentClick, true));
    onWillUnmount(() => document.removeEventListener("click", onDocumentClick, true));
  }

  // Draw a rectangle over empty space to select every row it touches. Row rectangles
  // are measured once at the start of the drag, not on every mouse move.
  _setupRubberband() {
    this._rubberbandJustEnded = false;
    const onMouseDown = (ev) => this._onRubberbandStart(ev);
    onMounted(() => document.addEventListener("mousedown", onMouseDown));
    onWillUnmount(() => document.removeEventListener("mousedown", onMouseDown));
  }

  _rubberbandStartAllowed(ev) {
    if (ev.button !== 0 || !this.canSelectRecord) {
      return false;
    }
    // Only inside the list container (not the bare table: that ends with the last row,
    // and the empty space below it must work too). Everything else - control panel,
    // sidebar, dialogs, popovers - is not a descendant, so no list of exceptions is needed.
    const container = this.tableRef.el?.closest(".o_list_renderer");
    if (!container || !container.contains(ev.target)) {
      return false;
    }
    // The checkbox column and the table head have click meanings of their own.
    return !(
      ev.target.closest(".o_list_record_selector") || ev.target.closest("thead")
    );
  }

  // In a dense folder there is often no empty space left, so - like the Explorer - a drag
  // may start anywhere on a row EXCEPT on the icon and name (that starts a move instead).
  // The horizontal bounds come from the measured rectangles of icon and label.
  _startsOnRowHandle(ev) {
    const rowEl = ev.target.closest("tr.o_data_row");
    if (!rowEl) {
      return false;
    }
    const handles = rowEl.querySelectorAll(
      ".o_int_filemanager_name_icon, .o_int_filemanager_name_label"
    );
    if (!handles.length) {
      return false;
    }
    const rects = [...handles].map((el) => el.getBoundingClientRect());
    const left = Math.min(...rects.map((r) => r.left));
    const right = Math.max(...rects.map((r) => r.right));
    return ev.clientX >= left && ev.clientX <= right;
  }

  _onRubberbandStart(ev) {
    if (!this._rubberbandStartAllowed(ev)) {
      return;
    }
    const records = this.props.list.records;
    const rowEls = [...this.tableRef.el.querySelectorAll("tr.o_data_row")];
    if (rowEls.length !== records.length || this._startsOnRowHandle(ev)) {
      return;
    }
    // Blur what had focus BEFORE preventDefault suppresses the browser's own blur: a
    // focused cell would otherwise keep Odoo's grey ":focus-within" background.
    document.activeElement?.blur();
    ev.preventDefault();

    const rowRects = rowEls.map((el, index) => ({
      record: records[index],
      rect: el.getBoundingClientRect(),
    }));
    const additive = ev.ctrlKey || ev.metaKey;
    const initiallySelected = additive
      ? new Set(records.filter((r) => r.selected))
      : new Set();
    const startX = ev.clientX;
    const startY = ev.clientY;
    let dragging = false;
    let overlay = null;
    let lastRect = null;
    // Record.toggleSelection is asynchronous (model mutex) and this handler runs outside
    // owl's render cycle: overlapping passes during fast mouse moves lost results. Only
    // one pass runs at a time while dragging; the final pass on mouse up is awaited and
    // authoritative.
    let isSelecting = false;

    const applySelection = async (rect) => {
      const promises = [];
      for (const {record, rect: rowRect} of rowRects) {
        const intersects =
          rowRect.left < rect.x2 &&
          rowRect.right > rect.x1 &&
          rowRect.top < rect.y2 &&
          rowRect.bottom > rect.y1;
        const shouldSelect = intersects || initiallySelected.has(record);
        if (record.selected !== shouldSelect) {
          promises.push(record.toggleSelection(shouldSelect));
        }
      }
      await Promise.all(promises);
      this.render();
    };
    const onMouseMove = (moveEv) => {
      const dx = moveEv.clientX - startX;
      const dy = moveEv.clientY - startY;
      if (!dragging) {
        // A plain click without movement is no rubber band.
        if (Math.hypot(dx, dy) < RUBBERBAND_THRESHOLD_PX) {
          return;
        }
        dragging = true;
        overlay = document.createElement("div");
        overlay.className = "o_int_filemanager_rubberband";
        document.body.appendChild(overlay);
      }
      moveEv.preventDefault();
      lastRect = {
        x1: Math.min(startX, moveEv.clientX),
        x2: Math.max(startX, moveEv.clientX),
        y1: Math.min(startY, moveEv.clientY),
        y2: Math.max(startY, moveEv.clientY),
      };
      overlay.style.left = `${lastRect.x1}px`;
      overlay.style.top = `${lastRect.y1}px`;
      overlay.style.width = `${lastRect.x2 - lastRect.x1}px`;
      overlay.style.height = `${lastRect.y2 - lastRect.y1}px`;
      if (!isSelecting) {
        isSelecting = true;
        applySelection(lastRect).finally(() => {
          isSelecting = false;
        });
      }
    };
    const onMouseUp = async () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      overlay?.remove();
      // Set synchronously, before any await: the browser fires a "click" right after
      // mouse up, and it must find this flag already set or it clears the selection.
      this._rubberbandJustEnded = dragging;
      if (dragging) {
        setTimeout(() => {
          this._rubberbandJustEnded = false;
        }, 300);
      }
      if (dragging && lastRect) {
        await applySelection(lastRect);
      }
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }

  // Touch: a tap opens directly (double click is no dependable gesture there), a long
  // press on an unselected row starts a selection. Once something is selected, Odoo's own
  // mobile behaviour toggles further rows, so this only covers the first one. Pointer
  // events cover touch and mouse alike.
  _setupLongPress() {
    let timer = null;
    let startX = 0;
    let startY = 0;
    const cancel = () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    };
    const onPointerDown = (ev) => {
      if (
        !this.env.isSmall ||
        !this.canSelectRecord ||
        this.props.list.selection.length
      ) {
        return;
      }
      const rowEl = ev.target.closest("tr.o_data_row");
      if (!rowEl || !this.tableRef.el) {
        return;
      }
      const rowEls = [...this.tableRef.el.querySelectorAll("tr.o_data_row")];
      const record = this.props.list.records[rowEls.indexOf(rowEl)];
      if (!record) {
        return;
      }
      startX = ev.clientX;
      startY = ev.clientY;
      timer = setTimeout(() => {
        timer = null;
        this._longPressSuppressClick = true;
        record.toggleSelection(true);
        this.render();
      }, LONG_PRESS_MS);
    };
    const onPointerMove = (ev) => {
      if (
        timer &&
        Math.hypot(ev.clientX - startX, ev.clientY - startY) >
          LONG_PRESS_MOVE_TOLERANCE_PX
      ) {
        cancel();
      }
    };
    onMounted(() => {
      document.addEventListener("pointerdown", onPointerDown);
      document.addEventListener("pointermove", onPointerMove);
      document.addEventListener("pointerup", cancel);
      document.addEventListener("pointercancel", cancel);
    });
    onWillUnmount(() => {
      cancel();
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerup", cancel);
      document.removeEventListener("pointercancel", cancel);
    });
  }

  // The checkbox column is also shown on mobile (Odoo hides it there by not rendering it);
  // all colspan/header maths read this one getter.
  get hasSelectors() {
    return this.props.allowSelectors;
  }

  // Odoo's grey ":focus-within" row colour stays on a row whose checkbox was just
  // unchecked, because the checkbox keeps browser focus. Blur only on deselect; on select
  // the focus ring stays for keyboard navigation, as in any Odoo list.
  toggleRecordSelection(record, ev) {
    super.toggleRecordSelection(record, ev);
    if (!record.selected) {
      document.activeElement?.blur();
    }
  }

  async onCellClicked(record, column, ev, newWindow) {
    if (ev.detail === 0) {
      return super.onCellClicked(record, column, ev, newWindow);
    }
    // The click after a successful long press must not turn the fresh selection into an
    // "open".
    if (this._longPressSuppressClick) {
      this._longPressSuppressClick = false;
      return undefined;
    }
    const open = () => {
      if (!this.props.archInfo.noOpen) {
        this.props.openRecord(record, {newWindow});
      }
    };
    // Mobile, nothing selected yet: a tap opens. Modifier clicks stay selections.
    if (
      this.env.isSmall &&
      !this.props.list.selection.length &&
      ev.detail === 1 &&
      !ev.ctrlKey &&
      !ev.metaKey &&
      !this.shiftKeyMode
    ) {
      open();
      return undefined;
    }
    if (ev.detail >= 2) {
      // Not super.onCellClicked: it would look at the selection the first click just made
      // and toggle it again instead of opening (a double click toggled twice, never opened).
      open();
      return undefined;
    }
    if (!this.canSelectRecord) {
      return undefined;
    }
    // Ctrl/Cmd add, Shift extends a range (Odoo's base class tracks the shift key); a plain
    // click replaces the selection by exactly this row.
    if (ev.ctrlKey || ev.metaKey || this.shiftKeyMode) {
      this.toggleRecordSelection(record);
      return undefined;
    }
    for (const other of this.props.list.records) {
      if (other !== record && other.selected) {
        other.toggleSelection(false);
      }
    }
    record.toggleSelection(true);
    this.lastCheckedRecord = record;
    return undefined;
  }
}
