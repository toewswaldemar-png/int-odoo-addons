<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_architectures.html · abgerufen 2026-10-02 -->

# View architectures – Teil 5/10: Kanban

## Kanban

Kanban views are used as a [kanban board](https://en.wikipedia.org/wiki/Kanban_board)
visualisation: they display records as „cards“, halfway between a list and a form view.

Records may be grouped in columns for use in workflow visualisation or manipulation (e.g., tasks or
work-progress management), or ungrouped (used simply to visualize records).

The root element of Kanban views is `kanban`.

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/kanban.svg |
> | ```xml <kanban>     ... </kanban> ``` |

> **Bemerkung**
>
> Kanban views load and display a maximum of ten columns. Any column after that is closed but can
> still be opened by the user.

### Root attributes

Optional attributes can be added to the root element `kanban` to customize the view.

**`string`**

The view title. It is displayed only if you open an action that has no name and whose target is
`new` (opening a dialog).

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

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

Disable/enable record deletion on the view through the Action dropdown.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`default_group_by`**

The name of the field on which the records should be grouped by default if no grouping is
specified via the action or the current search.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`default_order`**

A comma-separated list of fields names that overrides the ordering defined on the model through
the [`_order`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.models.BaseModel._order) attribute.

To inverse the sorting order of a field, postfix it with `desc`, separated by a space.

> **Example**
>
> ```xml
> <list default_order="sequence,name desc">
>     ...
> </list>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`class`**

Add HTML classes to the root HTML element of the view.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`examples`**

The key in the `KanbanExamplesRegistry` of the examples that can be browsed when creating a new
column in the grouped kanban view.

> **Siehe auch**
>
> [Use of the examples attribute in the utm module](https://github.com/odoo/odoo/blob/19.0/addons/utm/static/src/js/utm_campaign_kanban_examples.js)

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`group_create`**

Whether the Add a new column bar is visible.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`group_delete`**

Whether columns can be deleted via the cog menu.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`group_edit`**

Whether columns can be edited via the cog menu.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`groups_draggable`**

Whether columns can be reordered.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`records_draggable`**

Whether records can be dragged when the kanban view is grouped.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`archivable`**

Whether records belonging to a column can be archived and unarchived when the `active` field is
defined on the model.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`quick_create`**

Whether it should be possible to create records without switching to the form view.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True` when the kanban view is grouped by many2one, selection, char, or boolean fields,
otherwise `False`

**`quick_create_view`**

The reference of the form view to open when using the
quick creation of records.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`on_create`**

The custom action to call when clicking on Create.

If set to `'quick_create'`, the quick creation of records is used instead. If the quick creation
is disabled, the standard create action is called.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`can_open`**

By default, clicking on a kanban card opens the corresponding record in a form view.
This behavior can be disabled by setting the attribute `can_open` to `False`.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`highlight_color`**

Name of the integer field used to color the left border of the kanban cards.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

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

### Components

Kanban views accept the following children elements: templates, field, header, progressbar.

#### `templates`: define cards structure

The `templates` element is used to define the [QWeb templates](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/qweb.html#reference-qweb) that structure
the kanban cards.

The definition of a card’s structure can be split into multiple templates for clarity, but at least
one root `card` template must be defined.

An additional template can be defined: `menu`. If defined, it is rendered inside a dropdown
that can be toggled with a vertical ellipsis (⋮) on the top right of the card.

The templates are written in [JavaScript QWeb](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/qweb.html#reference-qweb-javascript).

```xml
<kanban>
   <templates>
      <t t-name="card">
         <field name="name"/>
      </t>
   </templates>
</kanban>
```

> **Warnung**
>
> These are QWeb templates, not [Owl](https://github.com/odoo/owl) templates, meaning that
> directives like `t-on-click` aren’t available.

##### Fields

Inside those templates, the `field` element allows to render a field. It can have the following
attributes:

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

By default, field nodes are replaced by a `span` containing their formatted value, unless the
`widget` attribute is specified, in which case their rendering and behavior depends on the
corresponding widget. The `widget` attribute can have different values including:

> **`handle`**
>
> Allows reordering records with a drag and drop, using the corresponding field as order.
>
> **`kanban_color_picker`**
>
> Allows editing a color (integer) field. Combined with the root attribute `highlight_color`,
> allows editing the color of the cards.

See the [Field section](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/javascript_reference.html#reference-js-widgets) to discover
various widgets and their options.

##### Rendering Context

Kanban templates being rendered with the [QWeb engine](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/qweb.html#reference-qweb-javascript), they have
a *rendering context*, a set of variables available in the templates, containing useful information
and tools. Here’re the available variables:

**`record`**

An object with all the fields defined in the view. Each field has two attributes: `value`
and `raw_value`. The former is formatted according to current user parameters, while the latter
is the raw value (e.g. the `id` for a many2one field). This object is useful for instance, for
using field values inside `t-if` conditions. For display purposes, we recommend using the
`<field>` tag.

> **Example**
>
> ```xml
> <kanban>
>    <templates>
>       <field name="is_company"/>
>       <t t-name="card">
>          <field name="name"/>
>          <field t-if="!record.is_company.raw_value" name="parent_id">
>       </t>
>    </templates>
> </kanban>
> ```

**`widget`**

An object with 2 keys defining the available actions for the user:

- `editable`: true if the user can edit records, false otherwise;
- `deletable`: true if the user can delete records, false otherwise.

This is useful to conditionally display elements requiring specific access rights.

> **Example**
>
> ```xml
> <kanban>
>    <templates>
>       <t t-name="card">
>          <field name="name"/>
>       </t>
>       <t t-name="menu">
>          <a t-if="widget.deletable" role="menuitem" type="delete" class="dropdown-item">Delete</a>
>       </t>
>    </templates>
> </kanban>
> ```

**`context`**

The current context propagated from either the action that opens the kanban view, or the one2many
or many2many field that embeds the kanban view in a form view.

**`read_only_mode`**

Indicates that the view is readonly.

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`selection_mode`**

Whether the kanban view is opened when selecting a many2one or many2many field (in mobile
environment).

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`luxon`**

The [luxon](https://moment.github.io/luxon/api-docs/index.html) object, allowing to
manipulate date and datetime field values.

**`JSON`**

The Javascript [JSON](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/JSON)
namespace object containing a `parse` method allowing to parse json field values into Javascript
Objects.

##### Buttons and links

While most of the kanban templates are standard [QWeb templates](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/qweb.html#reference-qweb), the kanban
view processes `button` and `a` elements is a special way. Buttons and links with a `type` attribute
perform different operations than their standard HTML function. The `type` attribute can have the
values `action` and `object` of regular buttons,
or the following values:

> **`open`**
>
> Clicking the element opens the card’s record in form view.
>
> **`delete`**
>
> Clicking the element deletes the card’s record and removes the card.
>
> **`archive`**
>
> Clicking the element archives the card’s record and removes the card.
>
> **`unarchive`**
>
> Clicking the element unarchives the card’s record and removes the card.
>
> **`set_cover`**
>
> Clicking the element allows to select an image to set as cover image of the record.

##### Widgets

The `widget` element allows to insert dynamically generated (in Javascript) html inside the cards. It
has a mandatory `name` attribute, referring to a Javascript implementation (an Owl component)
registered to the `view_widgets` registry.

See the [Widget section](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/javascript_reference.html#reference-javascript-reference-view-widgets) to discover various
widgets and their options.

##### Layouts

Several card layouts can be easily obtained using standard html elements and [Bootstrap utility
classes](https://getbootstrap.com/docs/5.0/utilities/api/). By default, the card is a [flexbox
container](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_flexible_box_layout/Basic_concepts_of_flexbox)
with `column` direction.

> **Example**
>
> ```xml
> <kanban>
>    <templates>
>       <t t-name="card">
>          <field class="fw-bold fs-5" name="display_name"/>
>          <field class="text-muted" name="parent_id"/>
>          <field name="tag_ids" widget="many2many_tags"/>
>       </t>
>    </templates>
> </kanban>
> ```

The `footer` html element is styled to stick to the bottom of the card, and is as a flexbox
container with `row` direction, allowing to easily display several fields on the same line.

> **Example**
>
> ```xml
> <kanban>
>    <templates>
>       <t t-name="card">
>          <field class="fw-bold fs-5" name="display_name"/>
>          <field class="text-muted" name="parent_id"/>
>          <field name="tag_ids" widget="many2many_tags"/>
>          <footer>
>             <field name="priority" widget="priority"/> <!-- bottom left corner -->
>             <field class="ms-auto" name="activity_ids" widget="kanban_activity"/> <!-- bottom right corner -->
>          </footer>
>       </t>
>    </templates>
> </kanban>
> ```

To display some content, like an image, on the side of the card, one can use `aside` and `main` html
elements, with the `flex-row` classname on the card. The `main` node is a flexbox container like the
card is when there’s no `aside`.

> **Example**
>
> ```xml
> <kanban>
>    <templates>
>       <t t-name="card" class="flex-row">
>          <aside>
>             <field name="avatar_128" widget="image" alt="Avatar"/>
>          </aside>
>          <main class="ms-2">
>             <field class="fw-bold fs-5" name="display_name"/>
>             <field class="text-muted" name="parent_id"/>
>             <field name="tag_ids" widget="many2many_tags"/>
>             <footer>
>                <field name="priority" widget="priority"/>
>                <field class="ms-auto" name="activity_ids" widget="kanban_activity"/>
>             </footer>
>          </main>
>       </t>
>    </templates>
> </kanban>
> ```

> **Tipp**
>
> The classname `o_kanban_aside_full` set on the `aside` element removes the padding so that the
> image spreads to the borders of the card.

#### `field`: declare more fields to fetch

The `field` element can also be used *outside* the kanban templates. In that case, it allows to declare fields that are
not displayed in the card, but still need to be fetched, for instance because their value is used
in a `t-if` condition.

> **Example**
>
> ```xml
> <kanban>
>    <templates>
>       <field name="is_company"/>
>       <t t-name="card">
>          <field name="name"/>
>          <field t-if="!record.is_company.raw_value" name="parent_id">
>       </t>
>    </templates>
> </kanban>
> ```

#### `header`: display buttons in the control panel

The `header` element is used to insert custom buttons in the control panel.

```xml
<kanban>
   <header>
      ...
   </header>
   ...
</kanban>
```

The `header` element accepts only `button` children elements, similar to list views‘ button elements.

The `button` element used as a child element of the `header` element can have the following
additional attributes:

**`display`**

The display mode of the button. It can have two different values:

**`display`**

The button is displayed only when some records are selected; their action applies to the
selected records.

**`always`**

The button is displayed at all times, even if no records are selected.

> **Wichtig**
>
> Only the `always` display mode is available because it is not yet possible to select records
> in a kanban view.

> **Example**
>
> ```xml
> <header>
>     <button name="toDoAlways" type="object" string="Always displayed" display="always"/>
>     <button name="toDoSelection" type="object" string="Displayed if selection"/>
> </header>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`display`

#### `progressbar`: show progress bars on top of columns

The `progressbar` element is used to define a progress bar to display on top of kanban columns in
grouped kanban views.

```xml
<kanban>
    <progressbar field="FIELD_NAME"/>
    ...
</kanban>
```

The `progressbar` element can have the following attributes:

**`field`**

The name of the field on which the progress bar’s sub-groups
are based.

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`colors`**

The mapping of the progress bar’s field values to the color values `muted`, `success`, `warning`,
and `danger`.

**`Requirement`**

Mandatory

**`Type`**

[JSON](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/JSON)

**`sum_field`**

The name of the field to use in a sum displayed next to the progress bar. If not set, the total
number of records is displayed instead.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/kanban_progressbar.svg |
> | ```xml <kanban>     <progressbar field="activity_state"                  colors="{'planned': 'success', 'today': 'warning', 'overdue': 'danger'}"                  sum_field="expected_revenue"/>     <templates>         ...     </templates> </kanban> ``` |

#### `control`: customize create and delete actions

Like for list views.
