"""The projects lose their vehicle and their folder record: the name of a version holds both ("vehicle/name").

The folder record and its column in the version table still exist while this script runs (they go at the end of the update, see
end-migration.py), so the names are copied from them here.
"""


def migrate(cr, version):
    if not version:  # a new installation has nothing to carry over
        return
    cr.execute("SELECT to_regclass('int_workbench_project_folder') IS NOT NULL")
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        UPDATE int_workbench_project_version AS version
           SET project = CASE WHEN COALESCE(folder.vehicle, '') <> '' THEN folder.vehicle || '/' || folder.name ELSE folder.name END
          FROM int_workbench_project_folder AS folder
         WHERE folder.id = version.folder_id
        """
    )
