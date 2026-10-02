<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html · abgerufen 2026-10-02 -->

# ORM API – Teil 5/6: Common ORM methods

## Common ORM methods

### Create/Update

**`Model.create(vals_list: list[ValuesType]) → Self`**

Create new records for the model.

The new records are initialized using the values from the list of dicts
`vals_list`, and if necessary those from `default_get()`.

**`Parameter`**

**vals_list** –

values for the model’s fields, as a list of dictionaries:

```
[{'field_name': field_value, ...}, ...]
```

For backward compatibility, `vals_list` may be a dictionary.
It is treated as a singleton list `[vals]`, and a single record
is returned.

see `write()` for details

**`Rückgabe`**

the created records

**`Verursacht`**

- **AccessError** – if the current user is not allowed to create records of the specified model
- **ValidationError** – if user tries to enter invalid value for a selection field
- [**ValueError**](https://docs.python.org/3/library/exceptions.html#ValueError) – if a field name specified in the create values does not exist.
- **UserError** – if a loop would be created in a hierarchy of objects a result of the operation
  (such as setting an object as its own parent)

**`Model.copy(default: ValuesType | None = None) → Self`**

Duplicate record `self` updating it with default values.

**`Parameter`**

**default** – dictionary of field values to override in the
original values of the copied record, e.g: `{'field_name': overridden_value, ...}`

**`Rückgabe`**

new records

**`Model.default_get(fields: Sequence[str]) → ValuesType`**

Return default values for the fields in `fields_list`. Default
values are determined by the context, user defaults, user fallbacks
and the model itself.

**`Parameter`**

**fields** – names of field whose default is requested

**`Rückgabe`**

a dictionary mapping field names to their corresponding default values,
if they have a default value.

> **Bemerkung**
>
> Unrequested defaults won’t be considered, there is no need to return a
> value for fields whose names are not in `fields_list`.

**`Model.name_create(name: str) → Union[tuple[int, str], Literal[False]]`**

Create a new record by calling `create()` with only one value
provided: the display name of the new record.

The new record will be initialized with any default values
applicable to this model, or provided through the context. The usual
behavior of `create()` applies.

**`Parameter`**

**name** – display name of the record to create

**`Rückgabe`**

the (id, display_name) pair value of the created record

**`Model.write(vals: ValuesType) → typing.Literal[True]`**

Update all records in `self` with the provided values.

**`Parameter`**

**vals** – fields to update and the value to set on them

**`Verursacht`**

- **AccessError** – if user is not allowed to modify the specified records/fields
- **ValidationError** – if invalid values are specified for selection fields
- **UserError** – if a loop would be created in a hierarchy of objects a result of the operation (such as setting an object as its own parent)

- For numeric fields (`Integer`,
  `Float`) the value should be of the
  corresponding type
- For `Boolean`, the value should be a
  [`bool`](https://docs.python.org/3/library/functions.html#bool)
- For `Selection`, the value should match the
  selection values (generally [`str`](https://docs.python.org/3/library/stdtypes.html#str), sometimes
  [`int`](https://docs.python.org/3/library/functions.html#int))
- For `Many2one`, the value should be the
  database identifier of the record to set
- The expected value of a `One2many` or
  `Many2many` relational field is a list of
  `Command` that manipulate the relation the
  implement. There are a total of 7 commands:
  `create()`,
  `update()`,
  `delete()`,
  `unlink()`,
  `link()`,
  `clear()`, and
  `set()`.
- For `Date` and `~odoo.fields.Datetime`,
  the value should be either a date(time), or a string.

  > **Warnung**
  >
  > If a string is provided for Date(time) fields,
  > it must be UTC-only and formatted according to
  > `odoo.tools.misc.DEFAULT_SERVER_DATE_FORMAT` and
  > `odoo.tools.misc.DEFAULT_SERVER_DATETIME_FORMAT`
- Other non-relational fields use a string for value

### Search/Read

**`Model.browse(ids: int | typing.Iterable[IdType] = ()) → Self`**

Return a recordset for the ids provided as parameter in the current
environment.

```python
self.browse([7, 18, 12])
res.partner(7, 18, 12)
```

**`Model.search(domain: DomainType, offset: int = 0, limit: int | None = None, order: str | None = None) → Self`**

Search for the records that satisfy the given `domain`
search domain.

**`Parameter`**

- **domain** – A search domain. Use an empty
  list to match all records.
- **offset** – number of results to ignore (default: none)
- **limit** – maximum number of records to return (default: all)
- **order** – sort string

**`Rückgabe`**

at most `limit` records matching the search criteria

**`Verursacht`**

**AccessError** – if user is not allowed to access requested information

This is a high-level method, which should not be overridden. Its actual
implementation is done by method `_search()`.

**`Model.search_count(domain: DomainType, limit: int | None = None) → int`**

Return the number of records in the current model matching
the provided domain.

**`Parameter`**

- **domain** – A search domain. Use an empty
  list to match all records.
- **limit** – maximum number of record to count (upperbound) (default: all)

This is a high-level method, which should not be overridden. Its actual
implementation is done by method `_search()`.

**`Model.search_fetch(domain: DomainType, field_names: Sequence[str] | None = None, offset: int = 0, limit: int | None = None, order: str | None = None) → Self`**

Search for the records that satisfy the given `domain`
search domain, and fetch the given fields
to the cache. This method is like a combination of methods `search()`
and `fetch()`, but it performs both tasks with a minimal number of
SQL queries.

**`Parameter`**

- **domain** – A search domain. Use an empty
  list to match all records.
- **field_names** – a collection of field names to fetch, or `None` for
  all accessible fields marked with `prefetch=True`
- **offset** – number of results to ignore (default: none)
- **limit** – maximum number of records to return (default: all)
- **order** – sort string

**`Rückgabe`**

at most `limit` records matching the search criteria

**`Verursacht`**

**AccessError** – if user is not allowed to access requested information

**`Model.name_search(name: str = '', domain: DomainType | None = None, operator: str = 'ilike', limit: int = 100) → list[tuple[int, str]]`**

Search for records that have a display name matching the given
`name` pattern when compared with the given `operator`, while also
matching the optional search domain (`domain`).

This is used for example to provide suggestions based on a partial
value for a relational field. Should usually behave as the reverse of
`display_name`, but that is not guaranteed.

This method is equivalent to calling `search()` with a search
domain based on `display_name` and mapping id and display_name on
the resulting search.

**`Parameter`**

- **name** – the name pattern to match
- **domain** – search domain (see `search()` for syntax),
  specifying further restrictions
- **operator** – domain operator for matching `name`,
  such as `'like'` or `'='`.
- **limit** – max number of records to return

**`Rückgabe`**

list of pairs `(id, display_name)` for all matching records.

**`Model.fetch(field_names: Collection[str] | None = None) → None`**

Make sure the given fields are in memory for the records in `self`,
by fetching what is necessary from the database. Non-stored fields are
mostly ignored, except for their stored dependencies. This method should
be called to optimize code.

**`Parameter`**

**field_names** – a collection of field names to fetch, or `None` for
all accessible fields marked with `prefetch=True`

**`Verursacht`**

**AccessError** – if user is not allowed to access requested information

This method is implemented thanks to methods `_search()` and
`_fetch_query()`, and should not be overridden.

**`Model.read(fields: Sequence[str] | None = None, load: str = '_classic_read') → list[ValuesType]`**

Read the requested fields for the records in `self`, and return their
values as a list of dicts.

**`Parameter`**

- **fields** – field names to return (default is all fields)
- **load** – loading mode, currently the only option is to set to
  `None` to avoid loading the `display_name` of m2o fields

**`Rückgabe`**

a list of dictionaries mapping field names to their values,
with one dictionary per record

**`Verursacht`**

- **AccessError** – if user is not allowed to access requested information
- [**ValueError**](https://docs.python.org/3/library/exceptions.html#ValueError) – if a requested field does not exist

This is a high-level method that is not supposed to be overridden. In
order to modify how fields are read from database, see methods
`_fetch_query()` and `_read_format()`.

**`Model._read_group(domain: DomainType, groupby: Sequence[str] = (), aggregates: Sequence[str] = (), having: DomainType = (), offset: int = 0, limit: int | None = None, order: str | None = None) → list[tuple]`**

Get fields aggregations specified by `aggregates` grouped by the given `groupby`
fields where record are filtered by the `domain`.

**`Parameter`**

- **domain** – A search domain. Use an empty
  list to match all records.
- **groupby** – list of groupby descriptions by which the records will be grouped.
  A groupby description is either a field (then it will be grouped by that field)
  or a string `'field:granularity'`. Right now, the only supported granularities
  are `'day'`, `'week'`, `'month'`, `'quarter'` or `'year'`, and they only make sense for
  date/datetime fields.
  Additionally integer date parts are also supported:
  `'year_number'`, `'quarter_number'`, `'month_number'`, `'iso_week_number'`, `'day_of_year'`, `'day_of_month'`,
  ‚day_of_week‘, ‚hour_number‘, ‚minute_number‘ and ‚second_number‘.
- **aggregates** – list of aggregates specification.
  Each element is `'field:agg'` (aggregate field with aggregation function `'agg'`).
  The possible aggregation functions are the ones provided by
  [PostgreSQL](https://www.postgresql.org/docs/current/static/functions-aggregate.html),
  `'count_distinct'` with the expected meaning and `'recordset'` to act like `'array_agg'`
  converted into a recordset.
- **having** – A domain where the valid „fields“ are the aggregates.
- **offset** – optional number of groups to skip
- **limit** – optional max number of groups to return
- **order** – optional `order by` specification, for
  overriding the natural sort ordering of the groups,
  see also `search()`.

**`Rückgabe`**

list of tuples containing in the order the groups values and aggregates values (flatten):
`[(groupby_1_value, ... , aggregate_1_value_aggregate, ...), ...]`.
If group is related field, the value of it will be a recordset (with a correct prefetch set).

**`Verursacht`**

**AccessError** – if user is not allowed to access requested information

#### Fields

**`Model.fields_get(allfields: Collection[str] | None = None, attributes: Collection[str] | None = None) → dict[str, ValuesType]`**

Return the definition of each field.

The returned value is a dictionary (indexed by field name) of
dictionaries. The _inherits’d fields are included. The string, help,
and selection (if present) attributes are translated.

**`Parameter`**

- **allfields** – fields to document, all if empty or not provided
- **attributes** – attributes to return for each field, all if empty or not provided

**`Rückgabe`**

dictionary mapping field names to a dictionary mapping attributes to values.

#### Search domains

A search domain is a first-order logical predicate used for
filtering and searching recordsets.
You combine simple conditions on a field expression with logical operators.

`Domain` can be used as a builder for domains.

```python
# simple condition domains
d1 = Domain('name', '=', 'abc')
d2 = Domain('phone', 'like', '7620')

# combine domains
d3 = d1 & d2  # and
d4 = d1 | d2  # or
d5 = ~d1      # not

# combine and parse multiple domains (any iterable of domains)
Domain.AND([d1, d2, d3, ...])
Domain.OR([d4, d5, ...])

# constants
Domain.TRUE   # true domain
Domain.FALSE  # false domain
```

A domain can be a simple condition `(field_expr, operator, value)` where:

- **`field_expr (str)`**

  a field name of the current model, or a relationship traversal through
  a `Many2one` using dot-notation e.g. `'street'`
  or `'partner_id.country'`. If the field is a date(time) field, you can also
  specify a part of the date using `'field_name.granularity'`. The supported
  granularities are `'year_number'`, `'quarter_number'`, `'month_number'`, `'iso_week_number'`,
  `'day_of_week'`, `'day_of_month'`, `'day_of_year'`, `'hour_number'`, `'minute_number'`,
  `'second_number'`.
  They all use an integer as value.
- **`operator (str)`**

  an operator used to compare the `field_expr` with the `value`. Valid
  operators are:

  **`=`**

  equals to

  **`!=`**

  not equals to

  **`>`**

  greater than

  **`>=`**

  greater than or equal to

  **`<`**

  less than

  **`<=`**

  less than or equal to

  **`=?`**

  unset or equals to (returns true if `value` is either `None` or
  `False`, otherwise behaves like `=`)

  **`=like (and not =like)`**

  matches `field_expr` against the `value` pattern. An underscore
  `_` in the pattern stands for (matches) any single character; a
  percent sign `%` matches any string of zero or more characters.

  **`like (and not like)`**

  matches `field_expr` against the `%value%` pattern. Similar to
  `=like` but wraps `value` with ‚%‘ before matching

  **`ilike (and not ilike)`**

  case insensitive `like`

  **`=ilike (and not =ilike)`**

  case insensitive `=like`

  **`in (and not in)`**

  is equal to any of the items from `value`, `value` should be a
  collection of items

  **`child_of`**

  is a child (descendant) of a `value` record (value can be either
  one item or a list of items).

  Takes the semantics of the model into account (i.e following the
  relationship field named by
  `_parent_name`).

  **`parent_of`**

  is a parent (ascendant) of a `value` record (value can be either
  one item or a list of items).

  Takes the semantics of the model into account (i.e following the
  relationship field named by
  `_parent_name`).

  **`any (and not any)`**

  matches if any record in the relationship traversal through
  `field_expr` (`Many2one`,
  `One2many`, or `Many2many`)
  satisfies the provided domain `value`.
  The `field_expr` should be a field name.

  **`any! (and not any!)`**

  like `any`, but bypasses access checks.
- **`value`**

  variable type, must be comparable (through `operator`) to the named
  field.

> **Example**
>
> To search for partners named *ABC*, with a phone or mobile number containing *7620*:
>
> ```
> Domain('name', '=', 'ABC') & (
>   Domain('phone', 'ilike', '7620') | Domain('mobile', 'ilike', '7620')
> )
> ```
>
> To search sales orders to invoice that have at least one line with
> a product that is out of stock:
>
> ```
> Domain('invoice_status', '=', 'to invoice') \
>   & Domain('order_line', 'any', Domain('product_id.qty_available', '<=', 0))
> ```
>
> To search for all partners born in the month of February:
>
> ```
> Domain('birthday.month_number', '=', 2)
> ```

`Domain` can be used to serialize the domain as a `list`
of simple conditions represented by 3-item `tuple` (or a `list`).
Such a serialized form may be sometimes faster to read or write.
Domain conditions can be combined using logical operators in a *prefix* notation.
You can combine 2 domains using `'&'` (AND), `'|'` (OR)
and you can negate 1 using `'!'` (NOT).

```python
# parse a domain (from list to Domain)
domain = Domain([('name', '=', 'abc'), ('phone', 'like', '7620')])

# serialize domain as a list (from Domain to list)
domain_list = list(domain)
# will output:
# ['&', ('name', '=', 'abc'), ('phone', 'like', '7620')]
```

**`Domain.iter_conditions() → Iterable[DomainCondition]`**

Yield simple conditions of the domain

**`Domain.map_conditions(function: Callable[[DomainCondition], Domain]) → Domain`**

Map a function to each condition and return the combined result

**`Domain.optimize(model: BaseModel) → Domain`**

Perform optimizations of the node given a model.

It is a pre-processing step to rewrite the domain into a logically
equivalent domain that is a more canonical representation of the
predicate. Multiple conditions can be merged together.

It applies basic optimizations only. Those are transaction-independent;
they only depend on the model’s fields definitions. No model-specific
override is used, and the resulting domain may be reused in another
transaction without semantic impact.
The model’s fields are used to validate conditions and apply
type-dependent optimizations. This optimization level may be useful to
simplify a domain that is sent to the client-side, thereby reducing its
payload/complexity.

**`Domain.validate(model: BaseModel) → None`**

Validates that the current domain is correct or raises an exception

#### Dynamic time values

In the context of search domains, for
date and datetime fields, the value can be a
moment relative to *now* in the timezone of the user. A simple language is
provided to specify these dates. It is a space-separated string of terms.
The first term is optional and is „today“ (at midnight) or „now“.
Then, each term starts with „+“ (add), „-“ (subtract) or „=“ (set), followed by
an integer and date unit or a lower-case weekday.

The date units are: „d“ (days), „w“ (weeks), „m“ (months), „y“ (years),
„H“ (hours), „M“ (minutes), „S“ (seconds).
For weekdays, „+“ and „-“ mean next and previous weekday (unless we are already
in that weekday) and „=“ means in current week starting on Monday.
When setting a date, the lower-units (hours, minutes and seconds) are set to 0.

> **Example**
>
> ```python
> Domain('some_date', '<', 'now')  # now
> Domain('some_date', '<', 'today')  # today at midnight
> Domain('some_date', '<', '-3d +1H')  # now - 3 days + 1 hour
> Domain('some_date', '<', '=3H')  # today at 3:00:00
> Domain('some_date', '<', '=5d')  # 5th day of current month at midnight
> Domain('some_date', '<', '=1m')  # January, same day of month at midnight
> Domain('some_date', '>=', '=monday -1w')  # Monday of the previous week
> ```

### Unlink

**`Model.unlink() → Literal[True]`**

Delete the records in `self`.

**`Verursacht`**

- **AccessError** – if the user is not allowed to delete all the given records
- **UserError** – if the record is default property for other records

### Record(set) information

**`Model.ids`**

Return the list of actual record ids corresponding to `self`.

**`odoo.models.env`**

Returns the environment of the given recordset.

**`Type`**

`Environment`

**`Model.exists() → Self`**

The subset of records in `self` that exist.
It can be used as a test on records:

```
if record.exists():
    ...
```

By convention, new records are returned as existing.

**`Model.ensure_one() → Self`**

Verify that the current recordset holds a single record.

**`Verursacht`**

**odoo.exceptions.ValueError** – `len(self) != 1`

**`Model.get_metadata() → list[ValuesType]`**

Return some metadata about the given records.

**`Rückgabe`**

list of ownership dictionaries for each requested record with the following keys:

- id: object id
- create_uid: user who created the record
- create_date: date when the record was created
- write_uid: last user who changed the record
- write_date: date of the last change to the record
- xmlid: XML ID to use to refer to this record (if there is one), in format `module.name`
- xmlids: list of dict with xmlid in format `module.name`, and noupdate as boolean
- noupdate: A boolean telling if the record will be updated or not

### Operations

Recordsets are immutable, but sets of the same model can be combined using
various set operations, returning new recordsets.

- `record in set` returns whether `record` (which must be a 1-element
  recordset) is present in `set`. `record not in set` is the inverse
  operation
- `set1 <= set2` and `set1 < set2` return whether `set1` is a subset
  of `set2` (resp. strict)
- `set1 >= set2` and `set1 > set2` return whether `set1` is a superset
  of `set2` (resp. strict)
- `set1 | set2` returns the union of the two recordsets, a new recordset
  containing all records present in either source
- `set1 & set2` returns the intersection of two recordsets, a new recordset
  containing only records present in both sources
- `set1 - set2` returns a new recordset containing only records of `set1`
  which are *not* in `set2`

Recordsets are iterable so the usual Python tools are available for
transformation ([`map()`](https://docs.python.org/3/library/functions.html#map), [`sorted()`](https://docs.python.org/3/library/functions.html#sorted),
`ifilter()`, …) however these return either a
[`list`](https://docs.python.org/3/library/stdtypes.html#list) or an [iterator](https://docs.python.org/3/glossary.html#term-iterator), removing the ability to
call methods on their result, or to use set operations.

Recordsets therefore provide the following operations returning recordsets themselves
(when possible):

#### Filter

**`Model.filtered(func: str | Callable[[Self], bool] | Domain) → Self`**

Return the records in `self` satisfying `func`.

**`Parameter`**

**func** – a function, Domain or a dot-separated sequence of field names

**`Rückgabe`**

recordset of records satisfying func, may be empty.

```python
# only keep records whose company is the current user's
records.filtered(lambda r: r.company_id == user.company_id)

# only keep records whose partner is a company
records.filtered("partner_id.is_company")
```

**`Model.filtered_domain(domain: DomainType) → Self`**

Return the records in `self` satisfying the domain and keeping the same order.

**`Parameter`**

**domain** – A search domain.

#### Map

**`Model.mapped(func: str | Callable[[Self], T]) → list | BaseModel`**

Apply `func` on all records in `self`, and return the result as a
list or a recordset (if `func` return recordsets). In the latter
case, the order of the returned recordset is arbitrary.

**`Parameter`**

**func** – a function or a dot-separated sequence of field names

**`Rückgabe`**

self if func is falsy, result of func applied to all `self` records.

```python
# returns a list of summing two fields for each record in the set
records.mapped(lambda r: r.field1 + r.field2)
```

The provided function can be a string to get field values:

```python
# returns a list of names
records.mapped('name')

# returns a recordset of partners
records.mapped('partner_id')

# returns the union of all partner banks, with duplicates removed
records.mapped('partner_id.bank_ids')
```

> **Bemerkung**
>
> Since V13, multi-relational field access is supported and works like a mapped call:
>
> ```python
> records.partner_id  # == records.mapped('partner_id')
> records.partner_id.bank_ids  # == records.mapped('partner_id.bank_ids')
> records.partner_id.mapped('name')  # == records.mapped('partner_id.name')
> ```

#### Sort

**`Model.sorted(key: Callable[[Self], typing.Any] | str | None = None, reverse: bool = False) → Self`**

Return the recordset `self` ordered by `key`.

**`Parameter`**

- **key** –

  It can be either of:

  - a function of one argument that returns a comparison key for each record
  - a string representing a comma-separated list of field names with optional
    NULLS (FIRST|LAST), and (ASC|DESC) directions
  - `None`, in which case records are ordered according the default model’s order
- **reverse** – if `True`, return the result in reverse order

```python
# sort records by name
records.sorted(key=lambda r: r.name)
# sort records by name in descending order, then by id
records.sorted('name DESC, id')
# sort records using default order
records.sorted()
```

#### Grouping

**`Model.grouped(key: str | Callable[[Self], T]) → dict[typing.Any, Self]`**

Eagerly groups the records of `self` by the `key`, returning a
dict from the `key`’s result to recordsets. All the resulting
recordsets are guaranteed to be part of the same prefetch-set.

Provides a convenience method to partition existing recordsets without
the overhead of a `_read_group()`, but performs no aggregation.

> **Bemerkung**
>
> unlike [`itertools.groupby()`](https://docs.python.org/3/library/itertools.html#itertools.groupby), does not care about input
> ordering, however the tradeoff is that it can not be lazy

**`Parameter`**

**key** – either a callable from a `Model` to a (hashable)
value, or a field name. In the latter case, it is equivalent
to `itemgetter(key)` (aka the named field’s value)
