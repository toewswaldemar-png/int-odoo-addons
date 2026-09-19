/** @odoo-module **/

// Geteilte Controller-Logik zwischen der nativen ListView (native_list_view.js) und der
// nativen KanbanView (native_kanban_view.js) - Navigation, Mutationen (mkdir/rename/delete/
// upload/link), Breadcrumbs, Chatter-Seitenpanel, Drag&Drop-Upload und das Aktionsmenue sind
// fuer beide View-Typen identisch, nur "wie eine Zeile/Karte geoeffnet wird" (openRecord) und
// "welche native Basisklasse erweitert wird" unterscheiden sich strukturell zwischen
// ListController und KanbanController (siehe docs/int_filemanager_native_ui.md). Als Mixin-
// Funktion statt gemeinsamer Vaterklasse umgesetzt, weil JS keine Mehrfachvererbung kennt -
// IntFilemanagerListController muss ListController erweitern, IntFilemanagerKanbanController
// KanbanController; ein Mixin (Base) => class extends Base {...} laesst beide denselben Code
// erben, unabhaengig davon, welche native Basisklasse konkret hereingereicht wird.
//
// Mutationen (mkdir/rename/delete/upload/link) rufen weiterhin dieselben authz-geprueften
// /int_filemanager/* JSON-RPC-Routen auf statt native type="object"-Buttons - Begruendung
// unveraendert siehe docs/int_filemanager_native_ui.md, Abschnitt "Sicherheitsrelevanter
// Stolperstein".
import { onMounted, onPatched, onWillUnmount, useExternalListener, useRef, useState, useSubEnv } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { browser } from "@web/core/browser/browser";
import { useBus, useChildRef, useService } from "@web/core/utils/hooks";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { useNavigation } from "@web/core/navigation/navigation";
import { usePopover } from "@web/core/popover/popover_hook";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { IntTextInputDialog } from "../shared/text_input_dialog";
import { IntLinkRecordDialog } from "../shared/link_record_dialog";
import { IntTextEditorDialog } from "./text_editor_dialog";
import { IntDocumentReviewDialog } from "./document_review_dialog";
import { IntZipContentsDialog } from "./zip_contents_dialog";
import { IntFilemanagerContextMenu } from "./context_menu";
import { domPathToPath } from "./folder_tree";

// Video ist nativ im FileViewer verdrahtet (file_viewer.js/.xml: state.file.isVideo -> echtes
// <video controls>) - hier nur an dessen bereits vorhandene Faehigkeit angeschlossen, nichts
// Neues gebaut. Auf die vier Formate beschraenkt, die Browser ohne Zusatz-Codec nativ abspielen
// (mov u.ae. bewusst weggelassen - haeufig kein nativer Chrome/Firefox-Support, wuerde nur einen
// leeren Player zeigen).
const VIDEO_EXTENSIONS = new Set(["mp4", "webm", "ogv"]);
const VIDEO_MIME_TYPES = { mp4: "video/mp4", webm: "video/webm", ogv: "video/ogg" };

// Persistenz der per Drag eingestellten Ordnerbaum-Breite (Nutzerwunsch 2026-09-18) - gleiches
// Muster wie Discuss' eigene DISCUSS_SIDEBAR_COMPACT_LS (mail/core/public_web/discuss_sidebar.js)
// und die Spaltenreihenfolge in int_generic: ein einzelner localStorage-Wert, kein neues
// DB-Modell noetig fuer eine reine UI-Praeferenz ohne Serverbezug.
const TREE_WIDTH_LS = "int_filemanager.treeWidth";
const TREE_WIDTH_DEFAULT = 280;

// Audio laeuft NICHT ueber den FileViewer (anders als Video, das dort nativ verdrahtet ist),
// sondern ueber den eigenen Systray-Player (systray/audio_player_service.js) - Nutzerentscheidung
// 2026-09-18, "voller ueberlebt-Navigation-Effekt wie Cloudreve", den ein Modal-Dialog
// strukturell nicht bieten kann (schliesst sich beim Verlassen der View). Bewusst ohne "wma" -
// mediameta.py unterstuetzt es serverseitig fuer Metadaten, aber kein Browser spielt das
// proprietaere Format nativ ab (gleiche Begruendung wie das fehlende "mov" bei Video oben).
const AUDIO_EXTENSIONS = new Set(["mp3", "wav", "flac", "ogg", "m4a", "aac"]);
const AUDIO_MIME_TYPES = {
    mp3: "audio/mpeg", wav: "audio/wav", flac: "audio/flac",
    ogg: "audio/ogg", m4a: "audio/mp4", aac: "audio/aac",
};

// Reine Textformate oeffnen direkt den Editor (IntTextEditorDialog) statt der readonly
// FileViewer-Vorschau - deshalb bewusst NICHT Teil von PREVIEWABLE_EXTENSIONS (das wuerde ueber
// onPreview() die alte iframe-Vorschau ausloesen, die der Editor ersetzt).
const TEXT_EDIT_EXTENSIONS = new Set(["txt", "csv", "log", "md", "json"]);

// AUDIO_EXTENSIONS bewusst NICHT Teil davon (anders als frueher, siehe Kommentar oben) - Audio
// wird in openRecord() VOR dieser Pruefung abgefangen, isPreviewable()/onPreview() betreffen nur
// noch den echten FileViewer.
const PREVIEWABLE_EXTENSIONS = new Set([
    "pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", ...VIDEO_EXTENSIONS,
]);

// Ported from legacy_ui/filemanager_action.js's EDITABLE_EXTENSIONS - narrowed to actual
// Office formats only. txt/csv are deliberately left out here (unlike the legacy set):
// TEXT_EDIT_EXTENSIONS above already opens them in the native CodeEditor, a better fit than
// round-tripping through ONLYOFFICE for plain text - no regression, an improvement already
// present in this UI that the port keeps instead of reintroducing the old behaviour.
const OFFICE_EDIT_EXTENSIONS = new Set([
    "doc", "docx", "odt", "rtf",
    "xls", "xlsx", "ods",
    "ppt", "pptx", "odp",
]);

// Archivinhalt ansehen (Nutzerwunsch 2026-09-12) - eigener Dialog statt Download, siehe
// zip_contents_dialog.js. Nur "zip" (das einzige Format, das Pythons stdlib-zipfile ohne
// Zusatzpaket liest) - rar/7z/tar bewusst nicht, waeren zusaetzliche Abhaengigkeiten.
const ZIP_EXTENSIONS = new Set(["zip"]);

// Only Word/Excel/PowerPoint have an "ofe" protocol handler on Windows for launching the
// desktop app straight from a URL - odt/rtf/ods/odp have no equivalent, they stay editable
// via ONLYOFFICE only. Ported verbatim from legacy_ui/filemanager_action.js.
const OFFICE_PROTOCOL = {
    doc: "ms-word", docx: "ms-word",
    xls: "ms-excel", xlsx: "ms-excel",
    ppt: "ms-powerpoint", pptx: "ms-powerpoint",
};

// Exportiert (statt modulintern), weil analyze_button_widget.js (der neue Direkt-Icon-Button
// auf Zeile/Karte, siehe docs/int_filemanager_native_ui.md) dieselbe Erweiterungs-Pruefung
// braucht, um sich fuer Ordner/nicht-unterstuetzte Dateitypen unsichtbar zu machen - eine
// einzige Quelle der Wahrheit dafuer statt einer zweiten, potenziell abweichenden Kopie.
export function extOf(name) {
    const i = name.lastIndexOf(".");
    return i === -1 ? "" : name.slice(i + 1).toLowerCase();
}

function isPreviewable(name) {
    return PREVIEWABLE_EXTENSIONS.has(extOf(name));
}

function isOfficeEditable(name) {
    return OFFICE_EDIT_EXTENSIONS.has(extOf(name));
}

// Nur echte Text-Eingabefelder zaehlen als "Tippkontext" - NICHT jedes <input>. Live als Bug
// gefunden 2026-09-14 (Nutzerreport "ESC deselektiert nicht"): die Auswahl-Checkbox der Zeile
// ist selbst ein <input type="checkbox">, behielt nach einem Checkbox-Klick den DOM-Fokus, und
// die vorherige Pruefung (tagName === "INPUT" ohne type-Check) hielt das faelschlich fuer ein
// Tippfeld - F2/Escape taten dann nichts, weil sie fruehzeitig abbrachen.
const NON_TEXT_INPUT_TYPES = new Set(["checkbox", "radio", "button", "submit", "reset", "file", "image", "range", "color"]);
function isTypingContext(el) {
    if (!el) {
        return false;
    }
    if (el.tagName === "TEXTAREA" || el.isContentEditable) {
        return true;
    }
    return el.tagName === "INPUT" && !NON_TEXT_INPUT_TYPES.has(el.type);
}

// Muss mit fulltext.py's PLAIN_TEXT_EXTENSIONS/PDF_EXTENSIONS uebereinstimmen (nur zur
// UI-Verfuegbarkeit des "Werte erkennen"-Menuepunkts - der Server bleibt bei der eigentlichen
// Analyse die einzige Quelle der Wahrheit, siehe onAnalyzeDocument). TEXT_EDIT_EXTENSIONS oben
// deckt sich bereits 1:1 mit PLAIN_TEXT_EXTENSIONS, daher wiederverwendet statt dupliziert.
export function isFulltextSupported(name) {
    const ext = extOf(name);
    return TEXT_EDIT_EXTENSIONS.has(ext) || ext === "pdf";
}

export function filemanagerControllerMixin(Base) {
    return class extends Base {
        setup() {
            super.setup();
            // Unterdrueckt Odoos eigenen, global registrierten "PagerIndicator"-Toast auf Mobil
            // (position:fixed, top:0, end:0 - ueberlagerte sichtbar den lila App-Navbar,
            // Nutzerreport 2026-09-16 mit Screenshot: "1-1 / 1"-Box oben rechts). Grund: die
            // eigentliche <Pager/>-Komponente ist trotz der CSS-Ausblendung des Control Panels
            // (native_list_view.scss) weiterhin voll aktiv gemountet - ihr eigener useEffect
            // (web/core/pager/pager.js) feuert bei JEDER Aenderung von offset/limit/total, SOLANGE
            // env.isSmall true ist, unabhaengig von CSS display:none. Ein reiner CSS-Fix kann einen
            // laufenden JS-Seiteneffekt nicht stoppen. Sauberer Ansatz statt weiterer CSS-Ausblendung:
            // usePager() (web/search/pager_hook.js), von ListController/KanbanController in ihrem
            // eigenen super.setup() bereits aufgerufen, hat env.config.pagerProps gerade erst per
            // useSubEnv gesetzt - ein zweiter, hier SPAETER aufgerufener useSubEnv() ueberschreibt
            // das fuer alle Kind-Komponenten dieses Controllers (insbesondere das native
            // ControlPanel). Mit env.config.pagerProps == undefined bleibt ControlPanel.pagerProps
            // (control_panel.js: "this.env.config.pagerProps ? useState(...) : undefined") dauerhaft
            // undefined, <Pager/> mountet dort nie (control_panel.xml: "t-if=\"pagerProps and
            // pagerProps.total > 0\"") - kein Pager-useEffect, kein PAGER:UPDATED-Event, kein Toast.
            // Auf Desktop unveraendert (env.config.pagerProps bleibt dort einfach das Original).
            if (this.env.isSmall) {
                useSubEnv({ config: { ...this.env.config, pagerProps: undefined } });
            }
            this.dialog = useService("dialog");
            this.notification = useService("notification");
            this.fileUpload = useService("file_upload");
            this.actionService = useService("action");
            this.busService = useService("bus_service");
            this.fileViewer = useFileViewer();
            this.audioPlayer = useService("int_filemanager.audioPlayer");
            this.fileInput = useRef("fileInput");

            // Drag&Drop-Upload (2026-09-05): Mitarbeiter ziehen PDFs heute per Drag&Drop direkt aus
            // dem Dateisystem oder als Anhang aus Outlook in PaperOffice - dieselbe Erfassungs-Routine
            // sollte hier nicht verloren gehen, nur weil die UI wechselt (siehe
            // docs/int_filemanager_paperoffice_recherche.md, Baustein 0). Auf window statt auf einem
            // einzelnen DOM-Element gehaengt: robust gegenueber der genauen Struktur des von
            // web.ListView/web.KanbanView geerbten Templates, kein eigenes Drop-Zone-Element noetig,
            // das irgendwo exakt ueber der Liste/dem Karten-Grid sitzen muesste. dragenter/dragleave
            // feuern bei jedem Kind-Element einzeln (Owl-Events bubbeln normal) - ein einfacher
            // Boolean wuerde beim Ueberqueren von Kindelementen flackern, deshalb ein Tiefenzaehler
            // statt eines Flags. dataTransfer.types filtert echte Datei-Drags von anderen
            // Drag-Interaktionen (z.B. Text-Selektion) heraus.
            this.dropState = useState({ dragging: false });
            this._dragDepth = 0;
            useExternalListener(window, "dragenter", this.onWindowDragEnter);

            // Inline-Umbenennen per F2 (Nutzerwunsch 2026-09-12, Explorer-Muster) - bewusst NICHT
            // ueber Odoos natives Listen-Inline-Editing (list.enterEditMode()): das committet ueber
            // ein rohes ORM write() auf das Feld, wuerde also nur den DB-Namen aendern, nicht die
            // echte Datei umbenennen/authz pruefen - derselbe "Sicherheitsrelevanter Stolperstein"
            // wie bei jeder anderen Mutation (docs/int_filemanager_native_ui.md). Committet deshalb
            // ueber denselben authz-geprueften /int_filemanager/rename-Aufruf wie der bestehende
            // onRename()-Dialog (_performRename unten).
            //
            // Das <input> selbst wird NICHT hier im Controller gerendert - es sitzt inline in
            // name_icon_field.js/.xml, genau an der Stelle, an der sonst der Text-Span steht
            // (t-if darauf, ob "isRenaming" fuer das jeweilige Feld-Widget-Record zutrifft).
            // useSubEnv gibt dem Feld-Widget (ein eigenstaendig instanziertes Owl-Kind der Zeile/
            // Karte, kein direktes Geschwister von Controller-Methoden) Zugriff auf den
            // reaktiven Zustand plus die commit/cancel-Callbacks.
            //
            // Fruehere Version (bis 2026-09-13/14): ein separates, ueberlagerndes <input> mit
            // position:fixed und Koordinaten aus getBoundingClientRect() - grundsaetzlich fragil,
            // weil der echte Zellentext dabei die ganze Zeit im DOM sichtbar blieb. Vier
            // Nutzerreports in Folge (Icon verdeckt, sichtbarer Rahmen trotz .o_input, lange
            // Namen falsch markiert, Position lief beim Scrollen auseinander) waren alles
            // Symptome derselben Grundkonstruktion, das letzte (sichtbares Doppelbild bei
            // Cursor-Bewegung, sobald der Hintergrund transparent war) hat den Ansatz endgueltig
            // disqualifiziert. Inline-Rendering im Feld-Widget selbst hat zu jedem Zeitpunkt nur
            // genau ein Text-Element im DOM - keine Positionsberechnung, keine
            // Scroll-Nachfuehrung, kein Doppelbild moeglich.
            this.renameState = useState({ recordId: null, value: "" });
            useSubEnv({
                filemanagerRename: {
                    state: this.renameState,
                    commit: (name) => this._commitRename(name),
                    cancel: () => { this.renameState.recordId = null; },
                },
            });
            // useHotkey("f2", ...) wuerde hart crashen: Odoos Hotkey-Service whitelisted nur
            // a-z/0-9/Navigationstasten/escape, F-Tasten sind dort in Odoo 18 UND 19
            // kategorisch ausgeschlossen (registerHotkey() wirft synchron beim useHotkey-Aufruf
            // selbst, kein Options-Flag umgeht das - am Odoo-Quellcode geprueft, siehe
            // core/hotkeys/hotkey_service.js: AUTHORIZED_KEYS). Live-Fehler auf Produktiv am
            // 2026-09-13 ("hotkey ('f2') ... not whitelisted"). Deshalb roher keydown-Listener
            // statt useHotkey, mit derselben Editable-Schutzlogik, die der Hotkey-Service sonst
            // automatisch mitbringt (sonst wuerde F2 auch beim Tippen im Suchfeld/eigenen
            // Umbenennen-Input feuern).
            useExternalListener(window, "keydown", (ev) => {
                if (ev.key === "F2") {
                    // preventDefault() VOR der Editable-Pruefung, nicht danach: sonst bekommt der
                    // Browser beim zweiten F2-Druck (Fokus liegt schon im eigenen Rename-Input) doch
                    // wieder die Taste zu sehen und oeffnet seine eigene Befehlsliste - live so
                    // beobachtet (F2, F2, F2, F2 schaltete abwechselnd Rename/Edge-Fenster um).
                    // isEditable verhindert nur das erneute AUSLOESEN von onF2Rename() waehrend des
                    // Tippens, nicht mehr das preventDefault selbst.
                    ev.preventDefault();
                    if (isTypingContext(document.activeElement)) {
                        return;
                    }
                    this.onF2Rename();
                    return;
                }
                // Escape deselektiert die Auswahl (Explorer-/web-filemanager-Konvention, siehe
                // dortiges useListSelection.ts) - erreicht diesen Listener waehrend eines aktiven
                // F2-Renames ohnehin nie, weil onRenameKeydown in name_icon_field.js dort
                // stopPropagation() aufruft (eigene Escape-Behandlung = cancel()). isEditable
                // schuetzt z.B. das Suchfeld (Odoo soll dessen eigenes Escape-Verhalten behalten),
                // die Dialog-Ausnahme laesst offene Modals (z.B. Bestaetigungsdialoge) ihr eigenes
                // Escape-zum-Schliessen unangetastet, statt zusaetzlich die Auswahl zu leeren.
                if (ev.key === "Escape") {
                    if (isTypingContext(document.activeElement) || document.querySelector(".modal.show, .o_dialog")) {
                        return;
                    }
                    for (const record of this.model.root.selection) {
                        record.toggleSelection(false);
                    }
                    // Checkbox-Auswahl und Odoos eigener nativer "fokussierte Zelle"-Rahmen
                    // (Tastaturnavigation, .o_data_cell mit tabindex="-1") sind zwei getrennte
                    // Dinge - Nutzerreport 2026-09-14: nach dem Deselect blieb der Rahmen sichtbar
                    // stehen, sah aus wie "ESC tut nichts". blur() nimmt der zuletzt fokussierten
                    // Zelle den Fokus, der Rahmen verschwindet mit. Kein Ziel-Check noetig -
                    // blur() auf einem bereits unfokussierten Element (z.B. document.body) ist
                    // ein No-Op.
                    document.activeElement?.blur();
                }
                // capture:true (nicht der Default/Bubble) ist hier Pflicht, nicht Kosmetik: Escape
                // ist - anders als F2 - in Odoos Hotkey-Service ausdruecklich WHITELISTED
                // (AUTHORIZED_KEYS, siehe Kommentar oben). Live gefunden 2026-09-14: ein normaler
                // Bubble-Listener bekam die Escape-Taste nie zu Gesicht (kein einziges Debug-Log
                // feuerte) - irgendetwas in Odoos eigener Hotkey-/Listen-Tastaturbehandlung
                // konsumiert sie vorher. Gleiches Muster/dieselbe Begruendung wie in
                // web-filemanagers useListSelection.ts (dort explizit gegen Radix' eigenen
                // Escape-Handler). isTypingContext() oben schuetzt weiterhin zuverlaessig das
                // eigene Rename-Input: waehrend des Renamens IST activeElement dieses Input,
                // Capture-Phase aendert daran nichts.
            }, { capture: true });
            useExternalListener(window, "dragleave", this.onWindowDragLeave);
            useExternalListener(window, "dragover", (ev) => ev.preventDefault());
            useExternalListener(window, "drop", this.onWindowDrop);

            // Verschieben per Drag&Drop zwischen Ordnern (2026-09-07, Nutzerwunsch) - eigene,
            // von der Datei-Upload-Drag&Drop-Logik oben unabhaengige Ereigniskette (beide
            // laufen ueber dieselben nativen dragstart/dragover/drop-Events auf window, werden
            // aber ueber den dataTransfer-Typ sauber auseinandergehalten: ein OS-Datei-Drag
            // traegt immer den Typ "Files" - siehe _isFileDrag oben -, unser eigener interner
            // Verschiebe-Drag NIE, weil wir ihn selbst ohne "Files" setzen). Bewusst KEIN
            // useSortable (Odoos Kanban-Spalten-Drag-Hook): der ist fuers Umsortieren
            // *innerhalb* einer nach einem Feld gruppierten Liste gedacht (Schreiben von
            // sequence/dem Gruppierungsfeld), nicht fuer "Zeile auf eine andere, inhaltlich
            // andersartige Zeile ziehen" - passt strukturell nicht. Stattdessen die nackte
            // HTML5-Drag&Drop-API von Hand, ueber Event-Delegation auf window (gleiches
            // Grundmuster wie der Upload-Drop oben) statt ueber eigene t-on-dragstart-Attribute
            // in der Arch: Zeilen/Karten werden von Odoos ListRenderer/KanbanRecord selbst
            // gerendert, wir bekommen deren Wurzelelement nicht direkt in die Hand - aber jede
            // Zeile/Karte traegt nativ bereits ein data-id-Attribut (list_renderer.xml/
            // kanban_record.xml: t-att-data-id="record.id", am Odoo-19-Quellcode verifiziert),
            // das reicht als Angriffspunkt fuer die Ereignis-Delegation vollstaendig aus.
            onMounted(() => {
                this._makeRecordsDraggable();
                this._checkMobileBreadcrumbOverflow();
                this._measureChatterTop();
            });
            onPatched(() => {
                this._makeRecordsDraggable();
                this._checkMobileBreadcrumbOverflow();
                this._measureChatterTop();
            });
            useExternalListener(window, "dragstart", this.onWindowDragStartRecord);
            useExternalListener(window, "dragover", this.onWindowDragOverRecord);
            useExternalListener(window, "drop", this.onWindowDropRecord);
            useExternalListener(window, "dragend", this.onWindowDragEndRecord);

            // Rechtsklick-Kontextmenue (Nutzerwunsch 2026-09-17) - dieselben Eintraege wie das
            // bestehende "Aktionen"-Dropdown (getStaticActionMenuItems() unten, Odoos eigener
            // ListController/KanbanController-Override-Punkt, der normalerweise das native
            // web.ActionMenus im Control-Panel speist), hier nur zusaetzlich am Cursor geoeffnet.
            //
            // Nutzerkorrektur 2026-09-17 "sauber nativ, kein CSS-Gebastel": ein erster Versuch
            // mit eigenen CSS-Klassen + einer eigenen Reset-Regel gegen Popovers Bootstrap-
            // ".popover"-Kartenoptik sah optisch nicht Odoo-nativ aus (fehlendes Hover-Highlight,
            // siehe unten). Ersetzt durch Odoos EIGENE interne Rezeptur, 1:1 aus dropdown.js
            // (setup(), Zeilen ~131-177) uebernommen statt nachgebaut:
            // - useNavigation(menuRef, {getItems: ".o-navigable"-Kinder}) - das ist der
            //   tatsaechliche Mechanismus hinter dem Hover-/Pfeiltasten-Highlight. Odoos
            //   ".o-dropdown--menu"-CSS deaktiviert bewusst den normalen Browser-":hover"-Effekt
            //   (dropdown.scss: "&:not(.focus) { background-color: transparent; }") - das
            //   Highlight kommt ausschliesslich von der ".focus"-Klasse, die dieser Hook per
            //   mousemove/Tastatur verwaltet (navigation.js: "ACTIVE_ELEMENT_CLASS = 'focus'").
            //   Ohne diesen Hook blieb das Menue optisch stumm (genau der Nutzerreport).
            // - usePopover(...) mit denselben Optionen wie Dropdown fuer SEIN eigenes internes
            //   usePopover(DropdownPopover, ...): arrow:false, popoverClass "o-dropdown--menu
            //   dropdown-menu mx-0" (keine eigene Reset-CSS noetig - Odoos ".dropdown-menu"-Regeln
            //   gewinnen in der Bootstrap-eigenen Kaskade ohnehin gegen ".popover", genau wie beim
            //   echten Dropdown), role "menu". IntFilemanagerContextMenu (context_menu.js) statt
            //   Odoos eigener DropdownPopover-Komponente direkt, nur weil deren eingebautes
            //   Template keine Icons rendert (nur "t-out=item.label") - rendert aber selbst
            //   ausschliesslich echte <DropdownItem>-Kindkomponenten, keine eigene Nachbildung.
            // DropdownItem/useNavigation/usePopover sind damit echte, unveraenderte Odoo-Core-
            // Bausteine, exakt Dropdowns eigene Konfiguration - context_menu.js/.xml kleben sie
            // nur fuer den Cursor-Anwendungsfall zusammen, ohne eigenes CSS oder Interaktionslogik.
            this.contextMenuRef = useChildRef();
            this.contextMenuNavigation = useNavigation(this.contextMenuRef, {
                shouldRegisterHotkeys: false,
                isNavigationAvailable: () => this.contextMenuPopover.isOpen,
                getItems: () =>
                    this.contextMenuPopover.isOpen && this.contextMenuRef.el
                        ? this.contextMenuRef.el.querySelectorAll(":scope .o-navigable")
                        : [],
            });
            this.contextMenuPopover = usePopover(IntFilemanagerContextMenu, {
                animation: false,
                arrow: false,
                closeOnEscape: false,
                popoverClass: "o-dropdown--menu dropdown-menu mx-0",
                position: "bottom-start",
                ref: this.contextMenuRef,
                role: "menu",
                setActiveElement: false,
                onClose: () => {
                    this._contextMenuAnchorEl?.remove();
                    this._contextMenuAnchorEl = null;
                },
            });
            useExternalListener(window, "contextmenu", this.onWindowContextMenu);

            // Chatter-Seitenpanel (Baustein 2 Folgearbeit, 2026-09-06): standardmaessig zu,
            // per Toolbar-Toggle oeffenbar - siehe docs/int_filemanager_paperoffice_recherche.md,
            // Baustein 2. Bewusst ein ueberlagerndes Fixed-Panel statt eines echten, Platz
            // verdraengenden Flex-Layouts: Letzteres haette eine Patch von Odoos geteiltem
            // "web.Layout"-Template gebraucht (main.o_content liegt INNERHALB von Layouts
            // eigenem Template, nicht im hier ererbten "web.ListView"/"web.KanbanView"), was global
            // jede Listen-/Kanban-Ansicht im System betroffen haette - fuer ein Panel, das nur
            // dieser eine Dateimanager braucht, unverhaeltnismaessig riskant. topPx wird per
            // getBoundingClientRect() auf ".o_content" vermessen, damit das Panel exakt unter
            // der eigenen Toolbar/Breadcrumb-Zeile beginnt statt sie zu verdecken (Pager,
            // Suche etc. bleiben bedienbar), statt eine Navbar-Hoehe zu raten.
            this.chatterState = useState({ open: false, topPx: 0 });
            // Mobil-Ordnerbaum als Bottom-Sheet (env.isSmall, siehe native_list_view.js:
            // className) - dieselbe FolderTree-Komponente (folder_tree.js) wie die Desktop-Seitenleiste, nur anders
            // positioniert/getoggled (siehe native_list_view.xml/.scss). this.mobileTreeState.open
            // steuert nur eine CSS-Klasse (o_int_filemanager_mobile_tree_open, siehe
            // native_list_view.js: className), kein Einfluss auf die Domain-Logik selbst.
            this.mobileTreeState = useState({ open: false });
            // Desktop-Ordnerbaum-Seitenleiste (folder_tree.js) - anders als das Mobil-Sheet oben
            // immer sichtbar (kein eigener open/close-Zustand). Bis 2026-09-17 per position:fixed
            // relativ zum Viewport platziert; 2026-09-18 (Nutzerwunsch "Breite dragbar", "sauber
            // odoo nativ") ersetzt durch ein echtes CSS-Grid auf dem Controller-Root (siehe
            // folder_tree_layout.scss fuer die ausfuehrliche Begruendung, insbesondere warum
            // Flexbox dafuer NICHT reicht) plus Odoos eigener ResizablePanel-Kernkomponente
            // (@web/core/resizable_panel, dieselbe wie Discuss' Sidebar) fuer den Drag-Griff -
            // initialTreeWidth/onResizeTree unten sind die einzigen dafuer noch noetigen
            // Eigenanteile (Breiten-Persistenz), der Drag-Mechanismus selbst kommt unveraendert
            // aus Odoo.
            this.initialTreeWidth = Number(browser.localStorage.getItem(TREE_WIDTH_LS)) || TREE_WIDTH_DEFAULT;
            // Nutzerreport 2026-09-18 "beim Draggen verschwindet das Icon" = der Maus-Cursor
            // selbst, nicht ein UI-Icon: ResizablePanels eigener useResizable()-Hook
            // (resizable_panel.js: onMouseDown) haengt waehrend des Ziehens "pe-none" (=
            // pointer-events:none) an <body>, damit Text waehrend des Ziehens nicht versehentlich
            // markiert wird - das bricht nebenbei aber auch das normale Hit-Testing, ueber das der
            // Browser ermittelt, WESSEN "cursor:col-resize"-CSS gerade gilt (body selbst wird
            // dadurch fuers Hit-Testing uebersprungen), der Zeiger faellt deshalb zwischendurch auf
            // den Standardpfeil zurueck. Kein Eingriff in Odoos Kerndatei noetig: eigener,
            // zusaetzlicher Listener hier erkennt denselben (oeffentlichen, stabilen)
            // ".o_resizable_panel_handle"-Klassennamen aus resizable_panel.xml per Event-
            // Delegation und erzwingt den Cursor stattdessen auf <html> (documentElement) - das
            // liegt AUSSERHALB von Odoos pointer-events:none-Bereich (nur <body> betroffen, siehe
            // oben), bleibt also waehrend des gesamten Ziehens hit-testbar und zeigt den Cursor
            // durchgehend, exakt dasselbe Grundmuster (Klasse an-/abhaengen bei mousedown/mouseup),
            // das Odoo selbst fuer pe-none/user-select-none nutzt.
            useExternalListener(window, "mousedown", (ev) => {
                if (ev.target.closest(".o_resizable_panel_handle")) {
                    document.documentElement.classList.add("o_int_filemanager_resizing_tree");
                }
            });
            useExternalListener(window, "mouseup", () => {
                document.documentElement.classList.remove("o_int_filemanager_resizing_tree");
            });
            // Von folder_tree.js in dessen eigenem onMounted() gesetzt (registerApi-Prop) - erlaubt
            // reload() unten, gezielt nur den aktuell offenen Ordner im Baum-Cache zu invalidieren,
            // statt den ganzen Baum neu zu laden.
            this.folderTreeApi = null;
            // Von updateBreadcrumbs() gefuellt, von mobileBreadcrumbs unten gelesen - vor dem
            // ersten updateBreadcrumbs()-Aufruf (siehe dessen onMounted-Zeitpunkt-Begruendung
            // unten) leer, nie undefined.
            this.folderCrumbs = [];
            // Mobil-Breadcrumb-Kollabierung (Nutzerwunsch 2026-09-15): bei zu langem Pfad wird
            // statt horizontalem Scrollen alles zwischen erstem und letztem Segment zu einem
            // "…"-Dropdown zusammengefasst (siehe native_list_view.xml). Per echter
            // Breiten-Messung (scrollWidth > clientWidth) statt eines festen
            // Segmentanzahl-Schwellwerts, siehe _checkMobileBreadcrumbOverflow() unten -
            // "collapsed" wird bei jeder Ordner-Navigation in updateBreadcrumbs() zurueckgesetzt
            // und hier gegen die dann wieder VOLLSTAENDIG gerenderte Liste neu geprueft.
            this.mobileBreadcrumbState = useState({ collapsed: false });
            this.mobileBreadcrumbNavRef = useRef("mobileBreadcrumbNav");
            useExternalListener(window, "resize", () => this._measureChatterTop());

            // Everything already on the stack when this controller was created (normally
            // just the "Dateimanager" action entry itself, or "Verknüpfte Dateien" when opened
            // via the linkable-mixin smart button) stays as-is; folder
            // levels get appended after it. Breadcrumbs.xml always renders the LAST array
            // entry as the current (bold, non-clickable) one and everything before it as a
            // real link - so no special-casing needed for "which crumb is active".
            this.rootBreadcrumbCount = this.env.config.breadcrumbs.length;

            // Die letzte der bereits vorhandenen Root-Krumen ist IMMER die dieser Action selbst
            // (alles davor, falls vorhanden, gehoert einer aufrufenden Action/einem Datensatz - z.B.
            // "Kontakte / Administrator" -  und muss ihr eigenes, natives Verhalten behalten). Odoos
            // eigenes onSelected dafuer ruft restore(jsId) auf denselben, bereits aktiven Controller
            // auf (action_service.js) - live beobachtet, dass das die Kategorie-Auswahl NICHT
            // zuruecksetzt (Klick auf die Wurzel-Krume aenderte weder Liste noch die eigenen
            // Unterordner-Krumen). Deshalb hier zusaetzlich (nicht statt) auf Wurzel zuruecksetzen.
            const ownRootCrumb = this.env.config.breadcrumbs[this.rootBreadcrumbCount - 1];
            if (ownRootCrumb) {
                const nativeOnSelected = ownRootCrumb.onSelected;
                ownRootCrumb.onSelected = () => {
                    nativeOnSelected?.();
                    this.env.searchModel.setIntFilemanagerFolderPath("");
                };
            }

            useBus(this.fileUpload.bus, "FILE_UPLOAD_LOADED", (ev) => {
                if (ev.detail.upload.id === this.pendingUploadId) {
                    this.reload();
                    this._analyzeUploadedFiles(this.pendingUploadFiles || []);
                }
            });
            // Reload when anything changes the index server-side, whether from this tab
            // (mutations below) or elsewhere (another tab, the filesystem watcher).
            // Debounced since a bulk change (e.g. a large folder copied in) fires one
            // notification per touched entry. Same pattern as filemanager_action.js.
            this._onFilemanagerChange = () => {
                clearTimeout(this._reloadTimeout);
                this._reloadTimeout = setTimeout(() => this.reload(), 800);
            };
            this.busService.addChannel("int_filemanager");
            this.busService.subscribe("int_filemanager.change", this._onFilemanagerChange);
            onWillUnmount(() => {
                clearTimeout(this._reloadTimeout);
                this.busService.unsubscribe("int_filemanager.change", this._onFilemanagerChange);
            });

            // Navigation (Zeilenklick/Kartenklick, Breadcrumb, Ordnerbaum) laeuft ab jetzt
            // AUSSCHLIESSLICH ueber env.searchModel.setIntFilemanagerFolderPath() (siehe
            // native_search_model.js) - siehe openRecord()/updateBreadcrumbs() unten. Kein eigenes
            // this.model.load({domain:[...]}) fuer
            // Ordnerwechsel mehr: useModel() (web/static/src/model/model.js) registriert selbst
            // unbedingt onWillUpdateProps((nextProps) => model.load(getSearchParams(nextProps)))
            // auf dieser Komponente - das laesst sich aus einer Subklasse nicht abschalten und
            // laeuft bei jeder Props-Aenderung (ausgeloest durch WithSearch, das bei jedem
            // searchModel "update"-Event neu rendert). Ein zweiter, eigener reload()-Aufruf mit
            // eigener Domain war deshalb ein zweiter Schreiber auf dasselbe Model und hat live
            // nachweisbar das Rennen gegen diesen nativen Reload verloren (siehe
            // docs/int_filemanager_native_ui.md). Mit genau einem Schreiber (searchModel) ist
            // das Rennen strukturell unmoeglich, nicht nur seltener.
            //
            // updateBreadcrumbs() unten haengt trotzdem an env.searchModel "update" - das schreibt
            // aber nur das rein kosmetische env.config.breadcrumbs-Array, nie model/domain, und ist
            // deshalb kein Ruecksturz in dasselbe Muster. Jede View bekommt beim Wechsel (siehe
            // docs/int_filemanager_native_ui.md) eine eigene, frische Controller-Instanz und damit
            // ein eigenes, frisch aus dem Action-Stack berechnetes env.config.breadcrumbs-Array
            // (action_service.js, _updateUI) - deshalb muss JEDE View, die dieses Mixin nutzt, hier
            // selbst wieder auf "update" subscriben und ihre Ordner-Krumen nachbauen, es gibt keinen
            // Weg, das nur einmal zu tun.
            useBus(this.env.searchModel, "update", () => this.updateBreadcrumbs());

            // Der ALLERERSTE Aufruf von updateBreadcrumbs() darf NICHT synchron hier in setup()
            // passieren, sondern erst in onMounted() - live auf Tower reproduziert (2026-09-07):
            // beim ersten Wechsel zu einer in dieser Session noch nie besuchten Ansicht
            // (Liste<->Kanban) waehrend man in einem Unterordner ist, stuerzt Breadcrumbs.template
            // ab ("Cannot read properties of undefined (reading 'actionStack')"), weil Odoos
            // eigenes Breadcrumbs-Template fuer jede NICHT-letzte Krume "url" auswertet
            // (router.stateToUrl(controller.state)) - und controller.state wird fuer einen frisch
            // erzeugten Controller (switchView() erzeugt bei jedem Wechsel eine neue
            // Controller-Instanz, siehe action_service.js) erst in dessen eigenem onMounted()
            // gesetzt (dortiges pushState()), nicht vorher. Haengen wir unsere Ordner-Krumen schon
            // synchron in setup() an, ist die eigentliche "Dateimanager"-Wurzelkrume beim ALLERSTEN
            // Render nicht mehr die letzte im Array (unsere Ordner-Krumen folgen ihr) und braucht
            // deshalb genau diese ".url", obwohl controller.state noch undefined ist - Absturz.
            // In onMounted() ist der erste Render bereits durch (die Wurzelkrume war zu dem
            // Zeitpunkt noch alleine und damit "letzte" Krume, kein .url-Zugriff noetig); die durch
            // unseren Push ausgeloeste Neuzeichnung ist eine spaetere, ueber Owls reaktiven
            // Scheduler asynchron eingeplante Aktualisierung, zu der pushState() (im synchronen
            // onMounted-Durchlauf des naeher an der Wurzel liegenden ControllerComponent bereits
            // gelaufen) controller.state sicher gesetzt hat.
            onMounted(() => this.updateBreadcrumbs());
        }

        onToggleChatterPanel() {
            this.chatterState.open = !this.chatterState.open;
        }

        // Vermisst den Startpunkt des ueberlagernden Chatter-Panels rechts (chatterState in
        // setup()). Bewusst UNTERHALB der eigenen Toolbar/Breadcrumb-Zeile verankert (".o_content",
        // schliesst die Toolbar ausdruecklich aus), NICHT an der (stabilen) Navbar-Hoehe wie
        // frueher der Desktop-Ordnerbaum (der braucht seit dem topPx-Flicker-Fix (2026-09-16) keine
        // JS-Messung mehr, siehe Kommentar bei der FolderTree-Seitenleiste in setup() - reine
        // CSS-Konstante statt Laufzeit-Messung, weil seine Position eben NICHT vom
        // Toolbar-Zeilenumbruch abhaengt).
        // ".o_content"s Top dagegen schwankt echt (z.B. Suchleiste faellt bei aktiven Facetten auf
        // zwei Zeilen), braucht deshalb weiterhin eine echte, mangels dediziertem Re-Measure-
        // Ausloeser bei Bedarf veraltete Messung.
        _measureChatterTop() {
            const contentEl = this.rootRef.el?.querySelector(".o_content");
            this.chatterState.topPx = contentEl ? Math.round(contentEl.getBoundingClientRect().top) : 0;
        }

        // Zeigt die (Checkbox-/Alt-Klick-)Auswahl der Liste bzw. Karten-Selektion, dieselbe
        // this.model.root.selection wie getStaticActionMenuItems() weiter unten - kein separater
        // Auswahlmechanismus. Erste markierte Zeile/Karte bei Mehrfachauswahl (Reihenfolge =
        // Anzeigereihenfolge), nicht die zuletzt angeklickte - einfach vorhersagbar, ohne eigene
        // Klick-Reihenfolge-Buchhaltung.
        get chatterRecord() {
            return this.model.root.selection[0] || null;
        }

        async openRecord(record) {
            if (record.data.is_dir) {
                this.env.searchModel.setIntFilemanagerFolderPath(record.data.path);
                return;
            }
            if (TEXT_EDIT_EXTENSIONS.has(extOf(record.data.name))) {
                this.onEditText(record);
                return;
            }
            if (isOfficeEditable(record.data.name)) {
                this.onEdit(record);
                return;
            }
            if (ZIP_EXTENSIONS.has(extOf(record.data.name))) {
                this.onOpenZip(record);
                return;
            }
            if (AUDIO_EXTENSIONS.has(extOf(record.data.name))) {
                this.onPlayAudio(record);
                return;
            }
            if (isPreviewable(record.data.name)) {
                this.onPreview(record);
                return;
            }
            window.open(`/int_filemanager/download?path=${encodeURIComponent(record.data.path)}`, "_blank");
        }

        // ONLYOFFICE-Bearbeitung, 1:1 aus legacy_ui/filemanager_action.js uebernommen - schon dort
        // vollstaendig nativ (this.actionService.doAction() mit einer ir.actions.client, demselben
        // Mechanismus, unter dem der onlyoffice_odoo-Editor seine Komponente registriert). Die
        // eine RPC vorweg ist unvermeidbares Bindeglied, kein Custom-Umweg: ONLYOFFICE editiert
        // ir.attachment-Datensaetze, unsere Dateien liegen aber roh auf der Platte - /open_editor
        // legt/findet dafuer den passenden Attachment serverseitig, bevor der native Editor startet.
        async onEdit(record) {
            try {
                const res = await rpc("/int_filemanager/open_editor", { path: record.data.path });
                this.actionService.doAction({
                    type: "ir.actions.client",
                    tag: "onlyoffice_editor",
                    name: record.data.name,
                    params: { attachment_id: res.attachment_id },
                });
            } catch (e) {
                this.notification.add(e.data?.message || e.message, { type: "danger" });
            }
        }

        // "Lokal oeffnen" (WebDAV-Handoff an die Desktop-App per ms-word:/ms-excel:/ms-powerpoint:-
        // Protokoll) - 1:1 aus legacy_ui uebernommen. Kein natives Odoo-Aequivalent moeglich: das ist
        // ein Windows/Office-eigener URL-Protocol-Handler, keine Odoo-UI-Mechanik - der Bruch mit
        // "moeglichst nativ" liegt am Feature selbst, nicht an der Umsetzung hier.
        async onOpenLocal(record) {
            const protocol = OFFICE_PROTOCOL[extOf(record.data.name)];
            if (!protocol) {
                return;
            }
            try {
                const res = await rpc("/int_filemanager/webdav_token", { path: record.data.path });
                window.location.href = `${protocol}:ofe|u|${res.url}`;
            } catch (e) {
                this.notification.add(e.data?.message || e.message, { type: "danger" });
            }
        }

        onOpenZip(record) {
            this.dialog.add(IntZipContentsDialog, {
                fileName: record.data.name,
                path: record.data.path,
            });
        }

        async onEditText(record) {
            const downloadUrl = `/int_filemanager/download?path=${encodeURIComponent(record.data.path)}&disposition=inline`;
            const content = await fetch(downloadUrl).then((r) => r.text());
            this.dialog.add(IntTextEditorDialog, {
                title: record.data.name,
                path: record.data.path,
                content,
                onSaved: () => this.reload(),
            });
        }

        async reload() {
            // Nutzerwunsch 2026-09-18 (Umbenennen soll die Auswahl behalten): Odoos eigenes
            // model.load() unten baut bei JEDEM Reload komplett neue Record-Datapoints auf
            // (relational_model/dynamic_record_list.js: "this.records = data.records.map(...)"
            // -> record.js-Konstruktor setzt "this.selected = false" fuer jeden neuen
            // Datenpunkt) - jede bestehende Auswahl geht dadurch architekturbedingt bei JEDEM
            // reload() verloren, kein eingebauter "ueber Reload hinweg merken"-Mechanismus in
            // Odoo (am Quellcode geprueft). Bewusst HIER zentral statt nur in _performRename():
            // eine Umbenennung loest oft ZWEI reload()-Aufrufe aus - den direkten hier
            // (_performRename) UND, ~800ms spaeter entprellt, einen zweiten ueber den
            // "int_filemanager.change"-Bus-Kanal (setup() oben), weil der eigene Server-Schreib-
            // vorgang vom Watcher erkannt und an denselben Tab zurueckgemeldet wird. Eine
            // Reselektion nur im ersten Aufruf wurde vom zweiten, spaeteren Aufruf wieder
            // verworfen (live so beobachtet: Auswahl kurz da, nach dem Lade-Toast wieder weg).
            // Zentral in reload() selbst greift die Wiederherstellung bei BEIDEN Aufrufen gleich.
            const selectedResIds = new Set(this.model.root.selection.map((r) => r.resId));
            // Kein Domain-Argument: this.model.config behaelt die zuletzt von useModel() aus
            // searchModel.domain uebernommene Domain bei (_getNextConfig merged nur fehlende
            // Parameter) - ein Refresh nach Mutation aendert also nichts am aktuellen Ordner.
            await this.model.load();
            if (selectedResIds.size) {
                for (const record of this.model.root.records) {
                    if (selectedResIds.has(record.resId)) {
                        record.toggleSelection(true);
                    }
                }
            }
            // model.load() aktualisiert nur die Inhaltsliste - der Ordnerbaum (folder_tree.js) hat
            // einen eigenen Cache pro Ebene, den das nicht anstoesst. mkdir/upload/rename/delete
            // im aktuellen Ordner aendern dessen direkte Kinder, ohne dass sich die Such-Domain
            // selbst aendert - genau den aktuell offenen Pfad im Baum invalidieren und (falls dort
            // gerade aufgeklappt) sofort neu laden deckt den ueberwiegenden Fall ab. Ein move() in
            // einen anderen, gerade nicht sichtbaren Ordner zeigt seine Wirkung dort automatisch
            // beim naechsten Aufklappen (kein Cache-Eintrag existiert dafuer, bis er tatsaechlich
            // gebraucht wird).
            await this.folderTreeApi?.refresh(this.currentPath || "");
        }

        // Baut env.config.breadcrumbs aus this.currentPath nach, dem literalen Pfad-String, den
        // der Ordnerbaum (folder_tree.js) bzw. env.searchModel.setIntFilemanagerFolderPath()
        // direkt vorgibt - keine Vorfahrenketten-Rekonstruktion mehr ueber SearchPanel-
        // Kategoriewerte noetig (siehe native_search_model.js), der Pfad-String traegt die
        // Hierarchie bereits selbst. this.currentPath wird NICHT fuer die Listen-/Kanban-Domain
        // verwendet (die kommt ausschliesslich aus searchModel.domain via useModel) - einziger
        // Zweck ist der "path"-Parameter der bestehenden authz-geprueften mkdir/upload-Routen
        // unten.
        updateBreadcrumbs() {
            // Neuer Pfad -> immer erst wieder vollstaendig rendern (siehe
            // _checkMobileBreadcrumbOverflow() unten, das gegen genau diese volle Darstellung
            // misst und bei Bedarf erneut kollabiert).
            this.mobileBreadcrumbState.collapsed = false;
            this.currentPath = this.env.searchModel.intFilemanagerFolderPath || "";
            const crumbs = this.env.config.breadcrumbs;
            crumbs.length = this.rootBreadcrumbCount;
            // Eigene Kopie der Ordner-Krumen (unten von mobileBreadcrumbs gelesen), unabhaengig
            // davon, ob sie auch in env.config.breadcrumbs landen - siehe Begruendung beim Push
            // unten.
            this.folderCrumbs = [];
            if (!this.currentPath) {
                return;
            }
            const segments = this.currentPath.split("/");
            let acc = "";
            for (const segment of segments) {
                acc = acc ? `${acc}/${segment}` : segment;
                const segmentPath = acc;
                const crumb = {
                    jsId: `int_filemanager_crumb_${segmentPath}`,
                    name: segment,
                    isFormView: false,
                    url: "#",
                    onSelected: () => this.env.searchModel.setIntFilemanagerFolderPath(segmentPath),
                };
                this.folderCrumbs.push(crumb);
                // Nur auf Desktop auch in Odoos eigenes Breadcrumb-Array schreiben (natives
                // Control-Panel/Navbar). Auf Mobil (env.isSmall) ersetzt der eigene Header diese
                // Rolle bereits vollstaendig (mobileBreadcrumbs unten, aus this.folderCrumbs) -
                // ein zusaetzlicher Eintrag hier wuerde im lila App-Navbar nur den Ordnernamen
                // duplizieren UND (Odoos eigenes Verhalten ab einem zweiten Breadcrumb-Eintrag)
                // einen Zurueck-Pfeil einblenden, beides auf Mobil unerwuenscht (Nutzerwunsch
                // 2026-09-16). Vorher per CSS ausgeblendet/mit einem ::before-Text ueberklebt -
                // das erzeugte einen sichtbaren Stilbruch (kleinere Schrift als im Wurzelzustand),
                // weil Odoos natives Breadcrumbs-Template fuer einen einzelnen vs. mehrere
                // Eintraege unterschiedlich rendert. Sauberer, den Navbar-Stack auf Mobil einfach
                // gar nicht erst wachsen zu lassen - Odoo zeigt dann von selbst exakt den
                // Wurzelzustand (kein Zurueck-Pfeil, volle Schriftgroesse), kein CSS-Override noetig.
                if (!this.env.isSmall) {
                    crumbs.push(crumb);
                }
            }
        }

        // Wird von folder_tree.js (Klick auf einen Knoten) aufgerufen. Schliesst das Mobil-Baum-
        // Bottom-Sheet nach einer Ordnerwahl NUR, wenn der gewaehlte Ordner ein Blattordner ist
        // (keine eigenen Unterordner) - Nutzerwunsch 2026-09-16, deckt sich mit Odoos eigenem
        // nativen Verhalten in der Small-Chip-Dropdown-Variante (search_panel.js: toggleCategory()
        // ruft getDropdownState(...).close() ausschliesslich im "value.childrenIds.length"-losen
        // Zweig auf - ein Ordner MIT Unterordnern laesst die Dropdown dort offen, man kann direkt
        // weiterklicken). Die Wurzel laeuft ueber onMobileGoHome() (schliesst immer), nicht hierueber.
        onFolderTreeSelect(path, hasChildren) {
            if (!path) {
                this.onMobileGoHome();
                return;
            }
            this.env.searchModel.setIntFilemanagerFolderPath(path);
            if (!hasChildren) {
                this.mobileTreeState.open = false;
            }
        }

        // -----------------------------------------------------------------
        // Mobil-Header (env.isSmall, siehe native_list_view.js/.xml/.scss)
        // -----------------------------------------------------------------

        // Rein additiv - das Header-Markup selbst lebt in native_list_view.xml, gated auf
        // env.isSmall, betrifft die Desktop-Ansicht also nie. this.folderCrumbs (updateBreadcrumbs()
        // oben) ist auf Mobil die einzige Kopie dieser Krumen - env.config.breadcrumbs bleibt dort
        // bewusst leer (siehe Begruendung dort), deshalb keine zweite, divergierende
        // Navigations-Buchhaltung noetig, nur eine andere Quelle als frueher. Eigener synthetischer
        // Wurzel-Eintrag ("Alle Ordner") davor, mit demselben Reset-Callback wie der Home-Button
        // (onMobileGoHome) - Nutzerwunsch 2026-09-15: echter klickbarer Breadcrumb-Pfad statt nur
        // des letzten Ordnernamens.
        get mobileBreadcrumbs() {
            return [
                { jsId: "int_filemanager_crumb_root", name: _t("Alle Ordner"), onSelected: () => this.onMobileGoHome() },
                ...this.folderCrumbs,
            ];
        }

        // Springt direkt zur Wurzel - derselbe Aufruf, den auch der native Wurzel-Breadcrumb in
        // setup() (ownRootCrumb.onSelected) ausloest.
        onMobileGoHome() {
            this.env.searchModel.setIntFilemanagerFolderPath("");
            this.mobileTreeState.open = false;
        }

        // Misst, ob die VOLLSTAENDIG gerenderte Breadcrumb-Zeile ihren verfuegbaren Platz
        // sprengt - nur waehrend !collapsed relevant (sobald kollabiert gerendert wird, passt es
        // per Definition, erneute Messung wuerde nur faelschlich wieder auf false zuruecksetzen).
        // Reine Breiten-Messung statt fester Segmentanzahl, damit lange Einzelnamen genauso
        // erkannt werden wie viele kurze Segmente.
        _checkMobileBreadcrumbOverflow() {
            if (this.mobileBreadcrumbState.collapsed) {
                return;
            }
            const el = this.mobileBreadcrumbNavRef.el;
            if (el && el.scrollWidth > el.clientWidth + 1) {
                this.mobileBreadcrumbState.collapsed = true;
            }
        }

        // Oeffnet/schliesst das Ordnerbaum-Bottom-Sheet (dieselbe FolderTree-Komponente wie die
        // Desktop-Seitenleiste, siehe native_list_view.scss fuer die Positionierungs-CSS und
        // native_list_view.js fuer die dortige Zustandsklasse). Schliesst sich selbst wieder
        // automatisch nach einer Blattordner-Wahl, siehe onFolderTreeSelect() oben.
        onToggleMobileTree() {
            this.mobileTreeState.open = !this.mobileTreeState.open;
        }

        // ResizablePanel (siehe initialTreeWidth oben) ruft dies bei JEDEM Pixel waehrend des
        // Ziehens auf, nicht nur bei mouseup - kein Debounce noetig, ein simpler
        // localStorage.setItem ist billig genug fuer diese Frequenz (dasselbe macht Discuss'
        // eigener onResize-Handler, siehe discuss_sidebar.js).
        onResizeTree(width) {
            browser.localStorage.setItem(TREE_WIDTH_LS, String(Math.round(width)));
        }

        // -----------------------------------------------------------------
        // preview
        // -----------------------------------------------------------------

        toViewerFile(record) {
            const path = record.data.path;
            const downloadUrl = `/int_filemanager/download?path=${encodeURIComponent(path)}&disposition=inline`;
            const ext = extOf(record.data.name);
            const isPdf = ext === "pdf";
            const isVideo = VIDEO_EXTENSIONS.has(ext);
            return {
                path,
                name: record.data.name,
                downloadUrl,
                isImage: PREVIEWABLE_EXTENSIONS.has(ext) && !isPdf && !isVideo,
                isPdf,
                isVideo,
                mimetype: isVideo ? VIDEO_MIME_TYPES[ext] : undefined,
                isViewable: isPreviewable(record.data.name),
                defaultSource: isPdf
                    ? `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(downloadUrl)}#pagemode=none`
                    : downloadUrl,
            };
        }

        onPreview(record) {
            const files = this.model.root.records
                .filter((r) => !r.data.is_dir && isPreviewable(r.data.name))
                .map((r) => this.toViewerFile(r));
            const file = files.find((f) => f.path === record.data.path);
            this.fileViewer.open(file, files);
        }

        // Queue = alle Audiodateien des AKTUELL GELADENEN Ordners, in Listenreihenfolge (dieselbe
        // Quelle wie onPreview() fuer Bilder/PDFs/Video) - Startindex ist die angeklickte Datei.
        // this.model.root.records ist bewusst NICHT dieselbe Menge wie state.queue im Service:
        // ein Ordnerwechsel danach aendert die Queue nicht rueckwirkend, der Player spielt die
        // einmal gestartete Liste zu Ende (Nutzererwartung: "Wiedergabe laeuft weiter", nicht
        // "Queue springt mit, wenn ich woanders hinklicke").
        onPlayAudio(record) {
            const files = this.model.root.records
                .filter((r) => !r.data.is_dir && AUDIO_EXTENSIONS.has(extOf(r.data.name)))
                .map((r) => ({
                    path: r.data.path,
                    name: r.data.name,
                    downloadUrl: `/int_filemanager/download?path=${encodeURIComponent(r.data.path)}&disposition=inline`,
                    mimetype: AUDIO_MIME_TYPES[extOf(r.data.name)],
                    // Von mediameta.py bereits befuellt, wenn die Datei ID3-/Vorbis-Tags hat -
                    // audio_player_systray.js zeigt "Interpret - Titel" statt des rohen
                    // Dateinamens, sobald beides vorhanden ist.
                    title: r.data.audio_title || "",
                    artist: r.data.audio_artist || "",
                    // Nur fuer die Queue-Liste im Panel gebraucht (audio_player_systray.js:
                    // queueHasMultipleFolders/trackFolder) - bei einer rekursiven Suche
                    // (native_search_model.js: filter_search_recursive) koennen
                    // model.root.records Dateien aus verschiedenen Ordnern enthalten, die Queue-
                    // Liste zeigt den Ordner dann pro Zeile an statt ihn zu verschweigen.
                    folderPath: r.data.folder_path || "",
                }));
            const startIndex = files.findIndex((f) => f.path === record.data.path);
            this.audioPlayer.playQueue(files, startIndex);
        }

        // -----------------------------------------------------------------
        // mutations - all via rpc() against the existing authz-checked routes
        // -----------------------------------------------------------------

        onNewFolder() {
            this.dialog.add(IntTextInputDialog, {
                title: _t("Neuer Ordner"),
                label: _t("Name des neuen Ordners"),
                confirmLabel: _t("Anlegen"),
                confirm: async (name) => {
                    try {
                        await rpc("/int_filemanager/mkdir", { path: this.currentPath, name });
                        await this.reload();
                    } catch (e) {
                        this.notification.add(e.data?.message || e.message, { type: "danger" });
                    }
                },
            });
        }

        triggerUpload() {
            this.fileInput.el.click();
        }

        // Gemeinsamer Upload-Pfad fuer den Datei-Dialog (onFileInputChange) und Drag&Drop
        // (onWindowDrop) - beide liefern letztlich nur eine FileList/ein Array von File-Objekten,
        // der Rest ist identisch. Fire-and-forget wie legacy_ui es tat: completion/errors surface
        // via the file_upload service's bus events (FILE_UPLOAD_LOADED above, FILE_UPLOAD_ERROR
        // shows its own toast automatically).
        async _uploadFiles(files) {
            if (!files.length) {
                return;
            }
            // Fuer den anschliessenden Analyse-Schritt gemerkt (siehe FILE_UPLOAD_LOADED oben) - der
            // Upload-Service liefert im "loaded"-Event nur die id zurueck, nicht die Dateiliste.
            this.pendingUploadFiles = files;
            const upload = await this.fileUpload.upload("/int_filemanager/upload", files, {
                buildFormData: (formData) => formData.append("path", this.currentPath),
            });
            this.pendingUploadId = upload.id;
        }

        // Pfad A (Baustein 1, docs/int_filemanager_paperoffice_recherche.md): fuer jede gerade
        // hochgeladene Datei sofort Volltext/Werte erkennen und bei echten Treffern zur Kontrolle
        // anzeigen - eine Datei nach der anderen (Nutzerentscheidung 2026-09-05), damit bei mehreren
        // gleichzeitig gezogenen Dateien nicht mehrere Dialoge gleichzeitig aufploppen. Kein eigener
        // Extension-Filter hier: nicht unterstuetzte Dateitypen (alles ausser PDF/Text, siehe
        // fulltext.py) liefern serverseitig ohnehin leere Vorschlaege, der Server bleibt die einzige
        // Quelle der Wahrheit dafuer, was unterstuetzt ist.
        async _analyzeUploadedFiles(files) {
            for (const file of files) {
                // safe_name() (controllers/main.py) kann den serverseitig gespeicherten Namen
                // geringfuegig aendern (Sonderzeichen) - in dem seltenen Fall liefert
                // analyze_document unten schlicht keinen Treffer (res_id=false), einfach
                // uebersprungen statt eines Fehlers.
                const path = this.currentPath ? `${this.currentPath}/${file.name}` : file.name;
                let result;
                try {
                    result = await rpc("/int_filemanager/analyze_document", { path });
                } catch {
                    continue;
                }
                if (!result.res_id) {
                    continue;
                }
                const hasSuggestions = result.suggested_tags.length || result.suggested_partner
                    || result.suggested_date || result.suggested_invoice_number || result.suggested_amount;
                if (!hasSuggestions) {
                    continue;
                }
                await new Promise((resolve) => {
                    this.dialog.add(
                        IntDocumentReviewDialog,
                        {
                            fileName: file.name,
                            resId: result.res_id,
                            suggestion: result,
                            onSaved: () => this.reload(),
                        },
                        { onClose: resolve }
                    );
                });
            }
        }

        async onFileInputChange(ev) {
            const files = [...ev.target.files];
            ev.target.value = "";
            await this._uploadFiles(files);
        }

        _isFileDrag(ev) {
            return Boolean(ev.dataTransfer) && Array.from(ev.dataTransfer.types || []).includes("Files");
        }

        onWindowDragEnter(ev) {
            if (!this._isFileDrag(ev)) {
                return;
            }
            ev.preventDefault();
            this._dragDepth++;
            this.dropState.dragging = true;
        }

        onWindowDragLeave(ev) {
            if (!this._isFileDrag(ev)) {
                return;
            }
            ev.preventDefault();
            this._dragDepth = Math.max(0, this._dragDepth - 1);
            if (this._dragDepth === 0) {
                this.dropState.dragging = false;
            }
        }

        async onWindowDrop(ev) {
            if (!this._isFileDrag(ev)) {
                return;
            }
            ev.preventDefault();
            this._dragDepth = 0;
            this.dropState.dragging = false;
            await this._uploadFiles([...ev.dataTransfer.files]);
        }

        // -----------------------------------------------------------------
        // Verschieben per Drag&Drop (2026-09-07) - siehe ausfuehrliche Begruendung des Ansatzes
        // in setup() oben.
        // -----------------------------------------------------------------

        // draggable wird bewusst NICHT deklarativ in einer Arch gesetzt (koennten wir auch gar
        // nicht - wir bekommen die von ListRenderer/KanbanRecord gerenderten Zeilen-/
        // Kartenwurzeln nie in die Hand), sondern nach jedem Render imperativ nachgetragen -
        // exakt dasselbe Grundmuster, das Odoo selbst in file_viewer.js fuer eine vergleichbare
        // "nach dem Rendern noch etwas am echten DOM nachjustieren"-Notwendigkeit nutzt
        // (useEffect dort fuer hidePDFJSButtons()), hier per onMounted+onPatched.
        //
        // Listenzeilen (<tr>) bekommen seit 2026-09-16 eine feinere Regel als Kanban-Karten
        // (Nutzerwunsch: Windows-Explorer-Verhalten, siehe native_list_renderer.js fuer die
        // ausfuehrliche Begruendung) - dort ist bei dicht gefuellten Ordnern sonst nirgends mehr
        // Platz fuer Rubberband-Auswahl. Draggable ist fuer eine Zeile deshalb NICHT die ganze
        // Zeile, sondern IMMER NUR Icon-Button + Name-Label (das sind die tatsaechlich
        // sichtbaren "Gegenstaende", die man im Explorer anfasst) - NICHT die ganze
        // .o_int_filemanager_name_cell (die als flex:1 1 auto-Container die komplette, extra
        // verbreiterte Spalte inkl. Leerraum fuellt, siehe Nutzerreport 2026-09-16 und Kommentar
        // in native_list_renderer.js).
        //
        // Frueherer Versuch (verworfen, Nutzerreport 2026-09-16 "rubberband funktioniert, dann
        // nicht, immer wieder DnD ausgeloest"): die ganze <tr> zusaetzlich draggable machen,
        // sobald record.selected true ist ("auf einer markierten Zeile soll Ziehen ueberall die
        // Auswahl verschieben" - so urspruenglich spezifiziert). Echtes Explorer-Verhalten ist
        // aber genauer: der Selektionsstatus einer Zeile aendert NICHTS daran, ob ein Ziehstart
        // auf ihrer freien Flaeche ein neues Rubberband oder eine Datei-Verschiebung ausloest -
        // auch eine bereits markierte Zeile bleibt fuer Rubberband ausserhalb von Icon/Name
        // anfassbar. Die verworfene Variante machte bei JEDER bereits markierten Zeile die
        // GANZE Zeile zum Drag-Ziel, wodurch praktisch jeder folgende Zieh-Versuch darauf
        // (selbst auf freier Flaeche) mit dem nativen Browser-Drag kollidierte, oft schon bei
        // kleinster Mausbewegung, bevor die eigene 4px-Rubberband-Schwelle in
        // native_list_renderer.js ueberhaupt greifen konnte - kein Timing-Zufall, strukturell so
        // angelegt. Mehrfachauswahl-Drag funktioniert trotzdem weiterhin unveraendert: wird ein
        // BEREITS markierter Datensatz per Icon/Name angefasst, liefert _recordsForDrag() oben
        // die ganze selection statt nur des einen Records.
        //
        // Bewusst NICHT auf volle Zeilenhoehe gestreckt (Nutzerreport 2026-09-16 "rubberband
        // greift nur unten/oben in der Namenszeile, mittig greift DnD" - die Icon/Label-Box ist
        // tatsaechlich nur eine Textzeile hoch, deutlich schmaler als die Zeile selbst): die
        // rubberband-seitige Ausschlusspruefung in native_list_renderer.js kompensiert das
        // bereits ueber gemessene Rects statt reiner .closest()-Treffer, eine zusaetzliche
        // CSS-Streckung hier haette das text-truncate/ellipsis-Verhalten des Labels riskiert
        // (Umbau auf display:flex noetig, siehe Kommentar dort) fuer einen Randfall (Ziehstart
        // exakt in der duennen Polsterzone ueber/unter der Box), der ohnehin nur bewirkt, dass
        // dort weder Rubberband noch Verschieben startet - ein einfacher Klick waehlt die Zeile
        // trotzdem unveraendert aus.
        //
        // Kanban-Karten (kein <tr>, keine Spalten, kein Rubberband-Bedarf) bleiben unveraendert
        // komplett draggable.
        _makeRecordsDraggable() {
            const els = this.rootRef.el?.querySelectorAll("[data-id]") || [];
            for (const el of els) {
                if (el.tagName !== "TR") {
                    el.draggable = true;
                    continue;
                }
                el.draggable = false;
                const dragHandles = el.querySelectorAll(
                    ".o_int_filemanager_name_icon, .o_int_filemanager_name_label"
                );
                for (const handle of dragHandles) {
                    handle.draggable = true;
                }
            }
        }

        _recordForLocalId(id) {
            return this.model.root.records.find((r) => r.id === id);
        }

        // Wird die gerade angefasste Zeile/Karte bereits mitausgewaehlt (Checkbox/Alt-Klick),
        // wandert die ganze Mehrfachauswahl mit - sonst nur der eine angefasste Datensatz.
        _recordsForDrag(startRecord) {
            const selection = this.model.root.selection;
            return selection.includes(startRecord) ? selection : [startRecord];
        }

        // Ein Ziel ist gueltig, wenn es ein Ordner ist, der zu KEINEM der gezogenen Datensaetze
        // identisch ist, und - falls einer der gezogenen Datensaetze selbst ein Ordner ist -
        // auch kein eigener Unterordner davon (serverseitig ohnehin nochmal geprueft, siehe
        // main.py's move()-Route, aber die Live-Rueckmeldung beim Ziehen soll nicht erst nach
        // einem fehlgeschlagenen RPC kommen). target hier ist die vereinheitlichte Form aus
        // _dropTargetFromEvent() ({el, resId, path, isDir}), NICHT direkt ein ORM-Record - der
        // Seitenleisten-Ordnerbaum liefert nie ein echtes Record-Objekt (nur Pfad-Strings, siehe
        // folder_tree.js), deshalb diese gemeinsame, schlankere Form fuer beide Zielarten.
        _isValidDropTarget(records, target) {
            if (!target.isDir) {
                return false;
            }
            return records.every((r) => {
                if (r.resId === target.resId) {
                    return false;
                }
                if (r.data.is_dir) {
                    const prefix = r.data.path + "/";
                    if (target.path === r.data.path || target.path.startsWith(prefix)) {
                        return false;
                    }
                }
                return true;
            });
        }

        // Vereinheitlicht die zwei moeglichen Drop-Ziel-Arten auf dieselbe schlanke Form
        // ({el, resId, path, isDir}): eine Zeile/Karte der aktuell offenen Ansicht (natives
        // data-id, siehe oben) ODER ein Knoten im eigenen Ordnerbaum (folder_tree.js/.xml,
        // data-int-filemanager-tree-path direkt auf dessen Header-Zeile). resId ist fuer einen
        // Baum-Knoten immer false - der Baum kennt nur Pfade, keine Odoo-Datensatz-IDs (siehe
        // folder_tree.js) - _isValidDropTarget() unten braucht sie ohnehin nicht: der
        // Selbst-Drop-Schutz laeuft dort vollstaendig ueber den Pfad-Vergleich, der resId-
        // Vergleich war fuer Zeilen-Ziele immer nur redundant dazu. Gibt null zurueck, wenn
        // unter dem Mauszeiger keins von beidem liegt.
        _dropTargetFromEvent(ev) {
            const rowEl = ev.target.closest("[data-id]");
            if (rowEl) {
                const record = this._recordForLocalId(rowEl.dataset.id);
                if (record) {
                    return { el: rowEl, resId: record.resId, path: record.data.path, isDir: record.data.is_dir };
                }
            }
            const treeEl = ev.target.closest("[data-int-filemanager-tree-path]");
            if (treeEl) {
                return { el: treeEl, resId: false, path: domPathToPath(treeEl.dataset.intFilemanagerTreePath), isDir: true };
            }
            return null;
        }

        onWindowDragStartRecord(ev) {
            if (!this.rootRef.el?.contains(ev.target)) {
                return;
            }
            // ev.target ist bei einem NATIVEN Text-Selektions-Drag oft ein reiner Textknoten
            // ohne .closest() (nur Element.prototype hat das) - z.B. wenn der Browser ueber
            // selektierbarem Text (statt einer echten Zeile) von sich aus einen Drag startet.
            // Live als Absturz beobachtet: TypeError "ev.target.closest is not a function".
            // parentElement als Fallback normalisiert auf ein echtes Element.
            const targetEl = ev.target.nodeType === Node.ELEMENT_NODE ? ev.target : ev.target.parentElement;
            const rowEl = targetEl?.closest("[data-id]");
            const record = rowEl && this._recordForLocalId(rowEl.dataset.id);
            if (!record) {
                return;
            }
            this._draggedRecords = this._recordsForDrag(record);
            ev.dataTransfer.effectAllowed = "move";
            // Nur ein Marker, keine echten Nutzdaten - der eigentliche Zustand (welche
            // Datensaetze gezogen werden) lebt in this._draggedRecords, siehe oben. Der Marker
            // dient ausschliesslich dazu, dragover/drop unten von einem OS-Datei-Drag (Upload)
            // zu unterscheiden.
            ev.dataTransfer.setData("application/x-int-filemanager-move", "1");
            // Einheitliches Ghost-Bild unabhaengig davon, ob der Ziehstart auf dem Icon-Button
            // oder dem Name-Label gefeuert hat (Nutzerreport 2026-09-16 "Icon und Text lassen
            // sich separat draggen"): beide sind seit dem Rubberband-Fix zwei GETRENNTE
            // draggable="true"-Elemente (_makeRecordsDraggable() oben, bewusst schmal statt der
            // ganzen Zeile - siehe Kommentar dort), der Browser rendert das Standard-Ghost aber
            // per HTML5-Spec immer aus exakt dem Element, auf dem dragstart gefeuert hat - Icon-
            // Ziehstart zeigte deshalb nur das Icon, Namens-Ziehstart nur den Text.
            // DataTransfer.setDragImage(element, x, y) ueberschreibt das explizit auf ein drittes,
            // gemeinsames Element (den Flex-Wrapper, der beide umschliesst) - x/y sind die
            // Cursor-Position INNERHALB dieses Bilds, nicht absolute Koordinaten, deshalb relativ
            // zu dessen eigenem getBoundingClientRect() berechnet, damit das Ghost genau dort
            // "gehalten" wird, wo tatsaechlich gegriffen wurde (Icon-Ende vs. Textmitte fuehlen
            // sich sonst unnatuerlich an).
            const nameCellEl = rowEl.querySelector(".o_int_filemanager_name_cell");
            if (!nameCellEl) {
                return;
            }
            const rect = nameCellEl.getBoundingClientRect();
            const offsetX = ev.clientX - rect.left;
            const offsetY = ev.clientY - rect.top;
            if (this._draggedRecords.length <= 1) {
                ev.dataTransfer.setDragImage(nameCellEl, offsetX, offsetY);
                return;
            }
            // Mehrfachauswahl-Ghost mit "+N"-Zaehler (Nutzerwunsch 2026-09-17): der Ghost zeigte
            // bisher immer nur die eine physisch angefasste Zeile, obwohl _recordsForDrag() oben
            // (bei Ziehstart auf einem bereits markierten Datensatz) die ganze Selektion
            // verschiebt - irrefuehrend, man sah dem Ziehen nicht an, dass mehr als eine Datei
            // bewegt wird. Odoo selbst hat dafuer kein wiederverwendbares Vorbild (recherchiert
            // 2026-09-17: kanban_renderer.js's eigenes useSortable() hebt die Selektion beim
            // Drag-Start sogar explizit auf, statt Mehrfachauswahl-Drag ueberhaupt zu
            // unterstuetzen - kein "+N"/Zaehler-Muster irgendwo im web-Modul gefunden), daher
            // hier eine eigene Loesung, nur mit Odoos eigener .badge-Bootstrap-Klasse fuer den
            // Zaehler selbst statt eigenem Badge-Design.
            //
            // setDragImage() braucht ein tatsaechlich gerendertes Element (ein reiner, nie
            // angehaengter Knoten wird nicht gezeichnet) - ein Klon wird deshalb kurz unsichtbar
            // (position:fixed ausserhalb des Viewports) ins DOM gehaengt, direkt danach per
            // setTimeout(0) wieder entfernt (die Spezifikation erfasst das Ghost-Bild erst beim
            // naechsten Frame, ein synchrones Entfernen kaeme in manchen Browsern zu frueh).
            // Explizite width vom Original-Rect (plus etwas Platz fuer das Badge, siehe unten):
            // der Klon haengt frei ohne den umgebenden Flex-Container, dessen Breite das
            // text-truncate/ellipsis-Verhalten der Originalzelle erst erzwingt - ohne das wuerde
            // der Name im Ghost in voller, nicht abgeschnittener Laenge gerendert statt wie in
            // der echten Zeile.
            const BADGE_SPACE = 32;
            const ghost = nameCellEl.cloneNode(true);
            ghost.style.position = "fixed";
            ghost.style.top = "-9999px";
            ghost.style.left = "-9999px";
            ghost.style.width = `${rect.width + BADGE_SPACE}px`;
            ghost.style.pointerEvents = "none";
            // Normales, zusaetzliches Flex-Kind statt absolut ueberlappender Positionierung
            // (erster Versuch, live widerlegt: setDragImage() rastert das uebergebene Element
            // offenbar exakt auf seine eigene Bounding-Box - ein per negativem top/right
            // ueberlappend positioniertes Badge lag ausserhalb dieser Box und wurde komplett
            // abgeschnitten, unsichtbar). Bleibt dadurch garantiert innerhalb der (jetzt
            // extra verbreiterten) Box, kein Clipping-Risiko mehr.
            const badge = document.createElement("span");
            badge.className = "badge rounded-pill bg-primary";
            badge.textContent = `+${this._draggedRecords.length - 1}`;
            ghost.appendChild(badge);
            document.body.appendChild(ghost);
            ev.dataTransfer.setDragImage(ghost, offsetX, offsetY);
            setTimeout(() => ghost.remove(), 0);
        }

        onWindowDragOverRecord(ev) {
            if (!this._draggedRecords || !Array.from(ev.dataTransfer.types || []).includes("application/x-int-filemanager-move")) {
                return;
            }
            const target = this._dropTargetFromEvent(ev);
            const targetEl = target?.el;
            const valid = target && this._isValidDropTarget(this._draggedRecords, target);
            if (this._dropTargetEl && this._dropTargetEl !== targetEl) {
                this._dropTargetEl.classList.remove("o_int_filemanager_drop_target");
                this._dropTargetEl = null;
            }
            // Der native "nicht erlaubt"-Cursor (siehe unten) allein war live als zu unauffaellig
            // gemeldet (Nutzerreport 2026-09-12) - zusaetzlich ein rotes Gegenstueck zum gruenen
            // o_int_filemanager_drop_target, gesetzt auf jedes tatsaechlich unter dem Cursor
            // liegende, aber ungueltige Ziel (Datei statt Ordner, das gezogene Element selbst,
            // eigener Unterordner) - nicht auf leere Flaeche ohne jedes Ziel (target === null).
            if (this._invalidDropTargetEl && this._invalidDropTargetEl !== targetEl) {
                this._invalidDropTargetEl.classList.remove("o_int_filemanager_drop_invalid");
                this._invalidDropTargetEl = null;
            }
            if (!valid) {
                if (target && this._invalidDropTargetEl !== targetEl) {
                    targetEl.classList.add("o_int_filemanager_drop_invalid");
                    this._invalidDropTargetEl = targetEl;
                }
                return;
            }
            // preventDefault() ist bei HTML5-Drag&Drop zwingend, um dragover ueberhaupt als
            // gueltiges Ziel zu erlauben - ohne das zeigt der Browser automatisch den
            // "nicht erlaubt"-Cursor, genau das gewuenschte Verhalten fuer ungueltige Ziele
            // (Dateien, das gezogene Element selbst, ein eigener Unterordner), deshalb hier kein
            // eigener "ungueltig"-Zweig noetig.
            ev.preventDefault();
            ev.dataTransfer.dropEffect = "move";
            if (this._dropTargetEl !== targetEl) {
                targetEl.classList.add("o_int_filemanager_drop_target");
                this._dropTargetEl = targetEl;
            }
        }

        async onWindowDropRecord(ev) {
            if (!this._draggedRecords || !Array.from(ev.dataTransfer.types || []).includes("application/x-int-filemanager-move")) {
                return;
            }
            const records = this._draggedRecords;
            this._draggedRecords = null;
            if (this._dropTargetEl) {
                this._dropTargetEl.classList.remove("o_int_filemanager_drop_target");
                this._dropTargetEl = null;
            }
            if (this._invalidDropTargetEl) {
                this._invalidDropTargetEl.classList.remove("o_int_filemanager_drop_invalid");
                this._invalidDropTargetEl = null;
            }
            const target = this._dropTargetFromEvent(ev);
            if (!target || !this._isValidDropTarget(records, target)) {
                return;
            }
            ev.preventDefault();
            const errors = [];
            for (const record of records) {
                try {
                    await rpc("/int_filemanager/move", { path: record.data.path, dest_path: target.path });
                } catch (e) {
                    errors.push(e.data?.message || e.message);
                }
            }
            await this.reload();
            if (errors.length) {
                this.notification.add(errors.join("\n"), { type: "danger" });
            }
        }

        // Feuert immer am Ende eines Drags (egal ob erfolgreich abgeschlossen oder z.B. per Esc
        // abgebrochen) - reines Aufraeumen, damit kein Highlight/Zustand haengen bleibt, falls
        // drop aus irgendeinem Grund nicht gefeuert hat.
        onWindowDragEndRecord() {
            this._draggedRecords = null;
            if (this._dropTargetEl) {
                this._dropTargetEl.classList.remove("o_int_filemanager_drop_target");
                this._dropTargetEl = null;
            }
            if (this._invalidDropTargetEl) {
                this._invalidDropTargetEl.classList.remove("o_int_filemanager_drop_invalid");
                this._invalidDropTargetEl = null;
            }
        }

        // Rechtsklick-Kontextmenue (Nutzerwunsch 2026-09-17) - siehe usePopover()-Setup oben.
        // Nur auf einer echten Datenzeile/-karte aktiv (leere Flaeche zeigt weiterhin das
        // normale Browser-Menue, wie ueberall sonst in der App auch), damit ev.preventDefault()
        // nicht versehentlich JEDEN Rechtsklick im Dateimanager abfaengt.
        async onWindowContextMenu(ev) {
            if (!this.rootRef.el?.contains(ev.target)) {
                return;
            }
            const targetEl = ev.target.nodeType === Node.ELEMENT_NODE ? ev.target : ev.target.parentElement;
            const rowEl = targetEl?.closest("[data-id]");
            const record = rowEl && this._recordForLocalId(rowEl.dataset.id);
            if (!record) {
                return;
            }
            ev.preventDefault();
            // Explorer-Konvention: Rechtsklick auf eine BEREITS markierte Zeile innerhalb einer
            // Mehrfachauswahl laesst die ganze Auswahl unangetastet (Menue wirkt dann auf alle),
            // Rechtsklick auf eine nicht markierte Zeile waehlt stattdessen nur noch diese eine
            // aus - identische Logik wie der normale Linksklick in native_list_renderer.js's
            // onCellClicked() (dort nicht wiederverwendbar: sitzt auf der Renderer-Subklasse,
            // nicht in diesem zwischen List/Kanban geteilten Mixin).
            if (!record.selected) {
                for (const other of this.model.root.records) {
                    if (other !== record && other.selected) {
                        other.toggleSelection(false);
                    }
                }
                await record.toggleSelection(true);
            }
            const items = Object.values(this.getStaticActionMenuItems())
                .filter((item) => item.isAvailable())
                .sort((a, b) => a.sequence - b.sequence);
            if (!items.length) {
                return;
            }
            // "Virtueller" Anker statt eines echten sichtbaren Elements - usePopover() braucht
            // trotzdem ein tatsaechliches HTMLElement zum Positionieren (target: HTMLElement laut
            // popover_service.js), ein 0x0-Element exakt an den Klick-Koordinaten reicht dafuer
            // vollstaendig aus. Wird erst beim Schliessen entfernt (onClose unten), nicht sofort
            // nach dem Oeffnen - der Positionierungs-Hook kann waehrend der offenen Popover-Zeit
            // (z.B. bei Fenstergroessenaenderung) erneut auf das Ziel zugreifen wollen.
            const anchor = document.createElement("div");
            anchor.style.position = "fixed";
            anchor.style.left = `${ev.clientX}px`;
            anchor.style.top = `${ev.clientY}px`;
            document.body.appendChild(anchor);
            this._contextMenuAnchorEl = anchor;
            this.contextMenuPopover.open(anchor, {
                items,
                close: () => this.contextMenuPopover.close(),
                navigator: this.contextMenuNavigation,
            });
        }

        // Gemeinsamer Commit-Pfad fuer Dialog- UND Inline-Umbenennen (onF2Rename unten) - immer
        // derselbe authz-geprueften /int_filemanager/rename-Aufruf, nie ein ORM write() auf name
        // (siehe Kommentar bei renameState in setup()).
        async _performRename(record, name) {
            if (!name || name === record.data.name) {
                return;
            }
            try {
                // record ist hier bereits ausgewaehlt (Dialog-Weg nur ueber "Aktionen" bei
                // aktiver Auswahl erreichbar, F2-Weg per onF2Rename()-Guard "selection.length
                // === 1") - reload() unten erhaelt eine bestehende Auswahl jetzt selbst
                // automatisch ueber Reloads (inkl. den spaeteren, vom eigenen Watcher
                // ausgeloesten Bus-Reload) hinweg, siehe dortiger Kommentar. Kein eigener
                // Reselektions-Code mehr noetig.
                await rpc("/int_filemanager/rename", { path: record.data.path, new_name: name });
                await this.reload();
            } catch (e) {
                this.notification.add(e.data?.message || e.message, { type: "danger" });
            }
        }

        onRename(record) {
            this.dialog.add(IntTextInputDialog, {
                title: _t("Umbenennen"),
                label: _t("Neuer Name"),
                value: record.data.name,
                confirmLabel: _t("Umbenennen"),
                confirm: (name) => this._performRename(record, name),
            });
        }

        // F2 auf genau einer ausgewaehlten Zeile/Karte - mehrere/keine Auswahl ignoriert den
        // Tastendruck absichtlich (kein sinnvolles "Umbenennen" fuer 0 oder >1 Datensaetze). Das
        // eigentliche <input> lebt in name_icon_field.js (siehe env.filemanagerRename-Kommentar
        // in setup()) - hier wird nur der Editier-Zustand gesetzt, keine DOM-Arbeit noetig.
        onF2Rename() {
            const selection = this.model.root.selection;
            if (selection.length !== 1) {
                return;
            }
            const record = selection[0];
            this.renameState.recordId = record.resId;
            this.renameState.value = record.data.name;
        }

        // Von name_icon_field.js ueber env.filemanagerRename.commit() aufgerufen (Blur oder
        // Enter dort). Sucht den Record ueber resId statt eine Referenz durchzureichen, weil das
        // Feld-Widget nur die env-Werte kennt, keine Controller-internen Objekte. recordId wird
        // sofort geleert (nicht erst nach der RPC), damit das Feld sofort zurueck auf die
        // schreibgeschuetzte Text-Anzeige wechselt, statt bis zum Server-Antwort editierbar zu
        // bleiben.
        async _commitRename(name) {
            const recordId = this.renameState.recordId;
            this.renameState.recordId = null;
            if (!recordId) {
                return;
            }
            const record = this.model.root.records.find((r) => r.resId === recordId);
            if (!record) {
                return;
            }
            await this._performRename(record, name);
        }

        onLinkRecord(record) {
            this.dialog.add(IntLinkRecordDialog, {
                path: record.data.path,
                metaId: record.resId,
                onSaved: () => this.reload(),
            });
        }

        // Manueller Auslöser fuer bereits bestehende Dateien (kein automatischer Backfill,
        // Nutzerentscheidung 2026-09-05 - siehe docs/int_filemanager_paperoffice_recherche.md,
        // Baustein 1) - derselbe interaktive Pfad A wie direkt nach einem Drag&Drop-Upload, nur
        // manuell fuer eine ausgewaehlte Bestandsdatei ausgeloest statt automatisch. Wartet seit
        // 2026-09-07 (Mehrfachauswahl-Nutzerfeedback) selbst auf das Schliessen des Dialogs
        // (onClose-Option, gleiches Wartemuster wie _analyzeUploadedFiles unten) - noetig, damit
        // onAnalyzeSelected() mehrere Dateien nacheinander statt gleichzeitig abfragen kann.
        // Fuer den Einzelaufruf (Aktionsmenue mit genau einer Auswahl, neuer
        // analyze_button_widget.js-Button) aendert das Warten selbst nichts, da bisher niemand
        // auf das zurueckgegebene Promise gewartet hat.
        async onAnalyzeDocument(record) {
            let result;
            try {
                result = await rpc("/int_filemanager/analyze_document", { path: record.data.path });
            } catch (e) {
                this.notification.add(e.data?.message || e.message, { type: "danger" });
                return;
            }
            if (!result.res_id) {
                this.notification.add(_t("Für diesen Dateityp ist keine Erkennung verfügbar."), { type: "warning" });
                return;
            }
            await new Promise((resolve) => {
                this.dialog.add(
                    IntDocumentReviewDialog,
                    {
                        fileName: record.data.name,
                        resId: result.res_id,
                        suggestion: result,
                        onSaved: () => this.reload(),
                    },
                    { onClose: resolve }
                );
            });
        }

        // Mehrfachauswahl (2026-09-07, Nutzerfeedback "aktuell nicht sehr effizient") - dieselbe
        // Sequenziell-Dialog-Schleife wie _analyzeUploadedFiles() fuer Mehrfach-Uploads, nur fuer
        // eine manuelle Auswahl bestehender Dateien statt gerade hochgeladener. Ordner und nicht
        // unterstuetzte Dateitypen werden aus der Auswahl still uebersprungen (der Server bleibt
        // ohnehin die einzige Quelle der Wahrheit dafuer, was unterstuetzt ist - isFulltextSupported
        // hier nur zur Vermeidung unnoetiger RPCs).
        async onAnalyzeSelected() {
            const records = this.model.root.selection.filter(
                (r) => !r.data.is_dir && isFulltextSupported(r.data.name)
            );
            for (const record of records) {
                await this.onAnalyzeDocument(record);
            }
        }

        // Freigeben - oeffnet dieselbe action_filemanager_file_share (ir.actions.act_window,
        // target="new") wie legacy_ui/filemanager_action.js, nur ueber this.actionService statt
        // einer eigenen Dialog-Komponente: mit echten ORM-Records braucht es keinen eigenen
        // Custom-Dialog mehr, die bestehende Action reicht unveraendert. Kein neuer Backend-Code -
        // action_generate_share_token()/action_revoke_share_token() (filemanager_file.py) und die
        // Portal-Freigabe-Logik sind bereits vollstaendig fertig und getestet.
        onShare(record) {
            this.actionService.doAction("int_filemanager.action_filemanager_file_share", {
                props: { resId: record.resId },
                onClose: () => this.reload(),
            });
        }

        onDeleteSelected() {
            const records = this.model.root.selection;
            const count = records.length;
            this.dialog.add(ConfirmationDialog, {
                title: _t("Löschen bestätigen"),
                body: _t("%s wirklich löschen?", count === 1 ? _t("1 Eintrag") : _t("%s Einträge", count)),
                confirmLabel: _t("Löschen"),
                confirmClass: "btn-danger",
                confirm: async () => {
                    const errors = [];
                    for (const record of records) {
                        try {
                            await rpc("/int_filemanager/delete", { path: record.data.path });
                        } catch (e) {
                            errors.push(e.data?.message || e.message);
                        }
                    }
                    await this.reload();
                    if (errors.length) {
                        this.notification.add(errors.join("\n"), { type: "danger" });
                    }
                },
            });
        }

        // -----------------------------------------------------------------
        // selection-dependent action menu ("Aktionen" dropdown) - replaces the
        // native export/duplicate/archive/unarchive entries, none of which are
        // meaningful for filesystem-backed records (native "delete" stays
        // disabled via delete="false" in the arch: ORM unlink() would only
        // remove the index row, not the file on disk).
        // -----------------------------------------------------------------

        getStaticActionMenuItems() {
            const selection = this.model.root.selection;
            return {
                int_link: {
                    isAvailable: () => selection.length === 1,
                    sequence: 10,
                    icon: "fa fa-link",
                    description: _t("Kontakt verknüpfen"),
                    callback: () => this.onLinkRecord(selection[0]),
                },
                int_share: {
                    // action_generate_share_token() (filemanager_file.py) already rejects
                    // folders server-side (siehe TestShareToken.test_generate_rejects_folders) -
                    // is_dir hier zusaetzlich ausgeblendet, damit der Eintrag gar nicht erst zum
                    // Fehlschlagen einlaedt, statt nur auf die Server-Validierung zu vertrauen.
                    isAvailable: () => selection.length === 1 && !selection[0].data.is_dir,
                    sequence: 15,
                    icon: "fa fa-share-alt",
                    description: _t("Freigeben"),
                    callback: () => this.onShare(selection[0]),
                },
                int_rename: {
                    isAvailable: () => selection.length === 1,
                    sequence: 20,
                    icon: "fa fa-pencil",
                    description: _t("Umbenennen"),
                    callback: () => this.onRename(selection[0]),
                },
                int_open_local: {
                    isAvailable: () => selection.length === 1 && extOf(selection[0].data.name) in OFFICE_PROTOCOL,
                    sequence: 30,
                    icon: "fa fa-external-link",
                    description: _t("Lokal öffnen"),
                    callback: () => this.onOpenLocal(selection[0]),
                },
                int_analyze: {
                    // Mehrfachauswahl seit 2026-09-07 (Nutzerfeedback) - verfuegbar sobald
                    // MINDESTENS eine ausgewaehlte Zeile/Karte in Frage kommt, nicht mehr nur bei
                    // Einzelauswahl. onAnalyzeSelected() filtert Ordner/nicht unterstuetzte Typen
                    // selbst heraus.
                    isAvailable: () => selection.some((r) => !r.data.is_dir && isFulltextSupported(r.data.name)),
                    sequence: 35,
                    icon: "fa fa-magic",
                    description: _t("Werte erkennen"),
                    callback: () => this.onAnalyzeSelected(),
                },
                int_delete: {
                    isAvailable: () => selection.length > 0,
                    sequence: 90,
                    icon: "fa fa-trash-o",
                    class: "text-danger",
                    description: _t("Löschen"),
                    callback: () => this.onDeleteSelected(),
                },
            };
        }
    };
}
