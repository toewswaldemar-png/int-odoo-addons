<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_architectures.html · abgerufen 2026-10-02 -->

# View architectures – Teil 8/10: Activity / Cohort

## Activity

The Activity view is used to display the activities linked to the records. The
data are displayed in a chart with the records forming the rows and the activity
types the columns. The first cell of each row displays a (customizable, see
`templates`, quite similarly to Kanban) card representing
the corresponding record. When clicking on others cells, a detailed description
of all activities of the same type for the record is displayed.

> **Warnung**
>
> The Activity view is only available when the `mail` module is installed,
> and for the models that inherit from the `mail.activity.mixin`.

The root element of the Activity view is `<activity>`, it accepts the following
attributes:

**`string (mandatory)`**

A title, which should describe the view

Possible children of the view element are:

**`field`**

declares fields to use in activity *logic*. If the field is simply displayed
in the activity view, it does not need to be pre-declared.

Possible attributes are:

**`name (required)`**

the name of the field to fetch

**`templates`**

defines the [QWeb Templates](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/qweb.html#reference-qweb) templates. Cards definition may be
split into multiple templates for clarity, but activity views *must* define at
least one root template `activity-box`, which will be rendered once for each
record.

The activity view uses mostly-standard [javascript qweb](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/qweb.html#reference-qweb-javascript) and provides the following context variables
(see Kanban for more details):

**`widget`**

the current `ActivityRecord()`, can be used to fetch some
meta-information. These methods are also available directly in the
template context and don’t need to be accessed via `widget`

**`record`**

an object with all the requested fields as its attributes. Each field has
two attributes `value` and `raw_value`

## Cohort

Enterprise feature

The cohort view is used to display and understand the way some data changes over
a period of time. For example, imagine that for a given business, clients can
subscribe to some service. The cohort view can then display the total number
of subscriptions each month, and study the rate at which client leave the service
(churn). When clicking on a cell, the cohort view will redirect you to a new action
in which you will only see the records contained in the cell’s time interval;
this action contains a list view and a form view.

> **Bemerkung**
>
> By default the cohort view will use the same list and form views as those
> defined on the action. You can pass a list view and a form view
> to the context of the action in order to set/override the views that will be
> used (the context keys to use being `form_view_id` and `list_view_id`)

For example, here is a very simple cohort view:

```xml
<cohort string="Subscription" date_start="date_start" date_stop="date" interval="month"/>
```

The root element of the Cohort view is <cohort>, it accepts the following
attributes:

**`string (mandatory)`**

A title, which should describe the view

**`date_start (mandatory)`**

A valid date or datetime field. This field is understood by the view as the
beginning date of a record

**`date_stop (mandatory)`**

A valid date or datetime field. This field is understood by the view as the
end date of a record. This is the field that will determine the churn.

**`disable_linking (optional)`**

Set to `1` to prevent from redirecting clicks on cohort cells to list view.

**`mode (optional)`**

A string to describe the mode. It should be either ‚churn‘ or
‚retention‘ (default). Churn mode will start at 0% and accumulate over time
whereas retention will start at 100% and decrease over time.

**`timeline (optional)`**

A string to describe the timeline. It should be either ‚backward‘ or ‚forward‘ (default).
Forward timeline will display data from date_start to date_stop, whereas backward timeline
will display data from date_stop to date_start (when the date_start is in future / greater
than date_stop).

**`interval (optional)`**

A string to describe a time interval. It should be ‚day‘, ‚week‘, ‚month‘‘
(default) or ‚year‘.

**`measure (optional)`**

A field that can be aggregated. This field will be used to compute the values
for each cell. If not set, the cohort view will count the number of occurrences.

**`<field> (optional)`**

allows to specify a particular field in order to manage it from the available measures, it’s
main use is for hiding a field from the selectable measures:

**`name (mandatory)`**

the name of the field to use in the view.

**`string (optional)`**

the name that would be used to display the field in the cohort view, overrides the
default python String attribute of the field.

**`invisible (optional)`**

if true, the field will not appear either in the active measures nor in the selectable
measures (useful for fields that do not make sense aggregated, such as fields in different
units, e.g. € and $).
If the value is a domain, the domain is evaluated in the context of the current row’s
record, if `True` the corresponding attribute is set on the cell.

**`widget (optional)`**

alternate representations for a field’s display.

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
