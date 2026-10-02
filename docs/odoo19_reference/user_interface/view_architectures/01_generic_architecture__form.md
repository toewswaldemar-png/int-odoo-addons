<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_architectures.html · abgerufen 2026-10-02 -->

# View architectures – Teil 1/10: Generic architecture / Python expression / Form

## Generic architecture

The architecture of a view is defined by XML data interpreted by the JavaScript framework.

For most views, there is a `*.rng` file defining the attributes and possible architectures.
Some views are not ruled by such a file either because they accept HTML content, or for performance
reasons.

> **Bemerkung**
>
> The current context and user access rights may impact the view abilities.

> **Siehe auch**
>
> [View records](https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_records.html)

## Python expression

When evaluating node attributes, e.g. the `readonly` modifier, it is possible to provide a **Python
expression** that will be executed in an environment that has access to the following variables:

- The names of all fields present in the current view, containing the value of the current record,
  except for `column_invisible` in list view;
  relational fields are given as a list of IDs;
- The ID of the current record;
- `parent`: the record that refers to the container; only inside sub-views of [relational
  fields](https://www.odoo.com/documentation/19.0/de/applications/studio/fields.html#studio-fields-relational-fields);
- `context (dict)`: the current view’s context;
- `uid (int)`: the id of the current user;
- `today (str)`: the current local date in the `YYYY-MM-DD` format;
- `now (str)`: the current local datetime in the `YYYY-MM-DD hh:mm:ss` format.

> **Example**
>
> ```xml
> <field name="field_a" readonly="True"/>
> <field name="field_b" invisible="context.get('show_me') and field_a == 4"/>
> ```

> **Example**
>
> ```xml
> <field name="field_a"/>
> <field name="x2m">
>     <!-- sub-view -->
>     <form>
>         <field name="field_b" invisible="parent.field_a"/>
>     </form>
> </field>
> ```

## Form

Form views are used to display the data from a single record. They are composed of regular [HTML](https://en.wikipedia.org/wiki/HTML)
with additional semantic and structural components.

The root element of form views is `form`.

```xml
<form>
    ...
</form>
```

### Root attributes

Optional attributes can be added to the root element `form` to customize the view.

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

**`duplicate`**

Disable/enable record duplication on the view through the **Action** dropdown.

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

**`js_class`**

The name of the JavaScript component the webclient will instantiate instead of the form view.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`disable_autofocus`**

Disable automatic focusing on the first field in the view.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

### Semantic components

Semantic components tie into the Odoo system and allow interaction with it.

Form views accept the following children semantic components: field, label,
button,
Chatter widget, and
Attachments preview widget.

Placeholders are denoted in all caps.

#### `field`: display field values

The `field` element renders (and allows editing of, possibly) a single field of the current record.

Using the same field multiple times in a form view is supported, and the fields can receive
different values for the `invisible` and `readonly` attributes. These fields may have the same
values but can be displayed differently. However, the behavior is not guaranteed when several fields
exist with different values for the `required` attribute.

```xml
<form>
    <field name="FIELD_NAME"/>
</form>
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

**`id`**

The node id. Useful when there are several occurrences of the same field in the view (see
label: display field labels).

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

The field name

**`string`**

The label of the field.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

The `string` attribute of the model’s field

**`help`**

The tooltip displayed when hovering the field or its label.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`options`**

The configuration options for the field’s widget (including default widgets), as a Python
expression that evaluates to a dict.

For relation fields, the following options are available: `no_create`, `no_quick_create`,
`no_open`, and `no_create_edit`.

> **Example**
>
> ```xml
> <field name="tag_ids" widget="many2many_tags" options="{'color_field': 'FIELD_NAME', 'no_quick_create': True}"/>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`{}`

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

**`domain`**

The filters to apply when displaying existing records for selection, as a Python expression that
evaluates to a [domain](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#reference-orm-domains).

> **Example**
>
> ```xml
> <field name="fname" domain="[('fname_a', '=', parent.fname_b)]"/>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`[]`

**`Scope`**

Relational fields

**`context`**

The context to use when fetching possible values and creating or searching records, as a Python
expression that evaluates to a dict.

> **Example**
>
> ```xml
> <field name="fname" context="{
>     'TYPE_view_ref': 'ADDON.MODEL_view_TYPE',
>     'group_by': 'FIELD_NAME',
>     'default_FIELD_NAME': ANY,
>     'search_default_FIELD_NAME': True,
>     'OTHER_BUSINESS_KEY': ANY,
>   }"/>
> ```

**`Requirement`**

Optional

**`Type`**

Python expression

**`Default`**

`{}`

**`Scope`**

Relational fields

**`nolabel`**

Whether the field label should be hidden.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

**`Scope`**

Fields that are a direct child of a `group` element

**`placeholder`**

The help message to display on *empty* fields. It can replace field labels in complex forms.
However, it *should not* be an example of data, as users may confuse placeholder text with filled
fields.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`mode`**

The comma-separated list of display modes (view types) to use for the field’s linked records.
Allowed modes are: `list`, `form`, `kanban`, and `graph`.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`list`

**`Scope`**

[`One2many`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.One2many) and [`Many2many`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Many2many) fields

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

**`filename`**

The name of the related field providing the name of the file.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`Scope`**

[`Binary`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Binary) fields

**`password`**

Whether the field stores a password and thus its data should not be displayed.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

**`Scope`**

[`Char`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.fields.Char) fields

**`kanban_view_ref`**

The XMLID of the specific Kanban [view record](https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_records.html) that should be used when
selecting records in a mobile environment.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`Scope`**

Relational fields

**`default_focus`**

Whether the field is focused when the view opens. It can be applied to only one field of a view.

**`Requirement`**

Optional

**`Type`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`Default`**

`False`

> **Bemerkung**
>
> [Relational fields](https://www.odoo.com/documentation/19.0/de/applications/studio/fields.html#studio-fields-relational-fields) nodes can contain specific subviews.
>
> > **Example**
> >
> > ```xml
> > <field name="children_ids">
> >    <list>
> >       <field name="name"/>
> >    </list>
> >    <form>
> >       <field name="id"/>
> >       <field name="name"/>
> >    </form>
> > </field>
> > ```

#### `label`: display field labels

When a field component is not placed directly
inside a group, or when its `nolabel` attribute is
set, the field’s label is not automatically displayed alongside its value. The `label` component is
the manual alternative of displaying the label of a field.

```xml
<form>
    <div class="col col-md-auto">
        <label for="FIELD_NAME" string="LABEL"/>
        <div>
            <field name="FIELD_NAME" class="oe_inline"/>
        </div>
    </div>
</form>
```

The `label` element can have the following attributes:

**`for`**

The reference to the field associated with the label. It can be either the name of the field, or
its id (the `id` attribute set on the field).

When there are several occurrences of the same field in the view, and there are several `label`
components associated with these field nodes, these labels must have unique `for` attribute; in
this case, referencing the `id` attribute of the corresponding field nodes.

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`string`**

The label to display.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

The field’s label coming from the field definition on the model

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

#### `button`: display action buttons

```xml
<form>
    <button type="object" name="ACTION" string="LABEL"/>
    <button type="object" name="ACTION" icon="FONT_AWESOME"/>
</form>
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

**`special`**

The behavior of the button for form views opened in dialog. It can have two different values:

**`save`**

Save the record and close the dialog.

**`cancel`**

Close the dialog without saving.

> **Example**
>
> ```xml
> <button special="cancel" icon="fa-trash"/>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`confirm`**

The confirmation message to display (and for the user to accept) before performing the button’s
action.

> **Example**
>
> ```xml
> <button name="action_destroye_gate" string="Send the goa'uld" type="object" confirm="Do you confirm the action?"/>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`data-hotkey`**

The hotkey ([keyboard_shortcut](https://en.wikipedia.org/wiki/Keyboard_shortcut), similar to an [accesskey](https://www.w3.org/TR/html5/editing.html#the-accesskey-attribute)) that is bound to the button. It is
enabled when the `alt` key is pressed together with the selected character, or together with the
`shift` key and the selected character when `shift+` is prepended to the value.

> **Example**
>
> ```xml
> <button type="object" name="action_confirm" string="Confirm" data-hotkey="c"/>
> <button type="object" name="action_tear" string="Tear the sheet" data-hotkey="shift+k"/>
> ```

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

#### Chatter widget

The [chatter widget](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/mixins.html#reference-mixins-mail-chatter) is the communication and log tool allowing
to email colleagues and customers directly from a record (task, order, invoice, event, note…).

It is added with a `chatter` element when the model inherits the `mail.thread` mixin.

> **Example**
>
> ```xml
> <form>
>     <sheet>
>         ...
>     </sheet>
>     <chatter/>
> </form>
> ```

#### Attachments preview widget

The attachment preview widget is added with an *empty* `div` element with the class
`o_attachment_preview`.

> **Example**
>
> ```xml
> <form>
>     <sheet>
>         ...
>     </sheet>
>     <div class="o_attachment_preview"/>
> <form>
> ```

### Structural components

Structural components provide structure or „visual“ features with little logic. They are used as
elements or sets of elements in form views.

Form views accept the following children structural components: group, sheet,
notebook,
notebook,
newline,
separator,
header,
footer,
Buttons container, and
Title container.

Placeholders are denoted in all caps.

#### `group`: define columns layouts

The `group` element is used to define column layouts in forms. By default, groups define 2 columns,
and most direct children of groups take a single column.

field elements that are direct children of groups
display a `label` by default, and the label and the field itself have a `colspan` of `1` each.

Children are laid out horizontally (they try to fill the next column before changing row).

```xml
 <form>
     <group>
         ...
     </group>
</form>
```

The `group` element can have the following attributes:

**`string`**

The title displayed for the group.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`col`**

The number of columns in a `group`.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`Default`**

`2`

**`colspan`**

The number of columns taken by a child element.

**`Requirement`**

Optional

**`Type`**

[int](https://docs.python.org/3/library/functions.html#int)

**`Default`**

`1`

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
> | ../../../_images/form_group.svg |
> | ```xml <group>     <field name="a" string="custom"/>     <field name="b"/> </group> <group string="title 1">     <group string="title 2">         <field name="c"/>         <field name="d"/>     </group>     <group>         <field name="e"/>         <field name="f"/>         <field name="g"/>     </group> </group> <group col="12">     <group colspan="8">         <field name="h"/>     </group>     <group colspan="4">         <field name="i"/>     </group> </group> ``` |

#### `sheet`: make the layout responsive

The `sheet` element can be used as a direct child of the form root element for a narrower and more responsive form layout
(centered page, margin…). It usually contains group elements.

```xml
<form>
    <sheet>
        ...
    </sheet>
</form>
```

#### `notebook` & `page`: add tabbed sections

The `notebook` element defines a tabbed section. Each tab is defined through a `page` child element.

The `notebook` element should not be placed within `group` elements.

```xml
<form>
    <notebook>
        <page string="LABEL">
            ...
        </page>
    </notebook>
</form>
```

The `page` element can have the following attributes:

**`string`**

The title of the tab.

**`Requirement`**

Optional

**`Type`**

`str`

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
> | ../../../_images/form_notebook.svg |
> | ```xml <form>     <notebook>         <page string="Page1">             ...         </page>         <page string="Page2">             ...         </page>     </notebook> </form> ``` |

#### `newline`: start new group rows

The `newline` element is used within group
elements to end the current row early and immediately switch to a new row, without filling any
remaining column beforehand.

```xml
<form>
    <group>
        ...
        <newline/>
        ...
    </group>
</form>
```

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/form_newline.svg |
> | ```xml <form>     <group string="Title 1">         <group string="Title 1.1">...</group>         <newline/>         <group string="Title 1.2">...</group>         <group string="Title 1.3">...</group>     </group> </form> ``` |

#### `separator`: add horizontal spacing

The `separator` element adds vertical spacing between elements within a group.

```xml
<form>
    ...
    <separator/>
    ...
</form>
```

The `<separator>` element can have the following attributes:

**`string`**

The title as a section title.

**`Requirement`**

Optional

**`Type`**

`str`

**`Default`**

`''`

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/form_separator.svg |
> | ```xml <form>     <group>         <FIELD/>         <separator string="Title 1"/>         <FIELD/>         <group>             <FIELD/>             <separator string="Title 2"/>             <FIELD/>         </group>         <group>             <FIELD/>             <FIELD/>         </group>     </group> </form> ``` |

> **Tipp**
>
> The `separator` element can be used to achieve visual separation between elements within the same
> inner `group` element while keeping them horizontally aligned.

#### `header`: display workflow buttons and a status

The `header` element combined with the sheet
element provides a full-width location above the sheet itself generally used to display workflow
button elements and a field element rendered as status widget.

```xml
<form>
    <header>
        <BUTTONS/>
    </header>
    <sheet>
        ...
    </sheet>
</form>
```

> **Example**
>
> ```xml
> <header>
>     <button string="Reset" type="object" name="set_draft" invisible="state != 'done'"/>
>     <field name="state" widget="statusbar" statusbar_visible="draft,posted" options="{'clickable': 1}"/>
> </header>
> ```

#### `footer`: display dialog buttons

The `footer` element is used to display buttons
elements at the end of dialogs.

```xml
<form>
    <sheet>
        ...
    </sheet>
    <footer>
        <BUTTONS/>
    </footer>
</form>
```

> **Example**
>
> ```xml
> <footer>
>     <button string="Save" special="save"/>
>     <button string="Feature action" type="object" name="my_action" class="btn-primary"/>
>     <button string="Discard" special="cancel"/>
> </footer>
> ```

When no `footer` element is specified, the view’s standard buttons (like Save or Discard) will be
present by default. It is also possible to avoid replacing the standard buttons in form or x2many
dialogs by using the `replace` attribute. This attribute defaults to `True` if not specified but
setting it to `False` (or 0) will make it so that the specified `footer` will be added next to the
default buttons instead of replacing them.

> **Example**
>
> ```xml
> <footer replace="0">
>     <button string="Custom added action" type="object" name="my_action" class="btn-primary"/>
> </footer>
> ```

#### Buttons container

A button elements container can be created with a
`div` element with the class `button_box`.

```xml
<form>
    <div name="button_box">
        <BUTTONS/>
    </div>
<form>
```

> **Possible structure and representation of its rendering**
>
> |  |
> | --- |
> | ../../../_images/form_button_box.svg |
> | ```xml <form>     <div name="button_box">         <button type="edit" name="edit" icon="fa-edit" string="Button1"/>         <button type="object" name="my_action" icon="fa-dollar">             <field name="total_inv" widget="statinfo" string="Invoices"/>         </button>     </div> <form> ``` |

#### Title container

A title field element container can be created with
a `div` element with the class `oe_title`.

```xml
<form>
    <sheet>
        <div class="oe_title">
            <h1><FIELD/></h1>
        </div>
    </sheet>
<form>
```
