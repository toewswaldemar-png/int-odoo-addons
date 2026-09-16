/** @odoo-module **/

// Sammel-Datei fuer alle Patches an nativen Odoo-Core-Komponenten, die ausschliesslich fuer
// unsere eigene Mobil-Einbettung (mobile_test/) noetig sind - zusammengelegt statt pro
// Komponente eine eigene Datei (Nutzerwunsch 2026-09-16, war vorher zwei separate Dateien:
// search_panel_mobile_tree_patch.js und search_bar_mobile_dropdown_patch.js).

// -----------------------------------------------------------------------
// SearchPanel: Mobil-Ordnerbaum-Bottom-Sheet
// -----------------------------------------------------------------------
// JS-Haelfte zu search_panel_patch.xml (dort die Template-Bedingung, hier der eigentliche
// Reaktivitaets-Fix). Live per Debug-Log verifiziert (2026-09-16, RPC-Log auf jedem
// SearchPanel-Render): env.mobileTreeState kommt in SearchPanel.env korrekt an, aber
// SearchPanel selbst rendert nach onToggleMobileTree() nie neu - der Backdrop/die CSS-Klasse
// (beide im ListController-eigenen Template) aktualisieren sich zwar sofort, SearchPanel
// bleibt aber auf ihrem allerersten Render (Small-Chip-Form) stehen.
//
// Grund: this.mobileTreeState = useState({open:false}) in filemanager_controller_mixin.js
// bindet Owls Reaktivitaets-Callback an die Komponente, die useState() aufgerufen hat (den
// ListController). Eine andere Komponente, die dasselbe Objekt nur ueber env liest
// (env.mobileTreeState.open in search_panel_patch.xml), abonniert sich dadurch NICHT
// automatisch selbst - Owl haengt den Re-Render-Callback an die *erzeugende* useState-Stelle,
// nicht an jede spaetere Lese-Stelle. Dasselbe Muster wie bei einem Service: eine Komponente,
// die auf dessen Aenderungen reagieren soll, muss ihn selbst nochmal per useState()
// "umwickeln" (siehe z.B. useService()-Konsumenten in Odoo-Core, die genauso verfahren).
//
// this.intFilemanagerMobileTreeState statt env.mobileTreeState direkt umbenannt (siehe
// search_panel_patch.xml) - dieselbe zugrunde liegende Objektinstanz, nur mit einer fuer
// SearchPanel selbst gebundenen Subscription.
//
// Zweiter, unabhaengiger Bug (Nutzerreport 2026-09-16, Screenshot: Breadcrumb zeigt "Alle
// Ordner / Produktiv-HM-Datenbank / EDV-Datenbank", der geoeffnete Baum zeigt aber ALLE
// Wurzelordner eingeklappt): SearchPanels eigener useBus(env.searchModel, "update", ...)-
// Handler (search_panel.js) haelt nur state.active synchron, NIE state.expanded - die
// Ast-Aufklappzustaende werden ausschliesslich einmalig in onWillStart() per
// expandDefaultValue() berechnet. Da unser Sheet an der Wurzel gemountet wird (bevor
// irgendwohin navigiert wurde), bleibt der Baum fuer die gesamte Sitzung auf diesem
// Erststand eingefroren, unabhaengig davon, wie tief man per Zeilenklick/Breadcrumb
// navigiert. Fix: dieselbe native expandDefaultValue() erneut aufrufen, sobald das Sheet
// geoeffnet wird - state.active ist zu dem Zeitpunkt (dank des oben beschriebenen
// useBus-Handlers) bereits korrekt, es fehlt nur der Ast-Aufklapp-Abgleich dazu.
import { useEffect, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { hasTouch } from "@web/core/browser/feature_detection";
import { SearchPanel } from "@web/search/search_panel/search_panel";
import { SearchBar } from "@web/search/search_bar/search_bar";

patch(SearchPanel.prototype, {
    setup() {
        super.setup();
        this.intFilemanagerMobileTreeState = this.env.mobileTreeState
            ? useState(this.env.mobileTreeState)
            : null;
        if (this.intFilemanagerMobileTreeState) {
            useEffect(
                (open) => {
                    if (!open) {
                        return;
                    }
                    this.expandDefaultValue();
                    // Aktuell ausgewaehlten Ordner beim Oeffnen mittig in den sichtbaren Bereich
                    // scrollen statt ihn (wie zuvor) ganz unten/knapp ausserhalb stehen zu lassen
                    // (Nutzerwunsch 2026-09-16, Screenshot: "Clients" klebte am unteren Rand).
                    // this.root ist dieselbe native t-ref="root"-Referenz, die SearchPanel
                    // bereits selbst fuer scrollTop/min-width nutzt (siehe super.setup()).
                    //
                    // ZWEI verschachtelte requestAnimationFrame statt einem (Nutzerreport
                    // 2026-09-16: zentriert bei flachen, aber nicht bei tieferen Unterordnern) -
                    // ein einzelnes rAF reicht nicht zuverlaessig: expandDefaultValue() schaltet
                    // im selben Zug auch display:none -> flex um (CSS-Klasse
                    // o_int_filemanager_mobile_tree_open), und je hoeher der neu aufgeklappte Baum
                    // (mehr Ebenen = mehr Hoehe), desto eher faellt der scrollIntoView-Aufruf noch
                    // in einen Frame, in dem der Browser das Layout dafuer noch nicht fertig
                    // berechnet hat - bei kurzen Baeumen fiel das bisher nicht auf. Das zweite rAF
                    // garantiert eine bereits abgeschlossene Layout-Runde, bevor gescrollt wird -
                    // Standardmuster fuer "nach einem Sichtbarkeitswechsel zuverlaessig Layout-
                    // Werte lesen/nutzen".
                    requestAnimationFrame(() => {
                        requestAnimationFrame(() => {
                            const activeEl = this.root.el?.querySelector(
                                ".o_search_panel_category_value > header.active"
                            );
                            activeEl?.scrollIntoView({ block: "center", behavior: "instant" });
                        });
                    });
                },
                () => [this.intFilemanagerMobileTreeState.open]
            );
        }
    },
});

// -----------------------------------------------------------------------
// SearchBar: Vorschlags-Dropdown auch auf Touch direkt beim Antippen oeffnen
// -----------------------------------------------------------------------
// Nutzerwunsch 2026-09-16: auf Mobil soll ein Klick ins leere Suchfeld direkt das
// Vorschlags-Dropdown oeffnen, genau wie am Desktop - nicht nur die Tastatur zum Eintippen.
// Odoos eigenes SearchBar.onSearchClick() (search_bar.js) unterdrueckt das Oeffnen bewusst auf
// Touch-Geraeten (Check auf hasTouch(), NICHT env.isSmall - siehe dortiger Code), weil ein
// Dropdown-beim-blossen-Antippen auf einem Handy normalerweise schlechte UX waere (man muesste
// erst wegtippen, bevor man wirklich tippen kann). Fuer unsere eigene Mobil-Einbettung
// (mobile_test/) ist genau dieses Verhalten aber explizit gewuenscht.
//
// super.onSearchClick() zuerst - deckt den Nicht-Touch-Fall (Desktop-Emulation im Browser
// z.B.) unveraendert ab, danach ergaenzen wir denselben Oeffnen-Ablauf fuer den Touch-Fall,
// aber NUR wenn der Kontext-Flag int_filemanager_mobile_header gesetzt ist (globalContext,
// siehe filemanager_controller_mixin.js/native_list_view.js fuer dasselbe Muster an anderer
// Stelle) - jede andere SearchBar im System (jede normale Odoo-Liste auf einem Tablet/Handy)
// bleibt beim nativen, bewusst Touch-unterdrueckten Verhalten.
patch(SearchBar.prototype, {
    onSearchClick() {
        super.onSearchClick();
        if (hasTouch() && this.env.searchModel.globalContext.int_filemanager_mobile_header) {
            if (!this.inputRef.el.value.length) {
                this.searchBarDropdownState.open();
            } else {
                this.inputDropdownState.open();
            }
        }
    },
});
