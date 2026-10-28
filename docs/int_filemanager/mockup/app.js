/* Dateimanager-Mockup mit Owl. Reine Frontend-Demo: der Zustand liegt in einem `reactive`-Store,
 * die Komponenten lesen ihn mit `useState` (wie ein Odoo-Service). Keine Verbindung zu Odoo. */
(function () {
    const { Component, App: OwlApp, useState, useRef, useEffect, useExternalListener, reactive, xml, markup } = owl;
    const { NOW, folders, tags, docs } = window.MOCK;

    // ======================= Helfer ======================= //

    const ICONS = {
        apps: "M4 4h4v4H4zM10 4h4v4h-4zM16 4h4v4h-4zM4 10h4v4H4zM10 10h4v4h-4zM16 10h4v4h-4zM4 16h4v4H4zM10 16h4v4h-4zM16 16h4v4h-4z",
        chat: "M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z",
        clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2",
        search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.3-4.3",
        folder: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
        star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
        download: "M12 3v12M7 10l5 5 5-5M5 21h14",
        upload: "M12 15V3M7 8l5-5 5 5M5 21h14",
        right: "M9 6l6 6-6 6",
        left: "M15 6l-6 6 6 6",
        down: "M6 9l6 6 6-6",
        up: "M6 15l6-6 6 6",
        list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
        grid: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
        pivot: "M3 5h18v14H3zM3 10h18M9 5v14",
        chart: "M4 20V10M10 20V4M16 20v-8M22 20H2",
        tag: "M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8zM7.5 7.5h.01",
        more: "M5 12h.01M12 12h.01M19 12h.01",
        eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
        x: "M6 6l12 12M18 6L6 18",
        plus: "M12 5v14M5 12h14",
        move: "M5 12h14M13 6l6 6-6 6",
        trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
        copy: "M9 9h11v11H9zM5 15V4h11",
        moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
        sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
        sidebar: "M3 4h18v16H3zM9 4v16",
        filter: "M3 5h18l-7 8v6l-4 2v-8z",
        info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v5M12 8h.01",
        check: "M5 12l5 5 10-10",
        file: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5",
        rows: "M4 6h16M4 12h16M4 18h16",
        sort: "M7 4v16M3 8l4-4 4 4M17 20V4M13 16l4 4 4-4",
        expand: "M4 14v6h6M20 10V4h-6M4 20l7-7M20 4l-7 7",
    };

    const KINDS = {
        pdf: { key: "pdf", label: "PDF-Dokument", short: "PDF", color: "var(--pdf)" },
        doc: { key: "doc", label: "Textdokument", short: "DOC", color: "var(--doc)" },
        xls: { key: "xls", label: "Tabelle", short: "XLS", color: "var(--xls)" },
        img: { key: "img", label: "Bild", short: "IMG", color: "var(--img)" },
        other: { key: "other", label: "Datei", short: "FILE", color: "var(--other)" },
    };
    const EXT_KIND = { pdf: "pdf", odt: "doc", docx: "doc", doc: "doc", rtf: "doc", xlsx: "xls", ods: "xls", jpg: "img", jpeg: "img", png: "img", gif: "img", webp: "img" };

    const fx = {
        ext: (name) => (name.includes(".") ? name.split(".").pop().toLowerCase() : ""),
        kind(name) {
            return KINDS[EXT_KIND[fx.ext(name)] || "other"];
        },
        size(bytes) {
            if (bytes < 1024 * 1024) {
                return `${Math.max(1, Math.round(bytes / 1024))} kB`;
            }
            const mb = bytes / 1024 / 1024;
            return `${mb.toLocaleString("de-DE", { maximumFractionDigits: mb < 10 ? 1 : 0 })} MB`;
        },
        /** Relativ: "Heute, 12:07", "Gestern", "12. Okt." (volles Datum im Tooltip). */
        date(d) {
            const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate());
            const days = Math.round((day(NOW) - day(d)) / 864e5);
            const time = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
            if (days === 0) return { main: "Heute", sub: time };
            if (days === 1) return { main: "Gestern", sub: time };
            const opts = { day: "numeric", month: "short" };
            if (d.getFullYear() !== NOW.getFullYear()) opts.year = "numeric";
            return { main: d.toLocaleDateString("de-DE", opts), sub: days < 7 ? time : "" };
        },
        dateFull: (d) => d.toLocaleString("de-DE", { dateStyle: "long", timeStyle: "short" }),
        folder: (id) => folders.find((f) => f.id === id),
        /** Namen von der Wurzel bis zum Ordner. */
        path(id) {
            const names = [];
            for (let f = fx.folder(id); f; f = f.parent && fx.folder(f.parent)) names.unshift(f.name);
            return names;
        },
        pathIds(id) {
            const ids = [];
            for (let f = fx.folder(id); f; f = f.parent && fx.folder(f.parent)) ids.unshift(f.id);
            return ids;
        },
        children: (id) => folders.filter((f) => f.parent === id),
        subtree(id) {
            const ids = new Set([id]);
            for (const f of fx.children(id)) fx.subtree(f.id).forEach((x) => ids.add(x));
            return ids;
        },
        esc: (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]),
    };

    const FILTERS = [
        { key: "pdf", label: "PDF", group: "type", test: (d) => fx.kind(d.name).key === "pdf" },
        { key: "img", label: "Bilder", group: "type", test: (d) => fx.kind(d.name).key === "img" },
        { key: "office", label: "Office", group: "type", test: (d) => ["doc", "xls"].includes(fx.kind(d.name).key) },
        { key: "fav", label: "Favoriten", icon: "star", test: (d) => d.fav },
        { key: "dup", label: "Duplikate", icon: "copy", test: (d) => store.dupHashes().has(d.hash) },
        { key: "mine", label: "Meine Uploads", icon: "upload", test: (d) => d.mine },
    ];
    const GROUPS = [
        { key: "", label: "Keine Gruppierung" },
        { key: "folder", label: "Ordner" },
        { key: "kind", label: "Dateityp" },
        { key: "month", label: "Monat" },
    ];

    // ======================= Store ======================= //

    const store = reactive({
        docs,
        folders,
        folderId: null,
        tagIds: [],
        filters: [],
        search: "",
        sortKey: "name",
        sortDir: 1,
        groupBy: "",
        page: 0,
        pageSize: 80,
        view: "list",
        density: "comfortable",
        selected: [],
        detailId: null,
        quickLookId: null,
        expanded: { 1: true, 2: true, 5: true },
        sidebarOpen: true,
        dark: false,
        menu: null,
        dropOver: null,
        dragIds: [],
        fileDrag: false,
        toasts: [],
        nextToast: 1,

        dupHashes() {
            const seen = new Map();
            for (const d of this.docs) seen.set(d.hash, (seen.get(d.hash) || 0) + 1);
            return new Set([...seen].filter(([, n]) => n > 1).map(([h]) => h));
        },
        matches(d, ignore = {}) {
            if (!ignore.folder && this.folderId && !fx.subtree(this.folderId).has(d.folderId)) return false;
            if (this.tagIds.length && !this.tagIds.some((t) => d.tagIds.includes(t))) return false;
            if (this.search && !d.name.toLowerCase().includes(this.search.toLowerCase())) return false;
            if (ignore.filters) return true;
            const active = FILTERS.filter((f) => this.filters.includes(f.key));
            const types = active.filter((f) => f.group === "type");
            if (types.length && !types.some((f) => f.test(d))) return false;
            return active.filter((f) => f.group !== "type").every((f) => f.test(d));
        },
        get visible() {
            const dir = this.sortDir;
            const key = {
                name: (a, b) => a.name.localeCompare(b.name, "de", { numeric: true, sensitivity: "base" }),
                folder: (a, b) => fx.path(a.folderId).join("/").localeCompare(fx.path(b.folderId).join("/"), "de"),
                size: (a, b) => a.size - b.size,
                date: (a, b) => a.date - b.date,
            }[this.sortKey];
            return this.docs.filter((d) => this.matches(d)).sort((a, b) => dir * key(a, b));
        },
        get pageDocs() {
            return this.visible.slice(this.page * this.pageSize, (this.page + 1) * this.pageSize);
        },
        get detail() {
            return this.docs.find((d) => d.id === this.detailId);
        },

        // --- Aktionen
        setFolder(id) {
            this.folderId = id;
            this.page = 0;
            for (const x of fx.pathIds(id || 0).slice(0, -1)) this.expanded[x] = true;
        },
        toggleFilter(key) {
            const i = this.filters.indexOf(key);
            i < 0 ? this.filters.push(key) : this.filters.splice(i, 1);
            this.page = 0;
        },
        toggleTag(id) {
            const i = this.tagIds.indexOf(id);
            i < 0 ? this.tagIds.push(id) : this.tagIds.splice(i, 1);
            this.page = 0;
        },
        toggleSelect(id) {
            const i = this.selected.indexOf(id);
            i < 0 ? this.selected.push(id) : this.selected.splice(i, 1);
        },
        sortBy(key) {
            this.sortDir = this.sortKey === key ? -this.sortDir : 1;
            this.sortKey = key;
        },
        toast(text, opts = {}) {
            const t = { id: this.nextToast++, text, icon: "check", ...opts };
            this.toasts.push(t);
            if (!opts.progress) setTimeout(() => this.dismiss(t.id), opts.action ? 7000 : 3500);
            return this.toasts.find((x) => x.id === t.id);
        },
        dismiss(id) {
            const i = this.toasts.findIndex((t) => t.id === id);
            if (i >= 0) this.toasts.splice(i, 1);
        },
        move(ids, folderId) {
            const before = ids.map((id) => [id, this.docs.find((d) => d.id === id).folderId]);
            for (const id of ids) this.docs.find((d) => d.id === id).folderId = folderId;
            this.toast(`${ids.length} ${ids.length === 1 ? "Dokument" : "Dokumente"} nach „${fx.folder(folderId).name}“ verschoben`, {
                action: { label: "Rückgängig", fn: () => before.forEach(([id, f]) => (this.docs.find((d) => d.id === id).folderId = f)) },
            });
            this.selected = [];
        },
        /** Simulierter Upload mit Fortschritt; echte Dateien liefern Name und Größe. */
        upload(files) {
            if (!files.length) return;
            if (!this.folderId) {
                this.toast("Wähle links zuerst einen Ordner.", { icon: "info" });
                return;
            }
            const folderId = this.folderId;
            const t = this.toast(`${files.length} ${files.length === 1 ? "Datei wird" : "Dateien werden"} hochgeladen …`, { progress: 0, icon: "upload" });
            const timer = setInterval(() => {
                t.progress += 12 + Math.random() * 18;
                if (t.progress < 100) return;
                clearInterval(timer);
                this.dismiss(t.id);
                for (const f of files) {
                    this.docs.unshift({ id: Math.max(...this.docs.map((d) => d.id)) + 1, name: f.name, folderId, size: f.size, date: new Date(NOW), tagIds: [], fav: false, hash: "n" + Math.random(), mine: true, isNew: true });
                }
                this.sortKey = "date";
                this.sortDir = -1;
                this.page = 0;
                this.toast(`${files.length} ${files.length === 1 ? "Datei" : "Dateien"} gespeichert`);
            }, 220);
        },
        newFolder() {
            const parent = this.folderId || 1;
            const id = Math.max(...this.folders.map((f) => f.id)) + 1;
            this.folders.push({ id, name: "Neuer Ordner", parent });
            this.expanded[parent] = true;
            this.setFolder(id);
            this.toast("Ordner „Neuer Ordner“ angelegt");
        },
    });
    window.store = store; // zum Ausprobieren in der Konsole

    // ======================= Bausteine ======================= //

    class Icon extends Component {
        static template = xml`<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path t-att-d="path"/></svg>`;
        get path() {
            return ICONS[this.props.name];
        }
    }

    class Thumb extends Component {
        static components = { Icon };
        static template = xml`
            <div class="thumb" t-att-class="'k-' + kind.key + (props.clickable ? ' clickable' : '')" t-attf-style="--s: {{props.size or 40}}px">
                <span class="ext" t-if="kind.key !== 'img'" t-esc="ext"/>
            </div>`;
        get kind() { return fx.kind(this.props.name); }
        get ext() { return (fx.ext(this.props.name) || "?").toUpperCase().slice(0, 4); }
    }

    class Paper extends Component {
        static template = xml`
            <div class="paper" t-att-class="'k-' + kind.key + (props.small ? ' sm' : '')">
                <span class="stamp" t-esc="kind.short"/>
                <h2 t-esc="props.name"/>
                <t t-foreach="lines" t-as="w" t-key="w_index"><div class="ln" t-attf-style="width: {{w}}%"/></t>
            </div>`;
        get kind() { return fx.kind(this.props.name); }
        get lines() {
            let s = this.props.name.length * 7;
            return Array.from({ length: 22 }, (_, i) => ((s = (s * 31 + 11) % 97), i % 6 === 5 ? 40 : 62 + (s % 38)));
        }
    }

    // ======================= Navigation ======================= //

    class Navbar extends Component {
        static components = { Icon };
        static template = xml`
            <header class="navbar">
                <div class="brand"><Icon name="'apps'"/> Dateimanager</div>
                <button class="menu-item active">Dokumente</button>
                <button class="menu-item">Papierkorb</button>
                <button class="menu-item">Freigaben</button>
                <button class="menu-item">Einlesen</button>
                <button class="menu-item">Texte der Dateien</button>
                <button class="menu-item">Einstellungen</button>
                <button class="menu-item">Konfiguration</button>
                <span class="spacer"/>
                <button class="nav-btn" t-on-click="() => store.dark = !store.dark" t-att-title="store.dark ? 'Heller Modus' : 'Dunkler Modus'"><Icon name="store.dark ? 'sun' : 'moon'"/></button>
                <button class="nav-btn"><Icon name="'chat'"/><span class="badge">2</span></button>
                <button class="nav-btn"><Icon name="'clock'"/></button>
                <span class="company">My Company</span>
                <span class="avatar">F</span>
            </header>`;
        setup() { this.store = useState(store); }
    }

    class FolderNode extends Component {
        static components = { Icon };
        static template = xml`
            <li>
                <div class="tree-row" t-att-class="{ active: store.folderId === props.folder.id, drop: store.dropOver === props.folder.id }"
                     t-attf-style="--depth: {{props.depth}}"
                     t-on-click="() => store.setFolder(props.folder.id)"
                     t-on-dragover.prevent="onDragOver" t-on-dragleave="() => store.dropOver = null" t-on-drop.prevent="onDrop">
                    <button class="tw" t-att-class="{ none: !children.length, open: open }" t-on-click.stop="toggle"><Icon name="'right'"/></button>
                    <span class="fic"><Icon name="'folder'"/></span>
                    <span class="name truncate" t-esc="props.folder.name" t-att-title="props.folder.name"/>
                    <span class="count" t-esc="props.counts[props.folder.id] or 0"/>
                </div>
                <ul t-if="open and children.length">
                    <FolderNode t-foreach="children" t-as="child" t-key="child.id" folder="child" depth="props.depth + 1" counts="props.counts"/>
                </ul>
            </li>`;
        setup() { this.store = useState(store); }
        get children() { return this.store.folders.filter((f) => f.parent === this.props.folder.id); }
        get open() { return Boolean(this.store.expanded[this.props.folder.id]); }
        toggle() { store.expanded[this.props.folder.id] = !this.open; }
        onDragOver() {
            store.dropOver = this.props.folder.id;
            // Wie im Original: ein Ordner unter dem Zeiger klappt nach kurzer Zeit auf.
            clearTimeout(this.hover);
            if (this.children.length && !this.open) this.hover = setTimeout(() => (store.expanded[this.props.folder.id] = true), 600);
        }
        onDrop() {
            clearTimeout(this.hover);
            store.dropOver = null;
            if (store.dragIds.length) store.move(store.dragIds, this.props.folder.id);
            store.dragIds = [];
        }
    }
    FolderNode.components.FolderNode = FolderNode;

    class Sidebar extends Component {
        static components = { Icon, FolderNode };
        static template = xml`
            <aside class="sidebar" t-att-class="{ collapsed: !store.sidebarOpen }">
                <div class="scroll">
                    <div class="side-title"><Icon name="'folder'"/> <span class="grow">Ordner</span></div>
                    <div class="tree-row" t-att-class="{ active: !store.folderId }" style="--depth: 0" t-on-click="() => store.setFolder(null)">
                        <span class="tw none"><Icon name="'right'"/></span>
                        <span class="fic"><Icon name="'file'"/></span>
                        <span class="name">Alle Dokumente</span>
                        <span class="count" t-esc="total"/>
                    </div>
                    <ul><FolderNode t-foreach="roots" t-as="f" t-key="f.id" folder="f" depth="0" counts="counts"/></ul>

                    <div class="side-title" style="margin-top: 18px"><Icon name="'tag'"/> <span class="grow">Tags</span></div>
                    <div class="tag-row" t-foreach="tags" t-as="tag" t-key="tag.id" t-att-class="{ active: store.tagIds.includes(tag.id) }" t-on-click="() => store.toggleTag(tag.id)">
                        <span class="dot" t-attf-style="background: {{tag.color}}"/>
                        <span class="name" t-esc="tag.name"/>
                        <span class="count muted" t-esc="tagCount(tag.id)"/>
                    </div>
                </div>
                <div class="side-foot">
                    <div class="usage"><b t-esc="used"/><span class="muted">von 5 GB belegt</span></div>
                    <div class="meter"><i t-attf-style="width: {{percent}}%"/></div>
                    <button class="trash"><Icon name="'trash'"/> Papierkorb <span class="muted" style="margin-left:auto">3</span></button>
                </div>
            </aside>`;
        setup() { this.store = useState(store); this.tags = tags; }
        get roots() { return this.store.folders.filter((f) => !f.parent); }
        get total() { return this.store.docs.length; }
        get counts() {
            const counts = {};
            for (const d of this.store.docs) for (const id of fx.pathIds(d.folderId)) counts[id] = (counts[id] || 0) + 1;
            return counts;
        }
        tagCount(id) { return this.store.docs.filter((d) => d.tagIds.includes(id)).length; }
        get bytes() { return this.store.docs.reduce((n, d) => n + d.size, 0); }
        get used() { return fx.size(this.bytes); }
        get percent() { return Math.max(2, (this.bytes / (5 * 1024 ** 3)) * 100); }
    }

    // ======================= Control Panel ======================= //

    class ControlPanel extends Component {
        static components = { Icon };
        static template = xml`
            <div class="control-panel">
                <div class="cp-left">
                    <button class="btn ghost icon" t-on-click="() => store.sidebarOpen = !store.sidebarOpen" title="Ordnerleiste ein-/ausblenden"><Icon name="'sidebar'"/></button>
                    <div class="dd">
                        <button class="btn primary" t-on-click.stop="() => store.menu = store.menu === 'new' ? null : 'new'"><Icon name="'plus'"/> Neu <Icon name="'down'"/></button>
                        <div class="dd-menu" t-if="store.menu === 'new'">
                            <button class="item" t-on-click="() => this.run(() => this.fileInput.el.click())"><Icon name="'upload'"/> Dateien hochladen <kbd class="k">U</kbd></button>
                            <button class="item" t-on-click="() => this.run(() => store.upload([{ name: 'Scan 2026-10-27.pdf', size: 840000 }, { name: 'Vollmacht.pdf', size: 120000 }, { name: 'Foto.jpg', size: 2400000 }]))"><Icon name="'folder'"/> Ordner hochladen</button>
                            <button class="item" t-on-click="() => this.run(() => store.newFolder())"><Icon name="'plus'"/> Neuer Ordner</button>
                            <hr/>
                            <button class="item" t-if="store.folderId" t-on-click="() => this.run(() => store.toast('ZIP wird vorbereitet …', { icon: 'download' }))"><Icon name="'download'"/> Ordner herunterladen</button>
                        </div>
                    </div>
                    <input type="file" multiple="multiple" class="d-none" style="display:none" t-ref="fileInput" t-on-change="onFiles"/>
                    <nav class="crumbs">
                        <button t-att-class="{ last: !store.folderId }" t-on-click="() => store.setFolder(null)">Dokumente</button>
                        <t t-foreach="crumbs" t-as="c" t-key="c.id">
                            <span class="sep"><Icon name="'right'"/></span>
                            <button t-att-class="{ last: c_last }" t-esc="c.name" t-on-click="() => store.setFolder(c.id)"/>
                        </t>
                    </nav>
                </div>

                <div class="dd">
                    <label class="searchbox">
                        <Icon name="'search'"/>
                        <span class="facets">
                            <span class="chip" t-if="store.folderId"><Icon name="'folder'"/> <t t-esc="leaf"/> <button t-on-click.prevent="() => store.setFolder(null)"><Icon name="'x'"/></button></span>
                            <span class="chip" t-foreach="store.tagIds" t-as="t" t-key="t"><Icon name="'tag'"/> <t t-esc="tagName(t)"/> <button t-on-click.prevent="() => store.toggleTag(t)"><Icon name="'x'"/></button></span>
                        </span>
                        <input t-ref="search" placeholder="Name oder Inhalt suchen …" t-att-value="store.search" t-on-input="onSearch"/>
                        <kbd t-if="!store.search">/</kbd>
                        <button class="btn ghost icon sm" type="button" t-on-click.prevent.stop="() => store.menu = store.menu === 'filter' ? null : 'filter'"><Icon name="'filter'"/></button>
                    </label>
                    <div class="dd-menu right" style="width: 100%; min-width: 260px" t-if="store.menu === 'filter'" t-on-click.stop="() => {}">
                        <div class="head">Filter</div>
                        <button class="item" t-foreach="filters" t-as="f" t-key="f.key" t-on-click="() => store.toggleFilter(f.key)">
                            <span class="check" t-att-class="{ on: store.filters.includes(f.key) }"><Icon name="'check'"/></span> <t t-esc="f.label"/>
                        </button>
                        <hr/>
                        <div class="head">Gruppieren nach</div>
                        <button class="item" t-foreach="groups" t-as="g" t-key="g.key" t-on-click="() => store.groupBy = g.key">
                            <span class="check" t-att-class="{ on: store.groupBy === g.key }" style="border-radius: 50%"><Icon name="'check'"/></span> <t t-esc="g.label"/>
                        </button>
                    </div>
                </div>

                <div class="cp-right">
                    <div class="pager">
                        <span t-esc="range"/>
                        <button class="btn ghost icon sm" t-att-disabled="store.page === 0" t-on-click="() => store.page--"><Icon name="'left'"/></button>
                        <button class="btn ghost icon sm" t-att-disabled="(store.page + 1) * store.pageSize >= store.visible.length" t-on-click="() => store.page++"><Icon name="'right'"/></button>
                    </div>
                    <div class="seg">
                        <button t-foreach="views" t-as="v" t-key="v.key" t-att-class="{ on: store.view === v.key }" t-att-title="v.label" t-on-click="() => store.view = v.key"><Icon name="v.icon"/></button>
                    </div>
                </div>
            </div>`;
        setup() {
            this.store = useState(store);
            this.fileInput = useRef("fileInput");
            this.searchInput = useRef("search");
            this.filters = FILTERS;
            this.groups = GROUPS;
            this.views = [
                { key: "list", label: "Liste", icon: "list" },
                { key: "kanban", label: "Kacheln", icon: "grid" },
                { key: "pivot", label: "Pivot", icon: "pivot" },
                { key: "graph", label: "Diagramm", icon: "chart" },
            ];
            useExternalListener(window, "keydown", (ev) => {
                if (ev.key === "/" && !["INPUT", "TEXTAREA"].includes(ev.target.tagName)) {
                    ev.preventDefault();
                    this.searchInput.el.focus();
                }
                if (ev.key.toLowerCase() === "u" && !ev.ctrlKey && !ev.metaKey && !["INPUT", "TEXTAREA"].includes(ev.target.tagName)) {
                    this.fileInput.el.click();
                }
            });
        }
        run(fn) { store.menu = null; fn(); }
        get crumbs() { return this.store.folderId ? fx.pathIds(this.store.folderId).map((id) => fx.folder(id)) : []; }
        get leaf() { return fx.folder(this.store.folderId).name; }
        tagName(id) { return tags.find((t) => t.id === id).name; }
        get range() {
            const { visible, page, pageSize } = this.store;
            const total = visible.length;
            if (!total) return "0 / 0";
            const from = page * pageSize + 1;
            return `${from}–${Math.min(total, from + pageSize - 1)} / ${total}`;
        }
        onSearch(ev) { store.search = ev.target.value; store.page = 0; }
        onFiles(ev) {
            store.upload([...ev.target.files].map((f) => ({ name: f.name, size: f.size })));
            ev.target.value = "";
        }
    }

    class QuickBar extends Component {
        static components = { Icon };
        static template = xml`
            <div class="quickbar">
                <button class="pill" t-att-class="{ on: !store.filters.length }" t-on-click="() => store.filters.splice(0)">Alle <span class="n" t-esc="count(null)"/></button>
                <button class="pill" t-foreach="filters" t-as="f" t-key="f.key" t-att-class="{ on: store.filters.includes(f.key) }" t-on-click="() => store.toggleFilter(f.key)">
                    <Icon t-if="f.icon" name="f.icon"/><t t-esc="f.label"/> <span class="n" t-esc="count(f)"/>
                </button>
                <span class="grow"/>
                <div class="seg" title="Zeilenhöhe">
                    <button t-att-class="{ on: store.density === 'comfortable' }" t-on-click="() => store.density = 'comfortable'" title="Komfortabel"><Icon name="'list'"/></button>
                    <button t-att-class="{ on: store.density === 'compact' }" t-on-click="() => store.density = 'compact'" title="Kompakt"><Icon name="'rows'"/></button>
                </div>
            </div>`;
        setup() { this.store = useState(store); this.filters = FILTERS; }
        /** Zähler richten sich nach Ordner, Tags und Suche, aber nicht nach den anderen Filtern. */
        count(f) {
            const base = this.store.docs.filter((d) => this.store.matches(d, { filters: true }));
            return f ? base.filter((d) => f.test(d)).length : base.length;
        }
    }

    // ======================= Liste ======================= //

    class DocRow extends Component {
        static components = { Icon, Thumb };
        static template = xml`
            <div class="row grid-cols" role="row"
                 t-att-class="{ selected: selected, detail: store.detailId === doc.id, 'is-new': doc.isNew, dragged: dragging, 'menu-open': store.menu === 'row' + doc.id }"
                 draggable="true" t-on-dragstart="onDragStart" t-on-dragend="() => store.dragIds = []"
                 t-on-click="onClick" t-on-dblclick="() => store.quickLookId = doc.id" t-on-contextmenu.prevent.stop="openMenu">
                <div class="check" t-att-class="{ on: selected }" t-on-click.stop="() => store.toggleSelect(doc.id)"><Icon name="'check'"/></div>
                <button class="star" t-att-class="{ on: doc.fav }" t-on-click.stop="() => doc.fav = !doc.fav" title="Favorit"><Icon name="'star'"/></button>

                <div class="name-cell">
                    <Thumb name="doc.name" size="store.density === 'compact' ? 26 : 38" clickable="true"/>
                    <div class="txt">
                        <span class="title truncate" t-att-title="doc.name" t-out="title"/>
                        <span class="sub">
                            <span t-esc="kind.label"/>
                            <span class="badge-dup" t-if="isDup" title="Dieselbe Datei liegt noch in einem anderen Ordner"><Icon name="'copy'"/> Duplikat</span>
                        </span>
                    </div>
                </div>

                <div class="loc" t-on-click.stop="() => store.setFolder(doc.folderId)" t-att-title="path.join(' / ')">
                    <span class="fic"><Icon name="'folder'"/></span>
                    <span class="where">
                        <span class="leaf truncate" t-esc="path[path.length - 1]"/>
                        <span class="trail truncate" t-esc="trail"/>
                    </span>
                </div>
                <div class="num" t-esc="fx.size(doc.size)"/>
                <div class="date" t-att-title="fx.dateFull(doc.date)"><b t-esc="date.main"/> <span t-if="date.sub" t-esc="date.sub"/></div>
                <div><span class="tagpill" t-foreach="doc.tagIds" t-as="t" t-key="t" t-attf-style="--c: {{tagColor(t)}}" t-esc="tagName(t)"/></div>

                <div class="row-actions dd" t-on-click.stop="() => {}">
                    <button class="ibtn" title="Vorschau (Leertaste)" t-on-click="() => store.quickLookId = doc.id"><Icon name="'eye'"/></button>
                    <button class="ibtn" title="Herunterladen" t-on-click="() => store.toast('„' + doc.name + '“ wird heruntergeladen', { icon: 'download' })"><Icon name="'download'"/></button>
                    <button class="ibtn" title="Mehr" t-on-click.stop="openMenu"><Icon name="'more'"/></button>
                    <div class="dd-menu right" t-if="store.menu === 'row' + doc.id" style="top: 100%">
                        <button class="item" t-on-click="() => this.act(() => store.quickLookId = doc.id)"><Icon name="'eye'"/> Ansehen <kbd class="k">Leertaste</kbd></button>
                        <button class="item" t-on-click="() => this.act(() => store.detailId = doc.id)"><Icon name="'info'"/> Eigenschaften</button>
                        <button class="item" t-on-click="() => this.act(() => store.toast('Wird heruntergeladen', { icon: 'download' }))"><Icon name="'download'"/> Herunterladen</button>
                        <hr/>
                        <button class="item" t-on-click="() => this.act(() => { store.selected = [doc.id]; store.toast('Zielordner wählen: einfach auf einen Ordner ziehen', { icon: 'info' }); })"><Icon name="'move'"/> Verschieben nach …</button>
                        <button class="item" t-on-click="() => this.act(() => doc.fav = !doc.fav)"><Icon name="'star'"/> <t t-esc="doc.fav ? 'Favorit entfernen' : 'Als Favorit markieren'"/></button>
                        <hr/>
                        <button class="item danger" t-on-click="() => this.act(() => store.toast('In den Papierkorb verschoben', { icon: 'trash' }))"><Icon name="'trash'"/> Archivieren</button>
                    </div>
                </div>
            </div>`;
        static props = ["doc"];
        setup() { this.store = useState(store); this.fx = fx; }
        get doc() { return this.props.doc; }
        get selected() { return this.store.selected.includes(this.doc.id); }
        get dragging() { return this.store.dragIds.includes(this.doc.id); }
        get kind() { return fx.kind(this.doc.name); }
        get path() { return fx.path(this.doc.folderId); }
        get trail() { return this.path.slice(0, -1).join(" › "); }
        get date() { return fx.date(this.doc.date); }
        get isDup() { return this.store.dupHashes().has(this.doc.hash); }
        get title() {
            const name = fx.esc(this.doc.name);
            if (!this.store.search) return markup(name);
            const re = new RegExp(`(${this.store.search.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig");
            return markup(name.replace(re, "<mark>$1</mark>"));
        }
        tagColor(id) { return tags.find((t) => t.id === id).color; }
        tagName(id) { return tags.find((t) => t.id === id).name; }
        act(fn) { store.menu = null; fn(); }
        onClick(ev) {
            if (ev.ctrlKey || ev.metaKey || store.selected.length) {
                store.toggleSelect(this.doc.id);
            } else {
                store.detailId = store.detailId === this.doc.id ? null : this.doc.id;
            }
        }
        openMenu(ev) {
            ev.preventDefault();
            store.menu = store.menu === "row" + this.doc.id ? null : "row" + this.doc.id;
        }
        onDragStart(ev) {
            store.dragIds = this.selected ? [...store.selected] : [this.doc.id];
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", store.dragIds.length + " Dokumente");
        }
    }

    class ListView extends Component {
        static components = { Icon, DocRow };
        static template = xml`
            <div class="list" t-att-class="'density-' + store.density">
                <div class="list-head grid-cols">
                    <div class="check" t-att-class="{ on: allSelected, mixed: someSelected }" t-on-click="toggleAll"><Icon name="allSelected ? 'check' : 'rows'"/></div>
                    <span/>
                    <button t-att-class="{ sorted: store.sortKey === 'name' }" t-on-click="() => store.sortBy('name')">Name <Icon t-if="store.sortKey === 'name'" name="store.sortDir > 0 ? 'up' : 'down'"/></button>
                    <button t-att-class="{ sorted: store.sortKey === 'folder' }" t-on-click="() => store.sortBy('folder')">Ablageort <Icon t-if="store.sortKey === 'folder'" name="store.sortDir > 0 ? 'up' : 'down'"/></button>
                    <button class="r" t-att-class="{ sorted: store.sortKey === 'size' }" t-on-click="() => store.sortBy('size')"><Icon t-if="store.sortKey === 'size'" name="store.sortDir > 0 ? 'up' : 'down'"/> Größe</button>
                    <button t-att-class="{ sorted: store.sortKey === 'date' }" t-on-click="() => store.sortBy('date')">Geändert <Icon t-if="store.sortKey === 'date'" name="store.sortDir > 0 ? 'up' : 'down'"/></button>
                    <span>Tags</span>
                    <span/>
                </div>
                <t t-foreach="rows" t-as="r" t-key="r.key">
                    <div class="group-head" t-if="r.group" t-esc="r.label"/>
                    <DocRow t-else="" doc="r.doc"/>
                </t>
                <div class="empty" t-if="!rows.length">
                    <div>
                        <div class="big"><Icon name="'search'"/></div>
                        <h3>Keine Dokumente gefunden</h3>
                        <p>Passe Suche oder Filter an – oder ziehe Dateien hierher, um sie hochzuladen.</p>
                        <button class="btn" t-on-click="reset">Filter zurücksetzen</button>
                    </div>
                </div>
            </div>`;
        setup() { this.store = useState(store); }
        get rows() {
            const rows = [];
            const label = {
                folder: (d) => fx.path(d.folderId).slice(-1)[0],
                kind: (d) => fx.kind(d.name).label,
                month: (d) => d.date.toLocaleDateString("de-DE", { month: "long", year: "numeric" }),
            }[this.store.groupBy];
            let last;
            for (const d of this.store.pageDocs) {
                if (label && label(d) !== last) {
                    last = label(d);
                    rows.push({ group: true, key: "g" + last, label: last });
                }
                rows.push({ key: d.id, doc: d });
            }
            return rows;
        }
        get allSelected() { return this.store.pageDocs.length > 0 && this.store.pageDocs.every((d) => this.store.selected.includes(d.id)); }
        get someSelected() { return !this.allSelected && this.store.selected.length > 0; }
        toggleAll() { store.selected = this.allSelected ? [] : store.pageDocs.map((d) => d.id); }
        reset() { store.filters.splice(0); store.tagIds.splice(0); store.search = ""; store.setFolder(null); }
    }

    // ======================= Weitere Ansichten ======================= //

    class KanbanView extends Component {
        static components = { Icon, Thumb };
        static template = xml`
            <div class="tiles">
                <div class="tile" t-foreach="store.pageDocs" t-as="d" t-key="d.id" t-att-class="{ selected: store.selected.includes(d.id) }"
                     draggable="true" t-on-dragstart="(ev) => onDragStart(ev, d)" t-on-dragend="() => store.dragIds = []"
                     t-on-click="() => store.detailId = d.id" t-on-dblclick="() => store.quickLookId = d.id">
                    <div class="check" t-att-class="{ on: store.selected.includes(d.id) }" t-on-click.stop="() => store.toggleSelect(d.id)"><Icon name="'check'"/></div>
                    <button class="star" t-att-class="{ on: d.fav }" t-on-click.stop="() => d.fav = !d.fav"><Icon name="'star'"/></button>
                    <div class="pic"><Thumb name="d.name" size="86"/></div>
                    <div class="meta">
                        <span class="t truncate" t-esc="d.name" t-att-title="d.name"/>
                        <span class="s"><span class="truncate" t-esc="fx.path(d.folderId).slice(-1)[0]"/><span t-esc="fx.size(d.size)"/></span>
                    </div>
                </div>
            </div>`;
        setup() { this.store = useState(store); this.fx = fx; }
        onDragStart(ev, d) {
            store.dragIds = store.selected.includes(d.id) ? [...store.selected] : [d.id];
            ev.dataTransfer.setData("text/plain", "docs");
        }
    }

    class PivotView extends Component {
        static template = xml`
            <div class="panel-card">
                <h3>Dokumente nach Dateityp</h3>
                <table class="pivot">
                    <thead><tr><th>Dateityp</th><th class="r">Anzahl</th><th class="r">Größe</th></tr></thead>
                    <tbody>
                        <tr t-foreach="rows" t-as="r" t-key="r.kind.key"><td><span class="dot" t-attf-style="background: {{r.kind.color}}; margin-right: 8px"/><t t-esc="r.kind.label"/></td><td class="r" t-esc="r.count"/><td class="r" t-esc="fx.size(r.size)"/></tr>
                        <tr class="total"><td>Gesamt</td><td class="r" t-esc="total.count"/><td class="r" t-esc="fx.size(total.size)"/></tr>
                    </tbody>
                </table>
            </div>`;
        setup() { this.store = useState(store); this.fx = fx; }
        get rows() {
            const map = new Map();
            for (const d of this.store.visible) {
                const kind = fx.kind(d.name);
                const row = map.get(kind.key) || { kind, count: 0, size: 0 };
                row.count++;
                row.size += d.size;
                map.set(kind.key, row);
            }
            return [...map.values()].sort((a, b) => b.size - a.size);
        }
        get total() { return { count: this.store.visible.length, size: this.store.visible.reduce((n, d) => n + d.size, 0) }; }
    }

    class GraphView extends PivotView {
        static template = xml`
            <div class="panel-card">
                <h3>Speicherbedarf nach Dateityp</h3>
                <div class="bars">
                    <t t-foreach="rows" t-as="r" t-key="r.kind.key">
                        <span t-esc="r.kind.label"/>
                        <div class="bar"><i t-attf-style="width: {{r.size / max * 100}}%; --c: {{r.kind.color}}"/></div>
                        <span class="num" t-esc="fx.size(r.size)"/>
                    </t>
                </div>
            </div>`;
        get max() { return Math.max(1, ...this.rows.map((r) => r.size)); }
    }

    // ======================= Overlays ======================= //

    class SelectionBar extends Component {
        static components = { Icon };
        static template = xml`
            <div class="selbar" t-if="store.selected.length">
                <span class="cnt"><t t-esc="store.selected.length"/> ausgewählt</span>
                <button t-on-click="() => store.toast('Download wird als ZIP vorbereitet …', { icon: 'download' })"><Icon name="'download'"/> Herunterladen</button>
                <button t-on-click="() => store.toast('Ziehe die Auswahl auf einen Ordner links', { icon: 'info' })"><Icon name="'move'"/> Verschieben</button>
                <button t-on-click="tag"><Icon name="'tag'"/> Tag</button>
                <button t-on-click="() => { store.toast(store.selected.length + ' Dokumente archiviert', { icon: 'trash' }); store.selected = []; }"><Icon name="'trash'"/> Archivieren</button>
                <span class="sep"/>
                <button t-on-click="() => store.selected = []" title="Auswahl aufheben (Esc)"><Icon name="'x'"/></button>
            </div>`;
        setup() { this.store = useState(store); }
        tag() {
            for (const id of store.selected) {
                const d = docs.find((x) => x.id === id);
                if (!d.tagIds.includes(1)) d.tagIds.push(1);
            }
            store.toast(`Tag „${tags[0].name}“ gesetzt`, { icon: "tag" });
        }
    }

    class DetailPanel extends Component {
        static components = { Icon, Paper };
        static template = xml`
            <aside class="detail" t-if="doc">
                <div class="dh">
                    <span class="t" t-esc="doc.name"/>
                    <button class="ibtn" title="Schließen (Esc)" t-on-click="() => store.detailId = null"><Icon name="'x'"/></button>
                </div>
                <div class="scroll">
                    <div class="preview" t-on-click="() => store.quickLookId = doc.id">
                        <Paper name="doc.name" small="true"/>
                        <span class="hint">Klicken oder Leertaste für Vollbild</span>
                    </div>
                    <div class="acts">
                        <button class="btn primary" t-on-click="() => store.toast('Wird heruntergeladen', { icon: 'download' })"><Icon name="'download'"/> Herunterladen</button>
                        <button class="btn" t-on-click="() => doc.fav = !doc.fav"><Icon name="'star'"/> <t t-esc="doc.fav ? 'Favorit' : 'Merken'"/></button>
                    </div>
                    <h4>Eigenschaften</h4>
                    <dl>
                        <dt>Ordner</dt><dd><a href="#" t-on-click.prevent="() => store.setFolder(doc.folderId)" t-esc="fx.path(doc.folderId).join(' › ')"/></dd>
                        <dt>Typ</dt><dd t-esc="fx.kind(doc.name).label + ' (' + fx.ext(doc.name).toUpperCase() + ')'"/>
                        <dt>Größe</dt><dd t-esc="fx.size(doc.size)"/>
                        <dt>Geändert</dt><dd t-esc="fx.dateFull(doc.date)"/>
                        <dt>Erstellt von</dt><dd>Administrator</dd>
                        <dt>Tags</dt><dd><span class="tagpill" t-foreach="doc.tagIds" t-as="t" t-key="t" t-attf-style="--c: {{tags[0].color}}" t-esc="tags[0].name"/><span class="muted" t-if="!doc.tagIds.length">–</span></dd>
                        <dt t-if="dups.length">Duplikate</dt>
                        <dd t-if="dups.length"><div t-foreach="dups" t-as="d" t-key="d.id"><a href="#" t-on-click.prevent="() => store.detailId = d.id" t-esc="fx.path(d.folderId).slice(-2).join(' › ')"/></div></dd>
                    </dl>
                    <h4>Verlauf</h4>
                    <div class="tl">
                        <div><i/><span>Hochgeladen von Administrator · <t t-esc="fx.date(doc.date).main"/></span></div>
                        <div t-if="fx.kind(doc.name).key === 'pdf'"><i/><span>Text erkannt (OCR) · 3 Seiten</span></div>
                        <div><i/><span>Vorschaubild erzeugt</span></div>
                    </div>
                </div>
            </aside>`;
        setup() { this.store = useState(store); this.fx = fx; this.tags = tags; }
        get doc() { return this.store.detail; }
        get dups() { return this.store.docs.filter((d) => d.hash === this.doc.hash && d.id !== this.doc.id); }
    }

    class QuickLook extends Component {
        static components = { Icon, Paper };
        static template = xml`
            <div class="overlay" t-if="doc" t-on-click="close">
                <div class="ql-bar" t-on-click.stop="() => {}">
                    <span class="t" t-esc="doc.name"/>
                    <span class="muted" t-esc="(index + 1) + ' von ' + list.length"/>
                    <button class="ibtn" title="Herunterladen"><Icon name="'download'"/></button>
                    <button class="ibtn" title="Schließen (Esc)" t-on-click="close"><Icon name="'x'"/></button>
                </div>
                <div class="ql-stage">
                    <button class="ql-nav l" t-on-click.stop="() => this.go(-1)"><Icon name="'left'"/></button>
                    <Paper name="doc.name"/>
                    <button class="ql-nav r" t-on-click.stop="() => this.go(1)"><Icon name="'right'"/></button>
                </div>
                <div class="ql-foot">← → blättern · Esc schließen</div>
            </div>`;
        setup() {
            this.store = useState(store);
            useExternalListener(window, "keydown", (ev) => {
                if (!store.quickLookId) return;
                if (ev.key === "ArrowRight") this.go(1);
                if (ev.key === "ArrowLeft") this.go(-1);
            });
        }
        get list() { return this.store.visible; }
        get index() { return this.list.findIndex((d) => d.id === this.store.quickLookId); }
        get doc() { return this.store.quickLookId && this.store.docs.find((d) => d.id === this.store.quickLookId); }
        go(step) {
            const next = this.list[(this.index + step + this.list.length) % this.list.length];
            if (next) store.quickLookId = next.id;
        }
        close() { store.quickLookId = null; }
    }

    class Toasts extends Component {
        static components = { Icon };
        static template = xml`
            <div class="toasts">
                <div class="toast" t-foreach="store.toasts" t-as="t" t-key="t.id">
                    <span t-att-class="t.icon === 'check' ? 'ok' : ''" style="display:contents"><Icon name="t.icon"/></span>
                    <div class="bd">
                        <div t-esc="t.text"/>
                        <div class="bar" t-if="t.progress !== undefined"><i t-attf-style="width: {{Math.min(100, t.progress)}}%"/></div>
                    </div>
                    <button t-if="t.action" t-on-click="() => { t.action.fn(); store.dismiss(t.id); }" t-esc="t.action.label"/>
                </div>
            </div>`;
        setup() { this.store = useState(store); this.Math = Math; }
    }

    class Dropzone extends Component {
        static components = { Icon };
        static template = xml`
            <div class="dropzone" t-if="store.fileDrag">
                <div class="box">
                    <Icon name="'upload'"/>
                    <h2>Dateien hier ablegen</h2>
                    <div t-if="store.folderId">Ziel: <b t-esc="fx.path(store.folderId).join(' › ')"/></div>
                    <div t-else="">Wähle zuerst einen Ordner in der Leiste links</div>
                </div>
            </div>`;
        setup() { this.store = useState(store); this.fx = fx; }
    }

    // ======================= App ======================= //

    class Root extends Component {
        static components = { Navbar, ControlPanel, QuickBar, Sidebar, ListView, KanbanView, PivotView, GraphView, DetailPanel, SelectionBar, QuickLook, Toasts, Dropzone };
        static template = xml`
            <div class="app" t-on-click="() => store.menu = null">
                <Navbar/>
                <ControlPanel/>
                <QuickBar/>
                <div class="body">
                    <Sidebar/>
                    <main class="main">
                        <div class="content">
                            <ListView t-if="store.view === 'list'"/>
                            <KanbanView t-elif="store.view === 'kanban'"/>
                            <PivotView t-elif="store.view === 'pivot'"/>
                            <GraphView t-else=""/>
                        </div>
                        <SelectionBar/>
                    </main>
                    <DetailPanel/>
                </div>
                <QuickLook/>
                <Toasts/>
                <Dropzone/>
            </div>`;
        setup() {
            this.store = useState(store);
            useEffect(
                (dark) => { document.documentElement.dataset.theme = dark ? "dark" : "light"; },
                () => [store.dark]
            );
            useExternalListener(window, "keydown", (ev) => {
                const typing = ["INPUT", "TEXTAREA"].includes(ev.target.tagName);
                if (ev.key === "Escape") {
                    if (store.menu) store.menu = null;
                    else if (store.quickLookId) store.quickLookId = null;
                    else if (store.detailId) store.detailId = null;
                    else if (store.selected.length) store.selected = [];
                    else if (typing) ev.target.blur();
                } else if (ev.key === " " && !typing) {
                    ev.preventDefault();
                    const id = store.quickLookId ? null : store.detailId || store.selected[0];
                    store.quickLookId = id || null;
                }
            });
            // Dateien von außen: Dropzone zeigen und hochladen.
            const hasFiles = (ev) => ev.dataTransfer && [...ev.dataTransfer.types].includes("Files");
            useExternalListener(window, "dragenter", (ev) => { if (hasFiles(ev)) store.fileDrag = true; });
            useExternalListener(window, "dragover", (ev) => { if (hasFiles(ev)) ev.preventDefault(); });
            useExternalListener(window, "dragleave", (ev) => { if (!ev.relatedTarget) store.fileDrag = false; });
            useExternalListener(window, "drop", (ev) => {
                if (!hasFiles(ev)) return;
                ev.preventDefault();
                store.fileDrag = false;
                store.upload([...ev.dataTransfer.files].map((f) => ({ name: f.name, size: f.size })));
            });
        }
    }

    new OwlApp(Root, { name: "int_filemanager_mockup" }).mount(document.getElementById("app"));
})();
