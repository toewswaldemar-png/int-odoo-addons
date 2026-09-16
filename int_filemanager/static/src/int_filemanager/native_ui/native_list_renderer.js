/** @odoo-module **/

// Datei-Explorer-Klickverhalten (Einzelklick = nur auswaehlen, Doppelklick = oeffnen/
// navigieren) statt Odoos Standard (Einzelklick oeffnet immer, ausser eine Checkbox ist
// bereits aktiv - siehe onCellClicked in web/static/src/views/list/list_renderer.js).
// Nutzerwunsch 2026-09-11, bewusste Abweichung vom Odoo-Standard.
//
// Echte Unterklasse statt patch(ListRenderer.prototype, ...) - list_view.js registriert
// "Renderer" als genauso austauschbaren Schluessel wie "Controller" (siehe
// native_list_view.js: Controller: IntFilemanagerListController), live gegen Odoos eigenes
// web/static/src/views/list/list_view.js verifiziert. Kapselung kommt damit automatisch aus
// der Registrierung (registry.category("views").add("int_filemanager_list", {...,
// Renderer: IntFilemanagerListRenderer})) - jede andere Odoo-Liste im System bleibt
// unangetastet, ohne dass diese Klasse selbst noch pruefen muesste, ob sie gerade fuer
// int_filemanager.file laeuft (der fruehere patch()-Ansatz brauchte dafuer manuelle
// resModel-Checks an jeder Methode).
//
// MouseEvent.detail (1 = Einzelklick, 2 = Doppelklick, 0 = programmatisch/Tastatur ausgeloest
// z.B. per Enter) unterscheidet beides ueber denselben t-on-click-Handler, den Odoo bereits
// auf der Datenzelle verdrahtet hat - keine eigene dblclick-Verdrahtung, kein XML-Template-
// Erben noetig. detail===0 faellt bewusst auf das Original-Verhalten (oeffnen) zurueck, sonst
// waere die Liste per Tastatur/Screenreader nicht mehr bedienbar (dort gibt es kein
// Doppelklick-Konzept).
import { onMounted, onWillUnmount } from "@odoo/owl";
import { ListRenderer } from "@web/views/list/list_renderer";

export class IntFilemanagerListRenderer extends ListRenderer {
    setup() {
        super.setup();
        // Wird von der Rubberband-Logik unten (nach dem Zeilenausschluss) auf true gesetzt,
        // sobald ein echter Zieh-Vorgang (nicht nur ein Klick) endet - der Browser feuert nach
        // mouseup naemlich trotzdem noch ein normales "click"-Ereignis an der Loslass-Position,
        // die bei einem Rubberband fast immer auf leerem Platz liegt. Ohne diese Sperre hat
        // genau dieser nachgelagerte Klick die gerade gezogene Auswahl sofort wieder aufgehoben
        // (live so beobachtet: Rechteck verschwindet beim Loslassen, Auswahl leer).
        let rubberbandJustEnded = false;

        // Klick ausserhalb der Liste (leerer Platz unterhalb der Zeilen, Seitenleiste, Navbar
        // oben, aber auch Suchleiste/Pager/"Neu"-Button im Control-Panel) deselektiert alles -
        // Nutzerwunsch, Datei-Explorer-Semantik. Bewusst NICHT deselektiert: Klicks auf eine
        // Datenzeile selbst (eigene Logik in onCellClicked unten), auf .o_selection_container
        // (umfasst sowohl das "N ausgewaehlt"-Badge/o_selection_box ALS AUCH den separaten
        // "Aktionen"-Dropdown-Button/o_cp_action_menus daneben - live per DOM-Chain verifiziert,
        // der Button liegt NICHT innerhalb von o_selection_box selbst; ein zu enger Selektor
        // deselektierte die Auswahl schon beim Klick auf "Aktionen", bevor die Aktion greifen
        // konnte), auf offene Dropdowns/Dialoge (Aktionen-Menuepunkte werden teils ausserhalb
        // des Control-Panels in den body portiert), auf das Chatter-Seitenpanel (chatterRecord
        // liest model.root.selection[0] - ohne diese Ausnahme riss ein Klick auf einen
        // Chatter-Button/das Nachrichtenfeld die Auswahl weg, WAEHREND der Klick noch lief, und
        // der Chatter brach mitten im eigenen Klick ab, Nutzerreport 2026-09-11) und auf den
        // Tabellenkopf (thead) - dort
        // sitzt Odoos native "Alle auswaehlen"-Kopfzeilen-Checkbox (list_renderer.xml:
        // t-on-click.stop="toggleSelection"). Diese Sperre laeuft in der Capture-Phase VOR
        // Odoos eigenem Klick-Handler: ohne die thead-Ausnahme deselektierte sie zuerst alles,
        // und Odoos toggleSelection() sah danach immer "0 ausgewaehlt" -> waehlte alles wieder
        // aus, statt abzuwaehlen - live so beobachtet ("Auswaehlen geht, Abwaehlen nicht").
        const onDocumentClick = (ev) => {
            // Long-Press-Nachlauf-Klick (siehe Long-Press-Handler weiter unten in setup()) muss
            // hier auf echter document-Capture-Ebene abgefangen werden, VOR Odoos eigenem
            // zeilengebundenen "t-on-click.capture" (list_renderer.xml, onClickCapture()) - live
            // am Quellcode nachvollzogen: dieser sitzt direkt auf <tr>, ein reiner
            // document.addEventListener(..., true) feuert aber immer zuerst (echte Capture-Phase
            // laeuft von document zum Ziel, unabhaengig von Registrierungsreihenfolge). Ohne
            // stopPropagation() hier wuerde Odoos eigener Handler denselben Nachlauf-Klick sehen
            // (list.selection.length ist zu diesem Zeitpunkt schon 1, durch den Long-Press
            // synchron gesetzt) und die gerade erst ausgewaehlte Zeile prompt wieder abwaehlen -
            // ein reiner Rueckgabe-Guard in onCellClicked() (bubble-Phase, tiefer im Baum) haette
            // dagegen keine Chance, weil Odoos Capture-Handler die Weiterleitung dorthin laengst
            // gestoppt haette.
            if (this._longPressSuppressClick) {
                this._longPressSuppressClick = false;
                ev.stopPropagation();
                ev.preventDefault();
                return;
            }
            if (rubberbandJustEnded) {
                rubberbandJustEnded = false;
                return;
            }
            if (!this.props.list.selection.length) {
                return;
            }
            if (
                ev.target.closest("tr.o_data_row") ||
                ev.target.closest(".o_selection_container") ||
                ev.target.closest(".dropdown-menu, .o-dropdown--menu") ||
                ev.target.closest(".modal, .o_dialog") ||
                ev.target.closest(".o_int_filemanager_chatter_panel") ||
                ev.target.closest("thead")
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
                // Mobil-Header (native_list_view.xml: SearchBar + Home/Baum-Toggle +
                // Breadcrumb-Zeile) ist KEIN .o_control_panel - der wird in der
                // Client-Action-Einbettung (mobile_test/) bewusst per
                // display={controlPanel:false} abgeschaltet und durch diesen eigenen Header
                // ersetzt. Ohne diesen Ausschluss faellt ein Antippen des Suchfelds durch alle
                // obigen Ausnahmen durch, preventDefault() unten (siehe Kommentar dort)
                // unterdrueckt dabei denselben normalen Browser-Fokus, den es beim
                // F2-Rename-Input schon einmal unterdrueckt hat - Nutzerreport 2026-09-16:
                // "Suchfeld reagiert gar nicht, keine Tastatur".
                ev.target.closest(".o_int_filemanager_mobile_header") ||
                ev.target.closest(".modal, .o_dialog") ||
                ev.target.closest(".o_int_filemanager_chatter_panel") ||
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
            //
            // Nebenwirkung, live gefunden 2026-09-14: preventDefault() auf mousedown unterdrueckt
            // auch den normalen Browser-Blur des zuvor fokussierten Elements. War das
            // F2-Umbenennen-Input aktiv, blieb es dadurch bei einem Klick auf leere Flaeche
            // haengen (onRenameBlur in name_icon_field.js feuerte nie, kein Commit). Deshalb hier
            // manuell blur() auf ein noch aktives Rename-Input, BEVOR preventDefault greift -
            // exakt das Explorer-Verhalten "Wegklicken uebernimmt den Namen" aus dem
            // onRenameBlur-Kommentar dort.
            const activeRenameInput = document.activeElement?.classList?.contains(
                "o_int_filemanager_rename_input"
            )
                ? document.activeElement
                : null;
            activeRenameInput?.blur();
            ev.preventDefault();
            const rowRects = rowEls.map((el, i) => ({ record: records[i], rect: el.getBoundingClientRect() }));
            const additive = ev.ctrlKey || ev.metaKey;
            const initiallySelected = additive ? new Set(records.filter((r) => r.selected)) : new Set();
            const startX = ev.clientX;
            const startY = ev.clientY;
            let dragging = false;
            let overlay = null;

            // record.toggleSelection() ist asynchron (this.model.mutex.exec(), siehe
            // relational_model/record.js) - Owl rendert danach auch nicht automatisch neu
            // (dieser Handler laeuft ueber einen rohen document-Listener, ausserhalb von Owls
            // eigenem Render-Zyklus, siehe applySelection unten). Bei schnellen
            // Mausbewegungen feuern mehrere mousemove-Ereignisse, bevor die vorherige Mutation
            // durch den Mutex durch ist - ein synchrones render() direkt nach dem (nicht
            // awaited) toggleSelection() zeigte deshalb live einen veralteten Zwischenstand,
            // teils blieb am Ende nur eine einzelne Zeile ausgewaehlt statt aller geschnittenen
            // (beobachtet: zwei rasch aufeinanderfolgende mousemove-Ereignisse ueberschnitten
            // sich, das Ergebnis der ersten Mutation ging verloren). isSelecting verhindert
            // ueberlappende Durchlaeufe waehrend des Ziehens (rein visuelles Overlay bleibt
            // trotzdem bei jeder Bewegung aktuell); der finale, garantiert korrekte Durchlauf
            // passiert erst in onMouseUp per await.
            let isSelecting = false;
            let lastRect = null;
            const applySelection = async (x1, x2, y1, y2) => {
                if (isSelecting) {
                    return;
                }
                isSelecting = true;
                try {
                    const promises = [];
                    for (const { record, rect } of rowRects) {
                        const intersects = rect.left < x2 && rect.right > x1 && rect.top < y2 && rect.bottom > y1;
                        const shouldSelect = intersects || initiallySelected.has(record);
                        if (record.selected !== shouldSelect) {
                            promises.push(record.toggleSelection(shouldSelect));
                        }
                    }
                    await Promise.all(promises);
                    this.render();
                } finally {
                    isSelecting = false;
                }
            };
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
                lastRect = { x1, x2, y1, y2 };
                applySelection(x1, x2, y1, y2);
            };
            const onMouseUp = async () => {
                document.removeEventListener("mousemove", onMouseMove);
                document.removeEventListener("mouseup", onMouseUp);
                overlay?.remove();
                // Synchron VOR jedem await setzen: der Browser feuert nach mouseup so gut wie
                // sofort noch ein "click"-Ereignis (derselbe Kontext-Wechsel, keine eigene
                // Task-Warteschlange) - wuerde diese Zeile erst NACH einem await stehen, liefe
                // onDocumentClick fuer diesen Klick bereits durch, bevor rubberbandJustEnded
                // ueberhaupt auf true gesetzt ist (live als Bug beobachtet: mit await davor
                // blieb die Sperre wirkungslos, die Auswahl verschwand beim Loslassen trotzdem).
                rubberbandJustEnded = dragging;
                if (dragging) {
                    setTimeout(() => {
                        rubberbandJustEnded = false;
                    }, 300);
                }
                // Finaler, autoritativer Durchlauf (bewusst OHNE isSelecting-Guard, direkt
                // awaited) - garantiert den korrekten Endzustand, selbst wenn waehrend des
                // Ziehens Zwischenschritte uebersprungen wurden.
                if (dragging && lastRect) {
                    const { x1, x2, y1, y2 } = lastRect;
                    const promises = [];
                    for (const { record, rect } of rowRects) {
                        const intersects = rect.left < x2 && rect.right > x1 && rect.top < y2 && rect.bottom > y1;
                        const shouldSelect = intersects || initiallySelected.has(record);
                        if (record.selected !== shouldSelect) {
                            promises.push(record.toggleSelection(shouldSelect));
                        }
                    }
                    await Promise.all(promises);
                    this.render();
                }
            };
            document.addEventListener("mousemove", onMouseMove);
            document.addEventListener("mouseup", onMouseUp);
        };
        onMounted(() => document.addEventListener("mousedown", onMouseDown));
        onWillUnmount(() => document.removeEventListener("mousedown", onMouseDown));

        // Mobile: Einzel-Tap oeffnet direkt statt zu selektieren (Nutzerwunsch 2026-09-15) -
        // Doppelklick als Oeffnen-Geste ist auf Touch kein verlaessliches Standard-Gesture.
        // Auswahl fuer Mehrfachaktionen passiert stattdessen per Long-Press auf eine noch nicht
        // ausgewaehlte Zeile; ist bereits etwas ausgewaehlt, uebernimmt Odoos eigenes natives
        // Mobil-Verhalten das Umschalten weiterer Zeilen unveraendert (list_renderer.js:
        // onClickCapture()/ignoreEventInSelectionMode(), Capture-Phase VOR onCellClicked - dieser
        // Long-Press-Handler muss deshalb nur die allererste Auswahl (0 -> 1) abdecken).
        // pointerdown/-up/-move/-cancel statt touchstart/-end: deckt Touch UND Maus einheitlich
        // ab (bewusst nicht auf pointerType==="touch" beschraenkt - eine "Press and hold"-Geste
        // mit der Maus in einem schmalen/Mobile-Breite-Fenster soll ebenso funktionieren,
        // schadet auf Desktop-Breite nicht, da env.isSmall dort ohnehin false ist).
        this._longPressSuppressClick = false;
        let longPressTimer = null;
        let longPressStartX = 0;
        let longPressStartY = 0;
        const cancelLongPress = () => {
            if (longPressTimer) {
                clearTimeout(longPressTimer);
                longPressTimer = null;
            }
        };
        const onPointerDown = (ev) => {
            if (!this.env.isSmall || !this.canSelectRecord || this.props.list.selection.length) {
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
            longPressStartX = ev.clientX;
            longPressStartY = ev.clientY;
            longPressTimer = setTimeout(() => {
                longPressTimer = null;
                this._longPressSuppressClick = true;
                record.toggleSelection(true);
                this.render();
            }, 500);
        };
        const onPointerMove = (ev) => {
            if (longPressTimer && Math.hypot(ev.clientX - longPressStartX, ev.clientY - longPressStartY) > 10) {
                cancelLongPress();
            }
        };
        onMounted(() => {
            document.addEventListener("pointerdown", onPointerDown);
            document.addEventListener("pointermove", onPointerMove);
            document.addEventListener("pointerup", cancelLongPress);
            document.addEventListener("pointercancel", cancelLongPress);
        });
        onWillUnmount(() => {
            cancelLongPress();
            document.removeEventListener("pointerdown", onPointerDown);
            document.removeEventListener("pointermove", onPointerMove);
            document.removeEventListener("pointerup", cancelLongPress);
            document.removeEventListener("pointercancel", cancelLongPress);
        });
    }

    // Checkbox-Spalte zusaetzlich zum Long-Press sichtbar machen (Nutzerwunsch 2026-09-15):
    // Odoo blendet sie auf Mobile nativ per "t-if" komplett aus (echtes Nicht-Rendern, kein
    // CSS-Verstecken - list_renderer.js: "return this.props.allowSelectors && !this.env.isSmall").
    // Ein-Zeilen-Override hier reicht, alle Colspan-/Header-Berechnungen im Original lesen
    // ohnehin nur "this.hasSelectors" und passen sich automatisch an. Die Checkbox-Zelle traegt
    // ihren eigenen "t-on-click.stop"-Handler (toggleRecordSelection) direkt in list_renderer.xml
    // - kein Konflikt mit onCellClicked()/dem Long-Press unten, die auf anderen Zellen sitzen.
    get hasSelectors() {
        return this.props.allowSelectors;
    }

    async onCellClicked(record, column, ev, newWindow) {
        if (ev.detail === 0) {
            return super.onCellClicked(record, column, ev, newWindow);
        }
        // Der "click", der nach einem erfolgreichen Long-Press (siehe setup()) beim Loslassen
        // trotzdem noch feuert, soll die gerade erst gesetzte Auswahl nicht sofort wieder in
        // ein "Oeffnen" ummuenzen - derselbe Nachlauf-Klick-Kaese wie bei rubberbandJustEnded
        // oben, nur fuer Long-Press statt Rubberband.
        if (this._longPressSuppressClick) {
            this._longPressSuppressClick = false;
            return;
        }
        // Mobile, noch keine Auswahl aktiv: Einzel-Tap oeffnet/navigiert direkt, statt zu
        // selektieren (siehe Long-Press-Handler in setup()). Modifier-Klicks (Ctrl/Cmd/Shift)
        // bleiben ausgenommen - die ergeben auf einem Touch-Geraet ohnehin keinen Sinn, sind
        // aber z.B. bei einer per Maus bedienten schmalen Fensterbreite weiterhin sinnvoll.
        if (
            this.env.isSmall &&
            !this.props.list.selection.length &&
            ev.detail === 1 &&
            !ev.ctrlKey &&
            !ev.metaKey &&
            !this.shiftKeyMode
        ) {
            if (!this.props.archInfo.noOpen) {
                this.props.openRecord(record, { newWindow });
            }
            return;
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
    }
}
