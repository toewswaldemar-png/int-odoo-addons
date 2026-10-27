{
    "name": "Filemanager share links",
    "summary": "Give a file or a folder to whoever has a link, with no account.",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["int_filemanager", "portal"],
    "pre_init_hook": "pre_init_hook",
    "data": [
        "security/int_filemanager_share_security.xml",
        "security/ir.model.access.csv",
        "views/int_filemanager_share_views.xml",
        "views/int_filemanager_share_templates.xml",
        "views/int_filemanager_document_views.xml",
        "views/int_filemanager_folder_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        # The item "Share" in the menu of a folder in the search panel of the documents.
        "web.assets_backend": [
            "int_filemanager_share/static/src/backend/**/*",
        ],
        # The upload area of the page of a shared folder: one interaction, loaded with the frontend.
        "web.assets_frontend": [
            "int_filemanager_share/static/src/interactions/**/*",
        ],
    },
}
