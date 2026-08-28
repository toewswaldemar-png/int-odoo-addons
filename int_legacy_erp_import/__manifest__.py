{
    "name": "Legacy ERP Import (Test)",
    "summary": "Testballon: Produktdaten aus dem alten ERP als Grundlage für die Frage, ob ein Odoo-Umstieg sinnvoll ist.",
    "description": (
        "Echte Produktfelder für die aus dem Altsystem übernommenen Werte (Artikelnummer, "
        "Kurzbezeichnung, Bestellnummer, Hersteller-Referenzen etc.), gruppiert auf der "
        "Karteikarte 'Allgemeine Informationen'. Rein für den Testimport gedacht - kein "
        "produktiver Datenimport."
    ),
    "version": "19.0.1.0.0",
    "category": "Inventory",
    "license": "LGPL-3",
    "depends": ["product"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "application": False,
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
}
