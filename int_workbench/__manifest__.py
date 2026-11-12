{
    "name": "Service Workbench",
    "summary": "Monitor and control controllers of vehicles through the Service Workbench.",
    "description": (
        "Controllers are records that a service (the Go program that holds the line to the controller) reports to through the JSON-2 "
        "API of Odoo, with the API key of a service user. The service tells which family each controller belongs to and what it can "
        "do, and the lists show or hide what a controller cannot do. The module shows the process values and the errors, lets "
        "operators clamp and release values (every request is a record that the service carries out and that stays in the clamp "
        "log), and shows the accounts, the write log and the project library of the service."
    ),
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["base", "web", "bus"],
    "data": [
        "security/int_workbench_groups.xml",
        "security/ir.model.access.csv",
        "data/int_workbench_capability_data.xml",
        "views/int_workbench_device_views.xml",
        "views/int_workbench_family_views.xml",
        "views/int_workbench_parameter_views.xml",
        "views/int_workbench_command_views.xml",
        "views/int_workbench_error_views.xml",
        "views/int_workbench_log_views.xml",
        "views/int_workbench_user_views.xml",
        "views/int_workbench_project_views.xml",
        "wizard/int_workbench_parameter_clamp_views.xml",
        "wizard/int_workbench_project_import_views.xml",
        "views/int_workbench_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_workbench/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
