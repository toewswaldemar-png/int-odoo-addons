{
    "name": "Filemanager full text search and text recognition",
    "summary": "Search in the text of the files, and read the text of scans (OCR).",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["int_filemanager"],
    "data": [
        "security/ir.model.access.csv",
        "views/int_filemanager_text_views.xml",
        "views/int_filemanager_document_views.xml",
        "views/int_filemanager_folder_views.xml",
        "views/res_config_settings_views.xml",
        "data/int_filemanager_text_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_filemanager_ocr/static/src/**/*",
        ],
        "web.assets_unit_tests": [
            "int_filemanager_ocr/static/tests/**/*",
        ],
    },
}
