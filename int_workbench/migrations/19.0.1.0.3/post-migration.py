"""The type record is gone: the device has its type number and its controller as text.

The columns of the type links and the table of the types still exist while this script runs (they go at the end of the update).
"""


def migrate(cr, version):
    if not version:  # a new installation has nothing to carry over
        return
    cr.execute("SELECT to_regclass('int_workbench_type') IS NOT NULL")
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        UPDATE int_workbench_device AS device
           SET device_type = COALESCE(NULLIF(type.ident, ''), type.name)
          FROM int_workbench_type AS type
         WHERE type.id = device.device_type_id
        """
    )
    cr.execute(
        """
        UPDATE int_workbench_device AS device
           SET controller_type = type.name
          FROM int_workbench_type AS type
         WHERE type.id = device.controller_type_id
        """
    )
