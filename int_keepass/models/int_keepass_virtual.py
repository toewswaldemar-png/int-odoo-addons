from odoo import models


class IntKeepassVirtual(models.AbstractModel):
    """Records that exist only in the .kdbx file.

    Same approach as ``account.code.mapping`` in the core: no table, the ids
    come from a ``_search`` override and the fields are computed from them.
    """

    _name = "int.keepass.virtual"
    _description = "KeePass Virtual Record"

    # key of this model in ``int.keepass.source._data()``
    _data_key = None

    def _search(self, domain, offset=0, limit=None, order=None, **kw):
        rows = self.env["int.keepass.source"]._data()[self._data_key]
        records = self.browse(list(rows)).filtered_domain(domain)
        records = records._sorted_by_order(order or self._order)
        start = offset or 0
        records = records[start:start + limit] if limit else records[start:]
        return records._as_query()

    def _sorted_by_order(self, order):
        """Sort like an SQL ``ORDER BY``: the terms in turn, the last one first (sorting is stable)."""
        records = self
        for term in reversed([term.split() for term in order.split(",") if term.strip()]):
            name = term[0]
            if name not in self._fields:
                continue
            reverse = len(term) > 1 and term[1].lower() == "desc"
            records = records.sorted(lambda record, name=name: record._sort_value(name), reverse=reverse)
        return records

    def _sort_value(self, name):
        value = self[name]
        if isinstance(value, models.BaseModel):
            value = value.display_name
        return value.lower() if isinstance(value, str) else (value or "")

    def _row(self):
        self.ensure_one()
        return self.env["int.keepass.source"]._data()[self._data_key].get(self.id, {})
