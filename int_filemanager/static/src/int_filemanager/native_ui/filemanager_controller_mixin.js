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
import { useBus, useService } from "@web/core/utils/hooks";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { IntTextInputDialog } from "../shared/text_input_dialog";
import { IntLinkRecordDialog } from "../shared/link_record_dialog";
import { IntTextEditorDialog } from "./text_editor_dialog";
import { IntDocumentReviewDialog } from "./document_review_dialog";
import { IntZipContentsDialog } from "./zip_contents_dialog";

// Video ist nativ im FileViewer verdrahtet (file_viewer.js/.xml: state.file.isVideo -> echtes
// <video controls>) - hier nur an dessen bereits vorhandene Faehigkeit angeschlossen, nichts
// Neues gebaut. Auf die vier Formate beschraenkt, die Browser ohne Zusatz-Codec nativ abspielen
// (mov u.ae. bewusst weggelassen - haeufig kein nativer Chrome/Firefox-Support, wuerde nur einen
// leeren Player zeigen).
const VIDEO_EXTENSIONS = new Set(["mp4", "webm", "ogv"]);
const VIDEO_MIME_TYPES = { mp4: "video/mp4", webm: "video/webm", ogv: "video/ogg" };

// Audio ist NICHT nativ im FileViewer verdrahtet - anders als bei Video gibt es dort keinen
// isAudio-Zweig (am Odoo-19-Quellcode geprueft: web/core/file_viewer/file_viewer.js/.xml kennt
// nur isImage/isPdf/isText/isVideo/isUrlYoutube). Deshalb file_viewer_patch.xml (t-inherit
// mode="extension" gegen web.FileViewer, gleiches Muster wie mail/static/src/chatter/web/
// form_controller.xml es fuer web.FormView nutzt) - patcht die geteilte Komponente selbst
// additiv um einen <audio>-Zweig, statt einen eigenen Player zu bauen. Bewusst ohne "wma" -
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

const PREVIEWABLE_EXTENSIONS = new Set([
    "pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", ...VIDEO_EXTENSIONS, ...AUDIO_EXTENSIONS,
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
            this.dialog = useService("dialog");
            this.notification = useService("notification");
            this.fileUpload = useService("file_upload");
            this.actionService = useService("action");
            this.busService = useService("bus_service");
            this.fileViewer = useFileViewer();
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
                if (ev.key !== "F2") {
                    return;
                }
                // preventDefault() VOR der Editable-Pruefung, nicht danach: sonst bekommt der
                // Browser beim zweiten F2-Druck (Fokus liegt schon im eigenen Rename-Input) doch
                // wieder die Taste zu sehen und oeffnet seine eigene Befehlsliste - live so
                // beobachtet (F2, F2, F2, F2 schaltete abwechselnd Rename/Edge-Fenster um).
                // isEditable verhindert nur das erneute AUSLOESEN von onF2Rename() waehrend des
                // Tippens, nicht mehr das preventDefault selbst.
                ev.preventDefault();
                const active = document.activeElement;
                const isEditable =
                    active &&
                    (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable);
                if (isEditable) {
                    return;
                }
                this.onF2Rename();
            });
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
            onMounted(() => this._makeRecordsDraggable());
            onPatched(() => this._makeRecordsDraggable());
            useExternalListener(window, "dragstart", this.onWindowDragStartRecord);
            useExternalListener(window, "dragover", this.onWindowDragOverRecord);
            useExternalListener(window, "drop", this.onWindowDropRecord);
            useExternalListener(window, "dragend", this.onWindowDragEndRecord);

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
            useExternalListener(window, "resize", () => {
                if (this.chatterState.open) {
                    this._measureChatterPanelTop();
                }
            });

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
                    const section = this.getCategorySection();
                    if (section) {
                        this.env.searchModel.toggleCategoryValue(section.id, false);
                    }
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

            // Navigation (Zeilenklick/Kartenklick, Breadcrumb, SearchPanel-Baum) laeuft ab jetzt
            // AUSSCHLIESSLICH ueber env.searchModel.toggleCategoryValue() - siehe openRecord()/
            // updateBreadcrumbs() unten. Kein eigenes this.model.load({domain:[...]}) fuer
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

        getCategorySection() {
            const [section] = this.env.searchModel.getSections(
                (s) => s.type === "category" && s.fieldName === "parent_id"
            );
            return section;
        }

        onToggleChatterPanel() {
            this.chatterState.open = !this.chatterState.open;
            if (this.chatterState.open) {
                this._measureChatterPanelTop();
            }
        }

        _measureChatterPanelTop() {
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
                const section = this.getCategorySection();
                this.env.searchModel.toggleCategoryValue(section.id, record.resId);
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
            // Kein Domain-Argument: this.model.config behaelt die zuletzt von useModel() aus
            // searchModel.domain uebernommene Domain bei (_getNextConfig merged nur fehlende
            // Parameter) - ein Refresh nach Mutation aendert also nichts am aktuellen Ordner.
            await this.model.load();
            // model.load() aktualisiert nur die Inhaltsliste - der SearchPanel-Ordnerbaum hat
            // einen eigenen Cache (searchModel.sections), den das nicht anstoesst. Odoos eigene
            // SearchModel._reloadSections() (web/static/src/search/search_model.js) refetcht eine
            // Kategorie nur bei enableCounters (hier bewusst deaktiviert, siehe
            // filemanager_file.py: search_panel_select_range) oder geaenderter Such-Domain -
            // reines mkdir/move/rename/delete aendert die Domain nicht, der Baum bliebe sonst auf
            // dem Stand des letzten vollen Seitenladens stehen (live beobachtet: neu erstellte/
            // verschobene Unterordner fehlten im Baum bzw. hingen faelschlich auf Wurzelebene,
            // bis ein Hard-Reload den ungated Erstlade-Pfad erneut durchlief). Fix: denselben
            // ungated Fetch+Notify-Aufruf, den SearchModel.load() beim Erstladen macht, hier
            // direkt nachstellen.
            const searchModel = this.env.searchModel;
            await searchModel._fetchSections(searchModel.categories, searchModel.filters);
            searchModel.trigger("update");
        }

        // Baut env.config.breadcrumbs UND this.currentPath aus der Vorfahrenkette des aktuell
        // gewaehlten SearchPanel-Werts nach - dieselben Daten (values/parentId), die der Baum links
        // ohnehin schon geladen hat, keine eigene, vom Model unabhaengige Pfad-Buchhaltung mehr.
        // this.currentPath wird NICHT fuer die Listen-/Kanban-Domain verwendet (die kommt
        // ausschliesslich aus searchModel.domain via useModel) - einziger Zweck ist der "path"-
        // Parameter der bestehenden authz-geprueften mkdir/upload-Routen (siehe unten), die den
        // literalen Dateisystempfad brauchen, nicht die parent_id. display_name je Ordner ist hier
        // einfach dessen "name"-Feld (kein name_get-Override auf dem Modell) - Aneinanderreihen der
        // Kette ergibt exakt denselben Pfadstring wie das "path"-Feld selbst.
        updateBreadcrumbs() {
            const section = this.getCategorySection();
            const crumbs = this.env.config.breadcrumbs;
            crumbs.length = this.rootBreadcrumbCount;
            if (!section) {
                this.currentPath = "";
                return;
            }
            const chain = [];
            let id = section.activeValueId;
            while (id) {
                const value = section.values.get(id);
                if (!value) {
                    break;
                }
                chain.unshift(value);
                id = value.parentId;
            }
            this.currentPath = chain.map((value) => value.display_name).join("/");
            for (const value of chain) {
                crumbs.push({
                    jsId: `int_filemanager_crumb_${value.id}`,
                    name: value.display_name,
                    isFormView: false,
                    url: "#",
                    onSelected: () => this.env.searchModel.toggleCategoryValue(section.id, value.id),
                });
            }
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
            const isAudio = AUDIO_EXTENSIONS.has(ext);
            return {
                path,
                name: record.data.name,
                downloadUrl,
                isImage: PREVIEWABLE_EXTENSIONS.has(ext) && !isPdf && !isVideo && !isAudio,
                isPdf,
                isVideo,
                isAudio,
                mimetype: isVideo ? VIDEO_MIME_TYPES[ext] : isAudio ? AUDIO_MIME_TYPES[ext] : undefined,
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
        _makeRecordsDraggable() {
            const els = this.rootRef.el?.querySelectorAll("[data-id]") || [];
            for (const el of els) {
                el.draggable = true;
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
        // Seitenleisten-Ordnerbaum liefert nie ein echtes Record-Objekt (nur SearchPanel-
        // Kategoriewerte, siehe dort), deshalb diese gemeinsame, schlankere Form fuer beide
        // Zielarten.
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

        // Baut den literalen Zielpfad aus der Vorfahrenkette eines SearchPanel-Kategoriewerts -
        // dieselbe Technik wie updateBreadcrumbs() oben (dort bewusst nicht wiederverwendet, um
        // die dort bereits live gehaertete Breadcrumb-Logik nicht anzufassen), nur hier fuer
        // einen BELIEBIGEN Baumeintrag statt zwingend den aktuell aktiven. valueId===false (die
        // Wurzel/"Alle") liefert korrekt "" (leere Kette), wie an anderer Stelle auch (z.B.
        // this.currentPath bei geoeffneter Wurzel).
        _pathForCategoryValue(section, valueId) {
            const chain = [];
            let id = valueId;
            while (id) {
                const value = section.values.get(id);
                if (!value) {
                    break;
                }
                chain.unshift(value);
                id = value.parentId;
            }
            return chain.map((value) => value.display_name).join("/");
        }

        // Vereinheitlicht die zwei moeglichen Drop-Ziel-Arten auf dieselbe schlanke Form
        // ({el, resId, path, isDir}): eine Zeile/Karte der aktuell offenen Ansicht (natives
        // data-id, siehe oben) ODER ein Eintrag im Seitenleisten-Ordnerbaum
        // (data-int-filemanager-value-id, per search_panel_patch.xml additiv auf das geteilte
        // web.SearchPanel.Category-Template aufgebracht - der Baum kann JEDEN Ordner im System
        // zeigen, nicht nur die der aktuell offenen Ansicht, deshalb kein echtes Record-Objekt
        // dafuer verfuegbar). Gibt null zurueck, wenn unter dem Mauszeiger keins von beidem
        // liegt oder der Kategoriewert zu keiner unserer eigenen SearchPanel-Sections gehoert.
        _dropTargetFromEvent(ev) {
            const rowEl = ev.target.closest("[data-id]");
            if (rowEl) {
                const record = this._recordForLocalId(rowEl.dataset.id);
                if (record) {
                    return { el: rowEl, resId: record.resId, path: record.data.path, isDir: record.data.is_dir };
                }
            }
            const treeEl = ev.target.closest("[data-int-filemanager-value-id]");
            if (treeEl) {
                const section = this.getCategorySection();
                const rawId = treeEl.dataset.intFilemanagerValueId;
                // "root" statt "false": search_panel_patch.xml mappt valueId===false explizit auf
                // diesen String, weil Owls kompiliertes Template das Attribut fuer den rohen
                // false-Wert live nachweisbar komplett wegliess (siehe Kommentar dort) - "root"
                // ist als String garantiert nie leer/falsy und uebersteht das unbeschadet.
                if (section && rawId === "root") {
                    // Die Wurzel ("Alle") ist nur ein Sentinel (category.rootIds enthaelt sie,
                    // category.values als Map aber nicht - live gegen search_model.js geprueft:
                    // dort wird ausschliesslich ueber echte, aus dem groupby gelesene Datensaetze
                    // befuellt) - deshalb hier ohne Map-Lookup direkt als gueltiges Ziel mit
                    // leerem Pfad behandelt, statt wie unten ueber section.values.get() zu gehen.
                    return { el: treeEl, resId: false, path: "", isDir: true };
                }
                const valueId = section ? parseInt(rawId, 10) : null;
                const value = section && section.values.get(valueId);
                if (value) {
                    return { el: treeEl, resId: valueId, path: this._pathForCategoryValue(section, valueId), isDir: true };
                }
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

        // Gemeinsamer Commit-Pfad fuer Dialog- UND Inline-Umbenennen (onF2Rename unten) - immer
        // derselbe authz-geprueften /int_filemanager/rename-Aufruf, nie ein ORM write() auf name
        // (siehe Kommentar bei renameState in setup()).
        async _performRename(record, name) {
            if (!name || name === record.data.name) {
                return;
            }
            try {
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
