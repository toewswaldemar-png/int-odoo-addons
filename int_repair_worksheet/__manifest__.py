{
    "name": "BE01412 Interaktives QWeb-Arbeitsblatt",
    "version": "19.0.1.0.0",
    "summary": "Reparatur-Arbeitsblatt direkt im QWeb-Layout ausfüllen, speichern und drucken",
    "category": "Manufacturing/Repair", "license": "LGPL-3",
    "depends": ["repair", "web"],
    "data": ["security/ir.model.access.csv", "security/worksheet_rules.xml",
             "report/worksheet_reports.xml", "report/worksheet_templates.xml",
             "views/worksheet_editor.xml", "views/worksheet_views.xml"],
    "installable": True, "application": False,
}
