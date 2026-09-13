{
    "name": "Filemanager",
    "summary": "Dateimanager für ein Verzeichnis auf der Festplatte, mit OnlyOffice-Integration.",
    "description": (
        "Browst und verwaltet ein Verzeichnis auf dem Server-Dateisystem direkt aus Odoo heraus "
        "(Upload, Download, Umbenennen, Löschen, Ordner anlegen). Office-Dokumente lassen sich "
        "über die bestehende ONLYOFFICE-Integration direkt im Browser bearbeiten; Änderungen "
        "werden zurück auf die Originaldatei geschrieben."
    ),
    "version": "19.0.1.7.2",
    "category": "Productivity",
    "license": "LGPL-3",
    "depends": ["base", "bus", "mail", "portal", "onlyoffice_odoo"],
    "post_load": "post_load",
    "post_init_hook": "post_init_hook",
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/filemanager_status.xml",
        "data/filemanager_extraction_pattern.xml",
        "views/filemanager_file_search.xml",
        "views/filemanager_file_list_view.xml",
        "views/filemanager_file_kanban_view.xml",
        "views/menu.xml",
        "views/res_config_settings_views.xml",
        "views/filemanager_protected_folder_views.xml",
        "views/filemanager_status_views.xml",
        "views/filemanager_extraction_pattern_views.xml",
        "views/res_partner_views.xml",
        "views/filemanager_file_form_view.xml",
        "views/filemanager_file_share_views.xml",
        "views/portal_templates.xml",
        "data/ir_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_filemanager/static/src/int_filemanager/**/*",
        ],
    },
    "installable": True,
    "application": True,
}
