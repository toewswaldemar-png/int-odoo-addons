{
    "name": "HM Filemanager",
    "summary": "Dateimanager für ein Verzeichnis auf der Festplatte, mit OnlyOffice-Integration.",
    "description": (
        "Browst und verwaltet ein Verzeichnis auf dem Server-Dateisystem direkt aus Odoo heraus "
        "(Upload, Download, Umbenennen, Löschen, Ordner anlegen). Office-Dokumente lassen sich "
        "über die bestehende ONLYOFFICE-Integration direkt im Browser bearbeiten; Änderungen "
        "werden zurück auf die Originaldatei geschrieben."
    ),
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "HM",
    "license": "LGPL-3",
    "depends": ["base", "onlyoffice_odoo"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hm_filemanager/static/src/hm_filemanager/*",
        ],
    },
    "installable": True,
    "application": True,
}
