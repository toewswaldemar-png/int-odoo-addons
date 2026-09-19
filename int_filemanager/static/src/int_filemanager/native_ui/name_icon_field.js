/** @odoo-module **/

import { Component, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Odoos eigenes Mimetype-Icon-Set (web/static/img/mimetypes/*.svg, ausgeliefert mit dem
// web-Modul) wird rein ueber CSS-Attribut-Selektoren auf data-mimetype angesprochen
// (web/static/src/scss/mimetypes.scss, z.B. "&[data-mimetype*='spreadsheet']") - ein
// Teilstring reicht, kein echter MIME-Type noetig. Deshalb hier nur grobe, clientseitig aus
// der Dateiendung abgeleitete Platzhalterwerte, kein Backend-Feld/keine Migration noetig
// (Performance-Ueberlegung siehe docs/int_filemanager_native_ui.md).
const EXT_TO_PSEUDO_MIMETYPE = {
    pdf: "application/pdf",
    doc: "application/msword",
    docx: "application/msword",
    odt: "application/msword",
    rtf: "application/msword",
    xls: "application/vnd.ms-excel",
    xlsx: "application/vnd.ms-excel",
    ods: "application/vnd.ms-excel",
    csv: "text/csv",
    ppt: "application/vnd.ms-powerpoint",
    pptx: "application/vnd.ms-powerpoint",
    odp: "application/vnd.ms-powerpoint",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    png: "image/png",
    gif: "image/gif",
    webp: "image/webp",
    bmp: "image/bmp",
    svg: "image/svg+xml",
    mp4: "video/mp4",
    webm: "video/webm",
    avi: "video/avi",
    mov: "video/quicktime",
    mp3: "audio/mpeg",
    wav: "audio/wav",
    flac: "audio/flac",
    ogg: "audio/ogg",
    zip: "application/zip",
    rar: "application/x-rar",
    "7z": "application/x-7z-compressed",
    tar: "application/x-tar",
    gz: "application/gzip",
    txt: "text/plain",
    md: "text/plain",
    log: "text/plain",
    json: "text/plain",
    html: "text/html",
    htm: "text/html",
    css: "text/css",
};

function pseudoMimetypeFor(name) {
    const ext = (name || "").split(".").pop().toLowerCase();
    return EXT_TO_PSEUDO_MIMETYPE[ext] || "";
}

// Ordner-Icon bewusst NICHT ueber das o_image/mimetypes-Set geloest (kein "folder.svg"
// darin - geprueft, das Set deckt nur Anhang-/Datei-Mimetypes ab, keine Verzeichnisse) -
// stattdessen dasselbe fa-folder wie im Ordnerbaum links (filemanager_file_search.xml,
// searchpanel icon="fa-folder"), fuer visuelle Konsistenz.
export class IntFilemanagerNameField extends Component {
    static template = "int_filemanager.NameField";
    static props = { ...standardFieldProps };

    setup() {
        // Inline-Umbenennen per F2 (filemanager_controller_mixin.js: env.filemanagerRename,
        // siehe dortigen Kommentar in setup() zur Vorgeschichte/Begruendung gegen ein
        // separates ueberlagerndes <input>). Fokus+Alles-Markieren beim Eintritt in den
        // Editier-Zustand, analog zum fruehreren renameInputRef-useEffect im Controller.
        //
        // useState() HIER nochmal auf dem bereits reaktiven state-Objekt aufgerufen (nicht nur
        // ueber env.filemanagerRename.state gelesen) - Pflicht, nicht Kosmetik: Owls reactive()
        // bindet Aenderungsbenachrichtigungen fest an die Callback-Funktion, die beim Erzeugen
        // des Proxys per useState() uebergeben wurde (im Controller: dessen eigenes render()).
        // Ein bloss lesender Zugriff auf einen fremden reaktiven Proxy - ohne ihn selbst nochmal
        // durch useState()/reactive() zu schicken - registriert diese Komponente NICHT als
        // Beobachter; nur der Controller wuerde bei einer Aenderung neu rendern, nie diese
        // Feld-Zelle. Live als Bug gefunden 2026-09-14 (per Debug-Logging bestaetigt: nach einer
        // Aenderung von recordId feuerte fuer KEINE Zeile ein erneuter Render/Effect).
        this.renameState = useState(this.env.filemanagerRename.state);
        this.renameInputRef = useRef("renameInput");
        // Auswahlbereich-Zyklus fuer wiederholtes F2 (Windows-Explorer-Konvention, Nutzerwunsch
        // 2026-09-14 - identisches Muster wie web-filemanagers useInlineRename.ts): 0 = voller
        // Name, 1 = nur Basisname (Startzustand beim Oeffnen), 2 = nur Endung. Reiner
        // Instanz-Zustand statt useState() - betrifft nur die Textauswahl INNERHALB eines
        // bereits offenen Rename-Inputs, kein Rendering haengt davon ab.
        this.selectionMode = 1;
        useEffect(
            () => {
                if (this.isRenaming && this.renameInputRef.el) {
                    this.selectionMode = 1;
                    this.renameInputRef.el.focus();
                    this._applySelection();
                }
            },
            () => [this.isRenaming]
        );
    }

    // Vergleich ueber resId, nicht Objektreferenz: das Feld-Widget bekommt sein eigenes
    // props.record vom Owl-Renderer, nicht zwingend dasselbe Objekt wie
    // model.root.selection[0] im Controller, auch wenn beide dieselbe DB-Zeile meinen.
    get isRenaming() {
        return this.renameState.recordId === this.props.record.resId;
    }

    // Setzt den Auswahlbereich im Input gemaess this.selectionMode. dot > 0 (nicht >= 0), damit
    // ein fuehrender Punkt (".gitignore") nicht als Endungstrenner zaehlt - ohne Endung (Ordner
    // oder Datei ohne ".") macht der Modus keinen Unterschied, dann immer voller Name. Richtung
    // "backward" haelt bei einer bei 0 beginnenden Auswahl den ANFANG des Texts sichtbar (manche
    // Browser scrollen Inputs sonst zum Selektionsende) - verhindert, dass der Namensanfang bei
    // langen Dateinamen aus dem sichtbaren Bereich wegscrollt.
    _applySelection() {
        const el = this.renameInputRef.el;
        const name = this.env.filemanagerRename.state.value;
        const dot = name.lastIndexOf(".");
        const hasExt = !this.isDir && dot > 0;
        let start, end, direction;
        if (!hasExt || this.selectionMode === 0) {
            start = 0;
            end = name.length;
            direction = "backward";
        } else if (this.selectionMode === 1) {
            start = 0;
            end = dot;
            direction = "backward";
        } else {
            start = dot + 1;
            end = name.length;
            direction = "forward";
        }
        el.setSelectionRange(start, end, direction);
        el.scrollLeft = 0;
    }

    onRenameKeydown(ev) {
        // Verhindert, dass Odoos eigene Listen-/Kanban-Tastaturnavigation (Pfeiltasten,
        // Entf fuer Zeilen-Aktionen o.ae.) waehrend des Tippens im Inline-Input mitfeuert -
        // beim fruehreren, ausserhalb der Zeile ueberlagernden <input> war das kein Thema,
        // hier sitzt das Feld jetzt aber wirklich innerhalb der Zeile im DOM.
        ev.stopPropagation();
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.renameInputRef.el.blur();
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.env.filemanagerRename.cancel();
        } else if (ev.key === "F2") {
            // stopPropagation() oben verhindert, dass dieses Event je den window-Listener in
            // filemanager_controller_mixin.js erreicht (der dort sein eigenes preventDefault
            // haette) - ohne eigenes preventDefault HIER bekommt der Browser also ein
            // zweites F2 waehrend des Renamens ungehindert zu sehen und oeffnet seine eigene
            // Befehlsliste (live beobachtet: F2/F2/F2/F2 schaltete Rename/Browserfenster um).
            // Erneutes F2 verlaesst den Rename-Modus nicht, sondern schaltet nur den
            // Auswahlbereich weiter (Windows-Explorer-Konvention, siehe _applySelection()).
            ev.preventDefault();
            this.selectionMode = (this.selectionMode + 1) % 3;
            this._applySelection();
        }
    }

    // Blur committet (Explorer-Verhalten: Wegklicken uebernimmt den Namen, nicht verwirft
    // ihn) - Escape oben ruft cancel() VOR dem Blur auf, der dadurch ausgeloeste Aufruf hier
    // findet dann kein aktives recordId mehr vor (siehe _commitRename im Controller).
    onRenameBlur() {
        this.env.filemanagerRename.commit(this.env.filemanagerRename.state.value);
    }

    get isDir() {
        return this.props.record.data.is_dir;
    }

    get value() {
        return this.props.record.data[this.props.name];
    }

    // Pfad-Unterzeile bei aktiver Suche (Nutzerwunsch 2026-09-16, auf Desktop erweitert
    // 2026-09-16). Reine Ordnernavigation (Baum/Breadcrumb/Zeilenklick) laeuft ausschliesslich
    // ueber env.searchModel.setIntFilemanagerFolderPath() (siehe native_search_model.js) und
    // ruehrt env.searchModel.query nie an - "query" enthaelt ausschliesslich echte
    // Sucheintraege/Filter, ist also ein sauberes, von der reinen Ordnerposition unabhaengiges
    // Signal fuer "Suchergebnis". Urspruenglich auf env.isSmall beschraenkt, weil bei normaler
    // Ordnernavigation der Pfad redundant zum Breadcrumb ist - das gilt bei aktiver Suche aber
    // unabhaengig von der Fensterbreite gleichermassen (Suchergebnisse ueber mehrere Ordner
    // hinweg brauchen die Einordnung auch auf Desktop).
    get showPath() {
        return Boolean(this.env.searchModel.query.length);
    }

    get parentPath() {
        const path = this.props.record.data.path || "";
        const idx = path.lastIndexOf("/");
        return idx === -1 ? "" : path.slice(0, idx);
    }

    get pseudoMimetype() {
        return pseudoMimetypeFor(this.value);
    }
}

export const intFilemanagerNameField = {
    component: IntFilemanagerNameField,
    supportedTypes: ["char"],
    // Odoos "Magic Column Widths" (column_width_hook.js) berechnet Spaltenbreiten per JS und
    // SCHRUMPFT Feldspalten bei Platzmangel aktiv auf ein hartkodiertes Minimum - ohne eigenen
    // Eintrag in FIELD_WIDTHS faellt das auf DEFAULT_MIN_WIDTH (80px) zurueck, was jede
    // CSS-min-width auf der Zelle bei jedem Neuberechnen wieder ueberschreibt (live so
    // gefunden 2026-09-14, Nutzerreport "Name-Spalte generell zu schmal"). listViewWidth als
    // Array (nicht einzelne Zahl) setzt NUR minWidth, kein maxWidth - identisches Muster wie
    // Odoos eigenes "char: [80]" in FIELD_WIDTHS, siehe getWidthSpecs() dort. Spalte darf bei
    // viel Platz also weiterhin wachsen, wird aber nicht mehr unter 400px zusammengedrueckt.
    //
    // Als Funktion statt starrem Array (Nutzerwunsch 2026-09-16: Name-Spalte soll auf Mobil
    // exakt die Displaybreite einnehmen, die anderen Spalten bleiben erhalten statt
    // ausgeblendet zu werden) - column_width_hook.js:323-327 wertet listViewWidth explizit als
    // Funktion aus, falls vorhanden ("typeof width === 'function'"), und berechnet laut
    // eigenem Kommentar im Hook bei jedem Fenster-Resize neu ("forget the computed widths and
    // start over"). window.innerWidth statt env.isSmall, weil dieser Registry-Eintrag rein
    // statisch ist (kein Komponenten-this/env verfuegbar) - 768px ist derselbe isSmall-
    // Schwellwert, den Odoo selbst an anderer Stelle nutzt (siehe native_list_view.scss). Auf
    // Mobil bekommt die Spalte dadurch mindestens die volle Bildschirmbreite als minWidth und
    // (kein maxWidth) waechst nicht darueber hinaus - die anderen Spalten bleiben im DOM und
    // in der Tabelle vorhanden, ruecken aber ausserhalb des sichtbaren Bereichs, erreichbar per
    // horizontalem Scrollen (native_list_view.scss macht die Liste dafuer bereits mobil
    // scrollbar).
    listViewWidth: () => (window.innerWidth < 768 ? [window.innerWidth] : [400]),
};

registry.category("fields").add("int_filemanager_name", intFilemanagerNameField);
