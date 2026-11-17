"""name is the own name of a process value, or else the description of the project (source_name)."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("UPDATE int_workbench_parameter SET name = COALESCE(NULLIF(label, ''), source_name, '')")
