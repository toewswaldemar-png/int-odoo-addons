/* Testdaten des Mockups: die 18 Zeilen des Screenshots, danach erzeugte bis 199 (feste Zufallsfolge). */
(function () {
    const NOW = new Date(2026, 9, 27, 13, 0); // 27. Okt. 2026, wie im Screenshot

    const folders = [
        { id: 1, name: "Test", parent: null },
        { id: 2, name: "Anträge und Formulare", parent: 1 },
        { id: 3, name: "Formulare", parent: 2 },
        { id: 4, name: "Kinderzuschlag", parent: 3 },
        { id: 5, name: "Kinderzuschlag & Wohngeld", parent: 2 },
        { id: 6, name: "2024-02 Kinderzuschlag", parent: 5 },
        { id: 7, name: "2025-02Kinderzuschlag", parent: 5 },
        { id: 8, name: "2025-04 Wohngeld", parent: 5 },
        { id: 9, name: "Nachweise", parent: 8 },
        { id: 10, name: "2026-02 Kinderzuschlag", parent: 5 },
        { id: 11, name: "Antrag", parent: 10 },
        { id: 12, name: "Antrag", parent: 7 },
        { id: 13, name: "Nachweise", parent: 7 },
    ];

    const tags = [{ id: 1, name: "dsfsfds", color: "#c13fa4" }];

    const KB = 1024;
    const MB = 1024 * 1024;
    const at = (h, m, d = 27, mo = 9, y = 2026) => new Date(y, mo, d, h, m);

    // [Name, Ordner, Bytes, Datum, Tags, Favorit, Hash]
    const real = [
        ["1 Hinweise zur Antragstellung.pdf", 4, 182 * KB, at(12, 30), [1], true, "h1"],
        ["2 Antrag auf Kinderzuschlag (1).pdf", 6, 1.2 * MB, at(12, 7), [], true, "h2"],
        ["2 Antrag auf Kinderzuschlag Unterschrift.pdf", 7, 896 * KB, at(12, 7), [], false, "h3"],
        ["2 Antrag auf Kinderzuschlag unterschrieben.pdf", 11, 1.8 * MB, at(12, 7), [], false, "h4"],
        ["2 Antrag auf Kinderzuschlag unterschrieben.pdf", 12, 491 * KB, at(12, 7), [], false, "h5"],
        ["2 Antrag auf Kinderzuschlag.pdf", 7, 1.9 * MB, at(12, 7), [], false, "h6"],
        ["2 Antrag auf Kinderzuschlag.pdf", 6, 1.9 * MB, at(12, 7), [], false, "h7"],
        ["2 Antrag auf Kinderzuschlag.pdf", 10, 1.9 * MB, at(12, 7), [], false, "h8"],
        ["2 Antrag auf Kinderzuschlag.pdf", 4, 1.1 * MB, at(12, 7), [], false, "h9"],
        ["2023 Rechnung Schornsteinfeger.pdf", 9, 495 * KB, at(12, 7), [], false, "h10"],
        ["2024 Abrechnung 12 Monate.pdf", 9, 212 * KB, at(12, 7), [], false, "h11"],
        ["2024 Abrechnung 6 Monate Waldemar Toews.pdf", 13, 108 * KB, at(12, 7), [], false, "h12"],
        ["2024 Abwasser.pdf", 6, 10.4 * MB, at(12, 7), [], false, "h13"],
        ["2024 Beitragsrechnung KFZ Haftpflicht.pdf", 13, 24 * KB, at(12, 7), [], false, "h14"],
        ["2024 Berechnung Fahrtkosten zur Arbeitsstätte.odt", 8, 26 * KB, at(12, 7), [], false, "h15"],
        ["2024 Berechnung Fahrtkosten zur Arbeitsstätte.odt", 7, 28 * KB, at(12, 7), [], false, "h16"],
        ["2024 Bescheinigung Risikolebensversicherung.pdf", 13, 59 * KB, at(12, 7), [], false, "h17"],
        ["2024 Bescheinigung Risikolebensversicherung.pdf", 9, 59 * KB, at(12, 7), [], false, "h17"],
    ];

    // Erzeugte Dokumente (ab hier nur Füllung für Seiten, Suche und Filter).
    let seed = 7;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    const pick = (list) => list[Math.floor(rnd() * list.length)];
    const stems = [
        "Bescheid Wohngeld", "Mietvertrag", "Kontoauszug", "Gehaltsabrechnung", "Nebenkostenabrechnung",
        "Versicherungspolice", "Steuerbescheid", "Kita Gebührenbescheid", "Rentenauskunft", "Kündigung Handyvertrag",
        "Arztrechnung", "Schulbescheinigung", "Meldebescheinigung", "Antrag Bildung und Teilhabe", "Scan",
        "Strom Jahresabrechnung", "Gasabschlag", "Fahrtkostennachweis", "Vollmacht", "Bankbestätigung",
    ];
    const exts = ["pdf", "pdf", "pdf", "pdf", "jpg", "png", "docx", "xlsx", "odt"];
    const folderIds = folders.filter((f) => f.id > 3).map((f) => f.id);
    const monthsBack = [0, 0, 1, 1, 2, 3, 5, 8, 11, 14];

    const docs = real.map(([name, folderId, size, date, tagIds, fav, hash], i) => ({
        id: i + 1, name, folderId, size: Math.round(size), date, tagIds, fav, hash, mine: i % 3 === 0,
    }));
    for (let i = docs.length; i < 199; i++) {
        const ext = pick(exts);
        const back = pick(monthsBack);
        const date = new Date(2026, 9 - back, 1 + Math.floor(rnd() * 27), 7 + Math.floor(rnd() * 11), Math.floor(rnd() * 60));
        const year = 2023 + Math.floor(rnd() * 4);
        docs.push({
            id: i + 1,
            name: `${year} ${pick(stems)}${rnd() > 0.7 ? " " + (1 + Math.floor(rnd() * 9)) : ""}.${ext}`,
            folderId: pick(folderIds),
            size: Math.round((ext === "jpg" || ext === "png" ? 0.4 + rnd() * 4 : 0.02 + rnd() * 2) * MB),
            date: date > NOW ? NOW : date,
            tagIds: rnd() > 0.93 ? [1] : [],
            fav: rnd() > 0.95,
            hash: "g" + i,
            mine: rnd() > 0.6,
        });
    }

    window.MOCK = { NOW, folders, tags, docs };
})();
