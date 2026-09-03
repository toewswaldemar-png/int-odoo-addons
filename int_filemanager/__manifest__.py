{
    "name": "Filemanager",
    "summary": "Dateimanager für ein Verzeichnis auf der Festplatte, mit OnlyOffice-Integration.",
    "description": (
        "Browst und verwaltet ein Verzeichnis auf dem Server-Dateisystem direkt aus Odoo heraus "
        "(Upload, Download, Umbenennen, Löschen, Ordner anlegen). Office-Dokumente lassen sich "
        "über die bestehende ONLYOFFICE-Integration direkt im Browser bearbeiten; Änderungen "
        "werden zurück auf die Originaldatei geschrieben."
    ),
    "version": "19.0.1.3.0",
    "category": "Productivity",
    "license": "LGPL-3",
    "depends": ["base", "bus", "onlyoffice_odoo"],
    "post_load": "post_load",
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/filemanager_file_search.xml",
        "views/menu.xml",
        "views/filemanager_protected_folder_views.xml",
        "views/res_partner_views.xml",
        "data/ir_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_filemanager/static/src/int_filemanager/*",
        ],
    },
    "installable": True,
    "application": True,
}
