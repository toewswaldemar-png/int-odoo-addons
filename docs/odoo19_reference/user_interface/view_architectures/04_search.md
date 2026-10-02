<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_architectures.html · abgerufen 2026-10-02 -->

# View architectures – Teil 4/10: Search

## Search

Search views are different from other view types in that they are not used to display content.
Although they apply to a specific model, they are used to filter another view’s content (usually
aggregated views; e.g., List and
Graph).

The root element of search views is `search`.

It takes no attributes.

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/search.svg |
> | ```xml <search>     ... </search> ``` |

### Components

Search views accept the following children elements: field, filter, separator, group, and searchpanel.

Placeholders are denoted in all caps.

#### `field`: filter based on field values

The `field` element defines domains or contexts with user-provided values. When search domains are
generated, field domains are joined with each other and with filters using the **AND** operator.

```xml
<search>
    <field name="FIELD_NAME"/>
</search>
```

The `field` element can have the following attributes:

**`name`**

The name of the field to filter on.

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`string`**

The label of the field.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

The `string` attribute of the model’s field

**`operator`**

By default, fields generate domains of the form `[(name, {operator}, value)]`, where `name`
is the field’s name and `value` is the value provided by the user, possibly filtered or
transformed (e.g., a user is expected to provide the *label* of a selection field’s value, not
the value itself).

The `operator` attribute allows overriding the default operator, which depends on the field’s
type (e.g., `=` for float fields, but `ilike` for char fields and `child_of` for many2one).

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`=`

**`filter_domain`**

The domain to use as the field’s search domain, as a Python expression that evaluates to a
[domain](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#reference-orm-domains).

It can use the `self` variable to inject the provided value in the custom domain. It can be used
to generate significantly more flexible domains than with the `operator` attribute alone (e.g.,
search on multiple fields at once).

If both the `operator` and `filter_domain` attributes are provided, `filter_domain` takes
precedence.

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`[]`

**`context`**

The context to merge into the context of the view that the search view is targeting, as a Python
expression that evaluates to a dict.

It can contain user-provided values, which are available under the `self` variable.

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`{}`

**`domain`**

The filters to apply to the completion results for fields that allow for auto-completion (e.g.,
[`Many2one`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Many2one)).

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`[]`

**`groups`**

The comma-separated list of user groups to whom the element is displayed. Users who do not belong
to at least one of these groups are unable to see the element. Groups can be prefixed with the
negative `!` operator to exclude them.

> **Example**
>
> ```xml
> <field name="FIELD_NAME" groups="base.group_no_one,!base.group_multi_company"/>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`invisible`**

Whether the element is visible (`False`) or hidden (`True`), as a Python expression that
evaluates to a bool.

> **Bemerkung**
>
> There are two uses for the `invisible` attribute:
>
> - Usability: to avoid overloading the view and to make it easier for the user to read,
>   depending on the content.
> - Technical: a field must be present (invisible is enough) in the view to be used in a
>   Python expression.

> **Example**
>
> ```xml
> <field name="fname_b" invisible="fname_c != 3 and fname_a == parent.fname_d"/>
> <group invisible="fname_c != 4">
>     <field name="fname_c"/>
>     <field name="fname_d"/>
> <group>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`False`

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/search_field.svg |
> | ```xml <search>     <field name="name" string="My Custom Name"/>     <field name="amount"/>     <field name="currency_id"/>     <field name="ref" filter_domain="[('name', 'like', self)]"/> </search> ``` |

#### `filter`: create pre-defined filters

The `filter` element is used to create pre-defined filters that can be toggled in the search view.
It allows adding data to the search context the context passed to the data view for
searching/filtering, or appending new sections to the search filter.

```xml
<search>
    <filter string="LABEL" domain="DOMAIN"/>
</search>
```

The `filter` element can have the following attributes:

**`name`**

The technical name of the filter. It can be used to enable it by default or as an [inheritance hook](https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_records.html#reference-view-records-inheritance).

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`string`**

The label of the filter.

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`help`**

The tooltip displayed when hovering the filter.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`domain`**

The domain to append to the action’s domain as part of the search domain.

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`[]`

**`date`**

The name of the `date` or `datetime` field to filter on.

When used, this attribute creates a set of filters available in a sub-menu of the
Filters menu. The available filters are time-dependent but not dynamic in the sense
that their domains are evaluated at the time of the control panel instantiation.

> **Example**
>
> ```xml
> <filter string="Creation Date" name="filter_create_date" date="create_date"/>
> ```

By default, these filters contain a dropdown with different sub-filters that allow you to filter based on months, quarters and years.
Additionally, you can create custom sub-filters that allow filtering using domains.
These custom filters must have the following attributes: `name`, `string` and `domain`.

> **Example**
>
> ```xml
> <filter string="Creation Date" name="filter_create_date" date="create_date">
>    <filter name="create_date_last_30_days" string="Last 30 Days" domain="[('create_date', '&gt;', datetime.datetime.combine(context_today() - relativedelta(days=30), datetime.time(23, 59, 59)).to_utc())]"/>
> </filter>
> ```

Note that all custom filters defined this way are mutually exclusive with each other and with the other sub-filters.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`start_month`**

The earliest month that will show up in the dropdown of a date filter, as an offset relative to the current month.

> **Example**
>
> ```xml
> <filter string="Creation Date" name="filter_create_date" date="create_date" start_month="-3"/>
> ```
>
> If the current month is February, the earliest month selectable in the dropdown will be November.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`Default`**

`-2`

**`Scope`**

Filters with a non-empty `date` attribute

**`end_month`**

The latest month that will show up in the dropdown of a date filter, as an offset relative to the current month.

> **Example**
>
> ```xml
> <filter string="Creation Date" name="filter_create_date" date="create_date" end_month="2"/>
> ```
>
> If the current month is February, the latest month selectable in the dropdown will be March.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`Default`**

`0`

**`Scope`**

Filters with a non-empty `date` attribute

**`start_year`**

The earliest year that will show up in the dropdown of a date filter, as an offset relative to the current year.

> **Example**
>
> ```xml
> <filter string="Creation Date" name="filter_create_date" date="create_date" start_year="-3"/>
> ```
>
> If the current year is 2024, the earliest year selectable in the dropdown will be 2021.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`Default`**

`-2`

**`Scope`**

Filters with a non-empty `date` attribute

**`end_year`**

The latest year that will show up in the dropdown of a date filter, as an offset relative to the current year.

> **Example**
>
> ```xml
> <filter string="Creation Date" name="filter_create_date" date="create_date" end_year="2"/>
> ```
>
> If the current year is 2024, the latest year selectable in the dropdown will be 2025.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`Default`**

`0`

**`Scope`**

Filters with a non-empty `date` attribute

**`default_period`**

The default period of the time-based filter (with a `date` attribute). It must be one of, or a
comma-separated list of valid filter ids.

Valid filter ids include the following:

- `first_quarter`, `second_quarter`, `third_quarter` and `fourth_quarter`.
- One of `month`, `month-x` and `month+x`, where `x` is a non-zero integer value between `start_month` and `end_month`.
- One of `year`, `year-x` and `year+x`, where `x` is a non-zero integer value between `start_year` and `end_year`.
- The `name` of any custom filter defined within the filter, prepended with `custom_`.

The filter must be in the default set of filters activated at the view initialization.

> **Example**
>
> ```xml
> <filter string="Creation Date" name="filter_create_date" date="create_date" default_period="year,month-1"/>
> ```

> **Example**
>
> ```xml
> <filter string="Creation Date" name="filter_create_date" date="create_date" default_period="custom_create_date_last_30_days">
>    <filter name="create_date_last_30_days" string="Last 30 Days" domain="[('create_date', '&gt;', datetime.datetime.combine(context_today() - relativedelta(days=30), datetime.time(23, 59, 59)).to_utc())]"/>
> </filter>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`month`, or the closest value to the current month if unavailable

**`Scope`**

Filters with a non-empty `date` attribute

**`invisible`**

Whether the element is visible (`False`) or hidden (`True`), as a Python expression that
evaluates to a bool.

> **Bemerkung**
>
> There are two uses for the `invisible` attribute:
>
> - Usability: to avoid overloading the view and to make it easier for the user to read,
>   depending on the content.
> - Technical: a field must be present (invisible is enough) in the view to be used in a
>   Python expression.

> **Example**
>
> ```xml
> <field name="fname_b" invisible="fname_c != 3 and fname_a == parent.fname_d"/>
> <group invisible="fname_c != 4">
>     <field name="fname_c"/>
>     <field name="fname_d"/>
> <group>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`False`

**`groups`**

The comma-separated list of user groups to whom the element is displayed. Users who do not belong
to at least one of these groups are unable to see the element. Groups can be prefixed with the
negative `!` operator to exclude them.

> **Example**
>
> ```xml
> <field name="FIELD_NAME" groups="base.group_no_one,!base.group_multi_company"/>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`context`**

The context merged into the action’s domain to generate the search domain

The context key `group_by` set with a field as value can be used to define a group available in
the Group By menu. When the field is of type `date` or `datetime`, the filter
generates a submenu of the Group By menu with the following interval options
available: Year, Quarter, Month, Week, and
Day.

> **Example**
>
> ```xml
> <filter string="Category" name="groupby_category" context="{'group_by': 'category_id'}"/>
> <filter string="Creation Date" name="groupby_create_date" context="{'group_by': 'create_date:week'}"/>
> ```

> **Bemerkung**
>
> The results of `formatted_read_group` grouped on a field may be influenced by its `group_expand`
> attribute, allowing to display empty groups when needed. For more information, please refer to
> [`Field`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Field).

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`{}`

> **Vorsicht**
>
> Sequences of filters (without non-filters elements separating them) are treated as inclusively
> composited: they will be composed with `OR` rather than the usual `AND`.
>
> > **Example**
> >
> > ```xml
> > <filter domain="[('state', '=', 'draft')]"/>
> > <filter domain="[('state', '=', 'done')]"/>
> > ```
> >
> > Records whose `state` field is `draft` or `done` are shown.
>
> > **Example**
> >
> > ```xml
> > <filter domain="[('state', '=', 'draft')]"/>
> > <separator/>
> > <filter domain="[('delay', '&lt;', 15)]"/>
> > ```
> >
> > Records whose `state` field is `draft` **and** `delay` field is below 15.

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/search_filter.svg |
> | ```xml <search>     <filter string="My Custom Name" domain="[('name', 'ilike', 'AAA')]"/>     <filter string="My orders" domain="[('user_id', '=', uid)]"/>     <filter string="Category" context="{'group_by': 'category_id'}"/> </search> ``` |

#### `separator`: separate groups of filters

The `separator` element is used to separates groups of filters in simple search views. For more complex search views,
the group element is recommended.

```xml
<search>
    <FILTERS/>
    <separator/>
    <FILTERS/>
</search>
```

The `separator` element takes no attributes.

#### `group`: separate groups of filters

The `group` element is used to separate groups of filters in cluttered search views. In simpler search views, it
can be substituted for the separator element.

```xml
<search>
    <group>
        <FILTERS/>
    </group>
</search>
```

The `group` element takes no attributes.

#### `searchpanel`: display search panels

The `searchpanel` element displays a search panel to the left of multi-records views. It allows for
quickly filtering data on the basis of given fields.

```xml
<search>
    <searchpanel>
        <FIELDS/>
    </searchpanel>
</search>
```

The `searchpanel` element accepts only `field` children elements.

The `field` element used as a child element of a `searchpanel` element can have the following
attributes:

**`name`**

The name of the field to filter on.

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`string`**

The label of the field.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

The `string` attribute of the model’s field

**`select`**

The behavior and display of the field. It can have two different values:

**`one`**

At most one value can be selected. Supported field types are `many2one` and `selection`.

**`multi`**

Several values can be selected. Supported field types are `many2one`, `many2many` and
`selection`.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`one`

**`groups`**

The comma-separated list of user groups to whom the element is displayed. Users who do not belong
to at least one of these groups are unable to see the element. Groups can be prefixed with the
negative `!` operator to exclude them.

> **Example**
>
> ```xml
> <field name="FIELD_NAME" groups="base.group_no_one,!base.group_multi_company"/>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`icon`**

The icon of the field.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`color`**

The color of the field.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

When the `field` element has the `select=one` attribute set, it can have the following additional
attributes:

**`hierarchize`**

Whether child categories should appear under their parent category, or at the same hierarchy
level.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`Scope`**

[`Many2one`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Many2one) fields

**`depth`**

If set to a non zero integer, the hierarchy (if any) will be unfold up to the given level.

**`Requirement`**

Optional

**`Type`**

integer

**`Default`**

`0`

**`Scope`**

[`Many2one`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Many2one) fields

When the `field` element has the `select=multi` attribute set, it can have the following additional
attributes:

**`enable_counters`**

Whether the record counters is computed and displayed if non-zero.

> **Tipp**
>
> This attribute exists to avoid impacting performance. Another way to address performance
> issues is to override the `search_panel_select_range` and `search_panel_select_multi_range`
> methods.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

**`expand`**

Whether categories and filters with no records should be shown.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

**`limit`**

The maximal number of values to fetch for the field. If the limit is reached, no values are
displayed on the search panel, and an error message is shown instead. If set to 0, all values are
fetched.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`Default`**

`200`

**`domain`**

The conditions that the records have to satisfy.

> **Example**
>
> ```xml
> <searchpanel>
>     <field name="department_id"/>
>     <field name="manager_id" select="multi" domain="[('department_id', '=', department_id)]"/>
> </searchpanel>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`[]`

**`groupby`**

The name of the field name on which values should be grouped.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`Scope`**

[`Many2one`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Many2one) and [`Many2many`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Many2many) fields

### Search defaults

Search fields and filters can be configured through the action’s `context` using
`search_default_{name}` keys. For fields, the value must be the value to set to the field. For
filters, it must be a boolean value or a number.

> **Example**
>
> With `foo`, a field, and `bar`, a filter, the following action context will search `foo` on
> `acro` and enable `bar` by default:
>
> ```python
> {
>     'search_default_foo': 'acro',
>     'search_default_bar': 1
> }
> ```

A numeric value (between 1 and 99) can be used to define the order of default *groupby* filters.

> **Example**
>
> With `foo` and `bar`, two *groupby* filters, the following action context will first enable
> `bar`, then `foo`.
>
> ```python
> {
>     'search_default_foo': 2,
>     'search_default_bar': 1
> }
> ```
