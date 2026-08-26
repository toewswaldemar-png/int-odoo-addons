{
    "name": "Web Tweaks",
    "summary": "Kleinere generische Anpassungen am Odoo-Web-Client, ohne Bindung an eine Business-App.",
    "description": (
        "Sammelmodul für kleinere Odoo-Web-Client-Anpassungen, die nur von 'web'/'base' abhängen. "
        "Jede Anpassung liegt in einer eigenen, unabhängigen Datei unter static/src/."
    ),
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "assets": {
        "web.assets_backend": [
            "int_web_tweaks/static/src/list_column_reorder.js",
            "int_web_tweaks/static/src/list_column_reorder.xml",
            "int_web_tweaks/static/src/list_column_reorder.scss",
        ],
    },
    "installable": True,
    "application": False,
}
