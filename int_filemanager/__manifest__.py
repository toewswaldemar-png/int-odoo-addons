{
    "name": "Filemanager",
    "summary": "Folders and documents as plain Odoo records.",
    "version": "19.0.1.0.1",
    "category": "Productivity",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/int_filemanager_groups.xml",
        "security/ir.model.access.csv",
        "security/ir.model.access.xml",
        "security/int_filemanager_folder_security.xml",
        "security/int_filemanager_document_security.xml",
        "security/int_filemanager_link_security.xml",
        "security/int_filemanager_model_folder_security.xml",
        "views/int_filemanager_menus.xml",
        "wizard/int_filemanager_move_views.xml",
        "views/int_filemanager_folder_views.xml",
        "views/int_filemanager_document_views.xml",
        "views/int_filemanager_link_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_users_views.xml",
        "data/int_filemanager_document_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_filemanager/static/src/int_filemanager/**/*",
        ],
        # The tests of the scripts (Hoot).
        "web.assets_unit_tests": [
            "int_filemanager/static/tests/**/*",
        ],
    },
    "application": True,
}
