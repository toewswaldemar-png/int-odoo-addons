/** @odoo-module **/

// Datei-Explorer-Klickverhalten (Einzelklick = nur auswaehlen, Doppelklick = oeffnen/
// navigieren) statt Odoos Standard (Einzelklick oeffnet immer, ausser eine Checkbox ist
// bereits aktiv - siehe onCellClicked in web/static/src/views/list/list_renderer.js).
// Nutzerwunsch 2026-09-11, bewusste Abweichung vom Odoo-Standard (der Rest von Odoo bleibt
// unveraendert, siehe resModel-Scope unten).
//
// MouseEvent.detail (1 = Einzelklick, 2 = Doppelklick, 0 = programmatisch/Tastatur ausgeloest
// z.B. per Enter) unterscheidet beides ueber denselben t-on-click-Handler, den Odoo bereits
// auf der Datenzelle verdrahtet hat - keine eigene dblclick-Verdrahtung, kein XML-Template-
// Erben noetig. detail===0 faellt bewusst auf das Original-Verhalten (oeffnen) zurueck, sonst
// waere die Liste per Tastatur/Screenreader nicht mehr bedienbar (dort gibt es kein
// Doppelklick-Konzept).
//
// Scoped auf this.props.list.resModel, exakt dasselbe Muster wie search_model_patch.js fuer
// SearchModel.prototype._getCategoryDomain - jede andere Odoo-Liste im System (Kanban-Klicks
// sind ohnehin ein anderer Code-Pfad) bleibt unangetastet.
import { onMounted, onWillUnmount } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        if (this.props.list.resModel !== "int_filemanager.file") {
            return;
        }
        // Klick ausserhalb der Liste (leerer Platz unterhalb der Zeilen, Seitenleiste, Navbar
        // oben, aber auch Suchleiste/Pager/"Neu"-Button im Control-Panel) deselektiert alles -
        // Nutzerwunsch, Datei-Explorer-Semantik. Bewusst NICHT deselektiert: Klicks auf eine
        // Datenzeile selbst (eigene Logik in onCellClicked unten), auf .o_selection_container
        // (umfasst sowohl das "N ausgewaehlt"-Badge/o_selection_box ALS AUCH den separaten
        // "Aktionen"-Dropdown-Button/o_cp_action_menus daneben - live per DOM-Chain verifiziert,
        // der Button liegt NICHT innerhalb von o_selection_box selbst; ein zu enger Selektor
        // deselektierte die Auswahl schon beim Klick auf "Aktionen", bevor die Aktion greifen
        // konnte) und auf offene Dropdowns/Dialoge (Aktionen-Menuepunkte werden teils
        // ausserhalb des Control-Panels in den body portiert).
        const onDocumentClick = (ev) => {
            if (!this.props.list.selection.length) {
                return;
            }
            if (
                ev.target.closest("tr.o_data_row") ||
                ev.target.closest(".o_selection_container") ||
                ev.target.closest(".dropdown-menu, .o-dropdown--menu") ||
                ev.target.closest(".modal, .o_dialog")
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

        // Rubberband-Auswahl (Ziehen ueber leeren Platz spannt ein Auswahlrechteck auf,
        // markiert alle geschnittenen Zeilen) - Nutzerwunsch, Datei-Explorer-Semantik.
        // Zeilen-Positionen werden einmal bei Drag-Start eingesammelt (this.tableRef.el, siehe
        // list_renderer.js: this.tableRef = useRef("table")), nicht bei jedem mousemove neu
        // vermessen - bei vielen Dateien waere wiederholtes getBoundingClientRect() pro Zeile
        // und Mausbewegung spuerbar langsam. this.props.list.records und die gerenderten
        // tr.o_data_row-Zeilen haben dieselbe Reihenfolge (kein Grouping in dieser Ansicht),
        // deshalb per Index gezippt statt ueber ein DOM-Attribut aufgeloest.
        const onMouseDown = (ev) => {
            if (ev.button !== 0 || !this.canSelectRecord) {
                return;
            }
            // Start auf einer Datenzeile bleibt dem bestehenden Drag&Drop-Verschieben
            // vorbehalten (eigener Event-Pfad, draggable="true"/dragstart, siehe
            // filemanager_controller_mixin.js) - Rubberband startet nur auf echt leerem Platz.
            // Ebenso ausgenommen: Checkbox-Spalte, Tabellenkopf (Sortier-Klicks), Control-Panel,
            // SearchPanel-Seitenleiste, und jedes offene Modal/Dialog (live beobachtet: ohne
            // diese Ausnahme loeste ein Rubberband-Versuch INNERHALB eines Dialogs - z.B. dem
            // Odoo-Fehler-Modal selbst - einen echten Absturz aus: der Browser startet bei
            // Ziehen ueber Text einen nativen Text-Selektions-Drag, der global ein "dragstart"-
            // Ereignis feuert, das wiederum onWindowDragStartRecord() in
            // filemanager_controller_mixin.js trifft - dort wird ev.target als Element
            // angenommen (ev.target.closest("[data-id]")), bei einem Text-Selektions-Drag ist
            // ev.target aber oft ein reiner Textknoten ohne .closest -> TypeError, Absturz der
            // ganzen Ansicht. document.querySelector() statt closest(), da document.activeElement
            // bei einem Dialog nicht zuverlaessig innerhalb des Modal-DOM liegt.
            if (
                ev.target.closest("tr.o_data_row") ||
                ev.target.closest(".o_list_record_selector") ||
                ev.target.closest("thead") ||
                ev.target.closest(".o_control_panel") ||
                ev.target.closest(".o_search_panel") ||
                ev.target.closest(".modal, .o_dialog") ||
                document.querySelector(".modal.show, .o_dialog")
            ) {
                return;
            }
            if (!this.tableRef.el) {
                return;
            }
            const records = this.props.list.records;
            const rowEls = [...this.tableRef.el.querySelectorAll("tr.o_data_row")];
            if (rowEls.length !== records.length) {
                return;
            }
            // preventDefault auf dem mousedown selbst (nicht erst im mousemove, siehe unten):
            // verhindert, dass der Browser ueberhaupt erst eine native Text-Selektion/einen
            // nativen Drag startet, falls der Mausdown zufaellig auf/neben selektierbarem Text
            // in der Leerflaeche liegt - derselbe Fehlerklasse wie oben, nur vorbeugend statt
            // nur reaktiv per Modal-Ausschluss.
            ev.preventDefault();
            const rowRects = rowEls.map((el, i) => ({ record: records[i], rect: el.getBoundingClientRect() }));
            const additive = ev.ctrlKey || ev.metaKey;
            const initiallySelected = additive ? new Set(records.filter((r) => r.selected)) : new Set();
            const startX = ev.clientX;
            const startY = ev.clientY;
            let dragging = false;
            let overlay = null;

            const onMouseMove = (moveEv) => {
                const dx = moveEv.clientX - startX;
                const dy = moveEv.clientY - startY;
                if (!dragging) {
                    // Schwelle von 4px: ein einfacher Klick ohne Bewegung soll nicht als
                    // (Mikro-)Rubberband zaehlen, sondern normal ueber onCellClicked laufen.
                    if (Math.hypot(dx, dy) < 4) {
                        return;
                    }
                    dragging = true;
                    overlay = document.createElement("div");
                    overlay.className = "o_int_filemanager_rubberband";
                    document.body.appendChild(overlay);
                }
                moveEv.preventDefault();
                const x1 = Math.min(startX, moveEv.clientX);
                const x2 = Math.max(startX, moveEv.clientX);
                const y1 = Math.min(startY, moveEv.clientY);
                const y2 = Math.max(startY, moveEv.clientY);
                overlay.style.left = x1 + "px";
                overlay.style.top = y1 + "px";
                overlay.style.width = x2 - x1 + "px";
                overlay.style.height = y2 - y1 + "px";
                for (const { record, rect } of rowRects) {
                    const intersects = rect.left < x2 && rect.right > x1 && rect.top < y2 && rect.bottom > y1;
                    const shouldSelect = intersects || initiallySelected.has(record);
                    if (record.selected !== shouldSelect) {
                        record.toggleSelection(shouldSelect);
                    }
                }
                // record.toggleSelection() aendert record.selected korrekt (per Debug-Log
                // bestaetigt), aber Owl rendert die Checkboxen/das "N ausgewaehlt"-Badge nicht
                // automatisch neu - anders als bei einem normalen Odoo-eigenen Event-Handler
                // (t-on-click), wo Owls Scheduler den Flush ohnehin an den Klick-Callback
                // haengt, laeuft dieser Handler hier ueber einen rohen document-Listener,
                // ausserhalb von Owls eigenem Render-Zyklus. this.render() stoesst den Flush
                // manuell an.
                this.render();
            };
            const onMouseUp = () => {
                document.removeEventListener("mousemove", onMouseMove);
                document.removeEventListener("mouseup", onMouseUp);
                overlay?.remove();
            };
            document.addEventListener("mousemove", onMouseMove);
            document.addEventListener("mouseup", onMouseUp);
        };
        onMounted(() => document.addEventListener("mousedown", onMouseDown));
        onWillUnmount(() => document.removeEventListener("mousedown", onMouseDown));
    },
    async onCellClicked(record, column, ev, newWindow) {
        if (this.props.list.resModel !== "int_filemanager.file" || ev.detail === 0) {
            return super.onCellClicked(record, column, ev, newWindow);
        }
        if (ev.detail >= 2) {
            // NICHT super.onCellClicked() aufrufen: das Original prueft selbst wieder
            // hasSelection (durch den Einzelklick-Handler unten kurz zuvor haeufig bereits
            // aktiv) und wuerde dann erneut nur toggleRecordSelection() ausloesen statt zu
            // oeffnen - live so beobachtet (Doppelklick schaltete die Auswahl zweimal um,
            // navigierte nie). Direkt openRecord() aufrufen umgeht diesen Konflikt, exakt der
            // Original-Zweig aus list_renderer.js's eigenem onCellClicked.
            if (!this.props.archInfo.noOpen) {
                this.props.openRecord(record, { newWindow });
            }
            return;
        }
        if (!this.canSelectRecord) {
            return;
        }
        // Datei-Explorer-Semantik: einfacher Klick (ohne Modifier) ersetzt die Auswahl durch
        // genau diese eine Zeile, statt additiv umzuschalten - live so gemeldet (mehrere Klicks
        // nacheinander sammelten Zeilen an, statt immer nur eine auszuwaehlen). Ctrl/Cmd- bzw.
        // Shift-Klick bleiben additiv/Bereichsauswahl (this.shiftKeyMode wird von der Basisklasse
        // bereits per keydown/keyup gepflegt, siehe list_renderer.js) - toggleRecordSelection()
        // deckt beide Faelle unveraendert ab, nur der Plain-Click-Fall ist hier neu.
        if (ev.ctrlKey || ev.metaKey || this.shiftKeyMode) {
            this.toggleRecordSelection(record);
            return;
        }
        for (const other of this.props.list.records) {
            if (other !== record && other.selected) {
                other.toggleSelection(false);
            }
        }
        record.toggleSelection(true);
        this.lastCheckedRecord = record;
    },
});
