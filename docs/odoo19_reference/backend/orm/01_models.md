<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html · abgerufen 2026-10-02 -->

# ORM API – Teil 1/6: Models

## Models

Model fields are defined as attributes on the model itself:

```
from odoo import models, fields
class AModel(models.Model):
    _name = 'a.model.name'

    field1 = fields.Char()
```

> **Warnung**
>
> this means you cannot define a field and a method with the same
> name, the last one will silently overwrite the former ones.

By default, the field’s label (user-visible name) is a capitalized version of
the field name, this can be overridden with the `string` parameter.

```
field2 = fields.Integer(string="Field Label")
```

For the list of field types and parameters, see the fields reference.

Default values are defined as parameters on fields, either as a value:

```
name = fields.Char(default="a value")
```

or as a function called to compute the default value, which should return that
value:

```
def _default_name(self):
    return self.get_value()

name = fields.Char(default=lambda self: self._default_name())
```

API

**`class odoo.models.BaseModel`**

Base class for Odoo models.

Odoo models are created by inheriting one of the following:

- `Model` for regular database-persisted models
- `TransientModel` for temporary data, stored in the database but
  automatically vacuumed every so often
- `AbstractModel` for abstract super classes meant to be shared by
  multiple inheriting models

The system automatically instantiates every model once per database. Those
instances represent the available models on each database, and depend on
which modules are installed on that database. The actual class of each
instance is built from the Python classes that create and inherit from the
corresponding model.

Every model instance is a „recordset“, i.e., an ordered collection of
records of the model. Recordsets are returned by methods like
`browse()`, `search()`, or field accesses. Records have no
explicit representation: a record is represented as a recordset of one
record.

To create a class that should not be instantiated,
the `_register` attribute may be set to False.

**`_auto: bool = False`**

Whether a database table should be created.
If set to `False`, override `init()`
to create the database table.

Automatically defaults to `True` for abstract models.

> **Tipp**
>
> To create a model without any table, inherit
> from `AbstractModel`.

**`_log_access`**

Whether the ORM should automatically generate and update the
Access Log fields.

Defaults to whatever value was set for `_auto`.

**`_table: str = ''`**

SQL table name used by model if `_auto`

**`_register: bool = False`**

registry visibility

**`_abstract: bool = True`**

Whether the model is *abstract*.

> **Siehe auch**
>
> `AbstractModel`

**`_transient: bool = False`**

Whether the model is *transient*.

> **Siehe auch**
>
> `TransientModel`

**`_name: str = None`**

the model name (in dot-notation, module namespace)

**`_description: str | None = None`**

the model’s informal name

**`_inherit: str | list[str] | tuple[str, ...] = ()`**

Python-inherited models:

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str) or [list](https://docs.python.org/3/library/stdtypes.html#list)([str](https://docs.python.org/3/library/stdtypes.html#str)) or [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)([str](https://docs.python.org/3/library/stdtypes.html#str))

> **Bemerkung**
>
> - If `_name` is set, name(s) of parent models to inherit from
> - If `_name` is unset, name of a single model to extend in-place

**`_inherits: frozendict[str, str] = {}`**

dictionary {‚parent_model‘: ‚m2o_field‘} mapping the _name of the parent business
objects to the names of the corresponding foreign key fields to use:

```
_inherits = {
    'a.model': 'a_field_id',
    'b.model': 'b_field_id'
}
```

implements composition-based inheritance: the new model exposes all
the fields of the inherited models but stores none of them:
the values themselves remain stored on the linked record.

> **Warnung**
>
> if multiple fields with the same name are defined in the
> `_inherits`-ed models, the inherited field will
> correspond to the last one (in the inherits list order).

**`_rec_name: str | None = None`**

field to use for labeling records, default: `name`

**`_order: str = 'id'`**

default order field for searching results

**`_check_company_auto: bool = False`**

On write and create, call `_check_company` to ensure companies
consistency on the relational fields having `check_company=True`
as attribute.

**`_parent_name: str = 'parent_id'`**

the many2one field used as parent field

**`_parent_store: bool = False`**

set to True to compute parent_path field.

Alongside a `parent_path` field, sets up an indexed storage
of the tree structure of records, to enable faster hierarchical queries
on the records of the current model using the `child_of` and
`parent_of` domain operators.

**`_fold_name: str = 'fold'`**

field to determine folded groups in kanban views

### AbstractModel

**`odoo.models.AbstractModel`**

alias of `odoo.orm.models.BaseModel`

### Model

**`class odoo.models.Model(env: Environment, ids: tuple[IdType, ...], prefetch_ids: Reversible[IdType])`**

Main super-class for regular database-persisted Odoo models.

Odoo models are created by inheriting from this class:

```
class ResUsers(Model):
    ...
```

The system will later instantiate the class once per database (on
which the class‘ module is installed).

**`_auto: bool = True`**

Whether a database table should be created.
If set to `False`, override `init()`
to create the database table.

Automatically defaults to `True` for abstract models.

> **Tipp**
>
> To create a model without any table, inherit
> from `AbstractModel`.

**`_abstract: typing.Literal[False] = False`**

Whether the model is *abstract*.

> **Siehe auch**
>
> `AbstractModel`

### TransientModel

**`class odoo.models.TransientModel(env: Environment, ids: tuple[IdType, ...], prefetch_ids: Reversible[IdType])`**

Model super-class for transient records, meant to be temporarily
persistent, and regularly vacuum-cleaned.

A TransientModel uses the same access rights mechanisms as a regular
`Model`, through access control lists and record rules.

**`_transient_max_count = 0`**

maximum number of transient records, unlimited if `0`

**`_transient_max_hours = 1.0`**

maximum idle lifetime (in hours), unlimited if `0`

**`_transient_vacuum()`**

Clean the transient records.

This unlinks old records from the transient model tables whenever the
`_transient_max_count` or `_transient_max_hours` conditions
(if any) are reached.

Actual cleaning will happen only once every 5 minutes. This means this
method can be called frequently (e.g. whenever a new record is created).

Example with both max_hours and max_count active:

Suppose max_hours = 0.2 (aka 12 minutes), max_count = 20, there are
55 rows in the table, 10 created/changed in the last 5 minutes, an
additional 12 created/changed between 5 and 10 minutes ago, the rest
created/changed more than 12 minutes ago.

- age based vacuum will leave the 22 rows created/changed in the last 12
  minutes
- count based vacuum will wipe out another 12 rows. Not just 2,
  otherwise each addition would immediately cause the maximum to be
  reached again.
- the 10 rows that have been created/changed the last 5 minutes will NOT
  be deleted
