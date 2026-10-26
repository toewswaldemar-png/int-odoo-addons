{
    "name": "Filemanager import",
    "summary": "Read a folder of the server's disk into the filemanager.",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["int_filemanager"],
    "data": [
        "security/int_filemanager_import_security.xml",
        "security/int_filemanager_import_line_security.xml",
        "security/ir.model.access.csv",
        "views/int_filemanager_import_views.xml",
        "views/int_filemanager_import_line_views.xml",
        "views/res_config_settings_views.xml",
        "data/int_filemanager_import_data.xml",
    ],
}
