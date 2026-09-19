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
        this.state = useState({ error: false, loading: true });
        this.pdfDoc = null;
        this.renderTask = null;
        this._loadedUrl = null;
        this._renderId = 0;
        // Skalierungsfaktor (gerenderte CSS-Pixel je PDF-Punkt) der ZULETZT gerenderten Seite -
        // vom Template ueber boxStyle() gelesen, um die Markierungs-Boxen exakt uebereinstimmend
        // mit dem Canvas zu positionieren.
        this.scale = 1;

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
            this.scale = containerWidth / baseViewport.width;
            const viewport = page.getViewport({ scale: this.scale });
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            this.renderTask?.cancel();
            this.renderTask = page.render({ canvasContext: canvas.getContext("2d"), viewport });
            await this.renderTask.promise;
            this.state.loading = false;
        } catch (e) {
            if (e?.name !== "RenderingCancelledException") {
                this.state.error = true;
            }
        }
    }

    get pageBoxes() {
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
