"""The description a process value has until now is the one the project gives: keep it in source_name before the module is loaded
(name is computed from now on, and a recomputation must not find source_name empty)."""


def migrate(cr, version):
    if not version:  # a new installation has nothing to carry over
        return
    cr.execute("ALTER TABLE int_workbench_parameter ADD COLUMN IF NOT EXISTS source_name varchar")
    cr.execute("UPDATE int_workbench_parameter SET source_name = name WHERE source_name IS NULL")
