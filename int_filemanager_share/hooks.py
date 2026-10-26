from odoo.tools import SQL

# The columns that the table of the shares had in the layers before the restart of the filemanager
# (the share pointed at a node, and had an end and a block date of its own).
EARLIER_COLUMNS = ("node_id", "expires_at", "revoked_at")


def pre_init_hook(env):
    """Drop what the earlier layers left in the table of the shares.

    Odoo keeps the columns of a field that is gone, and the table of ``int.filemanager.share`` was
    there before this module: a column that is required would stop the first share. The migration
    scripts of a module do not run when it is installed, so the hook does it.
    """
    for column in EARLIER_COLUMNS:
        env.cr.execute(
            SQL("ALTER TABLE IF EXISTS int_filemanager_share DROP COLUMN IF EXISTS %s", SQL.identifier(column))
        )
