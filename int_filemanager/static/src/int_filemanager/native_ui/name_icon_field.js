/** @odoo-module **/

import { Component, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

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
        this.orm = useService("orm");
        this.actionService = useService("action");

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
        useEffect(
            () => {
                if (this.isRenaming && this.renameInputRef.el) {
                    this.renameInputRef.el.focus();
                    this.renameInputRef.el.select();
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
        }
    }

    // Blur committet (Explorer-Verhalten: Wegklicken uebernimmt den Namen, nicht verwirft
    // ihn) - Escape oben ruft cancel() VOR dem Blur auf, der dadurch ausgeloeste Aufruf hier
    // findet dann kein aktives recordId mehr vor (siehe _commitRename im Controller).
    onRenameBlur() {
        this.env.filemanagerRename.commit(this.env.filemanagerRename.state.value);
    }

    // Ersetzt die vorherige eigene "Details öffnen"-Spalte (Pfeil-Button, action_open_form) -
    // Klick auf das Icon selbst oeffnet jetzt das Formular (Nutzerwunsch 2026-09-11). Kein
    // <button type="object"> moeglich, das braucht ein direktes Arch-Element der View (siehe
    // Begruendung in analyze_button_widget.js) - stattdessen von Hand per orm.call() +
    // actionService nachgebaut, exakt das, was Odoos Button-Compiler bei type="object"
    // automatisch erledigt. ev.stopPropagation() noetig fuer die Kanban-Ansicht (kein
    // automatisches oe_kanban_action-Exempt fuer ein <button> innerhalb eines Feld-Widgets
    // statt eines direkten Arch-Buttons, siehe wieder analyze_button_widget.js) - fuer die
    // Liste reicht das rohe <button>-Element im Template bereits allein
    // (list_renderer.js prueft ev.target.closest("button")). orm.call()-Argumente: das erste
    // Positionsargument einer Modellmethode ist die ids-LISTE, nicht die nackte ID - live als
    // Bug gefunden (TypeError serverseitig ohne die Klammer).
    async onIconClick(ev) {
        ev.stopPropagation();
        const action = await this.orm.call("int_filemanager.file", "action_open_form", [
            [this.props.record.resId],
        ]);
        this.actionService.doAction(action);
    }

    get isDir() {
        return this.props.record.data.is_dir;
    }

    get value() {
        return this.props.record.data[this.props.name];
    }

    get pseudoMimetype() {
        return pseudoMimetypeFor(this.value);
    }
}

export const intFilemanagerNameField = {
    component: IntFilemanagerNameField,
    supportedTypes: ["char"],
};

registry.category("fields").add("int_filemanager_name", intFilemanagerNameField);
