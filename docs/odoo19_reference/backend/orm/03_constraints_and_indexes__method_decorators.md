<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html · abgerufen 2026-10-02 -->

# ORM API – Teil 3/6: Constraints and indexes / Recordsets / Method decorators

## Constraints and indexes

Similarly to fields, you can declare
`Constraint`,
`Index` and `UniqueIndex`.
The name of the attribute must begin with `_` to avoid name clashes with field
names.

You can customize error messages.
They can either be strings and their translation will be provided in the internal
reflected constraint table.
Otherwise, they can be functions that take `(env, diag)` as parameters
which respectively denote the environment and psycopg diagnostics.

> **Example**
>
> ```python
> class AModel(models.Model):
>     _name = 'a.model'
>     _my_check = models.Constraint("CHECK (x > y)", "x > y is not true")
>     _name_idx = models.Index("(last_name, first_name)")
> ```

## Recordsets

Interactions with models and records are performed through recordsets, an ordered
collection of records of the same model.

> **Warnung**
>
> Contrary to what the name implies, it is currently possible for
> recordsets to contain duplicates. This may change in the future.

Methods defined on a model are executed on a recordset, and their `self` is
a recordset:

```
class AModel(models.Model):
    _name = 'a.model'
    def a_method(self):
        # self can be anything between 0 records and all records in the
        # database
        self.do_operation()
```

Iterating on a recordset will yield new sets of *a single record*
(„singletons“), much like iterating on a Python string yields strings of a
single characters:

```
def do_operation(self):
    print(self) # => a.model(1, 2, 3, 4, 5)
    for record in self:
        print(record) # => a.model(1), then a.model(2), then a.model(3), ...
```

### Field access

Recordsets provide an „Active Record“ interface: model fields can be read and
written directly from the record as attributes.

> **Bemerkung**
>
> When accessing non-relational fields on a recordset of potentially multiple
> records, use `mapped()`:
>
> ```
> total_qty = sum(self.mapped('qty'))
> ```

Field values can also be accessed like dict items, which is more elegant and
safer than `getattr()` for dynamic field names.
Setting a field’s value triggers an update to the database:

```
>>> record.name
Example Name
>>> record.company_id.name
Company Name
>>> record.name = "Bob"
>>> field = "name"
>>> record[field]
Bob
```

> **Warnung**
>
> Trying to read a field on multiple records will raise an error for non relational
> fields.

Accessing a relational field (`Many2one`,
`One2many`, `Many2many`)
*always* returns a recordset, empty if the field is not set.

### Record cache and prefetching

Odoo maintains a cache for the fields of the records, so that not every field
access issues a database request, which would be terrible for performance. The
following example queries the database only for the first statement:

```
record.name             # first access reads value from database
record.name             # second access gets value from cache
```

To avoid reading one field on one record at a time, Odoo *prefetches* records
and fields following some heuristics to get good performance. Once a field must
be read on a given record, the ORM actually reads that field on a larger
recordset, and stores the returned values in cache for later use. The prefetched
recordset is usually the recordset from which the record comes by iteration.
Moreover, all simple stored fields (boolean, integer, float, char, text, date,
datetime, selection, many2one) are fetched altogether; they correspond to the
columns of the model’s table, and are fetched efficiently in the same query.

Consider the following example, where `partners` is a recordset of 1000
records. Without prefetching, the loop would make 2000 queries to the database.
With prefetching, only one query is made:

```
for partner in partners:
    print partner.name          # first pass prefetches 'name' and 'lang'
                                # (and other fields) on all 'partners'
    print partner.lang
```

The prefetching also works on *secondary records*: when relational fields are
read, their values (which are records) are subscribed for future prefetching.
Accessing one of those secondary records prefetches all secondary records from
the same model. This makes the following example generate only two queries, one
for partners and one for countries:

```
countries = set()
for partner in partners:
    country = partner.country_id        # first pass prefetches all partners
    countries.add(country.name)         # first pass prefetches all countries
```

> **Siehe auch**
>
> The methods `search_fetch()` and
> `fetch()` can be used to populate the cache of
> records, typically in cases where the prefetching mechanism does not work
> well.

## Method decorators

**`odoo.api.autovacuum(method: C) → C`**

Decorate a method so that it is called by the daily vacuum cron job (model
`ir.autovacuum`). This is typically used for garbage-collection-like
tasks that do not deserve a specific cron job.

A return value can be a tuple (done, remaining) which have simular meaning
as in [`_commit_progress()`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/actions.html#odoo.addons.base.models.ir_cron.IrCron._commit_progress).

**`odoo.api.constrains(*args) → Decorator`**

Decorate a constraint checker.

Each argument must be a field name used in the check:

```
@api.constrains('name', 'description')
def _check_description(self):
    for record in self:
        if record.name == record.description:
            raise ValidationError("Fields name and description must be different")
```

Invoked on the records on which one of the named fields has been modified.

Should raise `ValidationError` if the
validation failed.

> **Warnung**
>
> `@constrains` only supports simple field names, dotted names
> (fields of relational fields e.g. `partner_id.customer`) are not
> supported and will be ignored.
>
> `@constrains` will be triggered only if the declared fields in the
> decorated method are included in the `create` or `write` call.
> It implies that fields not present in a view will not trigger a call
> during a record creation. A override of `create` is necessary to make
> sure a constraint will always be triggered (e.g. to test the absence of
> value).

One may also pass a single function as argument. In that case, the field
names are given by calling the function with a model instance.

**`odoo.api.depends(*args) → Decorator`**

Return a decorator that specifies the field dependencies of a „compute“
method (for new-style function fields). Each argument must be a string
that consists in a dot-separated sequence of field names:

```
pname = fields.Char(compute='_compute_pname')

@api.depends('partner_id.name', 'partner_id.is_company')
def _compute_pname(self):
    for record in self:
        if record.partner_id.is_company:
            record.pname = (record.partner_id.name or "").upper()
        else:
            record.pname = record.partner_id.name
```

One may also pass a single function as argument. In that case, the
dependencies are given by calling the function with the field’s model.

**`odoo.api.depends_context(*args: str) → Decorator`**

Return a decorator that specifies the context dependencies of a
non-stored „compute“ method. Each argument is a key in the context’s
dictionary:

```
price = fields.Float(compute='_compute_product_price')

@api.depends_context('pricelist')
def _compute_product_price(self):
    for product in self:
        if product.env.context.get('pricelist'):
            pricelist = self.env['product.pricelist'].browse(product.env.context['pricelist'])
        else:
            pricelist = self.env['product.pricelist'].get_default_pricelist()
        product.price = pricelist._get_products_price(product).get(product.id, 0.0)
```

All dependencies must be hashable. The following keys have special
support:

- `company` (value in context or current company id),
- `uid` (current user id and superuser flag),
- `active_test` (value in env.context or value in field.context).

**`odoo.api.model(method: C) → C`**

Decorate a record-style method where `self` is a recordset, but its
contents is not relevant, only the model is. Such a method:

```
@api.model
def method(self, args):
    ...
```

**`odoo.api.model_create_multi(method: Callable[[T, list[ValuesType]], T]) → Callable[[T, list[ValuesType] | ValuesType], T]`**

Decorate a method that takes a list of dictionaries and creates multiple
records. The method may be called with either a single dict or a list of
dicts:

```
record = model.create(vals)
records = model.create([vals, ...])
```

**`odoo.api.onchange(*args: str) → Decorator`**

Return a decorator to decorate an onchange method for given fields.

In the form views where the field appears, the method will be called
when one of the given fields is modified. The method is invoked on a
pseudo-record that contains the values present in the form. Field
assignments on that record are automatically sent back to the client.

Each argument must be a field name:

```
@api.onchange('partner_id')
def _onchange_partner(self):
    self.message = "Dear %s" % (self.partner_id.name or "")
```

```python
return {
    'warning': {'title': "Warning", 'message': "What is this?", 'type': 'notification'},
}
```

If the type is set to notification, the warning will be displayed in a notification.
Otherwise it will be displayed in a dialog as default.

> **Warnung**
>
> `@onchange` only supports simple field names, dotted names
> (fields of relational fields e.g. `partner_id.tz`) are not
> supported and will be ignored

> **Gefahr**
>
> Since `@onchange` returns a recordset of pseudo-records,
> calling any one of the CRUD methods
> (`create()`, `read()`, `write()`, `unlink()`)
> on the aforementioned recordset is undefined behaviour,
> as they potentially do not exist in the database yet.
>
> Instead, simply set the record’s field like shown in the example
> above or call the `update()` method.

> **Warnung**
>
> It is not possible for a `one2many` or `many2many` field to modify
> itself via onchange. This is a webclient limitation - see [#2693](https://github.com/odoo/odoo/issues/2693).

**`odoo.api.ondelete(*, at_uninstall: bool) → Decorator`**

Mark a method to be executed during `unlink()`.

The goal of this decorator is to allow client-side errors when unlinking
records if, from a business point of view, it does not make sense to delete
such records. For instance, a user should not be able to delete a validated
sales order.

While this could be implemented by simply overriding the method `unlink`
on the model, it has the drawback of not being compatible with module
uninstallation. When uninstalling the module, the override could raise user
errors, but we shouldn’t care because the module is being uninstalled, and
thus **all** records related to the module should be removed anyway.

This means that by overriding `unlink`, there is a big chance that some
tables/records may remain as leftover data from the uninstalled module. This
leaves the database in an inconsistent state. Moreover, there is a risk of
conflicts if the module is ever reinstalled on that database.

Methods decorated with `@ondelete` should raise an error following some
conditions, and by convention, the method should be named either
`_unlink_if_<condition>` or `_unlink_except_<not_condition>`.

```python
@api.ondelete(at_uninstall=False)
def _unlink_if_user_inactive(self):
    if any(user.active for user in self):
        raise UserError("Can't delete an active user!")

# same as above but with _unlink_except_* as method name
@api.ondelete(at_uninstall=False)
def _unlink_except_active_user(self):
    if any(user.active for user in self):
        raise UserError("Can't delete an active user!")
```

**`Parameter`**

**at_uninstall** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Whether the decorated method should be called if
the module that implements said method is being uninstalled. Should
almost always be `False`, so that module uninstallation does not
trigger those errors.

> **Gefahr**
>
> The parameter `at_uninstall` should only be set to `True` if the
> check you are implementing also applies when uninstalling the module.
>
> For instance, it doesn’t matter if when uninstalling `sale`, validated
> sales orders are being deleted because all data pertaining to `sale`
> should be deleted anyway, in that case `at_uninstall` should be set to
> `False`.
>
> However, it makes sense to prevent the removal of the default language
> if no other languages are installed, since deleting the default language
> will break a lot of basic behavior. In this case, `at_uninstall`
> should be set to `True`.

**`odoo.api.private(method: C) → C`**

Decorate a record-style method to indicate that the method cannot be
called using RPC. Example:

```
@api.private
def method(self, args):
    ...
```

If you have business methods that should not be called over RPC, you
should prefix them with „_“. This decorator may be used in case of
existing public methods that become non-RPC callable or for ORM
methods.
