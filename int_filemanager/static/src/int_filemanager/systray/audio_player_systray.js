/** @odoo-module **/

import { Component, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { usePopover } from "@web/core/popover/popover_hook";

// Panel-Inhalt des Dropdowns (Titel/Fortschritt/Lautstaerke) - eigene Komponente statt Inline-
// Markup in der Systray selbst, aus demselben Grund wie IntFilemanagerContextMenu
// (context_menu.js): usePopover() mountet sie bei jedem Oeffnen frisch, sie braucht ihren
// eigenen Service-Zugriff.
export class AudioPlayerPanel extends Component {
    static template = "int_filemanager.AudioPlayerPanel";
    static props = { close: Function };

    setup() {
        this.player = useService("int_filemanager.audioPlayer");
        // useState() HIER nochmal ueber dem bereits reaktiven Service-State (nicht nur eine
        // Referenz darauf) - Pflicht, nicht Kosmetik: Owls reactive() im Service bindet
        // Aenderungsbenachrichtigungen an den Callback, der beim Erzeugen des Proxys uebergeben
        // wurde (dort keiner). Ein bloss lesender Zugriff auf diesen fremden reaktiven Proxy
        // registriert DIESE Komponente nicht als Beobachter - derselbe Bug/Fix wie in
        // name_icon_field.js's renameState, hier vorab vermieden statt live wiederentdeckt.
        this.state = useState(this.player.state);
        // Rein lokaler UI-Zustand (nicht im Service) - jede neue Panel-Instanz (usePopover
        // mountet bei jedem Oeffnen frisch, siehe Klassenkommentar oben) startet bewusst
        // eingeklappt, unabhaengig davon, ob die Liste beim letzten Mal offen war.
        this.uiState = useState({ showQueue: false });

        // Playlist bei Klick ausserhalb wieder einklappen (Nutzerwunsch 2026-09-18) - dieselbe
        // Technik, die dieses Modul schon zweimal fuer denselben Fehlerfall einsetzt
        // (native_list_renderer.js: onDocumentClick fuer Zeilenauswahl-Aufhebung; die
        // Rubberband-Eingrenzung dort). Odoo selbst hat dafuer keinen wiederverwendbaren
        // oeffentlichen Hook (useClickAway in web/core/popover/popover.js ist eine reine
        // Modul-interne Funktion, nicht exportiert - am Quellcode geprueft statt geraten),
        // baut intern aber auf genau demselben Muster auf: ein Capture-Phase-Listener auf dem
        // Dokument plus ein Containment-Check. queueRef/queueToggleRef schliessen den
        // Listen-Bereich UND den Umschalt-Button selbst aus - letzterer verwaltet sein eigenes
        // Umschalten ueber onToggleQueue() bereits selbst, ein Treffer dort soll hier nichts
        // zusaetzlich tun.
        this.queueRef = useRef("queueList");
        this.queueToggleRef = useRef("queueToggle");
        useExternalListener(
            document,
            "click",
            (ev) => {
                if (
                    !this.uiState.showQueue ||
                    this.queueRef.el?.contains(ev.target) ||
                    this.queueToggleRef.el?.contains(ev.target)
                ) {
                    return;
                }
                this.uiState.showQueue = false;
            },
            { capture: true }
        );
    }

    // state.queue[state.index] direkt statt eines "current"-Getters auf dem Service-State
    // (audio_player_service.js begruendet das ausfuehrlich) - ganz normale reactive Properties,
    // kein Sonderfall fuer Owls Tracking.
    get currentTrack() {
        return this.state.queue[this.state.index] || null;
    }

    // Nur relevant, wenn die Queue aus mehreren Ordnern stammt (Nutzerfrage 2026-09-18: "was
    // wenn man aus einer Suche heraus eine Audio oeffnet?" - bei aktiver rekursiver Suche
    // (native_search_model.js: filter_search_recursive) kann model.root.records Dateien aus
    // verschiedenen Ordnern enthalten). Nur dann lohnt sich pro Zeile ein Pfad-Hinweis -
    // stammt die Queue aus einem einzigen Ordner (der Normalfall), waere er redundant.
    get queueHasMultipleFolders() {
        return new Set(this.state.queue.map((f) => f.folderPath)).size > 1;
    }

    onToggleQueue() {
        this.uiState.showQueue = !this.uiState.showQueue;
    }

    onPlayAt(index) {
        this.player.playAt(index);
    }

    // "Interpret - Titel" aus den von mediameta.py extrahierten ID3-/Vorbis-Tags (Nutzerwunsch
    // 2026-09-18, Vorbild Cloudreve), Rueckfall auf den rohen Dateinamen wenn eine Datei keine
    // Tags hat (haeufig bei selbst aufgenommenen/konvertierten Dateien).
    get trackTitle() {
        return this.currentTrack ? this.currentTrack.title || this.currentTrack.name : "";
    }

    get trackArtist() {
        return this.currentTrack ? this.currentTrack.artist : "";
    }

    get progressPercent() {
        return this.state.duration ? (this.state.currentTime / this.state.duration) * 100 : 0;
    }

    formatTime(seconds) {
        if (!Number.isFinite(seconds) || seconds < 0) {
            return "0:00";
        }
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${String(s).padStart(2, "0")}`;
    }

    // mousedown statt click (Nutzerreport 2026-09-18 "laesst sich nur klicken, nicht ziehen") -
    // ein reiner click-Handler feuert erst beim Loslassen und nur, wenn Loslassen UND Klicken auf
    // demselben Element passieren, es gibt dabei aber keine Zwischen-Updates waehrend der Maus
    // gedrueckt gehalten wird. Dasselbe mousedown/mousemove/mouseup-Muster wie die
    // Rubberband-Auswahl in native_list_renderer.js: rect einmal bei mousedown einsammeln (nicht
    // bei jedem mousemove neu vermessen), document-weite Listener statt auf dem Balken selbst,
    // damit Ziehen ueber den Balkenrand hinaus (z.B. schnelle Mausbewegung nach links/rechts)
    // nicht abbricht - exakt das Verhalten von Odoos eigenem <video controls>-Scrubber, hier von
    // Hand nachgebaut, da wir bewusst keinen nativen <audio controls> mehr zeigen (siehe
    // audio_player_systray.xml).
    onSeekStart(ev) {
        if (!this.state.duration) {
            return;
        }
        const rect = ev.currentTarget.getBoundingClientRect();
        const applySeek = (clientX) => {
            const ratio = (clientX - rect.left) / rect.width;
            this.player.seek(Math.max(0, Math.min(1, ratio)) * this.state.duration);
        };
        applySeek(ev.clientX);
        const onMouseMove = (moveEv) => applySeek(moveEv.clientX);
        const onMouseUp = () => {
            document.removeEventListener("mousemove", onMouseMove);
            document.removeEventListener("mouseup", onMouseUp);
        };
        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
    }

    onVolume(ev) {
        this.player.setVolume(Number(ev.target.value));
    }

    // Dieselben drei Steuer-Buttons wie in der kompakten Navbar-Reihe (AudioPlayerSystray unten),
    // hier zusaetzlich im Panel (Nutzerwunsch 2026-09-18, Vorbild Cloudreve: die volle Steuerung
    // bleibt auch bei geoeffnetem Panel erreichbar statt nur Titel/Fortschritt/Lautstaerke).
    onPrev() {
        this.player.prev();
    }

    onTogglePlay() {
        this.player.toggle();
    }

    onNext() {
        this.player.next();
    }

    // Zyklischer Wiedergabemodus-Button (Nutzerwunsch 2026-09-18) - Icon/Tooltip je Modus,
    // dasselbe "ein Icon pro Zustand"-Muster wie Odoos eigener Sortier-Pfeil in
    // Listen-Spaltenkoepfen (audio_player_service.js begruendet das ausfuehrlich).
    get repeatModeIcon() {
        return {
            sequence: "fa-list-ol",
            single: "fa-repeat",
            random: "fa-random",
        }[this.state.repeatMode];
    }

    get repeatModeLabel() {
        return {
            sequence: "Der Reihe nach",
            single: "Einzelne Datei wiederholen",
            random: "Zufällig",
        }[this.state.repeatMode];
    }

    onCycleRepeatMode() {
        this.player.cycleRepeatMode();
    }

    // Beendet die Sitzung komplett (Vorbild Discuss' eigener Anruf-Balken: "Auflegen" sitzt dort
    // ebenfalls als normaler Eintrag IM Aktions-Panel, nicht als eigener Button in der kompakten,
    // immer sichtbaren Reihe). props.close() zusaetzlich zu stop(): das Panel zeigt sonst bis zum
    // naechsten Owl-Render noch den letzten (jetzt geleerten) Titel/Fortschritt an.
    onStop() {
        this.player.stop();
        this.props.close();
    }
}

export class AudioPlayerSystray extends Component {
    static template = "int_filemanager.AudioPlayerSystray";
    static props = {};

    setup() {
        this.player = useService("int_filemanager.audioPlayer");
        // Siehe Kommentar in AudioPlayerPanel.setup() oben - gleicher Grund.
        this.state = useState(this.player.state);
        // "o-dropdown--menu dropdown-menu mx-0" statt einer eigenen Klasse (Nutzerreport
        // 2026-09-18 "wirklich odoo nativ?") - exakt dieselben zwei Klassen, mit denen Odoos
        // eigenes <Dropdown> sein Panel oeffnet (web/core/dropdown/dropdown.js:
        // popoverClass: mergeClasses("o-dropdown--menu dropdown-menu mx-0", ...)), am
        // Quellcode verifiziert statt geraten - dasselbe Muster nutzt bereits context_menu.js
        // in diesem Modul. Ohne diese beiden Klassen war das Panel nur eine generische
        // Popover-Box (Browser-/Bootstrap-Zufallsoptik), keine echte Odoo-Dropdown-Huelle
        // (Hintergrund/Rand/Rundung/Schatten). Die eigene Klasse fuer Breite/Fortschrittsbalken
        // (o_int_filemanager_audio_panel) sitzt weiterhin NUR auf dem inneren Inhalts-Div im
        // Template, nicht hier auf der Huelle - genau wie z.B. Discuss' eigenes
        // .o-mail-MessagingMenu innerhalb der geteilten Dropdown-Huelle sitzt.
        this.popover = usePopover(AudioPlayerPanel, {
            position: "bottom-end",
            popoverClass: "o-dropdown--menu dropdown-menu mx-0",
        });
    }

    get hasTrack() {
        return Boolean(this.state.queue[this.state.index]);
    }

    // ev.stopPropagation() bei den drei Steuer-Buttons (Vorlage): sie sitzen in derselben
    // Button-Gruppe wie der Panel-Toggle, sollen aber nie versehentlich das Popover mit-toggeln -
    // eigener Handler pro Button reicht, kein gemeinsamer Container-Klick-Abfang noetig, da jeder
    // Button ohnehin einzeln behandelt wird.
    onPrev() {
        this.player.prev();
    }

    onTogglePlay() {
        this.player.toggle();
    }

    onNext() {
        this.player.next();
    }

    onTogglePanel(ev) {
        if (this.popover.isOpen) {
            this.popover.close();
        } else {
            this.popover.open(ev.currentTarget, {});
        }
    }
}

// sequence hoch statt niedrig (Nutzerwunsch 2026-09-18, "Buttons nach vorne"): Odoo sortiert
// Systray-Eintraege aufsteigend nach sequence und dreht die Liste dann um
// (web/webclient/navbar/navbar.js: systrayRegistry.getEntries().reverse()) - hoehere sequence
// landet dadurch WEITER VORNE/LINKS, nicht weiter hinten. Zum Vergleich, am echten Odoo-
// Quellcode verifiziert: Nachrichten (mail.messaging_menu) sequence 25, Aktivitaeten
// (mail.activity_menu) sequence 20, Discuss' eigener Anruf-Balken (discuss.CallMenu) sequence
// 100. 50 platziert uns vor Nachrichten/Aktivitaeten, aber hinter einem eventuellen Anruf.
registry.category("systray").add(
    "int_filemanager.audioPlayer",
    { Component: AudioPlayerSystray },
    { sequence: 50 }
);
