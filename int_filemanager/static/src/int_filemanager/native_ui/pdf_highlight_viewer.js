/** @odoo-module **/

// Phase C (docs/int_filemanager_ocr_selbstdefinierte_felder.md): eigener, schlanker PDF-Renderer
// fuer den Kontroll-Dialog - anders als der fertige pdfjs-iframe-Viewer
// (web/static/lib/pdfjs/web/viewer.html, siehe filemanager_controller_mixin.js::toViewerFile fuer
// die normale Dateivorschau) steuert diese Komponente Odoos bereits mitgelieferte pdfjs-Kern-
// Bibliothek (web/static/lib/pdfjs/build/pdf.js + pdf.worker.js - exakt dieselben Dateien, die das
// npm-Paket "pdfjs-dist" auch nur verpackt, keine neue Abhaengigkeit) direkt ueber die JS-API an,
// um pro erkanntem Wert eine Markierungs-Box ueber die gerenderte Seite zu zeichnen. Kontrolliert
// von aussen (page/boxes/activeKey als Props, kein eigener interner "welcher Wert ist aktiv"-
// Zustand) - der Dialog kennt die Werteliste und damit auch, welche Box beim Hover ueber eine
// Zeile aktiv werden soll.
import { Component, onMounted, onWillStart, onWillUnmount, onWillUpdateProps, useRef, useState } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

const PDFJS_BUILD_URL = "/web/static/lib/pdfjs/build/pdf.js";
const PDFJS_WORKER_URL = "/web/static/lib/pdfjs/build/pdf.worker.js";

// Zoombereich relativ zur Fit-Breite (1.0) - Nutzerwunsch 2026-09-19 (Vorschau "klein und kaum
// erkennbar"): Scroll-to-Zoom mit dem Mauszeiger als Fixpunkt, wie in gaengigen PDF-/Karten-
// Viewern. 0.5 als unteres Limit reicht, um wieder komplett herauszuzoomen; 6 als oberes Limit
// deckt auch feine Details (Kleingedrucktes) ab, ohne dass eine einzelne Seite unhandlich riesig
// (und damit das Rendering unnoetig teuer) wird.
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 6;
// Empirisch gewaehlt (Standard-Mausrad liefert deltaY meist in 100er-Schritten, Trackpads oft
// deutlich feinere Werte) - ein Mausrad-"Klick" ergibt damit ca. +/-14% Zoom pro Schritt, spuerbar
// aber nicht sprunghaft.
const ZOOM_INTENSITY = 0.0015;

export class IntPdfHighlightViewer extends Component {
    static template = "int_filemanager.PdfHighlightViewer";
    static props = {
        downloadUrl: String,
        pageNum: Number,
        boxes: Array, // [{key, page, x0, y0, x1, y1}, ...] - page 1-basiert, x0..y1 in PDF-Punkten
        activeKey: [String, Number, Boolean],
        onPageCountKnown: { type: Function, optional: true },
        onBoxClick: { type: Function, optional: true },
    };

    setup() {
        this.containerRef = useRef("container");
        this.canvasRef = useRef("canvas");
        // renderTick: reiner Zaehler ohne eigenen Sinn ausser dem Anstossen eines Owl-Renders -
        // scale/boxStyle() sind imperativ berechnete, nicht-reaktive Werte (siehe _renderPage()),
        // Owl wuerde eine reine Instanzvariablen-Aenderung sonst nie bemerken und die
        // Markierungs-Boxen wuerden nach einem Zoom an der alten Position stehen bleiben.
        this.state = useState({ error: false, loading: true, renderTick: 0 });
        this.pdfDoc = null;
        this.renderTask = null;
        this._loadedUrl = null;
        this._renderId = 0;
        // Skalierungsfaktor (gerenderte CSS-Pixel je PDF-Punkt) der ZULETZT gerenderten Seite -
        // vom Template ueber boxStyle() gelesen, um die Markierungs-Boxen exakt uebereinstimmend
        // mit dem Canvas zu positionieren. baseScale ist die reine Fit-Breite-Skalierung (Zoom
        // 100%), zoomFactor der Nutzer-Multiplikator darauf (bleibt beim Seitenwechsel erhalten -
        // wer einmal reingezoomt hat, will das ueblicherweise nicht pro Seite neu tun).
        this.scale = 1;
        this.baseScale = 1;
        this.zoomFactor = 1;

        onWillStart(async () => {
            await loadJS(PDFJS_BUILD_URL);
        });
        // onWillUpdateProps statt eines reaktiven useEffect: Canvas-Rendering ist inherent
        // imperativ (pdfjs zeichnet direkt auf das <canvas>-Element, das owl nicht selbst
        // ableiten kann) - Owl wartet mit dem Anwenden der neuen Props, bis das hier
        // zurueckgegebene Promise aufgeloest ist, das Canvas zeigt also nie kurz die alte Seite
        // mit bereits neuen Ueberlagerungs-Boxen.
        onMounted(() => this._sync(this.props));
        onWillUpdateProps((nextProps) => this._sync(nextProps));
        onWillUnmount(() => {
            this.renderTask?.cancel();
            this.pdfDoc?.destroy();
        });
    }

    async _sync(props) {
        if (this._loadedUrl !== props.downloadUrl) {
            await this._loadDocument(props);
        }
        await this._renderPage(props);
    }

    async _loadDocument(props) {
        this.state.loading = true;
        this.state.error = false;
        try {
            window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER_URL;
            this.pdfDoc?.destroy();
            this.pdfDoc = await window.pdfjsLib.getDocument(props.downloadUrl).promise;
            this._loadedUrl = props.downloadUrl;
            this.zoomFactor = 1;
            props.onPageCountKnown?.(this.pdfDoc.numPages);
        } catch {
            this.state.error = true;
        }
    }

    async _renderPage(props) {
        if (!this.pdfDoc || this.state.error) {
            return;
        }
        const myRenderId = ++this._renderId;
        try {
            const pageNum = Math.min(Math.max(1, props.pageNum), this.pdfDoc.numPages);
            const page = await this.pdfDoc.getPage(pageNum);
            if (myRenderId !== this._renderId) {
                return; // Zwischenzeitlich schon der naechste Seitenwechsel angefordert.
            }
            const canvas = this.canvasRef.el;
            const containerWidth = this.containerRef.el?.clientWidth || 600;
            const baseViewport = page.getViewport({ scale: 1 });
            this.baseScale = containerWidth / baseViewport.width;
            this.scale = this.baseScale * this.zoomFactor;
            const viewport = page.getViewport({ scale: this.scale });
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            this.renderTask?.cancel();
            this.renderTask = page.render({ canvasContext: canvas.getContext("2d"), viewport });
            await this.renderTask.promise;
            this.state.loading = false;
            this.state.renderTick++;
        } catch (e) {
            if (e?.name !== "RenderingCancelledException") {
                this.state.error = true;
            }
        }
    }

    // Scroll-to-Zoom mit dem Mauszeiger als Fixpunkt (Nutzerwunsch 2026-09-19): der PDF-Punkt
    // unter dem Cursor bleibt waehrend des Zoomens exakt an derselben Bildschirmposition stehen -
    // dafuer wird die Cursorposition VOR dem Reskalieren in PDF-Koordinaten umgerechnet und
    // danach der Scroll-Offset des Containers so gesetzt, dass genau dieser Punkt wieder unter
    // dem Cursor landet. e.preventDefault() verhindert, dass der Browser stattdessen die Seite
    // scrollt - diese Komponente behandelt Mausrad-Gesten grundsaetzlich als Zoom, nicht als
    // Scrollen (wie in gaengigen Karten-/PDF-Viewern), Verschieben bleibt per Scrollbar/Drag
    // moeglich.
    onWheel(ev) {
        if (!this.pdfDoc || !this.scale) {
            return;
        }
        ev.preventDefault();
        const container = this.containerRef.el;
        const rect = container.getBoundingClientRect();
        const cursorX = ev.clientX - rect.left + container.scrollLeft;
        const cursorY = ev.clientY - rect.top + container.scrollTop;
        const pdfX = cursorX / this.scale;
        const pdfY = cursorY / this.scale;

        const factor = Math.exp(-ev.deltaY * ZOOM_INTENSITY);
        const newZoomFactor = Math.min(Math.max(this.zoomFactor * factor, MIN_ZOOM), MAX_ZOOM);
        if (newZoomFactor === this.zoomFactor) {
            return;
        }
        this.zoomFactor = newZoomFactor;

        this._renderPage(this.props).then(() => {
            const offsetX = ev.clientX - rect.left;
            const offsetY = ev.clientY - rect.top;
            container.scrollLeft = pdfX * this.scale - offsetX;
            container.scrollTop = pdfY * this.scale - offsetY;
        });
    }

    // Doppelklick setzt auf Fit-Breite zurueck - ueblicher Begleiter zu Scroll-to-Zoom, sonst
    // gibt es ausser muehsamem Zurueckscrollen keinen schnellen Weg zur Ausgangsansicht.
    onDblClick() {
        if (this.zoomFactor === 1) {
            return;
        }
        this.zoomFactor = 1;
        this._renderPage(this.props);
    }

    get pageBoxes() {
        // Owls Reaktivitaet trackt nur tatsaechlich GELESENE state-Eigenschaften - renderTick
        // wird hier nur beruehrt, damit ein Zoom (siehe _renderPage()) ueberhaupt ein Neu-Rendern
        // dieser Getter-Ergebnisse (und damit boxStyle() mit dem neuen scale) auslöst, obwohl der
        // Zaehlerwert selbst nirgends inhaltlich gebraucht wird.
        void this.state.renderTick;
        return this.props.boxes.filter((b) => b.page === this.props.pageNum);
    }

    boxStyle(box) {
        const s = this.scale;
        return `left:${box.x0 * s}px; top:${box.y0 * s}px; width:${(box.x1 - box.x0) * s}px; height:${(box.y1 - box.y0) * s}px;`;
    }

    isActive(box) {
        return this.props.activeKey !== false && this.props.activeKey === box.key;
    }
}
