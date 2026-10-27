import os

from odoo.exceptions import UserError

from .models.int_filemanager_document import BLOB_FOLDER
from .tools.files import remove_path
from .tools.filestore import filestore

# The collation of the unique indexes of the names: it folds the case of a name as a person sees it
# ("Ä" and "ä" are one name), which the "C" locale of an Odoo database does not do.
COLLATION = "und-x-icu"


def pre_init_hook(env):
    """Stop the installation with a clear message on a PostgreSQL built without ICU."""
    env.cr.execute("SELECT 1 FROM pg_collation WHERE collname = %s", [COLLATION])
    if not env.cr.rowcount:
        raise UserError(
            env._(
                "This module needs a PostgreSQL built with ICU: the collation %(collation)s is missing.",
                collation=COLLATION,
            )
        )


def uninstall_hook(env):
    """Remove the files of the documents from the filestore of the database.

    The documents go with the module, and the garbage collector of the files is a method of
    the module: what lies in ``<filestore>/int_filemanager`` would stay for ever, with nobody
    to look after it. It runs after the commit: if the uninstallation fails and is rolled
    back, the documents are still there and need their files.
    """
    path = os.path.join(filestore(env), BLOB_FOLDER)
    env.cr.postcommit.add(lambda: remove_path(path))
