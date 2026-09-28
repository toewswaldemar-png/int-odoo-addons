/** @odoo-module **/

// Thumbnails: the server makes them in the background. This part tells it which files are
// on screen (so those come first), and looks again when it says something is ready.
import {onWillUnmount, useEffect} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {NODE_MODEL} from "./controller_navigation.js";

export const PREVIEW_READY_EVENT = "int_filemanager_preview_ready";
// The bus message can be missed (a sleeping laptop, a reconnect), so a slow look-again
// timer runs as long as thumbnails are still expected.
const POLL_MS = 30000;
const RELOAD_DELAY_MS = 1000;

export const previewsMixin = (Base) =>
  class extends Base {
    setup() {
      super.setup();
      const busService = useService("bus_service");
      this._previewTimers = new Set();
      this._onPreviewReady = () => this._scheduleRefresh(RELOAD_DELAY_MS);
      busService.subscribe(PREVIEW_READY_EVENT, this._onPreviewReady);
      onWillUnmount(() => {
        busService.unsubscribe(PREVIEW_READY_EVENT, this._onPreviewReady);
        this._previewTimers.forEach((timer) => clearTimeout(timer));
      });
      // Runs after every render, but only asks when the set of waiting files changed.
      useEffect(
        (key) => {
          if (key) {
            this.orm.call(NODE_MODEL, "request_previews", [this._pendingPreviewIds()]);
            this._scheduleRefresh(POLL_MS);
          }
        },
        () => [this._pendingPreviewIds().join(",")]
      );
    }

    _pendingPreviewIds() {
      return (this.model.root?.records || [])
        .filter((record) => record.data.preview_state === "pending")
        .map((record) => record.resId);
    }

    _scheduleRefresh(delay) {
      const timer = setTimeout(async () => {
        this._previewTimers.delete(timer);
        if (this._pendingPreviewIds().length) {
          await this.reload();
          // Still waiting for some: look again later.
          if (this._pendingPreviewIds().length) {
            this._scheduleRefresh(POLL_MS);
          }
        }
      }, delay);
      this._previewTimers.add(timer);
    }
  };
