{
    "name": "UI Showcase",
    "summary": "Test page with the UI building blocks of Odoo: views, field widgets, dialogs and core components.",
    "description": (
        "Shows every view type and field widget on one demo model and the Owl core components "
        "(notifications, dialogs, dropdown, select menu, tags, pager) on a client action page."
    ),
    "version": "19.0.1.0.0",
    "category": "Hidden/Tools",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["base", "web", "mail", "portal"],
    "data": [
        "security/ir.model.access.csv",
        "views/int_ui_showcase_views.xml",
        "views/int_ui_showcase_form.xml",
        "views/res_config_settings_views.xml",
        "views/int_ui_showcase_portal_templates.xml",
        "report/int_ui_showcase_report.xml",
        "views/int_ui_showcase_menus.xml",
        "data/int_ui_showcase_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "int_ui_showcase/static/src/components/ui_pages.js",
            "int_ui_showcase/static/src/components/ui_pages.xml",
            "int_ui_showcase/static/src/components/ui_components.js",
            "int_ui_showcase/static/src/components/ui_components.xml",
            "int_ui_showcase/static/src/components/numpad.scss",
        ],
        "web.assets_tests": [
            "int_ui_showcase/static/tests/tours/*.js",
        ],
    },
    "installable": True,
    "application": True,
}
