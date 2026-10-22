{
    "name": "KeePass",
    "summary": "Groups and entries of a KeePass file or a Vaultwarden account as virtual records.",
    "description": (
        "Shows the groups and entries (title, user name, address) of a KeePass file (.kdbx) or of a "
        "Vaultwarden account as ordinary records, without storing them in the database. Read only; "
        "passwords and notes are never read. The master password stays in the memory of the browser."
    ),
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Waldemar Toews",
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
