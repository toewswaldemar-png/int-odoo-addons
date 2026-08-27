{
    "name": "Repair Workshop Fields",
    "summary": "Werkstatt-Felder am Reparaturauftrag - löst die manuelle Excel-Reparaturübersicht ab.",
    "description": (
        "Ergänzt repair.order um Auftragsart, Eingangsdatum, eine berechnete Resttage-Anzeige und "
        "sieben Werkstattstufen (je ein Mitarbeiter-Feld: leer = noch nicht dran, gesetzt = erledigt "
        "und von wem). Odoos bestehende Felder (Produkt, Seriennummer, geplantes Datum, Priorität, "
        "Notizen) werden bewusst weiterverwendet statt dupliziert."
    ),
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Repair",
    "license": "LGPL-3",
    "depends": ["repair", "hr"],
    "data": [
        "views/repair_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_repair_workshop/static/src/repair_order_list.scss",
        ],
    },
    "installable": True,
    "application": False,
}
