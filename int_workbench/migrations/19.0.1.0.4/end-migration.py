"""The tables of the family record are not dropped by the update (the model has no table any more), so they go here."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("DROP TABLE IF EXISTS int_workbench_family_capability_rel CASCADE")
    cr.execute("DROP TABLE IF EXISTS int_workbench_family CASCADE")
