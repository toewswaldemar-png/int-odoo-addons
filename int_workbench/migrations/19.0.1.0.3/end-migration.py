"""The table of the type record is not dropped by the update (the model is no longer in the registry), so it goes here."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("DROP TABLE IF EXISTS int_workbench_type CASCADE")
