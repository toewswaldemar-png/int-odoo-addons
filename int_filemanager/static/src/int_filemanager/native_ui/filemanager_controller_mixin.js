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
import { onMounted, onWillUnmount, useExternalListener, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useBus, useService } from "@web/core/utils/hooks";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { IntTextInputDialog } from "../shared/text_input_dialog";
import { IntLinkRecordDialog } from "../shared/link_record_dialog";
import { IntTextEditorDialog } from "./text_editor_dialog";
import { IntDocumentReviewDialog } from "./document_review_dialog";

// Video ist nativ im FileViewer verdrahtet (file_viewer.js/.xml: state.file.isVideo -> echtes
// <video controls>) - hier nur an dessen bereits vorhandene Faehigkeit angeschlossen, nichts
// Neues gebaut. Auf die vier Formate beschraenkt, die Browser ohne Zusatz-Codec nativ abspielen
// (mov u.ae. bewusst weggelassen - haeufig kein nativer Chrome/Firefox-Support, wuerde nur einen
// leeren Player zeigen).
const VIDEO_EXTENSIONS = new Set(["mp4", "webm", "ogv"]);
const VIDEO_MIME_TYPES = { mp4: "video/mp4", webm: "video/webm", ogv: "video/ogg" };

// Reine Textformate oeffnen direkt den Editor (IntTextEditorDialog) statt der readonly
// FileViewer-Vorschau - deshalb bewusst NICHT Teil von PREVIEWABLE_EXTENSIONS (das wuerde ueber
// onPreview() die alte iframe-Vorschau ausloesen, die der Editor ersetzt).
const TEXT_EDIT_EXTENSIONS = new Set(["txt", "csv", "log", "md", "json"]);

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
            useExternalListener(window, "dragleave", this.onWindowDragLeave);
            useExternalListener(window, "dragover", (ev) => ev.preventDefault());
            useExternalListener(window, "drop", this.onWindowDrop);

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

        onRename(record) {
            this.dialog.add(IntTextInputDialog, {
                title: _t("Umbenennen"),
                label: _t("Neuer Name"),
                value: record.data.name,
                confirmLabel: _t("Umbenennen"),
                confirm: async (name) => {
                    if (name === record.data.name) {
                        return;
                    }
                    try {
                        await rpc("/int_filemanager/rename", { path: record.data.path, new_name: name });
                        await this.reload();
                    } catch (e) {
                        this.notification.add(e.data?.message || e.message, { type: "danger" });
                    }
                },
            });
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
