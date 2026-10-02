<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html · abgerufen 2026-10-02 -->

# ORM API – Teil 4/6: Environment

## Environment

**`class odoo.api.Environment(cr: odoo.sql_db.BaseCursor, uid: int, context: dict, su: bool = False)`**

The environment stores various contextual data used by the ORM:

- `cr`: the current database cursor (for database queries);
- `uid`: the current user id (for access rights checks);
- `context`: the current context dictionary (arbitrary metadata);
- `su`: whether in superuser mode.

It provides access to the registry by implementing a mapping from model
names to models. It also holds a cache for records, and a data
structure to manage recomputations.

```bash
>>> records.env
<Environment object ...>
>>> records.env.uid
3
>>> records.env.user
res.user(3)
>>> records.env.cr
<Cursor object ...>
```

When creating a recordset from an other recordset, the environment is
inherited. The environment can be used to get an empty recordset in an
other model, and query that model:

```bash
>>> self.env['res.partner']
res.partner()
>>> self.env['res.partner'].search([('is_company', '=', True), ('customer', '=', True)])
res.partner(7, 18, 12, 14, 17, 19, 8, 31, 26, 16, 13, 20, 30, 22, 29, 15, 23, 28, 74)
```

Some lazy properties are available to access the environment (contextual) data:

**`Environment.lang`**

Return the current language code.

**`Environment.user`**

Return the current user (as an instance).

**`Rückgabe`**

current user - sudoed

**`Rückgabetyp`**

`res.users record`

**`Environment.company`**

Return the current company (as an instance).

If not specified in the context (`allowed_company_ids`),
fallback on current user main company.

**`Verursacht`**

**AccessError** – invalid or unauthorized `allowed_company_ids` context key content.

**`Rückgabe`**

current company (default=`self.user.company_id`), with the current environment

**`Rückgabetyp`**

`res.company record`

> **Warnung**
>
> No sanity checks applied in sudo mode!
> When in sudo mode, a user can access any company,
> even if not in his allowed companies.
>
> This allows to trigger inter-company modifications,
> even if the current user doesn’t have access to
> the targeted company.

**`Environment.companies`**

Return a recordset of the enabled companies by the user.

If not specified in the context(`allowed_company_ids`),
fallback on current user companies.

**`Verursacht`**

**AccessError** – invalid or unauthorized `allowed_company_ids` context key content.

**`Rückgabe`**

current companies (default=`self.user.company_ids`), with the current environment

**`Rückgabetyp`**

`res.company recordset`

> **Warnung**
>
> No sanity checks applied in sudo mode !
> When in sudo mode, a user can access any company,
> even if not in his allowed companies.
>
> This allows to trigger inter-company modifications,
> even if the current user doesn’t have access to
> the targeted company.

### Useful environment methods

**`Environment.ref(xml_id: str, raise_if_not_found: Literal[True] = True) → BaseModel`**

**`Environment.ref(xml_id: str, raise_if_not_found: Literal[False]) → BaseModel | None`**

Return the record corresponding to the given `xml_id`.

**`Parameter`**

- **xml_id** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – record xml_id, under the format `<module.id>`
- **raise_if_not_found** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the method should raise if record is not found

**`Rückgabe`**

Found record or None

**`Verursacht`**

[**ValueError**](https://docs.python.org/3/library/exceptions.html#ValueError) – if record wasn’t found and `raise_if_not_found` is True

**`Environment.is_superuser() → bool`**

Return whether the environment is in superuser mode.

**`Environment.is_admin() → bool`**

Return whether the current user has group „Access Rights“, or is in
superuser mode.

**`Environment.is_system() → bool`**

Return whether the current user has group „Settings“, or is in
superuser mode.

**`Environment.execute_query(query: odoo.tools.sql.SQL) → list[tuple]`**

Execute the given query, fetch its result and it as a list of tuples
(or an empty list if no result to fetch). The method automatically
flushes all the fields in the metadata of the query.

### Altering the environment

**`Model.with_context(ctx: dict[str, typing.Any] | None = None, /, **overrides) → Self`**

Return a new version of this recordset attached to an extended
context.

The extended context is either the provided `context` in which
`overrides` are merged or the *current* context in which
`overrides` are merged e.g.:

```
# current context is {'key1': True}
r2 = records.with_context({}, key2=True)
# -> r2.env.context is {'key2': True}
r2 = records.with_context(key2=True)
# -> r2.env.context is {'key1': True, 'key2': True}
```

**`Model.with_user(user: BaseModel | IdType) → Self`**

Return a new version of this recordset attached to the given user, in
non-superuser mode, unless `user` is the superuser (by convention, the
superuser is always in superuser mode.)

**`Model.with_company(company: BaseModel | IdType) → Self`**

Return a new version of this recordset with a modified context, such that:

```
result.env.company = company
result.env.companies = self.env.companies | company
```

> **Warnung**
>
> When using an unauthorized company for current user,
> accessing the company(ies) on the environment may trigger
> an AccessError if not done in a sudoed environment.

**`Model.with_env(env: Environment) → Self`**

Return a new version of this recordset attached to the provided environment.

> **Bemerkung**
>
> The returned recordset has the same prefetch object as `self`.

**`Model.sudo(flag: bool = True) → Self`**

Return a new version of this recordset with superuser mode enabled or
disabled, depending on `flag`. The superuser mode does not change the
current user, and simply bypasses access rights checks.

> **Warnung**
>
> Using `sudo` could cause data access to cross the
> boundaries of record rules, possibly mixing records that
> are meant to be isolated (e.g. records from different
> companies in multi-company environments).
>
> It may lead to un-intuitive results in methods which select one
> record among many - for example getting the default company, or
> selecting a Bill of Materials.

> **Bemerkung**
>
> The returned recordset has the same prefetch object as `self`.

### SQL Execution

The `cr` attribute on environments is the
cursor for the current database transaction and allows executing SQL directly,
either for queries which are difficult to express using the ORM (e.g. complex
joins) or for performance reasons:

```
self.env.cr.execute("some_sql", params)
```

> **Warnung**
>
> Executing raw SQL bypasses the ORM and, by consequent, Odoo security rules.
> Please make sure your queries are sanitized when using user input and prefer using
> ORM utilities if you don’t really need to use SQL queries.

The recommended way to build SQL queries is to use the wrapper object

**`class odoo.tools.SQL(code: str | SQL = '', /, *args, to_flush: Field | Iterable[Field] | None = None, **kwargs)`**

An object that wraps SQL code with its parameters, like:

```
sql = SQL("UPDATE TABLE foo SET a = %s, b = %s", 'hello', 42)
cr.execute(sql)
```

The code is given as a `%`-format string, and supports either positional
arguments (with `%s`) or named arguments (with `%(name)s`). The arguments
are meant to be merged into the code using the `%` formatting operator.
Note that the character `%` must always be escaped (as `%%`), even if
the code does not have parameters, like in `SQL("foo LIKE 'a%%'")`.

The SQL wrapper is designed to be composable: the arguments can be either
actual parameters, or SQL objects themselves:

```
sql = SQL(
    "UPDATE TABLE %s SET %s",
    SQL.identifier(tablename),
    SQL("%s = %s", SQL.identifier(columnname), value),
)
```

The combined SQL code is given by `sql.code`, while the corresponding
combined parameters are given by the list `sql.params`. This allows to
combine any number of SQL terms without having to separately combine their
parameters, which can be tedious, bug-prone, and is the main downside of
`psycopg2.sql <https://www.psycopg.org/docs/sql.html>`.

The second purpose of the wrapper is to discourage SQL injections. Indeed,
if `code` is a string literal (not a dynamic string), then the SQL object
made with `code` is guaranteed to be safe, provided the SQL objects
within its parameters are themselves safe.

The wrapper may also contain some metadata `to_flush`. If not `None`,
its value is a field which the SQL code depends on. The metadata of a
wrapper and its parts can be accessed by the iterator `sql.to_flush`.

**`join(args: Iterable) → SQL`**

Join SQL objects or parameters with `self` as a separator.

**`classmethod identifier(name: str, subname: str | None = None, to_flush: Field | None = None) → SQL`**

Return an SQL object that represents an identifier.

One important thing to know about models is that they don’t necessarily perform
database updates right away. Indeed, for performance reasons, the framework
delays the recomputation of fields after modifying records. And some database
updates are delayed, too. Therefore, before querying the database, one has to
make sure that it contains the relevant data for the query. This operation is
called *flushing* and performs the expected database updates.

> **Example**
>
> ```python
> # make sure that 'partner_id' is up-to-date in database
> self.env['model'].flush_model(['partner_id'])
>
> self.env.cr.execute(SQL("SELECT id FROM model WHERE partner_id IN %s", ids))
> ids = [row[0] for row in self.env.cr.fetchall()]
> ```

Before every SQL query, one has to flush the data needed for that query. There
are three levels for flushing, each with its own API. One can flush either
everything, all the records of a model, or some specific records. Because
delaying updates improves performance in general, we recommend to be *specific*
when flushing.

**`Environment.flush_all() → None`**

Flush all pending computations and updates to the database.

**`Model.flush_model(fnames: Collection[str] | None = None) → None`**

Process the pending computations and database updates on `self`’s
model. When the parameter is given, the method guarantees that at least
the given fields are flushed to the database. More fields can be
flushed, though.

**`Parameter`**

**fnames** – optional iterable of field names to flush

**`Model.flush_recordset(fnames: Collection[str] | None = None) → None`**

Process the pending computations and database updates on the records
`self`. When the parameter is given, the method guarantees that at
least the given fields on records `self` are flushed to the database.
More fields and records can be flushed, though.

**`Parameter`**

**fnames** – optional iterable of field names to flush

Because models use the same cursor and the `Environment`
holds various caches, these caches must be invalidated when *altering* the
database in raw SQL, or further uses of models may become incoherent. It is
necessary to clear caches when using `CREATE`, `UPDATE` or `DELETE` in
SQL, but not `SELECT` (which simply reads the database).

> **Example**
>
> ```python
> # make sure 'state' is up-to-date in database
> self.env['model'].flush_model(['state'])
>
> self.env.cr.execute("UPDATE model SET state=%s WHERE state=%s", ['new', 'old'])
>
> # invalidate 'state' from the cache
> self.env['model'].invalidate_model(['state'])
> ```

Just like flushing, one can invalidate either the whole cache, the cache of all
the records of a model, or the cache of specific records. One can even
invalidate specific fields on some records or all records of a model. As the
cache improves performance in general, we recommend to be *specific* when
invalidating.

**`Environment.invalidate_all(flush: bool = True) → None`**

Invalidate the cache of all records.

**`Parameter`**

**flush** – whether pending updates should be flushed before invalidation.
It is `True` by default, which ensures cache consistency.
Do not use this parameter unless you know what you are doing.

**`Model.invalidate_model(fnames: Collection[str] | None = None, flush: bool = True) → None`**

Invalidate the cache of all records of `self`’s model, when the
cached values no longer correspond to the database values. If the
parameter is given, only the given fields are invalidated from cache.

**`Parameter`**

- **fnames** – optional iterable of field names to invalidate
- **flush** – whether pending updates should be flushed before invalidation.
  It is `True` by default, which ensures cache consistency.
  Do not use this parameter unless you know what you are doing.

**`Model.invalidate_recordset(fnames: Collection[str] | None = None, flush: bool = True) → None`**

Invalidate the cache of the records in `self`, when the cached
values no longer correspond to the database values. If the parameter
is given, only the given fields on `self` are invalidated from cache.

**`Parameter`**

- **fnames** – optional iterable of field names to invalidate
- **flush** – whether pending updates should be flushed before invalidation.
  It is `True` by default, which ensures cache consistency.
  Do not use this parameter unless you know what you are doing.

The methods above keep the caches and the database consistent with each other.
However, if computed field dependencies have been modified in the database, one
has to inform the models for the computed fields to be recomputed. The only
thing the framework needs to know is *what* fields have changed on *which*
records.

> **Example**
>
> ```python
> # make sure 'state' is up-to-date in database
> self.env['model'].flush_model(['state'])
>
> # use the RETURNING clause to retrieve which rows have changed
> self.env.cr.execute("UPDATE model SET state=%s WHERE state=%s RETURNING id", ['new', 'old'])
> ids = [row[0] for row in self.env.cr.fetchall()]
>
> # invalidate the cache, and notify the update to the framework
> records = self.env['model'].browse(ids)
> records.invalidate_recordset(['state'])
> records.modified(['state'])
> ```

One has to figure out which records have been modified. There are many ways to
do this, possibly involving extra SQL queries. In the example above, we take
advantage of the `RETURNING` clause of PostgreSQL to retrieve the information
without an extra query. After making the cache consistent by invalidation,
invoke the method `modified` on the modified records with the fields that
have been updated.

**`Model.modified(fnames: Collection[str], create: bool = False, before: bool = False) → None`**

Notify that fields will be or have been modified on `self`. This
invalidates the cache where necessary, and prepares the recomputation of
dependent stored fields.

**`Parameter`**

- **fnames** – iterable of field names modified on records `self`
- **create** – whether called in the context of record creation
- **before** – whether called before modifying records `self`
