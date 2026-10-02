<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_architectures.html · abgerufen 2026-10-02 -->

# View architectures – Teil 6/10: QWeb / Graph

## QWeb

QWeb views are standard [QWeb Templates](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/qweb.html#reference-qweb) templates inside a view’s
`arch`. They don’t have a specific root element. Because QWeb views don’t
have a specific root element, their type must be specified explicitly (it can
not be inferred from the root element of the `arch` field).

QWeb views have two use cases:

- they can be used as frontend templates, in which case
  [template](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/data.html#reference-data-template) should be used as a shortcut.
- they can be used as actual qweb views (opened inside an action), in which
  case they should be defined as regular view with an explicit `type` (it
  can not be inferred) and a model.

The main additions of qweb-as-view to the basic qweb-as-template are:

- qweb-as-view has a special case for a `<nav>` element bearing the CSS
  class `o_qweb_cp_buttons`: its contents should be buttons and will be
  extracted and moved to the control panel’s button area, the `<nav>` itself
  will be removed, this is a work-around to control panel views not existing
  yet
- qweb-as-view rendering adds several items to the standard qweb rendering
  context:

  **`model`**

  the model to which the qweb view is bound

  **`domain`**

  the domain provided by the search view

  **`context`**

  the context provided by the search view

  **`records`**

  a lazy proxy to `model.search(domain)`, this can be used if you just
  want to iterate the records and not perform more complex operations
  (e.g. grouping)
- qweb-as-view also provides additional rendering hooks:

  - `_qweb_prepare_context(view_id, domain)` prepares the rendering context
    specific to qweb-as-view
  - `qweb_render_view(view_id, domain)` is the method called by the client
    and will call the context-preparation methods and ultimately
    `env['ir.qweb'].render()`.

## Graph

The graph view is used to visualize aggregations over a number of records or
record groups. Its root element is `<graph>` which can take the following
attributes:

**`type (optional)`**

one of `bar` (default), `pie` and `line`, the type of graph to use

**`stacked (optional)`**

only used for `bar` charts. Set to `0` to prevent the bars within a group
to be stacked initially.

**`disable_linking (optional)`**

set to `1` to prevent from redirecting clicks on graph to list view

**`order (optional)`**

if set, x-axis values will be sorted by default according their measure with
respect to the given order (`asc` or `desc`). Only used for `bar` and
`pie` charts.

**`string (optional)`**

string displayed in the breadcrumbs when redirecting to list view.

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

The only allowed element within a graph view is `field` which can have the
following attributes:

**`name (mandatory)`**

the name of a field to use in the view. If used for grouping (rather
than aggregating)

**`invisible (optional)`**

if true, the field will not appear either in the active measures nor in the
selectable measures.

**`type (optional)`**

if set to `measure`, the field will be used as an aggregated value within a
group instead of a grouping criteria. It only works for the last field
with that attribute but it is useful for other fields with string attribute
(see below).

**`interval (optional)`**

on date and datetime fields, groups by the specified interval (`day`,
`week`, `month`, `quarter` or `year`) instead of grouping on the
specific datetime (fixed second resolution) or date (fixed day resolution).
Default is `month`.

**`string (optional)`**

only used for field with `type="measure"`. The name that will be used to
display the field in the graph view, overrides the default python String
attribute of the field.

The measures are automatically generated from the model fields; only the
aggregatable fields are used. Those measures are also alphabetically
sorted on the string of the field.

> **Warnung**
>
> graph view aggregations are performed on database content, non-stored
> function fields can not be used in graph views

In Graph views, a `field` can have a `widget` attribute to dictate its format.
The widget should be a field formatter, of which the most interesting are
`float_time`, and `monetary`.

```xml
<field name="working_hours_close" widget="float_time"/>
```
