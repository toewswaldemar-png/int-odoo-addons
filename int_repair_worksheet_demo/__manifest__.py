{
    "name": "BE01412 QWeb-Arbeitsblatt (Layouttest)",
    "version": "19.0.1.0.0",
    "summary": "Formulareingaben als Reparatur-Arbeitsblatt im BE01412-Layout drucken",
    "category": "Manufacturing/Repair",
    "license": "LGPL-3",
    "depends": ["repair", "web"],
    "data": [
        "security/ir.model.access.csv",
        "report/worksheet_reports.xml",
        "report/worksheet_templates.xml",
        "wizard/worksheet_views.xml",
    ],
    "installable": True,
    "application": False,
}
