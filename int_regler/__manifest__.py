{
    "name": "Controller",
    "summary": "Monitor and control the climate controllers of the vehicles through the controller service.",
    "description": (
        "Controllers are records with the address of the controller service (the Go program that holds the "
        "serial line to the 11HA controller). The page of the module shows status, process values and errors "
        "and, after a sign-in at the service, sets and releases clamps. The browser talks to the service "
        "directly; Odoo stores only the address."
    ),
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [
        "security/int_regler_groups.xml",
        "security/ir.model.access.csv",
        "views/int_regler_device_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_regler/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
