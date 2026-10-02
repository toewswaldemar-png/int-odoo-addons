<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/view_architectures.html · abgerufen 2026-10-02 -->

# View architectures – Teil 2/10: Settings

## Settings

Settings views are a customization of the form view. They
are used to display settings in a centralized place. They differ from generic form views in that
they have a search bar and a sidebar.

> **Example**
>
> ```xml
> <app string="CRM" name="crm">
>     <setting type="header" string="Foo">
>         <field name="foo" title="Foo?."/>
>         <button name="nameAction" type="object" string="Button"/>
>     </setting>
>     <block title="Title of group Bar">
>         <setting help="this is bar" documentation="/applications/technical/web/settings/this_is_a_test.html">
>             <field name="bar"/>
>         </setting>
>         <setting string="This is Big BAR" company_specific="1">
>             <field name="bar"/>
>         </setting>
>     </block>
>     <block title="Title of group Foo">
>         <setting string="Personalize setting" help="this is full personalize setting">
>             <div>This is a different setting</div>
>         </setting>
>     </block>
> </app>
> ```

### Components

Settings views accept the field, label and button elements of form views, as well as three additional children elements:
app, block, and setting.

Placeholders are denoted in all caps.

#### `app`: declare the application

The `app` element is used to declare the application on the settings view. It creates an entry with
the logo of the application on the sidebar of the view. It also acts as delimiter when searching.

```xml
<form>
    <app string="NAME" name="TECHNICAL_NAME">
    ...
    </app>
</form>
```

The `app` element can have the following attributes:

**`string`**

The name of the application.

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`name`**

The technical name of the application (the name of the module).

**`Requirement`**

Mandatory

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`logo`**

The [relative path](https://en.wikipedia.org/wiki/URL) to the logo.

**`Requirement`**

Optional

**`Type`**

[path](https://en.wikipedia.org/wiki/Path_(computing))

**`Default`**

A path computed with the `name` attribute: `/name/static/description/icon.png`

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

#### `block`: declare a group of settings

The `block` element is used to declare a group of settings. This group can have a title and a
description.

```xml
 <form>
     <app string="NAME" name="TECHNICAL_NAME">
         ...
         <block title="TITLE">
             ...
         </block>
         ...
     </app>
</form>
```

The `block` element can have the following attributes:

**`title`**

The title of the block of settings. One can search on its value.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`help`**

The description of the block of settings. One can search on its value.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

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

#### `setting`: declare the setting

The `setting` element is used to declare the setting itself.

The first field element in the setting is used as
the main field. It is placed on the left panel if it is a boolean field, and on the top of the right
panel otherwise. The field is also used to create the setting label if a `string` attribute is not
defined.

The `setting` element can also contain additional elements (e.g., HTML). All of those elements are
rendered in the right panel.

```xml
<form>
    <app string="NAME" name="TECHNICAL_NAME">
        <block title="TITLE">
            ...
            <setting string="SETTING_NAME">
                ...
                <field name="FIELD_NAME"/>
                ...
            </setting>
            ...
        </block>
    </app>
</form>
```

The `<setting>` element can have the following attributes:

**`type`**

By default, a setting is visually separated on two panels (left and right), and is used to edit a
given field. By defining `type="header"`, a
special kind of setting is rendered instead. This setting is used to modify the scope of the
other settings. For example, on the Website application, this setting is used to indicate to
which website the other settings apply. The header setting is visually represented as a banner on
top of the screen.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`string`**

The text used as the label of the setting.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

The first field’s label

**`title`**

The text used as a tooltip.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`help`**

The description of the setting. This text is displayed just below the setting label (with the
class `text-muted`).

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`company_dependent`**

Whether the setting is company-specific. If set, an icon is displayed next to the setting label.

It accepts only the value `'1'`.

**`Requirement`**

Optional

**`Type`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Default`**

`''`

**`documentation`**

The [path](https://en.wikipedia.org/wiki/Path_(computing)) to the documentation on the setting. If set, a clickable icon is displayed next to
the setting label. The path can be both an absolute or a [relative path](https://en.wikipedia.org/wiki/URL). In the latter case, it
is relative to `https://www.odoo.com/documentation/<version>`.

**`Requirement`**

Optional

**`Type`**

`path_`

**`Default`**

`''`

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
