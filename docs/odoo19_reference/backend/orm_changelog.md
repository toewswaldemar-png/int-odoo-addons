<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm/changelog.html · abgerufen 2026-10-02 -->

# Changelog

## Odoo version 19.0

- Add support for `GROUPING SETS` for pivot views.
  See [#194413](https://github.com/odoo/odoo/pull/194413).
- Adding support for dynamic dates in domains.
  See [#216665](https://github.com/odoo/odoo/pull/216665).
- Deprecated `odoo.osv` in [#217708](https://github.com/odoo/odoo/pull/217708).
- Deprecated `record._cr`, `record._context`, `record._uid` in [#193636](https://github.com/odoo/odoo/pull/193636).

## Odoo Online version 18.4

- The `reinit` option is added to the CLI to reinitialize modules.
  See [#206408](https://github.com/odoo/odoo/pull/206408).
- Possibility to write and combine custom domains for injecting arbitrary SQL.
  See [#205208](https://github.com/odoo/odoo/pull/205208).

## Odoo Online version 18.3

- Domain optimization is applied before executing `Fields.search` methods.
  All equalities are handled consistently: `=` is equivalent to `in`.
  See [#191549](https://github.com/odoo/odoo/pull/191549).
- New cron API for notifying progress with batch commits.
  See [#197781](https://github.com/odoo/odoo/pull/197781).
- Demo data no longer loaded by default.
  See [#194585](https://github.com/odoo/odoo/pull/194585).

## Odoo Online version 18.2

- `read_group` has been deprecated in favor of `_read_group` for backend usage and of
  `formatted_read_group` as formatted public API. See [#163300](https://github.com/odoo/odoo/pull/163300).
- `@api.private` is added to distinguish public Python methods from methods exposed for RPC calls.
  See [#195402](https://github.com/odoo/odoo/pull/195402).
- Native namespaces for `odoo` module [PEP-420](https://peps.python.org/pep-0420/).
  See [#195664](https://github.com/odoo/odoo/pull/195664).

## Odoo Online version 18.1

- New `odoo.domain` and `odoo.Domain` API for domain manipulation.
  See [#170009](https://github.com/odoo/odoo/pull/170009).
- Declare constraints and indexes as model attributes with [#175783](https://github.com/odoo/odoo/pull/175783).
- The `json` controllers have been renamed to `jsonrpc`. They are called the same, only the
  `type` in the python files changed. See [#183636](https://github.com/odoo/odoo/pull/183636).

## Odoo version 18.0

- Searching by name is now implemented as `_search_display_name` like all other fields.
  See [#174967](https://github.com/odoo/odoo/pull/174967).
- New methods to check access rights and rules now combine both access rights
  and rules: `check_access`, `has_access` and `_filtered_access`.
  See [#179148](https://github.com/odoo/odoo/pull/179148).
- Translations are made available from the `Environment` with [#174844](https://github.com/odoo/odoo/pull/174844).

## Odoo Online version 17.4

- The internal operator `inselect` is removed. The alternative is to use `in`
  with a Query or SQL object. [#171371](https://github.com/odoo/odoo/pull/171371).

## Odoo Online version 17.3

- We can now group by date parts numbers in `read_group`, `_read_group` and domains with [#159528](https://github.com/odoo/odoo/pull/159528).

## Odoo Online version 17.2

- The `group_operator` attribute of [`Field`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Field) is renamed into
  `aggregator` with [#127353](https://github.com/odoo/odoo/pull/127353).
- We can now group/aggregate/order by related no-store field with
  [#127353](https://github.com/odoo/odoo/pull/127353).

## Odoo Online version 17.1

- Method `_flush_search()` has been deprecated with
  [#144747](https://github.com/odoo/odoo/pull/144747).
  The flushing of fields is now done by [`execute_query()`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.api.Environment.execute_query),
  and is based on metadata put in the [`SQL`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.tools.SQL) object by
  `_search()` and other low-level ORM methods that
  build such objects. Those methods are also responsible for checking the access
  rights on the fields that are used in the SQL object.

## Odoo version 17.0

- Introduce an [`SQL`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.tools.SQL) wrapper object to make SQL composition
  easier and safer with respect to SQL injections. Methods of the ORM now use it
  internally. Introduced by [#134677](https://github.com/odoo/odoo/pull/134677).

## Odoo Online version 16.4

- Method `name_get()` has been deprecated with
  [#122085](https://github.com/odoo/odoo/pull/122085).
  Read field `display_name` instead.

## Odoo Online version 16.3

- Method [`_read_group()`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.models.Model._read_group) has a new signature with
  [#110737](https://github.com/odoo/odoo/pull/110737)

## Odoo Online version 16.2

- Refactor the implementation of searching and reading methods to be able to
  combine both in a minimal number of SQL queries. We introduce two new methods
  [`search_fetch()`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.models.Model.search_fetch) and [`fetch()`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.models.Model.fetch)
  that take advantage of the combination. More details can be found on the pull
  request [#112126](https://github.com/odoo/odoo/pull/112126).

## Odoo version 16.0

- Translations for translated fields are stored as JSONB values with
  [#97692](https://github.com/odoo/odoo/pull/97692)
  and [#101115](https://github.com/odoo/odoo/pull/101115).
  Code translations are no longer stored into the database.
  They become static and are extracted from the PO files when needed.
- [`search_count()`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.models.Model.search_count) takes the `limit` argument into account with [#95589](https://github.com/odoo/odoo/pull/95589).
  It limits the number of records to count, improving performance when a partial result is acceptable.

## Odoo Online version 15.4

- New API for flushing to the database and invalidating the cache with
  [#87527](https://github.com/odoo/odoo/pull/87527).
  New methods have been added to `odoo.models.Model` and `odoo.api.Environment`,
  and are less confusing about what is actually done in each case.
  See the section [SQL Execution](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#reference-orm-sql).

## Odoo Online version 15.3

- The argument `args` is renamed to `domain` for [`search()`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.models.Model.search), [`search_count()`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.models.Model.search_count)
  and `_search()`. [#83687](https://github.com/odoo/odoo/pull/83687)
- [`filtered_domain()`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.models.Model.filtered_domain) conserves the order of the current recordset. [#83687](https://github.com/odoo/odoo/pull/83687)
- [`browse()`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.models.Model.browse) does not accept [`str`](https://docs.python.org/3/library/stdtypes.html#str) as `ids`. [#83687](https://github.com/odoo/odoo/pull/83687)
- The methods `fields_get_keys()` and `get_xml_id()` on [`Model`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.models.Model) are deprecated. [#83687](https://github.com/odoo/odoo/pull/83687)
- The method `_mapped_cache()` is removed. [#83687](https://github.com/odoo/odoo/pull/83687)
- Remove the `limit` attribute of [`One2many`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.One2many) and [`Many2many`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Many2many). [#83687](https://github.com/odoo/odoo/pull/83687)

## Odoo Online version 15.2

- Specific index types on fields: With [#83274](https://github.com/odoo/odoo/pull/83274) and
  [#83015](https://github.com/odoo/odoo/pull/83015), developers can now define what type of
  indexes can be used on fields by PostgreSQL. See the [index property](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#reference-fields) of
  `odoo.fields.Field`.
- The `_sequence` attribute of [`Model`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.models.Model) is removed. Odoo lets PostgreSQL use the default sequence of the primary key. [#82727](https://github.com/odoo/odoo/pull/82727)
- The method `_write()` does not raise an error for non-existing records. [#82727](https://github.com/odoo/odoo/pull/82727)
- The `column_format` and `deprecated` attributes of [`Field`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Field) are removed. [#82727](https://github.com/odoo/odoo/pull/82727)
