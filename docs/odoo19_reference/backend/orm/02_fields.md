<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html · abgerufen 2026-10-02 -->

# ORM API – Teil 2/6: Fields

## Fields

**`class odoo.fields.Field`**

The field descriptor contains the field definition, and manages accesses
and assignments of the corresponding field on records. The following
attributes may be provided when instantiating a field:

**`Parameter`**

- **string** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – the label of the field seen by users; if not
  set, the ORM takes the field name in the class (capitalized).
- **help** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – the tooltip of the field seen by users
- **readonly** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) –

  whether the field is readonly (default: `False`)

  This only has an impact on the UI. Any field assignation in code will work
  (if the field is a stored field or an inversable one).
- **required** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the value of the field is required (default: `False`)
- **index** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) –

  whether the field is indexed in database, and the kind of index.
  Note: this has no effect on non-stored and virtual fields.
  The possible values are:

  - `"btree"` or `True`: standard index, good for many2one
  - **`"btree_not_null": BTREE index without NULL values (useful when most`**

    values are NULL, or when NULL is never searched for)
  - `"trigram"`: Generalized Inverted Index (GIN) with trigrams (good for full-text search)
  - `None` or `False`: no index (default)
- **default** (*value* *or* *callable*) – the default value for the field; this is either a static
  value, or a function taking a recordset and returning a value; use
  `default=None` to discard default values for the field
- **groups** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – comma-separated list of group xml ids (string); this
  restricts the field access to the users of the given groups only
- **company_dependent** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) –

  whether the field value is dependent of the current company;

  The value is stored on the model table as jsonb dict with the company id as the key.

  The field’s default values stored in model ir.default are used as fallbacks for
  unspecified values in the jsonb dict.
- **copy** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the field value should be copied when the record
  is duplicated (default: `True` for normal fields, `False` for
  `one2many` and computed fields, including property fields and
  related fields)
- **store** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the field is stored in database
  (default:`True`, `False` for computed fields)
- **default_export_compatible** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the field must be exported
  by default in an import-compatible export
- **search** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) –

  name of a method that implements search on the field.
  The method takes an operator and value. Basic domain optimizations are
  ran before calling this function.
  For instance, all `'='` are transformed to `'in'`, and boolean
  fields conditions are made such that operator is `'in'`/`'not in'`
  and value is `[True]`.

  The method should `return NotImplemented` if it does not support the
  operator.
  In that case, the ORM can try to call it with other, semantically
  equivalent, operators. For instance, try with the positive operator if
  its corresponding negative operator is not implemented.
  The method must return a Search domains that replaces
  `(field, operator, value)` in its domain.

  Note that a stored field can actually have a search method. The search
  method will be invoked to rewrite the condition. This may be useful for
  sanitizing the values used in the condition, for instance.

  ```python
  def _search_partner_ref(self, operator, value):
      if operator not in ('in', 'like'):
          return NotImplemented
      ...  # add your logic here, example
      return Domain('partner_id.ref', operator, value)
  ```

Aggregation

**`Parameter`**

- **aggregator** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) –

  default aggregate function used by the webclient
  on this field when using „Group By“ feature.

  Supported aggregators are:

  - `count` : number of rows
  - `count_distinct` : number of distinct rows
  - `bool_and` : true if all values are true, otherwise false
  - `bool_or` : true if at least one value is true, otherwise false
  - `max` : maximum value of all values
  - `min` : minimum value of all values
  - `avg` : the average (arithmetic mean) of all values
  - `sum` : sum of all values
- **group_expand** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) –

  function used to expand results when grouping on the
  current field for kanban/list/gantt views. For selection fields,
  `group_expand=True` automatically expands groups for all selection keys.

  ```python
  @api.model
  def _read_group_selection_field(self, values, domain):
      return ['choice1', 'choice2', ...] # available selection choices.

  @api.model
  def _read_group_many2one_field(self, records, domain):
      return records + self.search([custom_domain])
  ```

Computed Fields

**`Parameter`**

- **compute** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) –

  name of a method that computes the field

  > **Siehe auch**
  >
  > Advanced Fields/Compute fields
- **precompute** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) –

  whether the field should be computed before record insertion
  in database. Should be used to specify manually some fields as precompute=True
  when the field can be computed before record insertion.
  (e.g. avoid statistics fields based on search/_read_group), many2one
  linking to the previous record, … (default: `False`)

  > **Warnung**
  >
  > Precomputation only happens when no explicit value and no default
  > value is provided to create(). This means that a default value
  > disables the precomputation, even if the field is specified as
  > precompute=True.
  >
  > Precomputing a field can be counterproductive if the records of the
  > given model are not created in batch. Consider the situation were
  > many records are created one by one. If the field is not
  > precomputed, it will normally be computed in batch at the flush(),
  > and the prefetching mechanism will help making the computation
  > efficient. On the other hand, if the field is precomputed, the
  > computation will be made one by one, and will therefore not be able
  > to take advantage of the prefetching mechanism.
  >
  > Following the remark above, precomputed fields can be interesting on
  > the lines of a one2many, which are usually created in batch by the
  > ORM itself, provided that they are created by writing on the record
  > that contains them.
- **compute_sudo** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the field should be recomputed as superuser
  to bypass access rights (by default `True` for stored fields, `False`
  for non stored fields)
- **recursive** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the field has recursive dependencies (the field
  `X` has a dependency like `parent_id.X`); declaring a field recursive
  must be explicit to guarantee that recomputation is correct
- **inverse** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of a method that inverses the field (optional)
- **related** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) –

  sequence of field names

  > **Siehe auch**
  >
  > Advanced fields/Related fields

### Basic Fields

**`class odoo.fields.Boolean`**

Encapsulates a [`bool`](https://docs.python.org/3/library/functions.html#bool).

**`class odoo.fields.Char`**

Basic string field, can be length-limited, usually displayed as a
single-line string in clients.

**`Parameter`**

- **size** ([*int*](https://docs.python.org/3/library/functions.html#int)) – the maximum size of values stored for that field
- **trim** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) –

  states whether the value is trimmed or not (by default,
  `True`). Note that the trim operation is applied by both the server code and the web client
  This ensures consistent behavior between imported data and UI-entered data.

  - The web client trims user input during in write/create flows in UI.
  - The server trims values during import (in `base_import`) to avoid discrepancies between
    trimmed form inputs and stored DB values.
- **translate** ([*bool*](https://docs.python.org/3/library/functions.html#bool) *or* *callable*) – enable the translation of the field’s values; use
  `translate=True` to translate field values as a whole; `translate`
  may also be a callable such that `translate(callback, value)`
  translates `value` by using `callback(term)` to retrieve the
  translation of terms.

**`class odoo.fields.Float`**

Encapsulates a [`float`](https://docs.python.org/3/library/functions.html#float).

The precision digits are given by the (optional) `digits` attribute.

**`Parameter`**

- **digits** ([*tuple*](https://docs.python.org/3/library/stdtypes.html#tuple)*(*[*int*](https://docs.python.org/3/library/functions.html#int)*,*[*int*](https://docs.python.org/3/library/functions.html#int)*) or* [*str*](https://docs.python.org/3/library/stdtypes.html#str)) – a pair (total, decimal) or a string referencing a
  `DecimalPrecision` record name.
- **min_display_digits** ([*int*](https://docs.python.org/3/library/functions.html#int) *or* [*str*](https://docs.python.org/3/library/stdtypes.html#str)) – An int or a string referencing a
  `DecimalPrecision` record name.
  Represents the minimum number of decimal digits to display in the UI.
  So if it’s equal to 3:
  - `3.1` will be shown as `'3.100'`.
  - `3.1234` will be shown as `'3.1234'`.

When a float is a quantity associated with an unit of measure, it is important
to use the right tool to compare or round values with the correct precision.

The Float class provides some static methods for this purpose:

`round()` to round a float with the given precision.
`is_zero()` to check if a float equals zero at the given precision.
`compare()` to compare two floats at the given precision.

> **Example**
>
> To round a quantity with the precision of the unit of measure:
>
> ```
> fields.Float.round(self.product_uom_qty, precision_rounding=self.product_uom_id.rounding)
> ```
>
> To check if the quantity is zero with the precision of the unit of measure:
>
> ```
> fields.Float.is_zero(self.product_uom_qty, precision_rounding=self.product_uom_id.rounding)
> ```
>
> To compare two quantities:
>
> ```
> field.Float.compare(self.product_uom_qty, self.qty_done, precision_rounding=self.product_uom_id.rounding)
> ```
>
> The compare helper uses the __cmp__ semantics for historic purposes, therefore
> the proper, idiomatic way to use this helper is like so:
>
> > if result == 0, the first and second floats are equal
> > if result < 0, the first float is lower than the second
> > if result > 0, the first float is greater than the second

**`class odoo.fields.Integer`**

Encapsulates an [`int`](https://docs.python.org/3/library/functions.html#int).

### Advanced Fields

**`class odoo.fields.Binary`**

Encapsulates a binary content (e.g. a file).

**`Parameter`**

**attachment** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the field should be stored as `ir_attachment`
or in a column of the model’s table (default: `True`).

**`class odoo.fields.Html`**

Encapsulates an html code content.

**`Parameter`**

- **sanitize** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether value must be sanitized (default: `True`)
- **sanitize_overridable** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the sanitation can be bypassed by
  the users part of the `base.group_sanitize_override` group (default: `False`)
- **sanitize_tags** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to sanitize tags
  (only a white list of attributes is accepted, default: `True`)
- **sanitize_attributes** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to sanitize attributes
  (only a white list of attributes is accepted, default: `True`)
- **sanitize_style** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to sanitize style attributes (default: `False`)
- **sanitize_conditional_comments** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to kill conditional comments. (default: `True`)
- **sanitize_output_method** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to sanitize using html or xhtml (default: `html`)
- **strip_style** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to strip style attributes
  (removed and therefore not sanitized, default: `False`)
- **strip_classes** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to strip classes attributes (default: `False`)

**`class odoo.fields.Image`**

Encapsulates an image, extending `Binary`.

If image size is greater than the `max_width`/`max_height` limit of pixels, the image will be
resized to the limit by keeping aspect ratio.

**`Parameter`**

- **max_width** ([*int*](https://docs.python.org/3/library/functions.html#int)) – the maximum width of the image (default: `0`, no limit)
- **max_height** ([*int*](https://docs.python.org/3/library/functions.html#int)) – the maximum height of the image (default: `0`, no limit)
- **verify_resolution** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the image resolution should be verified
  to ensure it doesn’t go over the maximum image resolution (default: `True`).
  See `odoo.tools.image.ImageProcess` for maximum image resolution (default: `50e6`).

> **Bemerkung**
>
> If no `max_width`/`max_height` is specified (or is set to 0) and `verify_resolution` is False,
> the field content won’t be verified at all and a `Binary` field should be used.

**`class odoo.fields.Monetary`**

Encapsulates a [`float`](https://docs.python.org/3/library/functions.html#float) expressed in a given
`res_currency`.

The decimal precision and currency symbol are taken from the `currency_field` attribute.

**`Parameter`**

**currency_field** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the `Many2one` field
holding the `res_currency`
this monetary field is expressed in (default: `'currency_id'`)

**`class odoo.fields.Selection`**

Encapsulates an exclusive choice between different values.

**`Parameter`**

- **selection** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*tuple*](https://docs.python.org/3/library/stdtypes.html#tuple)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*,*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)**) or* *callable* *or* [*str*](https://docs.python.org/3/library/stdtypes.html#str)) – specifies the possible values for this field.
  It is given as either a list of pairs `(value, label)`, or a model
  method, or a method name.
- **selection_add** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*tuple*](https://docs.python.org/3/library/stdtypes.html#tuple)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*,*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)**)*) –

  provides an extension of the selection in the case
  of an overridden field. It is a list of pairs `(value, label)` or
  singletons `(value,)`, where singleton values must appear in the
  overridden selection. The new values are inserted in an order that is
  consistent with the overridden selection and this list:

  ```
  selection = [('a', 'A'), ('b', 'B')]
  selection_add = [('c', 'C'), ('b',)]
  > result = [('a', 'A'), ('c', 'C'), ('b', 'B')]
  ```
- **ondelete** –

  provides a fallback mechanism for any overridden
  field with a selection_add. It is a dict that maps every option
  from the selection_add to a fallback action.

  This fallback action will be applied to all records whose
  selection_add option maps to it.

  **`The actions can be any of the following:`**

  - ‘set null‘ – the default, all records with this option
    will have their selection value set to False.
  - ‘cascade‘ – all records with this option will be
    deleted along with the option itself.
  - ‘set default‘ – all records with this option will be
    set to the default of the field definition
  - ’set VALUE‘ – all records with this option will be
    set to the given value
  - <callable> – a callable whose first and only argument will be
    the set of records containing the specified Selection option,
    for custom processing

The attribute `selection` is mandatory except in the case of
`related` or extended fields.

**`class odoo.fields.Text`**

Very similar to `Char` but used for longer contents, does not
have a size and usually displayed as a multiline text box.

**`Parameter`**

**translate** ([*bool*](https://docs.python.org/3/library/functions.html#bool) *or* *callable*) – enable the translation of the field’s values; use
`translate=True` to translate field values as a whole; `translate`
may also be a callable such that `translate(callback, value)`
translates `value` by using `callback(term)` to retrieve the
translation of terms.

#### Date(time) Fields

`Dates` and `Datetimes`
are very important fields in any kind of business application.
Their misuse can create invisible yet painful bugs, this section
aims to provide Odoo developers with the knowledge required
to avoid misusing these fields.

When assigning a value to a Date/Datetime field, the following options are valid:

- A `date` or `datetime` object.
- A string in the proper server format:

  - `YYYY-MM-DD` for `Date` fields,
  - `YYYY-MM-DD HH:MM:SS` for `Datetime` fields.
- `False` or `None`.

The Date and Datetime fields class have helper methods to attempt conversion
into a compatible type:

- `to_date()` will convert to a [`datetime.date`](https://docs.python.org/3/library/datetime.html#datetime.date)
- `to_datetime()` will convert to a [`datetime.datetime`](https://docs.python.org/3/library/datetime.html#datetime.datetime).

> **Example**
>
> To parse date/datetimes coming from external sources:
>
> ```
> fields.Date.to_date(self._context.get('date_from'))
> ```

Date / Datetime comparison best practices:

- Date fields can **only** be compared to date objects.
- Datetime fields can **only** be compared to datetime objects.

> **Warnung**
>
> Strings representing dates and datetimes can be compared
> between each other, however the result may not be the expected
> result, as a datetime string will always be greater than a
> date string, therefore this practice is **heavily**
> discouraged.

Common operations with dates and datetimes such as addition, subtraction or
fetching the start/end of a period are exposed through both
`Date` and `Datetime`.
These helpers are also available by importing `odoo.tools.date_utils`.

> **Bemerkung**
>
> Timezones
>
> Datetime fields are stored as `timestamp without timezone` columns in the database and are stored
> in the UTC timezone. This is by design, as it makes the Odoo database independent from the timezone
> of the hosting server system. Timezone conversion is managed entirely by the client side.

**`class odoo.fields.Date`**

Encapsulates a python [`date`](https://docs.python.org/3/library/datetime.html#datetime.date) object.

**`static today(*args) → datetime.date`**

Return the current day in the format expected by the ORM.

> **Bemerkung**
>
> This function may be used to compute default values.

**`static context_today(record: BaseModel, timestamp: date | datetime | None = None) → date`**

Return the current date as seen in the client’s timezone in a format
fit for date fields.

> **Bemerkung**
>
> This method may be used to compute default values.

**`Parameter`**

- **record** – recordset from which the timezone will be obtained.
- **timestamp** – optional datetime value to use instead of
  the current date and time (must be a datetime, regular dates
  can’t be converted between timezones).

**`static to_date(value) → datetime.date | None`**

Attempt to convert `value` to a `date` object.

> **Warnung**
>
> If a datetime object is given as value,
> it will be converted to a date object and all
> datetime-specific information will be lost (HMS, TZ, …).

**`Parameter`**

**value** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *or* *date* *or* *datetime*) – value to convert.

**`Rückgabe`**

an object representing `value`.

**`static to_string(value: Union[datetime.date, Literal[False]]) → Union[str, Literal[False]]`**

Convert a `date` or `datetime` object to a string.

**`Parameter`**

**value** – value to convert.

**`Rückgabe`**

a string representing `value` in the server’s date format, if `value` is of
type `datetime`, the hours, minute, seconds, tzinfo will be truncated.

**`static start_of(value: D, granularity: Granularity) → D`**

Get start of a time period from a date or a datetime.

**`Parameter`**

- **value** – initial date or datetime.
- **granularity** – type of period in string, can be year, quarter, month, week, day or hour.

**`Rückgabe`**

a date/datetime object corresponding to the start of the specified period.

**`static end_of(value: D, granularity: Granularity) → D`**

Get end of a time period from a date or a datetime.

**`Parameter`**

- **value** – initial date or datetime.
- **granularity** – Type of period in string, can be year, quarter, month, week, day or hour.

**`Rückgabe`**

A date/datetime object corresponding to the start of the specified period.

**`static add(value: D, *args, **kwargs) → D`**

Return the sum of `value` and a `relativedelta`.

**`Parameter`**

- **value** – initial date or datetime.
- **args** – positional args to pass directly to `relativedelta`.
- **kwargs** – keyword args to pass directly to `relativedelta`.

**`Rückgabe`**

the resulting date/datetime.

**`static subtract(value: D, *args, **kwargs) → D`**

Return the difference between `value` and a `relativedelta`.

**`Parameter`**

- **value** – initial date or datetime.
- **args** – positional args to pass directly to `relativedelta`.
- **kwargs** – keyword args to pass directly to `relativedelta`.

**`Rückgabe`**

the resulting date/datetime.

**`class odoo.fields.Datetime`**

Encapsulates a python [`datetime`](https://docs.python.org/3/library/datetime.html#datetime.datetime) object.

**`static now(*args) → datetime.datetime`**

Return the current day and time in the format expected by the ORM.

> **Bemerkung**
>
> This function may be used to compute default values.

**`static today(*args) → datetime.datetime`**

Return the current day, at midnight (00:00:00).

**`static context_timestamp(record: BaseModel, timestamp: datetime) → datetime`**

Return the given timestamp converted to the client’s timezone.

> **Bemerkung**
>
> This method is *not* meant for use as a default initializer,
> because datetime fields are automatically converted upon
> display on client side. For default values, `now()`
> should be used instead.

**`Parameter`**

- **record** – recordset from which the timezone will be obtained.
- **timestamp** (*datetime*) – naive datetime value (expressed in UTC)
  to be converted to the client timezone.

**`Rückgabe`**

timestamp converted to timezone-aware datetime in context timezone.

**`Rückgabetyp`**

datetime

**`static to_datetime(value) → datetime.datetime | None`**

Convert an ORM `value` into a `datetime` value.

**`Parameter`**

**value** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *or* *date* *or* *datetime*) – value to convert.

**`Rückgabe`**

an object representing `value`.

**`static to_string(value: Union[datetime.datetime, Literal[False]]) → Union[str, Literal[False]]`**

Convert a `datetime` or `date` object to a string.

**`Parameter`**

**value** (*datetime* *or* *date*) – value to convert.

**`Rückgabe`**

a string representing `value` in the server’s datetime format,
if `value` is of type `date`,
the time portion will be midnight (00:00:00).

**`static start_of(value: D, granularity: Granularity) → D`**

Get start of a time period from a date or a datetime.

**`Parameter`**

- **value** – initial date or datetime.
- **granularity** – type of period in string, can be year, quarter, month, week, day or hour.

**`Rückgabe`**

a date/datetime object corresponding to the start of the specified period.

**`static end_of(value: D, granularity: Granularity) → D`**

Get end of a time period from a date or a datetime.

**`Parameter`**

- **value** – initial date or datetime.
- **granularity** – Type of period in string, can be year, quarter, month, week, day or hour.

**`Rückgabe`**

A date/datetime object corresponding to the start of the specified period.

**`static add(value: D, *args, **kwargs) → D`**

Return the sum of `value` and a `relativedelta`.

**`Parameter`**

- **value** – initial date or datetime.
- **args** – positional args to pass directly to `relativedelta`.
- **kwargs** – keyword args to pass directly to `relativedelta`.

**`Rückgabe`**

the resulting date/datetime.

**`static subtract(value: D, *args, **kwargs) → D`**

Return the difference between `value` and a `relativedelta`.

**`Parameter`**

- **value** – initial date or datetime.
- **args** – positional args to pass directly to `relativedelta`.
- **kwargs** – keyword args to pass directly to `relativedelta`.

**`Rückgabe`**

the resulting date/datetime.

#### Relational Fields

**`class odoo.fields.Many2one`**

The value of such a field is a recordset of size 0 (no
record) or 1 (a single record).

**`Parameter`**

- **comodel_name** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the target model
  `Mandatory` except for related or extended fields.
- **domain** – an optional domain to set on candidate values on the
  client side (domain or a python expression that will be evaluated
  to provide domain)
- **context** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – an optional context to use on the client side when
  handling that field
- **ondelete** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – what to do when the referred record is deleted;
  possible values are: `'set null'`, `'restrict'`, `'cascade'`
- **bypass_search_access** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether access rights are bypassed on the
  comodel (default: `False`)
- **delegate** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – set it to `True` to make fields of the target model
  accessible from the current model (corresponds to `_inherits`)
- **check_company** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Mark the field to be verified in
  [`_check_company()`](https://www.odoo.com/documentation/19.0/de/developer/howtos/company.html#odoo.models.Model._check_company). Has a different behaviour
  depending on whether the field is company_dependent or not.
  Constrains non-company-dependent fields to target records whose
  company_id(s) are compatible with the record’s company_id(s).
  Constrains company_dependent fields to target records whose
  company_id(s) are compatible with the currently active company.

**`class odoo.fields.One2many`**

One2many field; the value of such a field is the recordset of all the
records in `comodel_name` such that the field `inverse_name` is equal to
the current record.

**`Parameter`**

- **comodel_name** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the target model
- **inverse_name** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the inverse `Many2one` field in
  `comodel_name`
- **domain** – an optional domain to set on candidate values on the
  client side (domain or a python expression that will be evaluated
  to provide domain)
- **context** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – an optional context to use on the client side when
  handling that field
- **bypass_search_access** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether access rights are bypassed on the
  comodel (default: `False`)

The attributes `comodel_name` and `inverse_name` are mandatory except in
the case of related fields or field extensions.

**`class odoo.fields.Many2many`**

Many2many field; the value of such a field is the recordset.

**`Parameter`**

- **comodel_name** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the target model (string)
  mandatory except in the case of related or extended fields
- **relation** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – optional name of the table that stores the relation in
  the database
- **column1** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – optional name of the column referring to „these“ records
  in the table `relation`
- **column2** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – optional name of the column referring to „those“ records
  in the table `relation`

The attributes `relation`, `column1` and `column2` are optional.
If not given, names are automatically generated from model names,
provided `model_name` and `comodel_name` are different!

Note that having several fields with implicit relation parameters on a
given model with the same comodel is not accepted by the ORM, since
those field would use the same table. The ORM prevents two many2many
fields to use the same relation parameters, except if

- both fields use the same model, comodel, and relation parameters are
  explicit; or
- at least one field belongs to a model with `_auto = False`.

**`Parameter`**

- **domain** – an optional domain to set on candidate values on the
  client side (domain or a python expression that will be evaluated
  to provide domain)
- **context** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – an optional context to use on the client side when
  handling that field
- **check_company** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Mark the field to be verified in
  [`_check_company()`](https://www.odoo.com/documentation/19.0/de/developer/howtos/company.html#odoo.models.Model._check_company). Add a default company
  domain depending on the field attributes.

**`class odoo.fields.Command`**

`One2many` and `Many2many` fields
expect a special command to manipulate the relation they implement.

Internally, each command is a 3-elements tuple where the first element is a
mandatory integer that identifies the command, the second element is either
the related record id to apply the command on (commands update, delete,
unlink and link) either 0 (commands create, clear and set), the third
element is either the `values` to write on the record (commands create
and update) either the new `ids` list of related records (command set),
either 0 (commands delete, unlink, link, and clear).
This triplet is aliased as `CommandValue`.

Via Python, we encourage developers craft new commands via the various
functions of this namespace. We also encourage developers to use the
command identifier constant names when comparing the 1st element of
existing commands.

Via RPC, it is impossible nor to use the functions nor the command constant
names. It is required to instead write the literal 3-elements tuple where
the first element is the integer identifier of the command.

**`CREATE = 0`**

**`UPDATE = 1`**

**`DELETE = 2`**

**`UNLINK = 3`**

**`LINK = 4`**

**`CLEAR = 5`**

**`SET = 6`**

**`classmethod create(values: ValuesType) → CommandValue`**

Create new records in the comodel using `values`, link the created
records to `self`.

In case of a `Many2many` relation, one unique
new record is created in the comodel such that all records in `self`
are linked to the new record.

In case of a `One2many` relation, one new record
is created in the comodel for every record in `self` such that every
record in `self` is linked to exactly one of the new records.

Return the command triple `(CREATE, 0, {values})`

**`classmethod update(id: int, values: ValuesType) → CommandValue`**

Write `values` on the related record.

Return the command triple `(UPDATE, {id}, {values})`

**`classmethod delete(id: int) → CommandValue`**

Remove the related record from the database and remove its relation
with `self`.

In case of a `Many2many` relation, removing the
record from the database may be prevented if it is still linked to
other records.

Return the command triple `(DELETE, {id}, 0)`

**`classmethod unlink(id: int) → CommandValue`**

Remove the relation between `self` and the related record.

In case of a `One2many` relation, the given record
is deleted from the database if the inverse field is set as
`ondelete='cascade'`. Otherwise, the value of the inverse field is
set to False and the record is kept.

Return the command triple `(UNLINK, {id}, 0)`

**`classmethod link(id: int) → CommandValue`**

Add a relation between `self` and the related record.

Return the command triple `(LINK, {id}, 0)`

**`classmethod clear() → CommandValue`**

Remove all records from the relation with `self`. It behaves like
executing the `unlink` command on every record.

Return the command triple `(CLEAR, 0, 0)`

**`classmethod set(ids: Collection[int]) → CommandValue`**

Replace the current relations of `self` by the given ones. It behaves
like executing the `unlink` command on every removed relation then
executing the `link` command on every new relation.

Return the command triple `(SET, 0, {ids})`

#### Pseudo-relational fields

**`class odoo.fields.Reference`**

Pseudo-relational field (no FK in database).

The field value is stored as a [`string`](https://docs.python.org/3/library/stdtypes.html#str) following the pattern
`"res_model,res_id"` in database.

**`class odoo.fields.Many2oneReference`**

Pseudo-relational field (no FK in database).

The field value is stored as an [`integer`](https://docs.python.org/3/library/functions.html#int) id in database.

Contrary to `Reference` fields, the model has to be specified
in a `Char` field, whose name has to be specified in the
`model_field` attribute for the current `Many2oneReference` field.

**`Parameter`**

**model_field** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the `Char` where the model name is stored.

#### Computed Fields

Fields can be computed (instead of read straight from the database) using the
`compute` parameter. **It must assign the computed value to the field**. If
it uses the values of other *fields*, it should specify those fields using
`depends()`.

```
from odoo import api
total = fields.Float(compute='_compute_total')

@api.depends('value', 'tax')
def _compute_total(self):
    for record in self:
        record.total = record.value + record.value * record.tax
```

- dependencies can be dotted paths when using sub-fields:

  ```
  @api.depends('line_ids.value')
  def _compute_total(self):
      for record in self:
          record.total = sum(line.value for line in record.line_ids)
  ```
- computed fields are not stored by default, they are computed and
  returned when requested. Setting `store=True` will store them in the
  database and automatically enable searching and grouping.
  Note that by default, `compute_sudo=True` is set on the field.
- searching on a computed field can also be enabled by setting the `search`
  parameter. The value is a method name returning a
  Search domains.

  ```
  upper_name = field.Char(compute='_compute_upper', search='_search_upper')

  def _search_upper(self, operator, value):
      if operator == 'like':
          operator = 'ilike'
      return Domain('name', operator, value)
  ```
- computed fields are readonly by default. To allow *setting* values on a
  computed field, use the `inverse` parameter.
  It is the name of a function reversing the computation and
  setting the relevant fields:

  ```
  document = fields.Char(compute='_get_document', inverse='_set_document')

  def _get_document(self):
      for record in self:
          with open(record.get_document_path) as f:
              record.document = f.read()
  def _set_document(self):
      for record in self:
          if not record.document: continue
          with open(record.get_document_path()) as f:
              f.write(record.document)
  ```
- multiple fields can be computed at the same time by the same method, just
  use the same method on all fields and set all of them:

  ```
  discount_value = fields.Float(compute='_apply_discount')
  total = fields.Float(compute='_apply_discount')

  @api.depends('value', 'discount')
  def _apply_discount(self):
      for record in self:
          # compute actual discount from discount percentage
          discount = record.value * record.discount
          record.discount_value = discount
          record.total = record.value - discount
  ```

> **Warnung**
>
> While it is possible to use the same compute method for multiple
> fields, it is not recommended to do the same for the inverse
> method.
>
> During the computation of the inverse, **all** fields that use
> said inverse are protected, meaning that they can’t be computed,
> even if their value is not in the cache.
>
> If any of those fields is accessed and its value is not in cache,
> the ORM will simply return a default value of `False` for these fields.
> This means that the value of the inverse fields (other than the one
> triggering the inverse method) may not give their correct value and
> this will probably break the expected behavior of the inverse method.

#### Related fields

A special case of computed fields are *related* (proxy) fields, which provide
the value of a sub-field on the current record. They are defined by setting
the `related` parameter and like regular computed fields they can be
stored:

```
nickname = fields.Char(related='user_id.partner_id.name', store=True)
```

The value of a related field is given by following a sequence of
relational fields and reading a field on the reached model. The complete
sequence of fields to traverse is specified by the `related` attribute.

Some field attributes are automatically copied from the source field if
they are not redefined: `string`, `help`, `required` (only
if all fields in the sequence are required), `groups`, `digits`, `size`,
`translate`, `sanitize`, `selection`, `comodel_name`, `domain`,
`context`. All semantic-free attributes are copied from the source
field.

By default, related fields are:

- not stored
- not copied
- readonly
- computed in superuser mode

Add the attribute `store=True` to make it stored, just like computed
fields. Related fields are automatically recomputed when their
dependencies are modified.

> **Tipp**
>
> You can specify precise field dependencies if you don’t want
> the related field to be recomputed on any dependency change:
>
> ```
> nickname = fields.Char(
>     related='partner_id.name', store=True,
>     depends=['partner_id'])
> # The nickname will only be recomputed when the partner_id
> # is modified, not when the name is modified on the partner.
> ```

> **Warnung**
>
> You cannot chain `Many2many` or `One2many` fields in `related` fields dependencies.
>
> `related` can be used to refer to a `One2many` or
> `Many2many` field on another model on the
> condition that it’s done through a `Many2one` relation on the current model.
> `One2many` and `Many2many` are not supported and the results will not be
> aggregated correctly:
>
> ```
> m2o_id = fields.Many2one()
> m2m_ids = fields.Many2many()
> o2m_ids = fields.One2many()
>
> # Supported
> d_ids = fields.Many2many(related="m2o_id.m2m_ids")
> e_ids = fields.One2many(related="m2o_id.o2m_ids")
>
> # Won't work: use a custom Many2many computed field instead
> f_ids = fields.Many2many(related="m2m_ids.m2m_ids")
> g_ids = fields.One2many(related="o2m_ids.o2m_ids")
> ```

### Automatic fields

**`Model.id`**

Identifier `field`

If length of current recordset is 1, return id of unique record in it.

Raise an Error otherwise.

**`Model.display_name`**

Name `field` displayed by default in the web client

By default, it equals to `_rec_name` value field
but the behavior can be customized by overriding `_compute_display_name`

#### Access Log fields

These fields are automatically set and updated if
`_log_access` is enabled. It can be
disabled to avoid creating or updating those fields on tables for which they are
not useful.

By default, `_log_access` is set to the same value
as `_auto`

**`Model.create_date`**

Stores when the record was created, `Datetime`

**`Model.create_uid`**

Stores *who* created the record, `Many2one` to a
`res.users`.

**`Model.write_date`**

Stores when the record was last updated, `Datetime`

**`Model.write_uid`**

Stores who last updated the record, `Many2one` to a
`res.users`.

> **Warnung**
>
> `_log_access` *must* be enabled on
> `TransientModel`.

### Reserved Field names

A few field names are reserved for pre-defined behaviors beyond that of
automated fields. They should be defined on a model when the related
behavior is desired:

**`Model.name`**

default value for `_rec_name`, used to
display records in context where a representative „naming“ is
necessary.

`Char`

**`Model.active`**

toggles the global visibility of the record, if `active` is set to
`False` the record is invisible in most searches and listing.

`Boolean`

Special methods:

**`action_archive()`**

Set `active` to `False` on a recordset for active records.

Note, you probably want to override `write()` method if you want to take
action once the active field changes.

**`Model.action_unarchive()`**

Set `active` to `True` on a recordset for inactive records.

Note, you probably want to override `write()` method if you want to take
action once the active field changes.

**`Model.state`**

lifecycle stages of the object, used by the `states` attribute on
`fields`.

`Selection`

**`Model.parent_id`**

default_value of `_parent_name`, used to organize
records in a tree structure and enables the `child_of`
and `parent_of` operators in domains.

`Many2one`

**`Model.parent_path`**

When `_parent_store` is set to True, used to store a value reflecting
the tree structure of `_parent_name`, and to optimize the operators
`child_of` and `parent_of` in Search domains.
It must be declared with `index=True` for proper operation.

`Char`

**`Model.company_id`**

Main field name used for Odoo multi-company behavior.

Used by `:meth:~odoo.models._check_company` to check multi company consistency.
Defines whether a record is shared between companies (no value) or only
accessible by the users of a given company.

`Many2one`
:type: `res_company`
