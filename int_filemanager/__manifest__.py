{
    "name": "Filemanager",
    "summary": "Folders and documents as plain Odoo records.",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/int_filemanager_folder_security.xml",
        "security/int_filemanager_document_security.xml",
        "views/int_filemanager_menus.xml",
        "views/int_filemanager_folder_views.xml",
        "views/int_filemanager_document_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_filemanager/static/src/int_filemanager/**/*",
        ],
    },
    "application": True,
}
