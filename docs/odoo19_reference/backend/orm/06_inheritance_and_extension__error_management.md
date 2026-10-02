<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html · abgerufen 2026-10-02 -->

# ORM API – Teil 6/6: Inheritance and extension / Error management

## Inheritance and extension

Odoo provides three different mechanisms to extend models in a modular way:

- creating a new model from an existing one, adding new information to the
  copy but leaving the original module as-is
- extending models defined in other modules in-place, replacing the previous
  version
- delegating some of the model’s fields to records it contains

![../../../_images/inheritance_methods.png](../../../_images/inheritance_methods.png)

### Classical inheritance

When using the `_inherit` and
`_name` attributes together, Odoo creates a new
model using the existing one (provided via
`_inherit`) as a base. The new model gets all the
fields, methods and meta-information (defaults & al) from its base.

```python
class Inheritance0(models.Model):
    _name = 'inheritance.0'
    _description = 'Inheritance Zero'

    name = fields.Char()

    def call(self):
        return self.check("model 0")

    def check(self, s):
        return "This is {} record {}".format(s, self.name)

class Inheritance1(models.Model):
    _name = 'inheritance.1'
    _inherit = ['inheritance.0']
    _description = 'Inheritance One'

    def call(self):
        return self.check("model 1")
```

and using them:

```
a = env['inheritance.0'].create({'name': 'A'})
b = env['inheritance.1'].create({'name': 'B'})

a.call()
b.call()
```

will yield:

> „This is model 0 record A“
> „This is model 1 record B“

the second model has inherited from the first model’s `check` method and its
`name` field, but overridden the `call` method, as when using standard
[Python inheritance](https://docs.python.org/3/tutorial/classes.html#tut-inheritance).

### Extension

When using `_inherit` but leaving out
`_name`, the new model replaces the existing one,
essentially extending it in-place. This is useful to add new fields or methods
to existing models (created in other modules), or to customize or reconfigure
them (e.g. to change their default sort order)

```python
class Extension0(models.Model):
    _name = 'extension.0'
    _description = 'Extension zero'

    name = fields.Char(default="A")

class Extension0(models.Model):
    _inherit = 'extension.0'

    description = fields.Char(default="Extended")
```

```python
record = env['extension.0'].create({})
record.read()[0]
```

will yield:

```
{'name': "A", 'description': "Extended"}
```

> **Warnung**
>
> When `_inherit` is set to a string,
> then `_name` is set to the same value,
> unless `_name` is explicitly set.

> **Bemerkung**
>
> It will also yield the various automatic fields unless they’ve been disabled

### Delegation

The third inheritance mechanism provides more flexibility (it can be altered
at runtime) but less power: using the `_inherits`
a model *delegates* the lookup of any field not found on the current model
to „children“ models. The delegation is performed via
`Reference` fields automatically set up on the parent
model.

The main difference is in the meaning. When using Delegation, the model
**has one** instead of **is one**, turning the relationship in a composition
instead of inheritance

```python
class Screen(models.Model):
    _name = 'delegation.screen'
    _description = 'Screen'

    size = fields.Float(string='Screen Size in inches')

class Keyboard(models.Model):
    _name = 'delegation.keyboard'
    _description = 'Keyboard'

    layout = fields.Char(string='Layout')

class Laptop(models.Model):
    _name = 'delegation.laptop'
    _description = 'Laptop'

    _inherits = {
        'delegation.screen': 'screen_id',
        'delegation.keyboard': 'keyboard_id',
    }

    name = fields.Char(string='Name')
    maker = fields.Char(string='Maker')

    # a Laptop has a screen
    screen_id = fields.Many2one('delegation.screen', required=True, ondelete="cascade")
    # a Laptop has a keyboard
    keyboard_id = fields.Many2one('delegation.keyboard', required=True, ondelete="cascade")
```

```python
record = env['delegation.laptop'].create({
    'screen_id': env['delegation.screen'].create({'size': 13.0}).id,
    'keyboard_id': env['delegation.keyboard'].create({'layout': 'QWERTY'}).id,
})
record.size
record.layout
```

will result in:

```
13.0
'QWERTY'
```

and it’s possible to write directly on the delegated field:

```
record.write({'size': 14.0})
```

> **Warnung**
>
> when using delegation inheritance, methods are *not* inherited,
> only fields

> **Warnung**
>
> - `_inherits` is more or less implemented, avoid it if you can;
> - chained `_inherits` is essentially not implemented, we cannot guarantee anything on the final behavior.

### Fields Incremental Definition

A field is defined as class attribute on a model class. If the model
is extended, one can also extend the field definition by redefining
a field with the same name and same type on the subclass.
In that case, the attributes of the field are taken from the parent class
and overridden by the ones given in subclasses.

For instance, the second class below only adds a tooltip on the field
`state`

```python
class FirstFoo(models.Model):
    state = fields.Selection([...], required=True)

class FirstFoo(models.Model):
    _inherit = ['first.foo']
    state = fields.Selection(help="Blah blah blah")

class WrongFirstFooClassName(models.Model):
    _name = 'first.foo'  # force the model name
    _inherit = ['first.foo']
    state = fields.Selection(help="Blah blah blah")
```

## Error management

The Odoo Exceptions module defines a few core exception types.

Those types are understood by the RPC layer.
Any other exception type bubbling until the RPC layer will be
treated as a ‚Server error‘.

**`exception odoo.exceptions.UserError(message)`**

Generic error managed by the client.

Typically when the user tries to do something that has no sense given the current
state of a record.

**`exception odoo.exceptions.RedirectWarning(message, action, button_text, additional_context=None)`**

Warning with a possibility to redirect the user instead of simply
displaying the warning message.

**`Parameter`**

- **message** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – exception message and frontend modal content
- **action_id** ([*int*](https://docs.python.org/3/library/functions.html#int)) – id of the action where to perform the redirection
- **button_text** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – text to put on the button that will trigger
  the redirection.
- **additional_context** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – parameter passed to action_id.
  Can be used to limit a view to active_ids for example.

**`exception odoo.exceptions.AccessDenied(message='Access Denied')`**

Login/password error.

> **Bemerkung**
>
> Traceback only visible in the logs.

> **Example**
>
> When you try to log with a wrong password.

**`suppress_traceback()`**

Remove the traceback, cause and context of the exception, hiding
where the exception occured but keeping the exception message.

This method must be called in all situations where we are about
to print this exception to the users.

It is OK to leave the traceback (thus to *not* call this method)
if the exception is only logged in the logs, as they are only
accessible by the system administrators.

**`exception odoo.exceptions.AccessError(message)`**

Access rights error.

> **Example**
>
> When you try to read a record that you are not allowed to.

**`exception odoo.exceptions.CacheMiss(record, field)`**

Missing value(s) in cache.

> **Example**
>
> When you try to read a value in a flushed cache.

**`exception odoo.exceptions.MissingError(message)`**

Missing record(s).

> **Example**
>
> When you try to write on a deleted record.

**`exception odoo.exceptions.ValidationError(message)`**

Violation of python constraints.

> **Example**
>
> When you try to create a new user with a login which already exist in the db.
