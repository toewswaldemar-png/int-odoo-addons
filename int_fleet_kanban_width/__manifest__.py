{
    "name": "Fleet Kanban Width",
    "summary": "Fuhrpark-Kanban-Spalten teilen sich den verfuegbaren Platz statt horizontal zu scrollen.",
    "description": (
        "Odoos Standard-Kanban haelt pro Spalte eine Mindestbreite von ca. 320px+Padding ein "
        "(--KanbanGroup-width in web/kanban_controller.scss); bei mehr Stufen als bei dieser "
        "Breite reinpassen scrollt die Ansicht horizontal statt zu schrumpfen. Dieses Modul "
        "senkt die Mindestbreite nur fuer die Fahrzeuge-Kanban-Ansicht (fleet.vehicle), damit "
        "alle Stufen auf einen Blick sichtbar bleiben."
    ),
    "version": "19.0.1.0.0",
    "category": "Human Resources/Fleet",
    "license": "LGPL-3",
    "depends": ["fleet", "web"],
    "data": [
        "views/fleet_vehicle_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_fleet_kanban_width/static/src/fleet_kanban_width.scss",
        ],
    },
    "installable": True,
    "application": False,
}
