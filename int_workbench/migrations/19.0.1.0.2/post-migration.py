"""Projects and programs lose their approval (draft, approved, retired). What was retired is archived now.

The old state column is still there while this script runs (the update drops it at its end), so it is read here.
"""


def migrate(cr, version):
    if not version:  # a new installation has nothing to carry over
        return
    for table in ("int_workbench_project_version", "int_workbench_software"):
        cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = 'state'", (table,))
        if cr.fetchone():
            cr.execute(f"UPDATE {table} SET active = (state <> 'retired')")  # noqa: S608 - fixed table names
