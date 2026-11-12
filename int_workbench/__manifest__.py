{
    "name": "Controller",
    "summary": "Monitor and control the climate controllers of the vehicles through the controller service.",
    "description": (
        "Controllers are records that a controller service (the Go program that holds the serial line to the "
        "11HA controller) reports to through the JSON-2 API of Odoo, with the API key of a service user. The "
        "page of the module shows what was reported: status, process values and errors. Operators set and "
        "release clamps; each is a request that the service carries out and that stays in the clamp log."
    ),
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["base", "web", "bus"],
    "data": [
        "security/int_workbench_groups.xml",
        "security/ir.model.access.csv",
        "views/int_workbench_device_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_workbench/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
