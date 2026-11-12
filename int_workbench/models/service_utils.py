"""Small helpers for the models that mirror what the service answers (users, log, projects)."""

import json
from datetime import datetime, timezone


def parse_time(text):
    """Return a naive UTC datetime for a time of the service (ISO 8601 with offset), or False if there is none."""
    if not text or not isinstance(text, str):
        return False
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment.replace(microsecond=0)


def as_text(value):
    """Return a value of the service as text: a list as a comma list, an object as JSON."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return ", ".join(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def upsert(records, key_field, wanted):
    """Bring the records of one controller to what the service answered, writing only what differs.

    :param records: the existing records of the controller
    :param str key_field: the field that identifies a record in the service
    :param dict wanted: ``{key: vals}`` for every record the service has; ``vals`` includes ``device_id``
    :return: the records created or written
    """
    known = {record[key_field]: record for record in records}
    touched = records.browse()
    create = []
    for key, vals in wanted.items():
        record = known.get(key)
        if record is None:
            create.append({key_field: key, **vals})
            continue
        diff = {name: value for name, value in vals.items() if _differs(record[name], value)}
        if diff:
            record.write(diff)
            touched |= record
    if create:
        touched |= records.create(create)
    return touched


def _differs(old, new):
    if isinstance(new, bool):
        return bool(old) != new
    if isinstance(new, str):
        return (old or "") != new
    if isinstance(old, float) or isinstance(new, float):
        return float(old or 0) != float(new or 0)  # noqa: RUF069 (exact on purpose: an unchanged report value must cause no write)
    if hasattr(old, "id"):
        return old.id != new
    return (old or False) != (new or False)
