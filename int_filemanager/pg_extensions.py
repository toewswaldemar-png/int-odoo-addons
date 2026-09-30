"""PostgreSQL extensions the module can use when the database has them.

Odoo creates ``pg_trgm`` only in databases it made itself; in one that came from a
dump or an older setup a trigram index (``index="trigram"``) is silently left out,
and a search that needs it reads the whole table.
"""

import logging

import psycopg2

from odoo.modules import db as odoo_db
from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def ensure_extension(cr, name):
    """Create the extension if it is missing; False if that is not possible."""
    try:
        with cr.savepoint():
            cr.execute(SQL("CREATE EXTENSION IF NOT EXISTS %s", SQL.identifier(name)))
    except psycopg2.Error as exc:
        _logger.warning(
            "could not create the PostgreSQL extension %s (%s); create it as a "
            "database administrator and update the module",
            name,
            str(exc).strip(),
        )
        return False
    return True


def ensure_trigram(registry, cr):
    """Make sure trigram indexes work in this database, also for the running registry.

    Odoo decides once, when the registry is built, whether the database has
    ``pg_trgm``; the flag is corrected here so that the indexes of the module being
    installed or updated are made in this run and not only in the next one.
    """
    if registry.has_trigram:
        return True
    if ensure_extension(cr, "pg_trgm"):
        registry.has_trigram = odoo_db.has_trigram(cr)
    return registry.has_trigram


def pre_init_hook(env):
    """Install path: before the tables and indexes of the module are made."""
    ensure_trigram(env.registry, env.cr)
