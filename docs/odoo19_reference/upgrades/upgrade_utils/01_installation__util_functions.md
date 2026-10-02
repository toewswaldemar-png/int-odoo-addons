<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/upgrades/upgrade_utils.html · abgerufen 2026-10-02 -->

# Upgrade utils – Teil 1/2: Installation / Using upgrade utils / Util functions

## Installation

Clone the [Upgrade utils repository](https://github.com/odoo/upgrade-util/) locally and start
`odoo` with the `src` directory prepended to the `--upgrade-path` option.

```console
$ ./odoo-bin --upgrade-path=/path/to/upgrade-util/src,/path/to/other/upgrade/script/directory [...]
```

On platforms where you do not manage Odoo yourself, you can install this library via `pip`:

```console
$ python3 -m pip install git+https://github.com/odoo/upgrade-util@master
```

On [Odoo.sh](https://www.odoo.sh/) it is recommended to add it to the `requirements.txt` of
the custom repository. For this, add the following line inside the file:

```
odoo_upgrade @ git+https://github.com/odoo/upgrade-util@master
```

## Using upgrade utils

Once installed, the following packages are available for the upgrade scripts:

- `odoo.upgrade.util`: the helper itself.
- `odoo.upgrade.testing`: base TestCase classes.

To use it in upgrade scripts, simply import it:

```python
from odoo.upgrade import util

def migrate(cr, version):
   # Rest of the script
```

Now, the helper functions are available to be called through `util`.

## Util functions

Upgrade utils provides many useful functions to ease the upgrade process. Here, we describe some
of the most useful ones. Refer to the [util folder](https://github.com/odoo/upgrade-util/tree/master/src/util) for the comprehensive declaration of
helper functions.

> **Bemerkung**
>
> The `cr` parameter in util functions always refers to the database cursor. Pass the one
> received as a parameter in [`migrate()`](https://www.odoo.com/documentation/19.0/de/developer/reference/upgrades/upgrade_scripts.html#migrate). Not all functions need this parameter.

### Modules

Utility functions for module-level operations.

In most cases module operations (rename, merge, remove, …) should be performed in a
`base` script. The reason is that once the `base` module is upgraded, all the information
regarding modules should be already set in the DB for the upgrade process to function
correctly. The command line option `--pre-upgrade-scripts` (available from Odoo 16) allows
to run upgrade scripts *before* loading base. This is the recommended way to perform
module operations after a major upgrade.

**`force_install_module(cr, module, if_installed=None, reason='it has been explicitly asked for')`**

Force the ORM to install a module.

**`Parameter`**

- **module** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the module to install
- **if_installed** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*) or* [*None*](https://docs.python.org/3/library/constants.html#None)) – only force the install when these modules are
  already installed

**`Return str`**

the *new* state of the module

**`force_upgrade_of_fresh_module(cr, module, init=True)`**

Force the execution of upgrade scripts for a module that is being installed.

Standard Odoo doesn’t run upgrade scripts when a module is being installed. This makes
sense because, technically speaking, the module is not being upgraded. Still, it
happens that a (new) module needs to perform some operations for it to be correctly
installed, like grabbing data from another module. This is common when a module is
functionally *split* into several ones.

**`Parameter`**

- **module** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the module for which to force the execution of upgrade
  scripts
- **init** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to set the module to be in *init* mode

Being in init mode has the side effect of not respecting noupdate flags, in XML file
nor in `ir_model_data`.

**`merge_module(cr, old, into, update_dependers=True, xmlid_mapping=None)`**

Merge a module into another.

This function moves all references and records from the source module to the
destination module.

> **Warnung**
>
> This functions does not remove any record. It removes XMLIDs from the source
> module with a conflicting name in the destination module, unless explicitly renamed
> via `xmlid_mapping` parameter.

**`Parameter`**

- **old** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the module to be merged
- **into** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the module to merge into
- **update_dependers** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the dependencies of modules that depend on `old`
  are updated
- **xmlid_mapping** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – optional `{old_name: new_name}` mapping of XMLIDs to
  rename as part of the merge. Use this when an XMLID from
  `old` would otherwise collide by *name* with one already
  present in `into`.
  See `rename_xmlid()`

**`module_installed(cr, module)`**

Return whether a module is installed.

**`Parameter`**

**module** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the module to check

**`Rückgabetyp`**

[bool](https://docs.python.org/3/library/functions.html#bool)

See `modules_installed()`.

**`modules_installed(cr, *modules)`**

Return whether *all* given modules are installed.

**`Parameter`**

**modules** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – one or more module names to check (variadic)

**`Rückgabetyp`**

[bool](https://docs.python.org/3/library/functions.html#bool)

> **Bemerkung**
>
> In the context of upgrades a module is considered as installed if it is marked for
> upgrade, or for installation; even if they are not yet fully installed.

**`move_model(cr, model, from_module, to_module, move_data=False, keep=())`**

Move a model from one module to another.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the model to move
- **from_module** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the module where the model is originally defined
- **to_module** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the destination module where the model is to be moved
- **move_data** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to also update `ir_model_data` for records of the model
- **keep** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of XML ids to keep - not move

This function can be called for moving overrides of a model to another module. As it
cannot distinguish between source model or inherited model, it raises an exception if
the destination module isn’t installed.

**`remove_module(cr, module)`**

Completely remove a module.

This operation is equivalent to uninstall and removal of *all* references to
the module - no trace of it is left in the database.

**`Parameter`**

**module** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the module to remove

> **Warnung**
>
> Since this function removes *all* data associated to the module. Ensure to
> reassign records before calling this function.

**`remove_theme(cr, theme, base_theme=None)`**

Uninstall a theme module.

> **Warnung**
>
> This function can only be used in `post-` scripts.

See `remove_module()` and `uninstall_theme()`.

**`rename_module(cr, old, new)`**

Rename a module and all references to it.

**`Parameter`**

- **old** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – current name of the module to rename
- **new** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – new name of the module to rename

**`uninstall_module(cr, module)`**

Uninstall and remove all records owned by a module.

**`Parameter`**

**module** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the module to uninstall

**`uninstall_theme(cr, theme, base_theme=None)`**

Uninstall a theme module and remove it from websites.

**`Parameter`**

- **theme** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the theme module to uninstall
- **base_theme** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – if not `None`, unload first this base theme

> **Warnung**
>
> This function can only be used in `post-` scripts of `website` module as it relies
> on the ORM.

See `remove_theme()` and `uninstall_module()`.

### Models

Utility functions for modifying models.

Model operations are best done in `pre-` script of the involved modules.

**`merge_model(cr, source, target, drop_table=True, fields_mapping=None, ignore_m2m=())`**

Merge a model into another one.

This function moves all the references from `source` model into `target` model and
*removes* `source` model and its references. By default, only the fields with the
same name in both models are moved from source to target, optionally a mapping with
differently named fields can be provided.

> **Warnung**
>
> This function does not move the records from `source` model to `target` model.

**`Parameter`**

- **source** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the model to be merged
- **target** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the destination model to merge into
- **drop_table** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to drop the table of the source model
- **fields_mapping** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – mapping of field names from source to target
  model, when `None` only fields with same name are
  moved
- **ignore_m2m** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*) or* [*str*](https://docs.python.org/3/library/stdtypes.html#str)) – list of m2m tables ignored to remove from source model.

**`remove_inherit_from_model(cr, model, inherit, keep=(), skip_inherit=(), with_inherit_parents=True, skip_update_references=())`**

Remove `inherit` from `model`.

This function removes all fields inherited via `inherit` from a `model` and all
its descendant models. All fields from the inherit, including those from its parent
models are also removed, unless `with_inherit_parents` mode is unset. In such case
only fields from `inherit` are removed, excluding fields in its parents. Fields
listed in `keep` are never removed. If some descendants from `model` are listed in
`skip_inherit` they will keep the fields from `inherit`.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the model from which to remove the inherit
- **inherit** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the inherited model (or mixin) to remove
- **keep** ([*tuple*](https://docs.python.org/3/library/stdtypes.html#tuple)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – tuple with field names to keep
- **skip_inherit** ([*tuple*](https://docs.python.org/3/library/stdtypes.html#tuple)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of descendant models of `model` to not process
- **with_inherit_parents** (*boolean*) – if unset, remove fields coming from `inherit`
  only, keeping all fields from its parents
- **skip_update_references** ([*tuple*](https://docs.python.org/3/library/stdtypes.html#tuple)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*) or* *"*"*) – field names whose references should not be
  updated upon deletion. Use `"*"` for all fields.

**`remove_model(cr, model, drop_table=True, ignore_m2m=())`**

Remove a model and its references from the database.

Some required indirect references to the model are replaced by the *unknown model* -
an empty model that serves as placeholder for gone models.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the model to remove
- **drop_table** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to drop the table of this model
- **ignore_m2m** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*) or* [*str*](https://docs.python.org/3/library/stdtypes.html#str)) – list of m2m tables to ignore - not removed, use
  `"*"` to ignore (keep) all m2m tables

**`rename_model(cr, old, new, rename_table=True, ignored_m2ms='ALL_BEFORE_18_1')`**

Rename a model.

Updates all references to the model name in the DB.

If table rename is requested, from saas~18.1+, m2m table are updated too, unless
ignored. In older versions, m2m tables are skipped unless an empty list is passed.

**`Parameter`**

- **old** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – current model name
- **new** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – new model name
- **rename_table** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to also rename the table of the model
- **ignored_m2ms** – m2m tables to skip. Defaults to `"ALL_BEFORE_18_1"`, which skips
  all in Odoo 18 or below, none in saa~18.1+. For all versions, if
  the value is not the default, skip only the specified m2m tables.

### Fields

Utility functions for modifying model fields.

Field operations are best done in `pre-` script of the involved modules. In some cases a
preliminary operation could be done in pre and finished in post. A common example is to
remove a field in pre- keeping its column, later used in post when the column is finally
dropped.

**`change_field_selection_values(cr, model, field, mapping, skip_inherit=())`**

Replace references of values of a selection field.

This function replaces all references to selection values according to a mapping.
Domains are also updated.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – model name of the selection field to update
- **field** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the selection field to update
- **mapping** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – selection values to update, key values are replaced by
  their corresponding values in the mapping
- **skip_inherit** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*) or* [*str*](https://docs.python.org/3/library/stdtypes.html#str)) – list of inheriting models to skip in the update
  of the selection values, use `"*"` to skip all

**`convert_m2o_field_to_m2m(cr, model, field, new_name=None, m2m_table=None, col1=None, col2=None)`**

Convert a Many2one field to a Many2many.

It creates the relation table and fill it.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – model name of the field to convert
- **field** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – current name of the field to convert
- **new_name** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – new name of the field to convert.
  If not provide, it’s `field` with a trailing „s“.
- **m2m_table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the relation table. Automatically generated if not provided.
- **col1** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the column referencing `model`.
- **col2** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the column referencing the target of `field`.

**`dump_field_to_chatter(cr, model, field, res_id='id', res_model=None, label='%s', fk_display=None, fallback_column=None, where=None, html_escape=True, message_type='notification', subtype_xmlid=None)`**

Post a chatter message on each record to preserve a column value before it is dropped.

This is useful when a field is being removed during a migration but clients may need to
recover its values. The value is posted as a `mail_message` on the record’s chatter.

If the `mail` module is not installed (no `mail_message` table), the value is dumped
into `fallback_column` when one is provided, otherwise the function silently does nothing.

> **Example**
>
> ```python
> # Simple varchar column
> util.dump_field_to_chatter(
>     cr, "crm_lead", "mobile", label="Previous Mobile", where="{0}.phone != {0}.mobile"
> )
>
> # Drop team_id, save the team name
> util.dump_field_to_chatter(
>     cr, "res_partner", "team_id", label="Former Sales Team", fk_display="name"
> )
>
> # Dump from hr_version onto hr_employee's chatter
> util.dump_field_to_chatter(
>     cr, "hr_employee", "current_version_id", label="SSN", fk_display="ssnid"
> )
>
> # Raw HTML body (no label prefix)
> util.dump_field_to_chatter(
>     cr, "hr_employee", "notes", html_escape=False,
>     message_type="comment", subtype_xmlid="mail.mt_note"
> )
> ```

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – model of the field to dump
- **field** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – field whose value to preserve
- **label** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – message format. Any valid PG `format` string with a single `%s`
  is allowed. If `%s` is missing, `: %s` is appended automatically.
  Default `"%s"` produces the raw value with no prefix.
- **res_id** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – column that identifies the id of the record to put in the chatter.
- **res_model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – model of the record to post in the chatter, by default
  it is inferred from `res_id` target.
- **fk_display** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – when `column` is a foreign key, the column from the
  FK target table to use as display value (e.g.
  `"name"`). The FK target table is auto-detected. When
  omitted, only the id is shown. The id is always
  appended in parentheses.
- **fallback_column** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – column on the same table to dump the value into when
  the `mail` module is not installed (no
  `mail_message` table). The column must exist (e.g.
  `res_partner.comment`), raises otherwise. Translated
  (`jsonb`) columns are written through their `en_US`
  key.
- **where** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – extra SQL `WHERE` condition on the source records. It is a
  `str.format` template whose `{0}` is the source table alias; use it
  to qualify every column reference, e.g.
  `where="{0}.phone != {0}.mobile"`. By default, only rows where the
  dumped column is not `NULL` (and not empty for text types) are included.
- **html_escape** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to HTML-escape the value (default `True`).
- **message_type** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – `mail_message.message_type` (default `"notification"`).
- **subtype_xmlid** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – optional XML ID for the message subtype (e.g.
  `"mail.mt_note"`).

**`invert_boolean_field(cr, model, old, new, skip_inherit=())`**

Rename a boolean field and invert its value.

**`make_field_non_stored(cr, model, field, selectable=False)`**

Convert field to non-stored.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – model name of the field to convert
- **fieldname** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the field to convert
- **selectable** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the field is still selectable, if True custom `ir.filters` are not updated

**`move_field_to_module(cr, model, fieldname, old_module, new_module, skip_inherit=())`**

Move a field from one module to another.

This functions updates all references to a specific field, switching from the source
module to the destination module. It avoid data removal after the registry is fully
loaded. The field in inheriting models are also moved unless skipped.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the owner model of the field to move
- **fieldname** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the field to move
- **old_module** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – source module name from which the field is moved
- **new_module** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – target module name into which the field is moved
- **skip_inherit** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*) or* [*str*](https://docs.python.org/3/library/stdtypes.html#str)) – list of inheriting models for which the field is
  not to be moved, use `"*"` to skip all

**`remove_field(cr, model, fieldname, cascade=False, drop_column=True, skip_inherit=(), keep_as_attachments=False, update_references=True)`**

Remove a field and its references from the database.

This function also removes the field from inheriting models, unless exceptions are
specified in `skip_inherit`. When the field is stored we can choose to not drop the
column.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – model name of the field to remove
- **fieldname** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the field to remove
- **cascade** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the field column(s) are removed in `CASCADE` mode
- **drop_column** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the field’s column is dropped
- **skip_inherit** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*) or* [*str*](https://docs.python.org/3/library/stdtypes.html#str)) – list of inheriting models to skip the removal
  of the field, use `"*"` to skip all
- **keep_as_attachments** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – for binary fields, whether the data should be kept
  as attachments
- **update_references** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to update all references.
  If `False`, don’t update dashboard, filters, export paths,
  domains, and relations for related fields.

**`rename_field(cr, model, old, new, update_references=True, domain_adapter=None, skip_inherit=())`**

Rename a field and its references from `old` to `new` on the given `model`.

The field is updated in all inheriting models, except for models specified in
`skip_inherit`.

This functions also updates references, indirect or direct ones, including filters,
server actions, related fields, emails, dashboards, domains, and many more. See
`update_field_usage()`

For the update of domains a special adapter function can be used. The default adapter
just replaces `old` by `new` in each domain leaf. Refer to
`adapt_domains()` for information about domain adapters.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – model name of the field to rename
- **old** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – current name of the field to rename
- **new** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – new name of the field to rename
- **update_references** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to update all references
- **domain_adapter** (*function*) – adapter to use for domains, see
  `adapt_domains()`
- **skip_inherit** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*) or* [*str*](https://docs.python.org/3/library/stdtypes.html#str)) – models to skip when renaming the field in
  inheriting models, use `"*"` to skip all

**`update_field_usage(cr, model, old, new, domain_adapter=None, skip_inherit=())`**

Replace all references to the field `old` by `new` in different places.

**`Search in:`**

- ir_filters
- ir_exports_line
- ir_act_server
- mail_alias
- ir_ui_view_custom (dashboard)
- sign_item_type
- sign_item
- domains (using `domain_adapter`)
- related fields

This function can be used to replace the usage of a field by another. Domains are
updated using the `domain_adapter`. By default the domain adapter just replaces `old`
by `new` in domain leaves. See `adapt_domains()` for
more information about domain adapters.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – model name of the field
- **old** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – source name of the field to replace
- **new** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – target name of the field to set
- **domain_adapter** (*function*) – adapter to use for domains, see
  `adapt_domains()`
- **skip_inherit** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*) or* [*str*](https://docs.python.org/3/library/stdtypes.html#str)) – models to skip when renaming the field in
  inheriting models, use `"*"` to skip all

### Records

Utility functions for record-level operations.

**`delete_unused(cr, *xmlids, **kwargs)`**

Remove unused records.

This function will remove records pointed by `xmlids` only if they are not referenced
from any table. For hierarchical records (like product categories), it verifies
if the children marked as cascade removal are also not referenced. In which case
the record and its children are all removed.

> **Bemerkung**
>
> The records that cannot be removed are set as `noupdate=True`.

**`Parameter`**

- **xmlids** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of xml_ids to check for removal
- **deactivate** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to deactivate records that cannot be removed because
  they are referenced, `False` by default
- **keep_xmlids** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to keep the xml_ids of records that cannot be
  removed. By default `True` for versions up to 18.0,
  `False` from `saas~18.1` on.
- **include_m2m** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*) or* [*str*](https://docs.python.org/3/library/stdtypes.html#str)) – list of m2m tables to include in the search.
  `"*"` for all.

**`Rückgabe`**

list of ids of removed records, if any

**`Rückgabetyp`**

[list](https://docs.python.org/3/library/stdtypes.html#list)([int](https://docs.python.org/3/library/functions.html#int))

**`edit_view(cr, xmlid=None, view_id=None, skip_if_not_noupdate=True, active='auto')`**

Context manager to edit a view’s arch.

This function returns a context manager that may yield a parsed arch of a view as an
[etree Element](https://lxml.de/tutorial.html#the-element-class). Any changes done
in the returned object will be written back to the database upon exit of the context
manager, updating also the translated versions of the arch. Since the function may not
yield, use `skippable_cm()` to avoid errors.

```python
with util.skippable_cm(), util.edit_view(cr, "xml.id") as arch:
    arch.attrib["string"] = "My Form"
```

To select the target view to edit use either `xmlid` or `view_id`, not both.

When the view is identified by `view_id`, the arch is always yielded if the view
exists, with disregard to any `noupdate` flag it may have associated. When `xmlid` is
set, if the view `noupdate` flag is `False` then the arch will not be yielded *unless*
`skip_if_not_noupdate` is set to `False`. If `noupdate` is `True`, the view will be
yielded for edit.

If the `active` argument is `True` or `False`, the `active` flag of the view will be set
accordingly.

> **Bemerkung**
>
> If `active` is „auto“ (default value), the view will be activated if selected
> via `xmlid` and left untouched if selected via `view_id`.

**`Parameter`**

- **xmlid** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – optional, xml_id of the view edit
- **view_id** ([*int*](https://docs.python.org/3/library/functions.html#int)) – optional, ID of the view to edit
- **skip_if_not_noupdate** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to force the edit of views requested via
  `xmlid` parameter even if they are flagged as
  `noupdate=True`, ignored if `view_id` is set
- **active** ([*bool*](https://docs.python.org/3/library/functions.html#bool) *or* [*None*](https://docs.python.org/3/library/constants.html#None) *or* *"auto"*) – active flag value to set. Unchanged when `None`.

**`Rückgabe`**

a context manager that yields the parsed arch, upon exit the context manager
writes back the changes.

**`ensure_xmlid_match_record(cr, xmlid, model, values)`**

Ensure an xml_id references a record with specific values.

This function ensures the record pointed by an xml_id matches the values for the
fields specified in the `values` parameter. When the xmlid exist but it points to a
record that doesn’t match the values, the xmlid is updated to point to a record that
matches the values if one is found. If the xmlid doesn’t exist, it is created with the
found record. When no matching record is found, nothing is done. In all cases the
referenced record, after a possible update, of the xml_id is returned.

**`Parameter`**

- **xmlid** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – record xml_id, under the format `module.name`
- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – model name of the record
- **values** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) –

  mapping of field names to values the record must fulfill

  > **Example**
  >
  > ```python
  > values = {"id": 123}
  > values = {"name": "INV/2024/0001", "company_id": 1}
  > ```

**`Rückgabe`**

the ID of the matched record, `None` if no record found

**`Rückgabetyp`**

[int](https://docs.python.org/3/library/functions.html#int) or [None](https://docs.python.org/3/library/constants.html#None)

> **Tipp**
>
> This function is useful when migrating in-database records into a custom module, to
> create the xml_ids before the module is updated and avoid duplication.

**`force_noupdate(cr, xmlid, noupdate=True, warn=False)`**

Update the `noupdate` flag of a record.

**`Parameter`**

- **xmlid** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – record xml_id, under the format `module.name`
- **noupdate** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – value to set on the `noupdate` flag
- **warn** – whether to output a warning in the logs when the flag was switched from
  `True` to `False`

**`if_unchanged(cr, xmlid, callback, interval='1 minute', **kwargs)`**

Run `callback` if a record is unchanged.

This function will run a `callback` when the referred record is unchanged. The `xmlid`
and any extra parameter, but not `interval`, will be passed to the `callback`. In case
the record was changed it will be marked as `noupdate=True`. See also
`is_changed()` and
`force_noupdate()`.

This function is useful to take an action *only* when a record hasn’t been updated, a
common example is to force an update from XML even if the record was `noupdate=True`

```python
util.if_unchanged(cr, "mymodule.myrecord", util.update_record_from_xml)
```

**`Parameter`**

- **xmlid** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – xml_id of the record to check
- **callback** (*function*) – callback to execute in case the record was *not* changed, all
  extra parameters to this function are passed to the callback
- **interval** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – interval after `create_date` on which a record is considered as
  _changed_, see `is_changed()`

**`is_changed(cr, xmlid, interval='1 minute')`**

Return whether a record was changed.

This function checks if a record was changed before the current upgrade start time.
See `upgrade-util/src/base/0.0.0/pre-00-upgrade-start.py`

This utility will return a false positive on xmlids of records that match the
following conditions:

> - Have been updated in an upgrade preceding the current one
> - Have not been updated in the current upgrade

If the `xmlid` doesn’t exist in the DB this function returns `None`.

**`Parameter`**

- **xmlid** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – `xmlid` of the record to check
- **interval** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – SQL interval, a record is considered as changed if
  `write_date > create_date + interval`

**`Rückgabetyp`**

[bool](https://docs.python.org/3/library/functions.html#bool) or [None](https://docs.python.org/3/library/constants.html#None)

**`ref(cr, xmlid)`**

Return the id corresponding to the given [xml_id](https://www.odoo.com/documentation/19.0/de/developer/glossary.html#term-external-identifier).

**`Parameter`**

**xml_id** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – record xml_id, under the format `module.name`

**`Rückgabe`**

ID of the referenced record, `None` if not found.

**`Rückgabetyp`**

[int](https://docs.python.org/3/library/functions.html#int) or [None](https://docs.python.org/3/library/constants.html#None)

**`refs(cr, xmlids, strict=False)`**

Return a mapping of xmlid -> res_id for the given list of xmlids.

**`Parameter`**

- **xmlids** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)) – list of fully qualified xml_ids, each under the format `module.name`
- **strict** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – if `True`, only include xmlids that exist in the database.

**`Rückgabe`**

dict mapping each xmlid to its res_id; missing xmlids map to `None` unless
`strict=True`, in which case they are omitted from the result.

**`Rückgabetyp`**

[dict](https://docs.python.org/3/library/stdtypes.html#dict)

**`remove_record(cr, name)`**

Remove a record and its references corresponding to the given [xml_id](https://www.odoo.com/documentation/19.0/de/developer/glossary.html#term-external-identifier).

**`Parameter`**

**name** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – record xml_id, under the format `module.name`

**`remove_view(cr, xml_id=None, view_id=None, silent=False, key=None)`**

Remove a view and all its descendants.

This function recursively deletes the given view and its inherited views, as long as
they are part of a module. It also removes multi-website COWed views.

**`Parameter`**

- **xml_id** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – optional, the xml_id of the view to remove
- **view_id** ([*int*](https://docs.python.org/3/library/functions.html#int)) – optional, the ID of the view to remove
- **silent** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to show in the logs disabled custom views
- **key** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – key used to detect multi-website COWed views, if `None` then
  set to `xml_id` if provided, otherwise set to the xml_id
  referencing the view with ID `view_id` if any

> **Warnung**
>
> Either `xml_id` or `view_id` must be set. Specifying both will raise an error.

> **Tipp**
>
> When removing more than one view, use `remove_views()`, it
> batches the expensive operations:
>
> ```
> util.remove_views(cr, "module.view_one", "module.view_two")
> ```

**`remove_views(cr, *xml_ids, **kwargs)`**

Remove multiple views and all their descendants.

This function removes the given views and their inherited views, as long as they are
part of a module. It also removes multi-website COWed views. Whether child or COWed
views are removed or merely disabled is decided by its linked [xml_id](https://www.odoo.com/documentation/19.0/de/developer/glossary.html#term-external-identifier); a view that belongs to a module is removed, a user-defined one is
disabled.

**`Parameter`**

**xml_ids** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – the [xml_ids](https://www.odoo.com/documentation/19.0/de/developer/glossary.html#term-external-identifier) of the views to remove

**`rename_xmlid(cr, old, new, noupdate=None, on_collision='fail')`**

Rename an [external identifier](https://www.odoo.com/documentation/19.0/de/developer/glossary.html#term-external-identifier) (`xml_id`) of a record.

A rename cannot happen when the target name already exists on the database. In such
cases there are two options to control how this function behaves:

- `fail`: raise an exception and prevent renaming
- `merge`: rename the external identifier, remove the old one, and *replace*
  references. See `replace_record_references_batch()`

> **Bemerkung**
>
> This function does not remove records, it only updates xml_ids.

**`Parameter`**

- **old** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – current xml_id of the record, under the format `module.name`
- **new** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – new xml_id of the record, under the format `module.name`
- **noupdate** ([*bool*](https://docs.python.org/3/library/functions.html#bool) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – value to set on the `noupdate` flag of the xml_id,
  ignored if `None`
- **on_collision** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – how to proceed if the xml_id already exists, the options are
  `merge` or `fail` (default)

**`Rückgabe`**

the ID of the record referenced by the *new* xml_id, `None` when the record
doesn’t exist

**`Rückgabetyp`**

[int](https://docs.python.org/3/library/functions.html#int) or [None](https://docs.python.org/3/library/constants.html#None)

**`replace_in_all_jsonb_values(cr, table, column, old, new, extra_filter=None)`**

Replace values in JSONB columns.

This function replaces `old` by `new` in JSONB values. It is useful for replacing
values in *all* translations of translated fields.

**`Parameter`**

- **table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – table name where the values are to be replaced
- **column** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – column name where the values are to be replaced
- **old** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – original value to replace, can be a simple term (str) or a Postgres
  regular expression wrapped by `PGRegexp`
- **new** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – new value to set, can be a simple term or a expression using
  `<number>` notation to refer to *captured groups* if `old` is a
  regexp expression
- **extra_filter** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – extra `WHERE` compatible clause to filter the values to
  update, must use the `t` alias for the table, it can also
  include `{parallel_filter}` to execute the query in parallel,
  see `explode_execute()`

**`replace_record_references_batch(cr, id_mapping, model_src, model_dst=None, replace_xmlid=True, ignores=(), parent_field='parent_id')`**

Replace all references to records.

This functions replaces *all* references, direct or indirect to records of `model_src`
by the corresponding records in the mapping. If the target model of the mapping is not
the same as the source one, then `model_dst` parameter must be set.

**`Parameter`**

- **id_mapping** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)*(*[*int*](https://docs.python.org/3/library/functions.html#int)*,* [*int*](https://docs.python.org/3/library/functions.html#int)*)*) – mapping of IDs to replace, key value is replaced by
  the mapped value
- **model_src** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the source model of the records to replace
- **model_dst** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the target model of the records to replace, if `None`
  the target is assumed the same as the source
- **replace_xmlid** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to replace the references in xml_ids pointing to
  the source records
- **ignores** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of **table** names to skip when updating the referenced
  values

**`Paream str parent_field`**

when the target and source model are the same, and the model
table has `parent_path` column, this field will be used to
update it.

**`update_record_from_xml(cr, xmlid, reset_write_metadata=True, force_create=AUTO, from_module=None, reset_translations=(), ensure_references=False, fields=None)`**

Update a record based on its definition in the [Data Files](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/data.html).

This function ignores the `noupdate` flag on the record. It searches in all XML files
from the manifest of the module in the xmlid, or the `from_module` parameter if set,
for a matching definition. When found, it forces the ORM to update the record as in the
specs in the data file.

Optionally this function can reset the translations of some fields.

**`Parameter`**

- **xmlid** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – record xml_id, under the format `module.name`
- **reset_write_metadata** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to update the `write_date` of the record
- **force_create** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether the record is created if it does not exist.
  `True` by default, unless `fields` is not None.
- **from_module** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the module from which to update the record, necessary
  only when the specs are in a different module than the one in
  the xml_id
- **reset_translations** ([*set*](https://docs.python.org/3/library/stdtypes.html#set)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – field names whose translations get reset
- **ensure_references** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether referred records via `ref` XML attributes
  should also be updated.
- **fields** ([*set*](https://docs.python.org/3/library/stdtypes.html#set)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*) or* [*None*](https://docs.python.org/3/library/constants.html#None)) – optional list of fields to include in the XML declaration.
  If set, all other fields will be ignored. When set, record
  won’t be created if missing and all fields not found in
  the XML declaration will be set to NULL/their default.

> **Warnung**
>
> This functions uses the ORM, therefore it can only be used after **all** models
> referenced in the data specs of the record are already **loaded**. In practice this
> means that this function should be used in `post-` or `end-` scripts.

> **Bemerkung**
>
> The standard behavior of ORM is to create the record if it doesn’t exist, including
> its xml_id. That will happen on this function as well, unless `force_create` is set
> to `False`.

### ORM

Utility functions to perform operations via the ORM.

The functions on this module allow to use the ORM safely during upgrades. They enhance or
patch the ORM such that it can handle high volumes of data in a performant way. In some
cases totally different alternatives to the ORM’s own functions are provided. The functions
on this module work along the ORM of *all* supported versions.

**`env(cr)`**

Create a new environment.

> **Warnung**
>
> This function does *not* empty the cache maintained on the cursor for superuser
> with an empty environment. A call to `invalidate_cache` may be necessary every time
> data is modified directly in the database.

**`Rückgabe`**

the new environment

**`Rückgabetyp`**

[`Environment`](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.api.Environment)

**`get_inherit_model_names(model)`**

Get the names of the models the model directly or indirectly `_inherit`.

**`Parameter`**

**model** – recordset

**`Rückgabe`**

the names of the models the model directly or indirectly `_inherit`.
If `model._name` is not in the returned set, the model is defined once.
`base` is always in the returned set for non-`base` models.

**`Rückgabetyp`**

[list](https://docs.python.org/3/library/stdtypes.html#list)[[str](https://docs.python.org/3/library/stdtypes.html#str)]

**`class iter_browse(model, *args, **kw)`**

Iterate over recordsets.

The `callable` object returned by this class can be used as an iterator that loads
records by chunks (into a `recordset`). After each chunk is exhausted their data is
sent back to the database - flushed or committed - and a new chunk is loaded.

This class allows to run code like:

```python
for record in env['my.model'].browse(ids):
    record.field1 = val

env['my.model'].browse(ids)._compute_field2()
env['my.model'].create(values)
```

in a performant way while also avoiding `MemoryError`, even when `ids` or `values`
have millions of entries. The alternative using this class would be:

> **Example**
>
> ```python
> MyModel = util.env(cr)['my.model']
> for record in util.iter_browse(MyModel, ids):
>     record.field1 = val
>
> util.iter_browse(MyModel, ids)._compute_field2()
> util.iter_browse(MyModel, ids).create(values)
> ```

**`Parameter`**

- **model** (`odoo.model.Model`) – the model to iterate
- **ids** (*iterable**(*[*int*](https://docs.python.org/3/library/functions.html#int)*)*) – iterable of IDs of the records to iterate
- **size** ([*int*](https://docs.python.org/3/library/functions.html#int)) – the length of `ids`. Can be used to enable progress logging when `ids` has no `__length__`
- **query** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – alternative to ids, SQL query that can produce them.
  Can also be a DML statement with a RETURNING clause.
  See `query_ids()`
- **chunk_size** ([*int*](https://docs.python.org/3/library/functions.html#int)) – number of records to load in each iteration chunk, `200` by
  default
- **yield_chunks** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – when iterating, yield records in chunks of `chunk_size` instead of one by one.
  Default is `False`
- **logger** ([`logging.Logger`](https://docs.python.org/3/library/logging.html#logging.Logger)) – logger used to report the progress, by default
  `_logger`
- **strategy** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – whether to `flush` or `commit` on each chunk, default is `flush`

**`Rückgabe`**

the object returned by this class can be used to iterate, or call any model
method, safely on millions of records.

See also `env()`

**`create(values=None, query=None, **kw)`**

Create records.

An alternative to the default `create` method of the ORM that is safe to use to
create millions of records.

**`Parameter`**

- **values** (*iterable**(*[*dict*](https://docs.python.org/3/library/stdtypes.html#dict)*)*) – iterable of values of the records to create
- **size** ([*int*](https://docs.python.org/3/library/functions.html#int)) – the no. of elements produced by values or query.
  Can be used to enable progress logging when `ids` has no `__length__` or with query
- **query** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – alternative to values, SQL query that can produce them.
  Can also be a DML statement with a RETURNING clause.
- **multi** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to use the multi version of `create`, by default is
  `True` from Odoo 12 and above

**`recompute_fields(cr, model, fields, ids=None, logger=<Logger odoo.upgrade.util.orm (WARNING)>, chunk_size=256, strategy='auto', query=None)`**

Recompute field values.

This function will recompute fields of a model restricted to a set of records - or
all. The re-computation is not done on all records at the same time. It is split in
batches (chunks). This avoids performance issues, and, in the worse cases, failures
due to `MemoryError`. After each chunk is processed the data is sent back to the
database according to one of the following strategies:

- *flush*: use the `flush` method of the ORM
- *commit*: `commit` the cursor - also flush
- *auto*: pick the best alternative between the two above given the number of records
  to compute and the presence of tracked fields.

The *commit* strategy is less prone to cause a `MemoryError` for a huge volume of data.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the model to recompute
- **fields** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of the name of the fields to recompute
- **ids** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*int*](https://docs.python.org/3/library/functions.html#int)*) or* [*None*](https://docs.python.org/3/library/constants.html#None)) – list of the IDs of the records to recompute, when `None`
  recompute *all* records, unless `query` is also set (see
  below)
- **logger** ([`logging.Logger`](https://docs.python.org/3/library/logging.html#logging.Logger)) – logger used to report the progress
- **chunk_size** ([*int*](https://docs.python.org/3/library/functions.html#int)) – number of records per chunk - used to split the processing
- **strategy** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – strategy used to process the re-computation
- **query** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – query to get the IDs of records to recompute, it is an error to set
  both `ids` and `query`. Note that the processing will always happen
  in ascending order. If that is unwanted, you must use `ids` instead.

**`adapt_domains(cr, model, old, new, adapter=None, skip_inherit=(), force_adapt=False)`**

Replace `old` by `new` in domains using `model` and inheriting models.

`adapter` is a callback function to adapt leaves. Adapter functions must take three
arguments and return a [domain](https://www.odoo.com/documentation/19.0/de/developer/reference/upgrades/reference/orm/domains) that substitutes the original
leaf. The arguments are:

- `leaf`: a domain leaf which is a `tuple` of the form `(left, op, right)`
- `in_or`: a boolean, when `True` it means the leaf is part of an OR (`"|"`) domain,
  otherwise it is part of an AND (`"&"`) domain
- `negated`: a boolean, when `True` it means that the leaf is negated (`"!"`)

> **Example**
>
> ```python
> def adapter(leaf, in_or, negated):
>     left, op, right = leaf
>     ok, ko = (1, 2) if not negated else (2, 1)
>     if op == "="
>         return [(left, "=", ok)]
>     elif op == "!=":
>         return [(left, "=", ko)]
>     return [leaf]
> ```

`adapter` is called only on leaves that use the `old` field of `model` as **last**
part of the `left` part of leaves, unless `force_adapt` is `True`. In the latter case
the adapter is called if the field appears anywhere in the path, useful for relational
fields only.

The domains returned by an adapter do not need to have the `old` field replaced by
`new` in the `left` part of the input leaf. The replace will be done anyway to the
whole domain returned by the adapter. The usual purpose of the `adapter` is to modify
the operator and the `right` part of the input leaf. When `adapter` is not set only
the replacement takes place.

> **Example**
>
> When replacing `"field1"` by `"field2"`, the following happens:
>
> - `("foo.bar.baz.field1", "=", 1)` gets adapted *only* if the record pointed to by
>   `foo.bar.baz` is of the requested `model`.
> - `("foo.field1.baz", "=", 1)` is *not* adapted *even* if `foo` points to `model`,
>   unless `force_adapt` is `True`, because `field1` is not the last part of `left`
>   in this leaf.

> **Bemerkung**
>
> This function will replace domains in all *standard* domain fields. Including
> filters, dashboards, and standard fields known to represent a domain.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the model for which to adapt the domains
- **old** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the field to be adapted
- **new** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the field that should replace `old`
- **adapter** (*function*) – adapter for leaves
- **skip_inherit** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of inheriting model names to don’t adapt (skip)
- **force_adapt** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – when `True`, run the `adapter` on all leaves having `new` in
  `left` part of the leaf (path), useful when deleting a field
  (in which case `new` is ignored).

### SQL

Utility functions for interacting with PostgreSQL.

**`class ColumnList(list_=(), quoted=())`**

Encapsulate a list of elements that represent column names.

The resulting object can be rendered as string with leading/trailing comma or an alias.

**`Parameter`**

- **list** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of column names
- **quoted** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of quoted column names, it must correspond with the
  `list_` parameter

> **Example**
>
> ```
> >>> columns = ColumnList(["id", "field_Yx"], ["id", '"field_Yx"'])
> ```
>
> ```
> >>> list(columns)
> ['id', '"field_Yx"']
> ```
>
> ```
> >>> columns.using(alias="t").as_string(cr._obj)
> '"t"."id", "t"."field_Yx"'
> ```
>
> ```
> >>> columns.using(leading_comma=True).as_string(cr._obj)
> ', "id", "field_Yx"'
> ```
>
> ```
> >>> util.format_query(cr, "SELECT {} t.name FROM table t", columns.using(alias="t", trailing_comma=True))
> 'SELECT "t"."id", "t"."field_Yx", t.name FROM table t'
> ```
>
> ```
> >>> columns = ColumnList.from_unquoted(cr, ["foo", "BAR"])
> ```
>
> ```
> >>> list(columns)
> ['"foo"', '"BAR"']
> ```
>
> ```
> >>> list(columns.iter_unquoted())
> ['foo', 'BAR']
> ```

> **Bemerkung**
>
> This class is better used via `get_columns()`

**`classmethod from_unquoted(cr, list_)`**

Build a ColumnList from a list of column names that may need quoting.

**`Parameter`**

**list** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of unquoted column names

**`using(leading_comma=KEEP_CURRENT, trailing_comma=KEEP_CURRENT, alias=KEEP_CURRENT)`**

Set up parameters to render this list as a string.

**`Parameter`**

- **leading_comma** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to render a leading comma in front of this list
- **trailing_comma** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – whether to render a trailing comma
- **alias** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – alias of the table of the columns, no alias is added if
  set to `None`

**`Rückgabe`**

a copy of the list with the parameters set

**`Rückgabetyp`**

`ColumnList`

**`iter_unquoted()`**

Iterate over the raw column names, non quoted.

This is useful if the quoting is done outside this object. Also to get access to
raw column names as in Postgres catalog.

**`Rückgabe`**

an iterator for the raw column names

**`class PGRegexp`**

Wrapper for semantic meaning of parameters: this string is a Postgres regular expression.

See `replace_in_all_jsonb_values()`

**`class SQLStr`**

Wrapper for semantic meaning of parameters: this string is a valid SQL snippet.

See `format_query()`

**`alter_column_type(cr, table, column, type, using=None, where=None, logger=<Logger odoo.upgrade.util.pg (WARNING)>)`**

Alter the type of a column.

Do it efficiently using a temporary column and parallel UPDATE queries.

**`Parameter`**

- **table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the affected table.
- **column** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the column to alter type.
- **type** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – new type of the column.
- **using** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – SQL expression that define how to convert the value to the new type.
  The `{0}` placeholder will be replaced by the column name.
- **where** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – used to restrict the values converted via `using`.
- **logger** ([`logging.Logger`](https://docs.python.org/3/library/logging.html#logging.Logger)) – logger used to report the progress.

**`bulk_update_table(cr, table, columns, mapping, key_col='id')`**

Update table based on mapping.

Each `mapping` entry defines the new values for the specified `columns` for the row(s)
whose `key_col` value matches the key.

> **Example**
>
> ```python
> # single column update
> util.bulk_update_table(cr, "res_users", "active", {42: False, 27: True})
>
> # multi-column update
> util.bulk_update_table(
>     cr,
>     "res_users",
>     ["active", "password"],
>     {
>         "admin": [True, "1234"],
>         "demo": [True, "5678"],
>     },
>     key_col="login",
> )
> ```

**`Parameter`**

- **table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – table to update.
- **columns** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *|* [*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – columns spec for the update. It could be a single
  column name or a list of column names. The `mapping`
  must match the spec.
- **mapping** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – values to set, which must match the spec in `columns`,
  following the **same** order
- **key_col** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – column used as key to get the values from `mapping` during the
  update.

> **Warnung**
>
> The values in the mapping will be casted to the type of the target column.
> This function is designed to update scalar values, avoid setting arrays or json
> data via the mapping.

**`column_exists(cr, table, column)`**

Return whether a column exists.

**`Parameter`**

- **table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – table to check
- **column** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – column to check

**`Rückgabetyp`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`column_type(cr, table, column, sized=False)`**

Return the type of a column, if it exists.

**`Parameter`**

- **table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – table to check
- **column** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – column to check

**`Rückgabetyp`**

SQL type of the column

**`copy_column(cr, table, column, new_name=AUTO)`**

Copy a column.

This function copies a column if it exists. It raises an error otherwise.

**`Parameter`**

- **table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – table of the column
- **column** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the column
- **new_name** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the new column, if not passed the original column name
  will be used with suffix `_upg_copy`.

**`Rückgabe`**

new column name

**`Rückgabetyp`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`create_column(cr, table, column, definition, **kwargs)`**

Create a column.

This function will create the column only if it *doesn’t* exist. It will log an error
if the existing column has different type. If `fk_table` is set, it will ensure the
foreign key is setup, updating if necessary, with the right `on_delete_action` if any
is set.

**`Parameter`**

- **table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – table of the new column
- **column** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the new column
- **definition** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – column type of the new column. Use `AUTO`
  to infer the type from the `id` column of `fk_table`.
- **default** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – default value to set on the new column
- **fk_table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – if the new column is a foreign key, name of the foreign table
- **on_delete_action** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – `ON DELETE` clause, default `NO ACTION`, only valid if
  the column is a foreign key.

**`Rückgabe`**

whether the column was created

**`Rückgabetyp`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`create_m2m(cr, m2m, fk1, fk2, col1=None, col2=None)`**

Ensure a m2m table exists or is created.

This function creates the table associated to a m2m field.
If the table already exists, `fixup_m2m()` is run on it.
The table name can be generated automatically, applying the same logic of the ORM.
In order to do so, use the value „auto“ for the `m2m` parameter.

**`Parameter`**

- **m2m** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – table name to create,
  if `AUTO` it is auto-generated
- **fk1** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – first foreign key table name
- **fk2** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – second foreign key table name
- **col1** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – column referencing `fk1`, defaults to `"{fk1}_id"`
- **col2** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – column referencing `fk2`, defaults to `"{fk2}_id"`

**`Rückgabe`**

the name of the table just created/fixed-up

**`Rückgabetyp`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`explode_execute(cr, query, table, alias=None, bucket_size=10000, logger=<Logger odoo.upgrade.util.pg (WARNING)>, qualifier='queries', explode_on='id')`**

Execute a query in parallel.

The query is split by buckets of ids, then processed in parallel by workers. If the
query does not include the special `{parallel_filter}` value, it is added to the last
`WHERE` clause, possibly also adding it if none found. When the query already has the
filter nothing is done. The filter always expands to the splitting strategy. The split
is done into buckets where no more than `bucket_size` IDs are updated on each
individual query.

> **Example**
>
> ```python
> util.explode_execute(
>     cr,
>     '''
>     UPDATE res_users u
>        SET active = False
>      WHERE (u.login LIKE 'dummy' OR u.login = 'bob')
>        AND {parallel_filter}
>     ''',
>     table="res_users"
>     alias="u",
> )
> ```

**`Parameter`**

- **query** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – the query to execute.
- **table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the *main* table of the query, used to split the processing
- **alias** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – alias used for the main table in the query
- **explode_on** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – column used to split the queries on
- **bucket_size** ([*int*](https://docs.python.org/3/library/functions.html#int)) – size of the buckets of ids to split the processing
- **logger** ([`logging.Logger`](https://docs.python.org/3/library/logging.html#logging.Logger)) – logger used to report the progress
- **qualifier** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – qualifier of the queries. Used in the progression log

**`Rückgabe`**

the sum of `cr.rowcount` for each query run

**`Rückgabetyp`**

[int](https://docs.python.org/3/library/functions.html#int)

> **Warnung**
>
> It’s up to the caller to ensure the queries do not update the same records in
> different buckets. It is advised to never use this function for `DELETE` queries on
> tables with self references due to the potential `ON DELETE` effects.
> For more details see `parallel_execute()`.

**`format_query(cr, query, *args, **kwargs)`**

Safely format a query.

The `str` arguments to this function are assumed to be SQL identifiers. They are
wrapped in double quotes before being expanded using [`str.format()`](https://docs.python.org/3/library/stdtypes.html#str.format). Any other
[psycopg2.sql.Composable](https://www.psycopg.org/docs/sql.html#psycopg2.sql.Composable)
are also allowed. This includes `ColumnList`, see also
`get_columns()`

> **Example**
>
> ```python
> >>> util.format_query(cr, "SELECT {0} FROM {table}", "id", table="res_users")
> SELECT "id" FROM "res_users"
> ```

**`Parameter`**

**query** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – query to format, can use brackets `{}` as in `str.format()`

**`get_columns(cr, table, ignore=('id',))`**

Return a list of columns in a table.

**`Parameter`**

- **table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – table name whose columns are retrieved
- **ignore** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of column names to ignore in the returning list

**`Rückgabe`**

a list of column names present in the table

**`Rückgabetyp`**

`ColumnList`

**`get_common_columns(cr, table1, table2, ignore=('id',), type_check=True)`**

Return a list of columns present in both tables.

**`Parameter`**

- **table1** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – first table name whose columns are retrieved
- **table2** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – second table name whose columns are retrieved
- **ignore** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of column names to ignore in the returning list
- **type_check** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – only returns common columns with compatible data type

**`Rückgabe`**

a list of column names present in both table

**`Rückgabetyp`**

`ColumnList`

**`get_m2m_on(cr, table)`**

Return a list of m2m tables associated with `table`.

We identify as m2m table all tables that have only two columns, both of which are FKs.
This function will return m2m tables for which one FK points to `table`.

> **Bemerkung**
>
> M2m tables are returned only once. Regardless of whether multiple foreign keys
> are defined on the same columns or whether both columns of the m2m refer to
> `table`. In the second case, the columns are returned in alphabetical order.

**`Rückgabe`**

list of (m2m_table, fk_col_to_table, other_fk_col, other_table) tuples

**`class named_cursor(cr, itersize=None)`**

Server side cursor.

This class wraps a psycopg2 server-side cursor. It adds convenient methods like
`dictfetchmany` and `dictfetchall`. It should be used as a context manager.

Server-side cursors are useful to fetch huge amounts of data from the DB by chunks
while at the same time keep using the main upgrade cursor.

**`Parameter`**

**itersize** ([*int*](https://docs.python.org/3/library/functions.html#int)) – determines the number of rows fetched from PG at once.

**`parallel_execute(cr, queries, logger=<Logger odoo.upgrade.util.pg (WARNING)>, qualifier='queries')`**

Execute queries in parallel.

> **Example**
>
> ```python
> util.parallel_execute(cr, [util.format_query(cr, "REINDEX TABLE {}", t) for t in tables])
> ```

> **Tipp**
>
> If looking to speedup a single query, see `explode_execute()`.

**`Parameter`**

- **queries** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – list of queries to execute concurrently
- **logger** ([*Logger*](https://docs.python.org/3/library/logging.html#logging.Logger)) – logger used to report the progress
- **qualifier** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – qualifier of the queries. Used in the progression log

**`Rückgabe`**

the sum of `cr.rowcount` for each query run

**`Rückgabetyp`**

[int](https://docs.python.org/3/library/functions.html#int)

> **Warnung**
>
> - Due to the nature of `cr.rowcount`, the return value of this function may represent an
>   underestimate of the real number of affected records. For instance, when some records
>   are deleted/updated as a result of an `ondelete` clause, they won’t be taken into account.
> - As a side effect, the cursor will be committed.

> **Bemerkung**
>
> If a concurrency issue occurs, the *failing* queries will be retried sequentially.

**`class query_ids(cr, query, itersize=None)`**

Iterator over ids returned by a query.

This allows iteration over a potentially huge number of ids without exhausting memory.

**`Parameter`**

- **query** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – the query that returns the ids. It can be DML,
  e.g. `UPDATE table WHERE ... RETURNING id`.
- **itersize** ([*int*](https://docs.python.org/3/library/functions.html#int)) – determines the number of rows fetched from PG at once,
  see `named_cursor()`.

**`remove_constraint(cr, table, name, cascade=False, warn=True)`**

Remove a table constraint.

This function removes the constraint `name` from `table`. It also removes records from
`ir_model_constraint` and its xml_ids. It logs not found constraints.

> **Bemerkung**
>
> If there is no constraint `name`, this function will attempt to remove
> `{table}_{name}`, the latter is the default name the ORM uses for constraints
> created from `_sql_constraints`.

**`Parameter`**

- **table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – table from where to remove the constraint
- **name** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the constraint to remove
- **cascade** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – cascade the constraint removal
- **warn** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – use warning level when logging not found constraints, otherwise use
  info level

**`Rückgabe`**

whether the constraint was removed

**`Rückgabetyp`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`rename_table(cr, old_table, new_table, remove_constraints=True)`**

Rename a table.

This function renames the table `old_table` into `new_table`, as well as its primary
key (and sequence), indexes, and foreign keys.

**`Parameter`**

- **old_table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the table to rename
- **new_table** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – new name of the table

**`Para bool remove_constraints`**

whether to remove the table constraints

### Misc

Miscellaneous standalone functions.

**`chunks(iterable, size, fmt=None)`**

Split `iterable` into chunks of `size` and wrap each chunk using `fmt` function.

This function is useful for splitting huge input data into smaller chunks that can be
processed independently.

> **Example**
>
> ```python
> >>> list(chunks(range(10), 4, fmt=tuple))
> [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9)]
> >>> ' '.join(chunks('abcdefghijklm', 3))
> 'abc def ghi jkl m'
> ```

**`Parameter`**

- **iterable** (*iterable*) – iterable object to split
- **size** ([*int*](https://docs.python.org/3/library/functions.html#int)) – chunk size
- **fmt** (*function*) – function to apply to each chunk, when `None` is passed `fmt`
  becomes `"".join` if `iterable` is a string, otherwise `iter`

**`Rückgabe`**

a generator that iterates over the result of `fmt` applied to each chunk

**`expand_braces(s)`**

Expand braces in the input.

> **Example**
>
> ```python
> >>> util.expand_braces("a_{this,that}_b")
> ['a_this_b', 'a_that_b']
> ```

**`Parameter`**

**s** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – string to expand, must contain precisely one pair of braces.

**`Rückgabe`**

expanded input

**`import_code_upgrade(name)`**

Import a code upgrade script.

Allow import of [upgrade_code scripts](https://github.com/odoo/odoo/tree/HEAD/odoo/upgrade_code) to be used inside upgrade scripts.

**`Parameter`**

**name** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – name of the script to import.

**`import_script(path, name=None)`**

Import an upgrade script.

This function allows to import functions from other upgrade scripts into the
current one.

> **Example**
>
> In `mymodule/15.0.1.0/pre-migrate.py`
>
> ```python
> def my_util(cr):
>     # do stuff
> ```
>
> In `myothermodule/16.0.1.0/post-migrate.py`
>
> ```python
> from odoo.upgrade import util
>
> script = util.import_script("mymodule/15.0.1.0/pre-migrate.py")
>
> def migrate(cr, version):
>     script.my_util(cr)  # reuse the function
> ```
>
> This function returns a Python `module`.
>
> ```python
> >>> util.import_script("base/0.0.0/end-moved0.py", name="my-moved0")
> <module 'my-moved0' from '/home/odoo/src/upgrade-util/src/base/0.0.0/end-moved0.py'>
> ```

**`Parameter`**

- **path** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) –

  relative path to the script to import in the form
  `$module/$version/$script-name`

  > **Bemerkung**
  >
  > The script must be available in the upgrade path.
- **name** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – name to assign to the returned module. When `None`,
  a name is derived from `path` to mirror the name set
  by Odoo (>=16) when loading migration scripts:
  `odoo.upgrade.<module>.<version>.<script>`.

**`Rückgabe`**

a module created from the imported upgrade script

**`class once(lower, upper, logger=None)`**

Run code only once in a version interval during a multi-step upgrade.

When the upgrade source and target are known (via the `ODOO_UPG_DB_SOURCE_VERSION` and
`ODOO_UPG_DB_TARGET_VERSION` environment variables), this object evaluates to truthy only
at the *first* upgrade step whose destination version falls within `[lower, upper]`. At
every other step it evaluates to falsy.

When the environment variables are absent (e.g. in a single-step or standalone run), the
object is truthy when the current version is in the interval `[lower, upper]`. A `None`
value means unbound. At least one bound must be set.

It can be used as a plain boolean or as a decorator:

> **Example**
>
> As a boolean, run a migration only during the first step that reaches Odoo 17:
>
> ```python
> def migrate(cr, version):
>     if util.once("17.0", "18.0"):
>         util.rename_field(cr, "sale.order", "old_name", "new_name")
> ```
>
> As a decorator, same effect, wrapping the whole function body:
>
> ```python
> @util.once("17.0", "18.0")
> def migrate(cr, version):
>     util.rename_field(cr, "sale.order", "old_name", "new_name")
> ```

> **Bemerkung**
>
> This is only meaningful in multi-step upgrades, i.e. for `0.0.0` scripts or symlinked
> scripts.

**`Parameter`**

- **lower** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – lower bound of the version interval, inclusive. Defaults to the upgrade source
  version when `None`.
- **upper** ([*str*](https://docs.python.org/3/library/stdtypes.html#str) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – upper bound of the version interval, inclusive. Defaults to the upgrade target
  version when `None`.
- **logger** ([*logging.Logger*](https://docs.python.org/3/library/logging.html#logging.Logger) *or* [*None*](https://docs.python.org/3/library/constants.html#None)) – when set, a message is emitted on each evaluation reporting whether the wrapped
  code runs or is skipped at the current version.

**`parse_version(s: str) → tuple[str, ...]`**

Convert a version string to a chronologically-sortable key

This is a rough cross between distutils‘ StrictVersion and LooseVersion;
if you give it versions that would work with StrictVersion, then it behaves
the same; otherwise it acts like a slightly-smarter LooseVersion. It is
*possible* to create pathological version coding schemes that will fool
this parser, but they should be very rare in practice.

The returned value will be a tuple of strings. Numeric portions of the
version are padded to 8 digits so they will compare numerically, but
without relying on how numbers compare relative to strings. Dots are
dropped, but dashes are retained. Trailing zeros between alpha segments
or dashes are suppressed, so that e.g. „2.4.0“ is considered the same as
„2.4“. Alphanumeric parts are lower-cased.

The algorithm assumes that strings like „-“ and any alpha string that
alphabetically follows „final“ represents a „patch level“. So, „2.4-1“
is assumed to be a branch or patch of „2.4“, and therefore „2.4.1“ is
considered newer than „2.4-1“, which in turn is newer than „2.4“.

Strings like „a“, „b“, „c“, „alpha“, „beta“, „candidate“ and so on (that
come before „final“ alphabetically) are assumed to be pre-release versions,
so that the version „2.4“ is considered newer than „2.4a1“.

Finally, to handle miscellaneous cases, the strings „pre“, „preview“, and
„rc“ are treated as if they were „c“, i.e. as though they were release
candidates, and therefore are not as new as a version string that does not
contain them.

**`skippable_cm()`**

Return a context manager to allow another context manager to not yield.

See `edit_view()` for an example usage.

**`version_between(a, b)`**

Return whether currently running Odoo version is in the range `[a,b]`.

See also `version_gte()`

> **Bemerkung**
>
> The bounds are inclusive.

**`Parameter`**

- **a** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – Odoo version, lower bound
- **b** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – Odoo version, upper bound

**`Rückgabetyp`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`version_gte(version)`**

Return whether currently running Odoo version is greater or equal to `version`.

This function is useful for conditional execution in an upgrade script that applies to
multiple versions, e.g. `0.0.0` scripts.

**`Parameter`**

**version** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – Odoo version, must follow the format `[saas~]X.Y` where `X` is the
major Odoo version, `saas~` is necessary only when `Y` is nonzero

**`Rückgabetyp`**

[bool](https://docs.python.org/3/library/functions.html#bool)

### Report

Utility functions to report upgrade changes.

The info generated by the reporting functions will be visible as posts
in the Administrator channel post upgrade.

**`get_anchor_link_to_record(model, id, name=None, action_id=None)`**

Get an HTML link to a record in Odoo UI.

**`Parameter`**

- **model** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – technical model name.
- **id** ([*int*](https://docs.python.org/3/library/functions.html#int)) – record ID to link to.
- **name** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – link text (optional); defaults to „model(id=id)“ if omitted.
- **action_id** ([*int*](https://docs.python.org/3/library/functions.html#int)) – optional action to open the record through.

**`Rückgabe`**

HTML anchor tag, wrapped in Markup if available.

**`Rückgabetyp`**

str or `markupsafe.Markup`

**`html_escape()`**

Replace the characters `&`, `<`, `>`, `'`, and `"` in the string with HTML-safe sequences. Use this if you need to display text that might contain such characters in HTML.

If the object has an `__html__` method, it is called and the return value is assumed to already be safe for HTML.

**`Parameter`**

**s** – An object to be converted to a string and escaped.

**`Rückgabe`**

A `Markup` string with the escaped text.

**`report_message(message, category='Other', format='text')`**

Append the upgrade report with a new entry, formatted according to `format`.

**`Parameter`**

- **message** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – what to report.
- **category** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – Title of a report entry.
- **format** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) –

  format used to render `message`. Supported values:

  - `text`: plain text, escaped and displayed as-is.
  - `html`: rendered as raw HTML markup.
  - `md`: rendered as Markdown and converted to HTML.
  - `rst`: rendered as reStructuredText and converted to HTML.

**`report_with_list(summary, data, columns, row_format, links=None, total=None, limit=100, category='Other')`**

Append the upgrade report with a new entry that displays a list of records.

The entry consists of a category (title) and a summary (body).
The entry displays a list of records previously returned by SQL query, or any list.

> **Warnung**
>
> If the list to render would be empty, nothing is posted in the report.

> **Example**
>
> ```python
> total = cr.rowcount
> data = cr.fetchmany(20)
> util.report_with_list(
>     summary="The following records were altered.",
>     data=data,
>     columns=("id", "name", "city", "comment", "company_id", "company_name"),
>     row_format="Partner with id {partner_link} works at company {company_link} in {city}, ({comment})",
>     links={"company_link": ("res.company", "company_id", "company_name"), "partner_link": ("res.partner", "id", "name")},
>     total=total,
>     category="Accounting"
> )
> ```

**`Parameter`**

- **summary** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – description of a report entry.
- **data** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*tuple*](https://docs.python.org/3/library/stdtypes.html#tuple)*)*) – data to report, each entry would be a row in the report.
- **columns** ([*tuple*](https://docs.python.org/3/library/stdtypes.html#tuple)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*)*) – columns in `data`, can be referenced in `row_format`
- **row_format** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – format for rows, can use any name from `columns` or `links`, e.g.:
  „Partner {partner_link} that lives in {city} works at company {company_link}“.
- **links** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*,* [*tuple*](https://docs.python.org/3/library/stdtypes.html#tuple)*(*[*str*](https://docs.python.org/3/library/stdtypes.html#str)*,* [*str*](https://docs.python.org/3/library/stdtypes.html#str)*,* [*str*](https://docs.python.org/3/library/stdtypes.html#str)*)**)*) – optional model/record links spec,
  the keys can be referenced in `row_format`.
- **total** ([*int*](https://docs.python.org/3/library/functions.html#int)) – optional, total number of records.
  Taken as `len(data)` when `None` is passed.
  Useful when `data` was limited by the caller.
- **limit** ([*int*](https://docs.python.org/3/library/functions.html#int)) – maximum number of records to list in the report.
  If `data` contains more records than `limit`, the `total`
  number would be included in the report as well.
  Set `None` for no limit.
- **category** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – title of a report entry.

**`report_with_summary(summary, details, category='Other')`**

Append the upgrade report with a new entry.

**`Parameter`**

- **summary** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – Description of a report entry.
- **details** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – Detailed description that is going to be folded by default.
- **category** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – Title of a report entry.
