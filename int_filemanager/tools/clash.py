"""The names that a move would make twice in one folder.

A folder cannot hold two active folders (or two active documents) of one name, case aside; the
unique indexes say so (``_name_per_parent``, ``_name_per_folder``). They fail with a message that
names nothing, so a move looks for the clash first, to tell which names it is.
"""

from collections import Counter

from odoo.tools import SQL

# Names shown in the message, the rest is counted.
CLASH_NAMES_SHOWN = 5


def clashing_names(env, table, column, target_id, names, moving_ids):
    """The ``names`` that are taken in the folder ``target_id`` (False: the top level).

    Two cases: a name that an active record of the target has already (the records that are
    moving are not counted, they leave their place), and a name that two of the moving records
    share, since they all come to the same place. Case does not matter, like in the index.
    """
    names = list(names)
    taken = []
    if names:
        rows = env.execute_query(
            SQL(
                """
                SELECT moving.name FROM unnest(%(names)s::text[]) AS moving(name)
                WHERE lower(moving.name COLLATE "und-x-icu") IN (
                    SELECT lower(name COLLATE "und-x-icu") FROM %(table)s
                    WHERE active AND %(column)s IS NOT DISTINCT FROM %(target)s
                      AND NOT (id = ANY(%(moving)s)))
                """,
                names=names,
                table=SQL.identifier(table),
                column=SQL.identifier(column),
                target=target_id or None,
                moving=list(moving_ids),
            )
        )
        taken = [name for [name] in rows]
    twice = Counter(name.lower() for name in names)
    shared = [name for name in names if twice[name.lower()] > 1]
    return sorted({*taken, *shared}, key=str.lower)


def clash_summary(names):
    """The names for a message: the first few, then how many more there are."""
    shown = ", ".join(names[:CLASH_NAMES_SHOWN])
    more = len(names) - CLASH_NAMES_SHOWN
    return f"{shown} (+{more})" if more > 0 else shown
