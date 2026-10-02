<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_architectures.html · abgerufen 2026-10-02 -->

# View architectures – Teil 7/10: Pivot / Calendar

## Pivot

The pivot view is used to visualize aggregations as a [pivot table](https://en.wikipedia.org/wiki/Pivot_table). Its root
element is `<pivot>` which can take the following attributes:

**`disable_linking (optional)`**

Set to `1` to remove table cell’s links to list view.

**`display_quantity (optional)`**

Set to `1` to display the Quantity column by default.

**`default_order (optional)`**

The name of the measure and the order (asc or desc) to use as default order
in the view.

```xml
<pivot default_order="foo asc">
   <field name="foo" type="measure"/>
</pivot>
```

The only allowed element within a pivot view is `field` which can have the
following attributes:

**`name (mandatory)`**

the name of a field to use in the view. If used for grouping (rather
than aggregating)

**`string (optional)`**

the name that will be used to display the field in the pivot view,
overrides the default python String attribute of the field.

**`type (optional)`**

indicates whether the field should be used as a grouping criteria or as an
aggregated value within a group. Possible values are:

**`row (default)`**

groups by the specified field, each group gets its own row.

**`col`**

creates column-wise groups

**`measure`**

field to aggregate within a group

**`interval`**

on date and datetime fields, groups by the specified interval (`day`,
`week`, `month`, `quarter` or `year`) instead of grouping on the
specific datetime (fixed second resolution) or date (fixed day resolution).

**`invisible (optional)`**

if true, the field will not appear either in the active measures nor
in the selectable measures (useful for fields that do not make sense aggregated,
such as fields in different units, e.g. € and $).

**`sample`**

Whether the view should be populated with a set of sample records if none are found for the
current model.

These fake records have heuristics for certain field names/models. For example, a field
`display_name` on the model `res.users` will be populated with sample people names, while an
`email` field will be in the form `firstname.lastname@sample.demo`.

The user is unable to interact with these data, and they will be discarded as soon as an action
is performed (record created, column added, etc.).

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

The measures are automatically generated from the model fields; only the
aggregatable fields are used. Those measures are also alphabetically
sorted on the string of the field.

> **Warnung**
>
> like the graph view, the pivot aggregates data on database content
> which means that non-stored function fields can not be used in pivot views

In Pivot view a `field` can have a `widget` attribute to dictate its format.
The widget should be a field formatter, of which the most interesting are
`date`, `datetime`, `float_time`, and `monetary`.

For instance a timesheet pivot view could be defined as:

```
<pivot string="Timesheet">
    <field name="employee_id" type="row"/>
    <field name="date" interval="month" type="col"/>
    <field name="unit_amount" type="measure" widget="float_time"/>
</pivot>
```

## Calendar

Calendar views display records as events in a daily, weekly, monthly or yearly
calendar.

> **Bemerkung**
>
> By default the calendar view will be centered around the current date
> (today). You can pass a specific initial date to the context of the action in
> order to set the initial focus of the calendar on the period (see `mode`) around
> this date (the context key to use being `initial_date`)

Their root element is `<calendar>`. Available attributes on the root node are:

**`date_start`**

Name of the record’s field holding the start date for the event.

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`date_stop`**

Name of the record’s field holding the end date for the event.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`date_delay`**

Alternative to `date_stop`. Provides the duration of the event instead of
its end date (unit: hour).

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`scales`**

Comma-separated list of available scales, among `day`, `week`, `month`,
`year`. By default, all scales are available.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`"day,week,month,year"`

**`mode`**

Default scale of the calendar.

**`Requirement`**

Optional

**`Type`**

`"day"`, `"week"`, `"month"` or `"year"`

**`Default`**

`"week"`

**`color`**

Name of the record’s field to use for *color segmentation*. Records in the
same color segment are allocated the same highlight color in the calendar.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`all_day`**

Name of the record’s boolean field indicating whether the corresponding
event is flagged as day-long, in which case duration is irrelevant.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`aggregate`**

Name of the record’s field to use to display aggregated values next to
filters, in the filter side panel. The aggregator can be explicitly given
(e.g. `aggregate="expected_revenue:sum"`). If not given, the aggregator of
the field is used. Supported aggregators are `sum`, `avg`, `min`, `max`,
`count` and `count_distinct`.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`event_limit`**

Limits the number of events displayed in calendar cells, in `month` scale, and
for all-day events in `week` and `day` scales. If there are more events than
the limit, a „more“ button is added to show the rest of the events in a popover.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`Default`**

5

**`show_unusual_days`**

If set to true weekend days and public holidays have a greyed out background.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

**`hide_date`**

Set it to true to hide the date part in the record’s popover.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

**`hide_time`**

Set it to true to hide the time part in the record’s popover.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

False

**`month_overflow`**

By default, in month mode, the last days of the previous month and the first
days of the next months are displayed, as well as their events. This option
allows to disable this such that those sibling days are greyed out and their
events aren’t displayed.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`show_date_picker`**

By default, a mini calendar (in month mode) is displayed in the side panel,
next to the main calendar. This option allows to remove it by setting it to
`False`.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`event_open_popup`**

If true, open events in dialog to edit them, otherwise, open them in a
classical form view.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

**`form_view_id`**

View to open when the user creates or edits an event. By default, uses the
form view of the current action, if any.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`quick_create`**

Enables quick event creation on click: only asks the user for a `name` and
tries to create a new event with just that and the clicked event time. Falls
back to a full form view if the quick creation fails.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`create_name_field`**

Name of the record’s field holding the display name of the record. This field
is used when creating records through the ‚quick create‘ mechanism.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`name`

**`quick_create_view_id`**

Id of the form view to open when the attribute `quick_create` is set and the
user creates an event, instead of the default dialog which only allows to
specify a name.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`multi_create_view`**

Reference of a form view. When set, in **month** scale, allows to create (and
delete) records in batches by clicking on calendar cells or by selecting an
area of calendar cells. One record is then created for each selected cell and
for each active filter’s value, with the values of the multi create form view,
which is displayed in the side panel. In delete mode, all records displayed
in selected cells are deleted.

Note: if the side panel contains multiple filter sections, only the first one
is used, to avoid a combinatorial explosion.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`create`**

Disable/enable record creation on the view.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`edit`**

Disable/enable record edition on the view.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`delete`**

Disable/enable record deletion on the view.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`string`**

The view title. It is displayed only if you open an action that has no name and whose target is
`new` (opening a dialog).

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

### Components

Calendar views accept a single type of child elements: `<field>`. Those fields
are displayed in a popover, in the given order, which opens when a record
(a calendar event) is clicked.

> **Bemerkung**
>
> Fields in the popover are readonly. If the `edit` action is available,
> an `Edit` button is displayed in the popover, to open a form view where fields
> can be edited.

Field nodes can have the following attributes:

**`name`**

The name of the field to render.

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`widget`**

The widget used to represent the field. The selected widget can change the way the field is
rendered and/or the way it can be edited. It refers to a Javascript implementation (an Owl
component) registered to the `fields` registry.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`invisible`**

Python expression indicating whether the field should be displayed or not.
Other fields of the model can be used in the expression, as long as those
fields are also declared here.

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`False`

**`options`**

Python expression encoding an object of options for the field. In particular,
the option `icon`, allowing to specify, as classnames, which icon to display
in front of the field in the popover (for instance, `fa fa-users`). If no
icon is given, the option `string` can be set, and its value is then used as
label, displayed in front of the field.

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`{}`

Specifying a `<field>` in a calendar arch also allows to customize the filter
side panel, by setting the `filters` attribute. Extra attributes are then
available for that matter:

**`filters`**

If set to true, the field can be used as filter, from the side panel of the
calendar.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

**`avatar_field`**

Only for relational fields. Specify the name of the field on the co-model to
use to display as avatar in front of field values in the side panel filters.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`color`**

Specify which field to use to colorize the checkbox in the side panel filters.
By default, the color attribute of the calendar view is used to match events
with values in the filters.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`write_model`**

Allows to create new filter values on the fly. The given model is then used
as model for those filters. To combine with `write_field`.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`write_field`**

Combined with `write_model`, specifies the field name, in the given model,
to use to encode the filter value.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`filter_field`**

Combined with `write_model`, specifies the field name, in the given model,
to use to encode the status of the filter (whether it is checked or not).

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)
