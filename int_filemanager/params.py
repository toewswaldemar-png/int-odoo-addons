"""Checks for the arguments of public model methods.

Every public method can be called by any logged-in client with any JSON, so a wrong
type must end as a message for the user, not as a server error halfway through.
"""

from odoo.exceptions import UserError


def require_id(env, value, argument):
    """Return ``value`` if it is a record id, else raise a ``UserError``."""
    if type(value) is not int or value <= 0:
        raise UserError(env._("%(argument)s is not valid.", argument=argument))
    return value


def optional_id(env, value, argument):
    """Return ``value`` as a record id, or False when none was given."""
    if value is None or value is False or (type(value) is int and value == 0):
        return False
    return require_id(env, value, argument)


def require_ids(env, values, argument, limit):
    """Return ``values`` if it is a list of at most ``limit`` record ids."""
    if not isinstance(values, list | tuple) or len(values) > limit:
        raise UserError(env._("%(argument)s is not valid.", argument=argument))
    return [require_id(env, value, argument) for value in values]


def require_text(env, value, argument, max_length=None, non_empty=False):
    """Return ``value`` if it is a string (not empty, of at most ``max_length``)."""
    if (
        not isinstance(value, str)
        or (non_empty and not value)
        or (max_length and len(value) > max_length)
    ):
        raise UserError(env._("%(argument)s is not valid.", argument=argument))
    return value


def require_choice(env, value, argument, choices):
    """Return ``value`` if it is one of ``choices``."""
    if not isinstance(value, str) or value not in choices:
        raise UserError(env._("%(argument)s is not valid.", argument=argument))
    return value
