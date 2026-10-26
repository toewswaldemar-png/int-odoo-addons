from odoo.tools import SQL

# The tables of the models removed when the file manager restarted on folders and documents.
EARLIER_TABLES = (
    "int_filemanager_blob",
    "int_filemanager_derivative",
    "int_filemanager_extracted_value",
    "int_filemanager_extraction_field",
    "int_filemanager_extraction_hint",
    "int_filemanager_extraction_pattern",
    "int_filemanager_extraction_rule",
    "int_filemanager_field_value",
    "int_filemanager_file",
    "int_filemanager_file_int_filemanager_tag_rel",
    "int_filemanager_node",
    "int_filemanager_node_shared_partner_rel",
    "int_filemanager_node_tag_rel",
    "int_filemanager_operation",
    "int_filemanager_pf_read_rel",
    "int_filemanager_pf_unlink_rel",
    "int_filemanager_pf_write_rel",
    "int_filemanager_protected_folder",
    "int_filemanager_revision",
    "int_filemanager_scan_log",
    "int_filemanager_scope",
    "int_filemanager_scope_manage_group_rel",
    "int_filemanager_scope_purge_group_rel",
    "int_filemanager_scope_read_group_rel",
    "int_filemanager_scope_write_group_rel",
    "int_filemanager_share_log",
    "int_filemanager_shared_partner_rel",
    "int_filemanager_status",
    "int_filemanager_upload",
    "int_filemanager_version",
    "int_filemanager_write_journal",
    "int_filemanager_zip_job",
)


def migrate(cr, version):
    """Drop what the removed models left: Odoo keeps the tables of a model that is gone."""
    for table in EARLIER_TABLES:
        cr.execute(SQL("DROP TABLE IF EXISTS %s CASCADE", SQL.identifier(table)))
    cr.execute("""
        ALTER TABLE IF EXISTS int_filemanager_share
            DROP COLUMN IF EXISTS node_id,
            DROP COLUMN IF EXISTS expires_at,
            DROP COLUMN IF EXISTS revoked_at
    """)
    cr.execute("DELETE FROM ir_model WHERE model = 'int_filemanager.tag'")
    cr.execute("""
        DELETE FROM ir_config_parameter
         WHERE key IN ('int_filemanager.watcher_enabled', 'int_filemanager.last_scan_completed')
    """)
