"""The family record is gone: a device has the name of its original as text."""


def migrate(cr, version):
    if not version:  # a new installation has nothing to carry over
        return
    cr.execute("SELECT to_regclass('int_workbench_family') IS NOT NULL")
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        UPDATE int_workbench_device AS device
           SET family = COALESCE(NULLIF(family.label, ''), family.name)
          FROM int_workbench_family AS family
         WHERE family.id = device.family_id
        """
    )
