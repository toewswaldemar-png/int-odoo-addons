{
    "name": "Filemanager image editor",
    "summary": "Draw on, crop, filter and redact the pictures of the filemanager.",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["int_filemanager"],
    "assets": {
        "web.assets_backend": [
            "int_filemanager_image_editor/static/src/backend/**/*",
        ],
        # The editor for pictures and Fabric, the library it draws with: loaded at the first
        # click on "Edit" (the registry `lazy_components`), not with every page.
        "int_filemanager_image_editor.assets_image_editor": [
            "int_filemanager_image_editor/static/lib/fabric/fabric.js",
            "int_filemanager_image_editor/static/src/image_editor/**/*",
        ],
        # The tests of the picture editor (Hoot); they load the bundle of the editor themselves.
        "web.assets_unit_tests": [
            "int_filemanager_image_editor/static/tests/**/*",
        ],
    },
}
