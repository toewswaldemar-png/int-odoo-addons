<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_architectures.html · abgerufen 2026-10-02 -->

# View architectures – Teil 10/10: Gantt / Map

## Gantt

Enterprise feature

Gantt views appropriately display Gantt charts (for scheduling).

The root element of gantt views is `<gantt/>`, it has no children but can
take the following attributes:

**`string`**

string (default: `''`)

This view title is displayed only if you open an action that has no name and
whose target is ‚new‘ (opening a dialog)

**`create`**

bool (default: `True`)

Disable/enable record creation on the view.

**`edit`**

bool (default: `True`)

Disable/enable record edition on the view.

**`delete`**

bool (default: `True`)

Disable/enable record deletion on the view through the **Action** dropdown.

**`date_start (required)`**

name of the field providing the start datetime of the event for each
record.

**`date_stop (required)`**

name of the field providing the end duration of the event for each
record.

**`dependency_field`**

name of the `many2many` field that provides the dependency relation between two records.
If B depends on A, `dependency_field` is the field that allows getting A
from B. Both this field and `dependency_inverted_field` field are used to
draw dependency arrows between pills and reschedule them.

**`dependency_inverted_field (required if dependency_field is provided)`**

name of the `many2many` field that provides the invert dependency relation than
`dependency_field`. If B depends on A, `dependency_inverted_field` is
the field that allows getting B from A.

**`color`**

name of the field used to color the pills according to its value

**`decoration-{$name}`**

[python expression](https://docs.python.org/3/library/stdtypes.html#boolean-operations-and-or-not) that evaluates to a bool

allow changing the style of a cell’s text based on the corresponding
record’s attributes.

`{$name}` can be one of the following [bootstrap contextual color](https://getbootstrap.com/docs/3.3/components/#available-variations) (`danger`,
`info`, `secondary`, `success` or `warning`).

Define a conditional display of a record in the style of a row’s text based on the corresponding
record’s attributes.

Values are Python expressions. For each record, the expression is evaluated
with the record’s attributes as context values and if `true`, the
corresponding style is applied to the row. Here are some of the other values
available in the context:

- `uid`: the id of the current user,
- `today`: the current local date as a string of the form `YYYY-MM-DD`,
- `now`: same as `today` with the addition of the current time.
  This value is formatted as `YYYY-MM-DD hh:mm:ss`.

```xml
<gantt decoration-info="state == 'draft'"
      decoration-danger="state == 'help_needed'"
      decoration-bf="state == 'busy'">
  ...
</gantt>
```

**`default_group_by`**

name of a field to group tasks by

**`disable_drag_drop`**

if set to true, the gantt view will not have any drag&drop support

**`consolidation`**

field name to display consolidation value in record cell

**`consolidation_max`**

dictionary with the „group by“ field as key and the maximum consolidation
value that can be reached before displaying the cell in red
(e.g. `{"user_id": 100}`)

**`consolidation_exclude`**

name of the field that describes if the task has to be excluded
from the consolidation
if set to true it displays a striped zone in the consolidation line

**`create, cell_create, edit, delete, plan`**

allows *dis*abling the corresponding action in the view by setting the
corresponding attribute to `false` (default: `true`).

- `create`: If enabled, an `Add` button will be available in the control
  panel to create records.
- `cell_create`: If enabled and `create` enabled, a „**+**“ button will be
  displayed while hovering on a time slot cell to create a new record on that slot.
- `edit`: If enabled, the opened records will be in edit mode (thus editable).
- `plan`: If enabled and `edit` enabled, a „magnifying glass“ button will be displayed
  on time slots to plan unassigned records into that time slot.

> **Example**
>
> When you do not want to create records on the gantt view and the beginning and end
> dates are required on the model, the planning feature should be disabled
> because no record will ever be found.

**`offset`**

Depending on the scale, the number of units to add to today to compute the
default period. Examples: An offset of +1 in default_scale week will open the
gantt view for next week, and an offset of -2 in default_scale month will open
the gantt view of 2 months ago.

**`progress`**

name of a field providing the completion percentage for the record’s event,
between 0 and 100

**`string`**

title of the gantt view

**`precision`**

JSON object specifying snapping precisions for the pills in each scale.

Possible values for scale `day` are (default: `hour`):

- `hour`: records times snap to full hours (ex: 7:12 becomes 8:00)
- `hour:half`: records times snap to half hours (ex: 7:12 becomes 7:30)
- `hour:quarter`: records times snap to half hours (ex: 7:12 becomes 7:15)

Possible values for scale `week` are (default: `day:half`):

- `day`: records times snap to full days (ex: 7:28 AM becomes 11:59:59 PM of the previous day, 10:32 PM becomes 12:00 PM of the current day)
- `day:half`: records times snap to half hours (ex: 7:28 AM becomes 12:00 PM)

Possible values for scale `month` are (default: `day:half`):

- `day`: records times snap to full days (ex: 7:28 AM becomes 11:59:59 PM of the previous day, 10:32 PM becomes 12:00 PM of the current day)
- `day:half`: records times snap to half hours (ex: 7:28 AM becomes 12:00 PM)

Scale `year` always snap to full day.

Example of precision attribute: `{"day": "hour:quarter", "week": "day:half", "month": "day"}`

**`total_row`**

boolean to control whether the row containing the total count of records should
be displayed. (default: `false`)

**`collapse_first_level`**

boolean to control whether it is possible to collapse each row if grouped by
one field. (default: `false`, the collapse starts when grouping by two fields)

**`display_unavailability`**

boolean to mark the dates returned by the `gantt_unavailability` function of
the model as available inside the gantt view. Records can still be scheduled
in them, but their unavailability is visually displayed. (default: `false`)

**`default_scale`**

default scale when rendering the view. Possible values are (default: `month`):

- `day`
- `week`
- `month`
- `year`

**`scales`**

comma-separated list of allowed scales for this view. By default, all scales
are allowed. For possible scale values to use in this list, see `default_scale`.

**`templates`**

defines the [QWeb Templates](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/qweb.html#reference-qweb) template `gantt-popover` which is used
when the user hovers over one of the records in the gantt view.

The gantt view uses mostly-standard [javascript qweb](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/qweb.html#reference-qweb-javascript) and provides the following context variables:

**`widget`**

the current `GanttRow()`, can be used to fetch some
meta-information. The `getColor` method to convert in a color integer is
also available directly in the template context without using `widget`.

**`on_create`**

If specified when clicking the add button on the view, instead of opening a generic dialog, launch a client action.
this should hold the xmlid of the action (eg: `on_create="%(my_module.my_wizard)d"`

**`form_view_id`**

view to open when the user create or edit a record. Note that if this attribute
is not set, the gantt view will fall back to the id of the form view in the
current action, if any.

**`dynamic_range`**

if set to true, the gantt view will start at the first record,
instead of starting at the beginning of the year/month/day.

**`pill_label`**

If set to true, the time appears in the pill label when the scale is set on week or month. (e.g.
`7:00 AM - 11:00 AM (4h) - DST Task 1`)

**`thumbnails`**

This allows to display a thumbnail next to groups name if the group is a relationnal field.
This expects a python dict which keys are the name of the field on the active model.
Values are the names of the field holding the thumbnail on the related model.

Example: tasks have a field user_id that reference res.users. The res.users model has a field image that holds the avatar,
then:

```xml
<gantt
   date_start="date_start"
   date_stop="date_stop"
   thumbnails="{'user_id': 'image_128'}"
 >
 </gantt>
```

will display the users avatars next to their names when grouped by user_id.

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

## Map

Enterprise feature

This view is able to display records on a map and the routes between them. The records are represented by pins. It also allows the visualization of fields from the model in a popup tied to the record’s pin.

> **Bemerkung**
>
> The model on which the view is applied should contain a `res.partner` many2one since the view relies on the `res.partner`’s address and coordinates fields to localize the records.

### API

The view uses location data platforms‘ API to fetch the tiles (the map’s background), do the geoforwarding (converting addresses to a set of coordinates) and fetch the routes.
The view implements two API, OpenStreetMap and MapBox. OpenStreetMap is used by default and is able to fetch [tiles](https://wiki.openstreetmap.org/wiki/Tile_data_server) and do [geoforwarding](https://nominatim.org/release-docs/develop/). This API does not require a token.
As soon as a valid [MapBox](https://docs.mapbox.com/api/) token is provided in the general settings the view switches to the MapBox API. This API is faster and allows the computation of routes. A token can be obtained by [signing up](https://account.mapbox.com/auth/signup/) to MapBox.

### Structural components

The view’s root element is `<map>`. It can have the following attributes:

**`res_partner`**

Contains the `res.partner` many2one. If not provided the view resorts to create an empty map.

**`default_order`**

If a field is provided the view overrides the model’s default order. The field must be part of the model on which the view is applied, not from `res.partner`.

**`routing`**

if `1` display the routes between the records. The view needs a valid MapBox token and at least two located records (i.e the records have a `res.partner` many2one and the partner has an address or valid coordinates).

**`hide_name`**

if `1` hide the name from the pin’s popup (default: `0`).

**`hide_address`**

if `1` hide the address from the pin’s popup (default: `0`).

**`hide_title`**

if `1` hide the title from the pin list (default: `0`).

**`panel_title`**

String to display as title of the pin list. If not provided, the title is the action’s name or „Items“ if the view is not in an action.

**`limit`**

Maximum number of records to fetch (default: `80`). It must be a positive integer.

The `<map>` element can contain multiple `<field>` elements. Each `<field>` element is interpreted as a line in the pin’s popup. The field’s attributes are the following:

**`name`**

The field to display.

**`string`**

String to display before the field’s content. It can be used as a description.

**`For example here is a map:`**

```xml
<map res_partner="partner_id" default_order="date_begin" routing="1" hide_name="1">
    <field name="partner_id" string="Customer Name"/>
</map>
```
