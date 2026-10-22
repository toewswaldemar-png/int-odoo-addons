{
    "name": "KeePass",
    "summary": "Groups and entries of a KeePass database as virtual records (experiment).",
    "description": (
        "Experiment: shows the groups and entries of a .kdbx file as ordinary records "
        "without storing them in the database. Read only; passwords are never read."
    ),
    "version": "19.0.0.1.0",
    "category": "Productivity",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "external_dependencies": {"python": ["pykeepass"]},
    "data": [
        "security/ir.model.access.csv",
        "views/int_keepass_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_keepass/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
