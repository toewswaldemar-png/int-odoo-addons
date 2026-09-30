from odoo.modules.registry import Registry

from odoo.addons.int_filemanager import pg_extensions


def migrate(cr, version):
    """The text search of this version needs a trigram index on the derived text, and
    with it the pg_trgm extension, which a database that Odoo did not create itself
    may lack."""
    pg_extensions.ensure_trigram(Registry(cr.dbname), cr)
