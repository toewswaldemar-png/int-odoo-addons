{
    "name": "Filemanager records",
    "summary": "Documents tied to records (contacts, ...): seen and uploaded there.",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["int_filemanager"],
    "data": [
        "security/ir.model.access.csv",
        "security/ir.model.access.xml",
        "security/int_filemanager_document_security.xml",
        "security/int_filemanager_link_security.xml",
        "security/int_filemanager_model_folder_security.xml",
        "views/int_filemanager_link_views.xml",
        "views/int_filemanager_folder_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_filemanager_record/static/src/**/*",
        ],
    },
}
