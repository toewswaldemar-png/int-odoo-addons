{
    "name": "Generic",
    "summary": "Kleinere generische Anpassungen ohne Bindung an eine Business-App.",
    "description": (
        "Sammelmodul für kleinere, app-unabhängige Odoo-Anpassungen (Frontend wie Backend). "
        "Jede Anpassung liegt in eigenen, unabhängigen Dateien unter static/src/ bzw. models/."
    ),
    "version": "19.0.1.0.1",
    "category": "Productivity",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "assets": {
        "web.assets_backend": [
            "int_generic/static/src/list_column_reorder.js",
            "int_generic/static/src/list_column_reorder.scss",
        ],
    },
    "installable": True,
    "application": False,
}
