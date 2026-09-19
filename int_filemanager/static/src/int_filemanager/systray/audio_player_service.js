/** @odoo-module **/

import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

// Reihenfolge bestimmt die Klick-Zyklus-Reihenfolge des Wiedergabemodus-Buttons
// (audio_player_systray.js: cycleRepeatMode()) - "sequence" (Standard) -> "single" -> "random"
// -> wieder "sequence".
const REPEAT_MODES = ["sequence", "single", "random"];

// Eigener Service statt Zustand in der Systray-Komponente selbst: Odoos Popover-Service (siehe
// audio_player_systray.js/context_menu.js fuer dasselbe Muster) mountet die Panel-Komponente bei
// jedem Oeffnen/Schliessen frisch neu - das zugrunde liegende <audio>-Element und die
// Wiedergabe-Queue muessen davon unabhaengig weiterlaufen, exakt das Problem, fuer das Odoo
// selbst z.B. mail.store als Service statt Komponenten-State loest. Persistenz ueber
// Ordnerwechsel/App-Wechsel hinweg kommt hier "gratis" mit: ein Service lebt fuer die gesamte
// Webclient-Session, unabhaengig davon, welche View gerade aktiv ist (Nutzerwunsch 2026-09-18,
// "voller ueberlebt-Navigation-Effekt wie Cloudreve").
export const audioPlayerService = {
    dependencies: ["notification"],
    start(env, { notification }) {
        const audio = new Audio();
        audio.preload = "metadata";

        // Ohne Media Session API behandeln mobile Browser (v.a. Android Chrome) einen Tab, dessen
        // Audio kurz ins Buffering-Stocken geraet (z.B. weil das OS beim Sperren des Bildschirms
        // die Hintergrund-Netzwerkverbindung drosselt), nicht laenger als "spielt aktive Medien
        // ab" - genau das ist die Ausnahme, die Chrome sonst vor Tab-Freezing/-Throttling schuetzt
        // (Nutzerreport 2026-09-19: Wiedergabe stoppt beim Bildschirm-Aus, beim Wiedereinschalten
        // "Uncaught (in promise) NotSupportedError"). setActionHandler() wird weiter unten
        // registriert, nachdem toggle()/next()/prev() als benannte Funktionen existieren.
        const hasMediaSession = "mediaSession" in navigator;

        // Ob der aktuelle Track nach einem Ladefehler schon EINMAL automatisch neu geladen wurde -
        // ohne dieses Flag wuerde ein Fehler direkt zum naechsten Track weiterspringen (siehe
        // "error"-Listener weiter unten), was beim Aufwachen aus dem Bildschirm-Aus dazu fuehrt,
        // dass die ganze Restqueue in Sekundenbruchteilen durchgereicht wird, weil das Netzwerk
        // noch nicht wieder da ist - ein einziger Neuversuch mit derselben Datei faengt genau den
        // Fall ab, in dem die Verbindung eine Sekunde spaeter laengst wieder steht.
        let retriedCurrentAfterError = false;

        // Verhindert, dass ein einzelner Ladefehler zweimal behandelt wird: das "error"-Event des
        // <audio>-Elements und eine abgelehnte play()-Promise (safePlay() unten) koennen beide fuer
        // denselben Fehlschlag feuern.
        let failureHandled = false;

        const state = reactive({
            queue: [],
            index: -1,
            isPlaying: false,
            currentTime: 0,
            duration: 0,
            volume: 1,
            repeatMode: "sequence",
        });

        // Bewusst KEIN Object.defineProperty()-Getter fuer "current" auf dem reactive()-Proxy
        // (erster Versuch, live als Bug gefunden 2026-09-18 "Musik spielt, Navbar zeigt nichts"):
        // Owls Reactivity trackt Lesezugriffe ueber ihre eigenen Proxy-Get-Traps auf den Keys,
        // die reactive() beim Erzeugen kennt - ein NACHTRAEGLICH per defineProperty ergaenzter
        // Accessor haengt nicht zuverlaessig in dieser Tracking-Kette. Stattdessen ueberall direkt
        // queue[index] lesen (auch in den Komponenten) - das sind ganz normale, von Anfang an
        // bekannte reactive Properties, kein Sonderfall.
        function getCurrent() {
            return state.queue[state.index] || null;
        }

        // Zentrale play()-Stelle statt audio.play() verstreut aufzurufen: play() liefert ein
        // Promise, das bei jedem Fehlschlag (kein abspielbarer Source, Autoplay-Restriktion,
        // durch ein sofortiges pause() unterbrochen) ablehnt - ungefangen genau der
        // "Uncaught (in promise) NotSupportedError", den der Nutzer sieht. AbortError wird dabei
        // bewusst ignoriert: der entsteht z.B., wenn ein schneller Doppelklick auf "Weiter" das
        // vorherige play() per pause()/Source-Wechsel unterbricht - kein echter Fehler, kein Grund
        // fuer eine Meldung.
        function safePlay() {
            const p = audio.play();
            if (p && typeof p.catch === "function") {
                p.catch((err) => {
                    if (err && err.name === "AbortError") {
                        return;
                    }
                    handlePlaybackFailure();
                });
            }
        }

        function loadCurrent(autoplay) {
            const track = getCurrent();
            state.currentTime = 0;
            state.duration = 0;
            retriedCurrentAfterError = false;
            failureHandled = false;
            if (!track) {
                audio.removeAttribute("src");
                if (hasMediaSession) {
                    navigator.mediaSession.metadata = null;
                }
                return;
            }
            audio.src = track.downloadUrl;
            if (hasMediaSession) {
                navigator.mediaSession.metadata = new MediaMetadata({
                    title: track.title || track.name,
                    artist: track.artist || "",
                    album: track.album || "",
                });
            }
            if (autoplay) {
                safePlay();
            }
        }

        // Zufaellig einen ANDEREN Index als den aktuellen waehlen (Wiederholung desselben Tracks
        // waere bei "zufaellig" verwirrend) - bei nur einem Track in der Queue bleibt der Index
        // unveraendert, es gibt schlicht nichts anderes zur Auswahl.
        function randomOtherIndex() {
            if (state.queue.length < 2) {
                return state.index;
            }
            let i;
            do {
                i = Math.floor(Math.random() * state.queue.length);
            } while (i === state.index);
            return i;
        }

        // Gemeinsamer Sprung-Schritt fuer next()/onEnded()/onError() - "mode" statt state.repeatMode
        // direkt gelesen, damit onError() bewusst "sequence" erzwingen kann (siehe dort), ohne
        // den eigentlichen Modus des Nutzers zu veraendern.
        function advance(mode) {
            if (!state.queue.length) {
                return;
            }
            state.index = mode === "random" ? randomOtherIndex() : (state.index + 1) % state.queue.length;
            loadCurrent(true);
        }

        // Manueller "Weiter"-Klick: respektiert "zufaellig" (Spotify-Konvention: Shuffle wirkt
        // auch auf manuelles Weiterspringen), ignoriert aber "einzelne Datei" - ein Klick auf
        // "Weiter" soll immer tatsaechlich weiterspringen, nicht denselben Track neu starten
        // (das waere fuer einen Button namens "Weiter" nicht nachvollziehbar).
        function next() {
            advance(state.repeatMode === "single" ? "sequence" : state.repeatMode);
        }

        function prev() {
            if (!state.queue.length) {
                return;
            }
            // Neustart des aktuellen Tracks statt Sprung zum vorherigen, wenn schon >3s gelaufen
            // sind (Windows-Explorer-/Spotify-Konvention fuer den "Zurueck"-Knopf).
            if (audio.currentTime > 3) {
                audio.currentTime = 0;
                return;
            }
            state.index = (state.index - 1 + state.queue.length) % state.queue.length;
            loadCurrent(true);
        }

        function toggle() {
            if (!getCurrent()) {
                return;
            }
            if (audio.paused) {
                safePlay();
            } else {
                audio.pause();
            }
        }

        // Gemeinsame Fehlerbehandlung fuer sowohl das "error"-Event des <audio>-Elements als auch
        // eine abgelehnte play()-Promise (safePlay() oben) - beide koennen fuer denselben
        // Ladefehler feuern, failureHandled verhindert doppeltes Weiterspringen.
        function handlePlaybackFailure() {
            if (failureHandled) {
                return;
            }
            failureHandled = true;
            const track = getCurrent();
            if (!track) {
                return;
            }
            if (!retriedCurrentAfterError) {
                // Erster Fehlschlag: einmal automatisch neu laden statt sofort weiterzuspringen -
                // faengt genau den Fall ab, dass beim Aufwachen aus dem Bildschirm-Aus das Netzwerk
                // eine Sekunde spaeter laengst wieder da ist (siehe Deklaration von
                // retriedCurrentAfterError oben).
                retriedCurrentAfterError = true;
                const resumeTime = state.currentTime;
                setTimeout(() => {
                    if (getCurrent() !== track) {
                        return; // Nutzer ist inzwischen weitergesprungen, Neuversuch ist obsolet
                    }
                    failureHandled = false;
                    audio.src = track.downloadUrl;
                    audio.addEventListener(
                        "loadedmetadata",
                        () => {
                            audio.currentTime = resumeTime;
                        },
                        { once: true }
                    );
                    safePlay();
                }, 1000);
                return;
            }
            notification.add(_t("Wiedergabe fehlgeschlagen: %s", track.name), {
                type: "danger",
            });
            // "einzelne Datei" wird HIER (anders als bei einem normalen Songende) ignoriert: ein
            // Wiederholungsversuch derselben defekten Datei wuerde sonst endlos denselben Fehler
            // ausloesen. "zufaellig" bleibt dagegen unveraendert - dort besteht dieses
            // Endlosschleifen-Risiko nicht, jeder Versuch waehlt ohnehin einen anderen Index.
            advance(state.repeatMode === "single" ? "sequence" : state.repeatMode);
        }

        if (hasMediaSession) {
            navigator.mediaSession.setActionHandler("play", () => toggle());
            navigator.mediaSession.setActionHandler("pause", () => toggle());
            navigator.mediaSession.setActionHandler("previoustrack", () => prev());
            navigator.mediaSession.setActionHandler("nexttrack", () => next());
            navigator.mediaSession.setActionHandler("seekto", (details) => {
                if (details.seekTime != null) {
                    audio.currentTime = details.seekTime;
                }
            });
        }

        // Deckt den Fall ab, dass die Wiedergabe waehrend des Bildschirm-Aus stillstehend
        // (readyState/networkState im Fehlerzustand) haengen bleibt, OHNE dass ein "error"-Event
        // gefeuert hat (auf manchen Android-Versionen beobachtet: das <audio>-Element pausiert
        // stumm statt zu fehlern) - beim Zurueckkommen in den Vordergrund einmal pruefen und ggf.
        // denselben Neuversuch wie handlePlaybackFailure() anstossen.
        document.addEventListener("visibilitychange", () => {
            if (document.visibilityState !== "visible") {
                return;
            }
            // audio.error ist NUR gesetzt, wenn das Laden/Abspielen tatsaechlich fehlgeschlagen
            // ist - ein bewusstes audio.pause() (manuelle Pause, stop()) setzt es nie. Kein
            // zusaetzlicher "war gerade am Abspielen"-Check noetig: ein Fehler waehrend des
            // Hintergrunds loest ohnehin schon das "pause"-Event aus, isPlaying waere an dieser
            // Stelle also faelschlich schon false.
            const track = getCurrent();
            if (!track || !audio.paused || !audio.error) {
                return;
            }
            handlePlaybackFailure();
        });

        audio.addEventListener("timeupdate", () => {
            state.currentTime = audio.currentTime;
        });
        audio.addEventListener("durationchange", () => {
            state.duration = audio.duration || 0;
        });
        audio.addEventListener("play", () => {
            state.isPlaying = true;
            if (hasMediaSession) {
                navigator.mediaSession.playbackState = "playing";
            }
        });
        audio.addEventListener("pause", () => {
            state.isPlaying = false;
            if (hasMediaSession) {
                navigator.mediaSession.playbackState = "paused";
            }
        });
        // Anders als der manuelle next() oben: hier greift "einzelne Datei" tatsaechlich (Neustart
        // desselben Tracks) - genau der Sinn dieses Modus ist ja, dass eine natuerlich zu Ende
        // gespielte Datei sich selbst wiederholt, ein manueller "Weiter"-Klick aber unveraendert
        // weiterspringt (siehe next() oben).
        audio.addEventListener("ended", () => {
            if (state.repeatMode === "single") {
                audio.currentTime = 0;
                safePlay();
                return;
            }
            advance(state.repeatMode);
        });
        audio.addEventListener("error", handlePlaybackFailure);

        return {
            state,
            playQueue(files, startIndex) {
                state.queue = files;
                state.index = startIndex;
                loadCurrent(true);
            },
            // Direkter Sprung auf einen Eintrag der BESTEHENDEN Queue (Nutzerwunsch 2026-09-18,
            // Queue-Liste im Panel) - anders als playQueue() wird die Queue selbst nicht
            // ausgetauscht, nur der Index verschoben.
            playAt(index) {
                if (index < 0 || index >= state.queue.length) {
                    return;
                }
                state.index = index;
                loadCurrent(true);
            },
            // Beendet die Sitzung komplett (Nutzerwunsch 2026-09-18, "wie beenden" - Vorbild
            // Discuss' eigener Anruf-Balken: der verschwindet erst beim echten Auflegen
            // (leaveCall(), oi-close-Icon IM Aktions-Panel), nicht schon beim Stummschalten).
            // Queue leeren statt nur pausieren macht hasTrack() in der Systray automatisch
            // false, der ganze Balken verschwindet dadurch von selbst - keine eigene
            // Sichtbarkeits-Bedingung noetig.
            stop() {
                audio.pause();
                state.queue = [];
                state.index = -1;
                audio.removeAttribute("src");
                if (hasMediaSession) {
                    navigator.mediaSession.metadata = null;
                    navigator.mediaSession.playbackState = "none";
                }
            },
            toggle,
            next,
            prev,
            seek(time) {
                audio.currentTime = time;
            },
            setVolume(v) {
                audio.volume = v;
                state.volume = v;
            },
            // Zyklischer Button (Nutzerwunsch 2026-09-18) - dasselbe Klick-zyklisiert-Icon-Muster
            // wie Odoos eigener Sortier-Pfeil in Listen-Spaltenkoepfen (list_renderer.xml:
            // getSortableIconClass(), ein Klick schaltet "keine Sortierung -> aufsteigend ->
            // absteigend" weiter) - hier auf drei Wiedergabemodi statt drei Sortierzustaende
            // uebertragen, kein zusaetzliches Popover-Menue noetig.
            cycleRepeatMode() {
                const i = REPEAT_MODES.indexOf(state.repeatMode);
                state.repeatMode = REPEAT_MODES[(i + 1) % REPEAT_MODES.length];
            },
        };
    },
};

registry.category("services").add("int_filemanager.audioPlayer", audioPlayerService);
