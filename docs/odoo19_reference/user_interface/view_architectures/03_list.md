<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_architectures.html · abgerufen 2026-10-02 -->

# View architectures – Teil 3/10: List

## List

The root element of list views is `list` (the previous name was `tree`).

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/list.svg |
> | ```xml <list>     ... </list> ``` |

### Root attributes

Optional attributes can be added to the root element `list` to customize the view.

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

**`import`**

Disable/enable record import from data on the view.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`export_xlsx`**

Disable/enable record export to data on the view.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`True`

**`editable`**

Make the view’s records editable in-place, and allow creating new records from a row of the list.
It can have two different values:

**`top`**

New records are created from the top of the list.

**`bottom`**

New records are created from the bottom of the list.

The architecture for the inline form view is derived
from the list view. Most attributes valid on a form view’s fields and buttons are thus accepted
by list views, although they may not have any meaning if the list view is non-editable.

> **Wichtig**
>
> This behavior is disabled if the `edit` attribute is set to `False`.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`multi_edit`**

Activate the multi-editing feature that allows updating a field to the same value for multiple
records at once.

It accepts only the value `'1'`.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`open_form_view`**

Display a button at the end of each row to open the record in a form view.

It has no effect if the view is non-editable.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

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

**`decoration-<style>`**

The style that should be applied to matching records‘ rows, as a Python expression that evaluates
to a bool.

`<style>` must be replaced by one of `bf` (bold), `it` (italic), `info`, `warning`, `danger`,
`muted`, `primary`, and `success`.

> **Example**
>
> ```xml
> <list decoration-danger="field_qty &gt; field_limit">
>     ...
> </list>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`False`

**`limit`**

The default size of a page. It must be strictly positive.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`Default`**

`80` for list views, `40` for X2many lists in form views

**`groups_limit`**

The default number of groups on a page when the list view is grouped. It must be strictly
positive.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`Default`**

`80` for list views, `40` for X2many lists in form views

**`expand`**

Whether the first level of groups should be opened by default when the list view is grouped.

> **Warnung**
>
> It may be slow, depending on the number of groups.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

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

List views accept the following children elements: field, button, groupby, header, control, and create.

Placeholders are denoted in all caps.

#### `field`: display field values

The `field` element renders (and allows editing of, possibly) a single field of all current records
as a column.

Using the same field multiple times in a list view is not supported

```xml
<list>
    <field name="FIELD_NAME"/>
</list>
```

The `field` element can have the following attributes:

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

**`string`**

The label of the field.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

The `string` attribute of the model’s field

**`optional`**

Make the visibility of the field optional. The field’s column can be hidden or shown through a
button on the view’s header.

It can have two different values:

**`show`**

The field is shown by default.

**`hide`**

The field is hidden by default.

> **Example**
>
> ```xml
> <field name="fname_a" optional="show"/>
> <field name="fname_b" optional="hide"/>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`readonly`**

Whether the field can be modified by the user (`False`) or is read-only (`True`), as a Python
expression that evaluates to a bool.

> **Example**
>
> ```xml
> <field name="fname_a" readonly="True"/>
> <field name="fname_b" readonly="name_a in [fname_b, parent.fname_d]"/>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`False`

**`required`**

Whether the field can be left empty (`False`) or must be set (`True`), as a Python expression
that evaluates to a bool.

> **Example**
>
> ```xml
> <field name="fname_a" required="True"/>
> <field name="fname_b" required="fname_c != 3"/>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`False`

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

**`column_invisible`**

Whether the column is visible (`False`) or hidden (`True`), as a Python expression that evaluates
to a bool.

Unlike `invisible`, it affects the entire column, and is evaluated without the subtree values.

> **Example**
>
> ```xml
> <field name="product_is_late" column_invisible="parent.has_late_products == False"/>
> <button type="object" name="action_confirm" column_invisible="context.get('hide_confirm')"/>
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

**`decoration-<style>`**

The style that should be applied to matching records‘ field, as a Python expression that
evaluates to a bool.

`<style>` must be replaced by one of `bf` (bold), `it` (italic), `info`, `warning`, `danger`,
`muted`, `primary`, and `success`.

> **Example**
>
> ```xml
> <field name="name" decoration-bf="1"/>
> <field name="quantity" decoration-info="state == 'draft'"/>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`False`

**`sum, avg`**

The aggregate to display at the bottom of the column. The aggregation is computed on only
records that are currently displayed. The aggregation operation must match the corresponding
field’s `aggregator`.

> **Example**
>
> ```xml
> <field name="sent" sum="Total" />
> <field name="clicks_ratio" avg="Average"/>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`width`**

The list view always tries to optimize the available space among columns. For some field types,
this is done by enforcing a width, depending on the field type. For instance, we know exactly the
number of pixels required to display a date, so we can ensure that a column for a date field
doesn’t take more space than what is strictly necessary, thus leaving the extra space for the
other columns. However, the framework can’t guess the adequate width for every field types. For
instance, char fields can be used to encode large values, or 3-letter country codes. In the
latter case, one can set the width directly in the arch (e.g. `width="40px"`). It represents
the width (always in pixels) required to render the values inside the cells. The width of the
column will then be the sum of the given value and the cells‘ left and right paddings.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`nolabel`**

Whether the field’s column header should remain empty. If set, the column will not be sortable.

It accepts only the value `'1'`

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

> **Bemerkung**
>
> When a list view is grouped, numeric fields are aggregated and displayed for each group. Also, if
> there are too many records in a group, a pager appears on the right of the group row. For this
> reason, it is a bad practice to have a numeric field in the last column when the list view is in
> a situation where it can be grouped. However, it does not pose a problem for X2many fields in a
> form view, as they cannot be grouped.

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/list_field.svg |
> | ```xml <list>     <field name="name" string="My Custom Name"/>     <field name="amount" sum="Total"/>     <field name="currency_id"/>     <field name="tax_id"/> </list> ``` |

#### `button`: display action buttons

```xml
<list>
    <button type="object" name="ACTION" string="LABEL"/>
    <button type="object" name="ACTION" icon="FONT_AWESOME"/>
</list>
```

The `button` element can have the following attributes:

**`type`**

The type of the button indicating how it behaves. It can have two different values:

**`object`**

Call a method on the view’s model. The button’s `name` is the method that is called with the
current record ID and the current `context`.

**`action`**

Load and execute an `ir.actions` action record. The button’s `name` is the XMLID of the
action to load. The `context` is extended with the view’s model (as `active_model`) and with
the current record (as `active_id`).

> **Example**
>
> ```xml
> <button type="object" name="action_create_new" string="Create document"/>
> <button type="action" name="addon.action_create_view" string="Create and Edit"/>
> ```

**`Requirement`**

Mandatory if the `special` attribute is not set

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`name`**

The method to call if the `type` is `object`. The [XMLID](https://www.odoo.com/documentation/19.0/de/developer/glossary.html#term-external-identifier) of the
action to load if the `type` is `action`, either in raw format or in `%(XMLID)d` format.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`string`**

The button’s text if there is no `icon`, the `alt` text for the icon otherwise.

> **Example**
>
> ```xml
> <button type="object" name="action_create_new" string="Create document"/>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`icon`**

The icon to use to display the button. See [icons](https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/icons.html#reference-user-interface-ui-icons) for
the reference list.

> **Example**
>
> ```xml
> <button type="object" name="remove" icon="fa-trash"/>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`help`**

The tooltip message shown when hovering with the mouse cursor.

> **Example**
>
> ```xml
> <button type="object" name="remove" icon="fa-trash" help="Revoke"/>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`context`**

The context that is merged into the view’s context when performing the button’s call, as a Python
expression that evaluates to a dict.

> **Example**
>
> ```xml
> <button name="button_confirm" type="object" context="{'BUSINESS_KEY': ANY}" string="LABEL"/>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`{}`

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

**`column_invisible`**

Whether the column is visible (`False`) or hidden (`True`), as a Python expression that evaluates
to a bool.

Unlike `invisible`, it affects the entire column, and is evaluated without the subtree values.

> **Example**
>
> ```xml
> <field name="product_is_late" column_invisible="parent.has_late_products == False"/>
> <button type="object" name="action_confirm" column_invisible="context.get('hide_confirm')"/>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`False`

**`class`**

The [HTML class](https://en.wikipedia.org/wiki/HTML_attribute) to set on the generated element.

The styling uses the [Bootstrap](https://getbootstrap.com) framework and [UI icons](https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/icons.html#reference-user-interface-ui-icons). Common Odoo classes include:

- `oe_inline`: prevents the usual line break following fields, and limits their span;
- `oe_left`, `oe_right`: [floats](https://developer.mozilla.org/en-US/docs/Web/CSS/float) the
  element to the corresponding direction;
- `oe_read_only`, `oe_edit_only`: only displays the element in the corresponding form mode;
- `oe_avatar`: for image fields, displays images as an „avatar“ (max 90x90 square);
- `oe_stat_button`: defines a particular rendering to dynamically display information while being
  clickable to target an action.

> **Example**
>
> ```xml
> <field name="fname" class="oe_inline oe_left oe_avatar"/>
> ```

> **Example**
>
> ```xml
> <button type="object" name="ACTION" class="oe_stat_button" icon="FONT_AWESOME" help="HELP">
>    <div class="o_field_widget o_stat_info">
>       <span class="o_stat_value"><FIELD/></span>
>       <span class="o_stat_text">TEXT</span>
>    </div>
> </button>
> ```

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
> | ../../../_images/list_button.svg |
> | ```xml <list>     <field name="name"/>     <button type="edit" name="edit" icon="fa-edit" title="Edit"/>     <button type="object" name="my_method" string="Button1" column_invisible="context.get('hide_button')" invisible="amount &gt; 3"/>     <field name="amount"/>     <field name="currency_id"/>     <field name="tax_id"/> </list> ``` |

#### `groupby`: define group headers

The `groupby` element is used to define group headers with button elements when grouping records on
[`Many2one`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Many2one) fields. It also accepts field elements, which can be used for modifiers. These fields
thus belong on the Many2one co-model. These extra fields are fetched in batch.

```xml
<list>
    ...
    <groupby name="FIELD_NAME">
        <BUTTONS/>
        <FIELDS/>
    </groupby>
</list>
```

The `groupby` element can have the following attributes:

**`name`**

The name of the a [`Many2one`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Many2one) field to use as header.

A special button element with `type="edit"` can
be defined to open the Many2one field’s form view.

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/list_groupby.svg |
> | ```xml <list>     <field name="name"/>     <field name="amount"/>     <field name="currency"/>     <field name="tax_id"/>      <groupby name="partner_id">         <button type="edit" name="edit" icon="fa-edit" title="Edit"/>         <field name="email"/>         <button type="object" name="my_method" string="Button1" invisible="email == 'jhon@conor.com'"/>     </groupby> </list> ``` |

> **Bemerkung**
>
> Fields inside the `groupby` element are used only to fetch and store the value, but they are
> never displayed.

#### `header`: display workflow buttons

```xml
<list>
    <header>
        <BUTTONS/>
    </header>
    ...
</list>
```

The `header` element accepts the following children elements:

**`button`**

The `button` element allows defining buttons in the control panel. It is the same element as the
button element in list views, but it accepts
one more attribute when placed inside a `header` element:

**`display`**

Make the button available at all time, without having to select records.

It accepts only the value `always`.

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

`''`

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/list_header.svg |
> | ```xml <list>     <header>         <button type="object" name="to_draft" string="Button1" invisible="context.get('hide_button')"/>     </header>     <field name="name"/>     <field name="amount"/>     <field name="currency"/>     <field name="tax_id"/> </list> ``` |

#### `control`: customize create and delete actions

The `control` element allows to customize the create and delete actions. In particular, it allows
to add special create buttons with specific contexts, to use regular view buttons as create
actions, and to make the create and delete actions available only under certain conditions.

> **Wichtig**
>
> The `control` element is only supported in list views inside [`One2many`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.One2many) or
> [`Many2many`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Many2many) fields.

```xml
<list>
   <control>
       <create string="LABEL"/>
       <BUTTONS/>
       <delete invisible="parent.is_sent">
    </control>
    ...
</list>
```

The `control` element takes no attributes. It accepts the following children elements:

**`create`**

The given `create` elements replace the default Add a line button.
A `create` element can have the following attributes:

**`string`**

The button’s text.

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`context`**

The context that is merged into the view’s context when performing the button’s call, as a Python
expression that evaluates to a dict.

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`{}`

**`invisible`**

Whether the element is visible (`False`) or hidden (`True`), as a Python expression that evaluates to a
bool. The parent record and the context can be used in the expresion.

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`False`

**`button`**

Like regular view buttons

**`delete`**

The `delete` element allows to conditionnaly hide the delete icon, row by row. There can only be
one child of this type. It can have only one attribute:

**`invisible`**

Same as for `create`, except that in this case the record itself can also be used in the
expresion.

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/list_control.svg |
> | ```xml <list>     <field name="name"/>     <field name="amount"/>     <field name="currency"/>     <field name="tax_id"/>     <control>         <create string="Add an item"/>         <create string="Add a section" context="{'default_type': 'section'}"/>         <create string="Add a note" context="{'default_type': 'note'}"/>     </control> </list> ``` |
