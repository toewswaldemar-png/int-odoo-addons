from odoo.exceptions import UserError

# The collation that the unique indexes of the names use: the case of a name is folded as a person
# sees it ("Ä" and "ä" are one name), which the "C" locale of an Odoo database does not do.
COLLATION = "und-x-icu"


def pre_init_hook(env):
    """Stop the installation with a clear message on a PostgreSQL that is built without ICU."""
    env.cr.execute("SELECT 1 FROM pg_collation WHERE collname = %s", [COLLATION])
    if not env.cr.rowcount:
        raise UserError(
            env._(
                "This module needs a PostgreSQL built with ICU: the collation %(collation)s is missing.",
                collation=COLLATION,
            )
        )
