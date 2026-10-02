<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/upgrades/upgrade_utils.html · abgerufen 2026-10-02 -->

# Upgrade utils – Teil 2/2: Testing upgrade scripts

## Testing upgrade scripts

There are two main classes used testing during the upgrade.

- `UpgradeCase` for testing upgrade scripts,
- `IntegrityCase` for testing invariant values that must hold across versions.

Subclasses must implement:

- For `UpgradeCase`:

  - `prepare` method: prepare data before upgrade,
  - `check` method: check data was correctly upgraded.
- For `IntegrityCase`:

  - `invariant` method: compute a value that must remain consistent before and after the upgrade.

Put your test classes in a `tests` Python module (folder) in any of the folders
containing the upgrade scripts of your modules. The script containing your tests must
have a `test_` prefix. The `tests` module must contain an `__init__.py` file to be
detected by Odoo.

Example directory structure:

```
myupgrades/
└── mymodule1/
    ├── 18.0.1.1.2/
    │   └── pre-myupgrade.py
    └── tests/
        ├── __init__.py
        └── test_myupgrade.py
```

> **Bemerkung**
>
> The tests in the example above will be loaded only if `mymodule1` is being
> **upgraded.**

### Running Upgrade Tests

After receiving an upgraded database with all standard Odoo modules already upgraded to
their target version, you can test the upgrade of custom modules by following a three-step
process:

1. Prepare the test data

   ```bash
   $ ~/odoo/$version/odoo-bin -d DB --test-tags=$prepare_test_tag \
     --upgrade-path=~/upgrade-util/src,~/myupgrades \
     --addons=~/odoo/$version/addons,~/enterprise/$version,~/mymodules --stop
   ```
2. Upgrade the modules

   ```bash
   $ ~/odoo/$version/odoo-bin -d DB -u mymodule1,mymodule2 \
     --upgrade-path=~/upgrade-util/src,~/myupgrades \
     --addons=~/odoo/$version/addons,~/enterprise/$version,~/mymodules --stop
   ```
3. Check the upgraded data

   ```bash
   $ ~/odoo/$version/odoo-bin -d DB --test-tags=$check_test_tag \
     --upgrade-path=~/upgrade-util/src,~/myupgrades \
     --addons=~/odoo/$version/addons,~/enterprise/$version,~/mymodules --stop
   ```

The example above assumes that `$version` is the target version of your upgrade (e.g.
`18.0`), `DB` is the name of your database, and `mymodule1,mymodule2` are the
modules you want to upgrade. The directory structure assumes that `~/odoo/$version` and
`~/enterprise/$version` contain the Community and Enterprise source code for the target
Odoo version, respectively. `~/mymodules` contains the code of your custom modules
(`mymodule1`, …), `~/myupgrades` contains your custom upgrade scripts, and
`~/upgrade-util` contains the [upgrade utils](https://github.com/odoo/upgrade-util/)
repo.

The variables `$prepare_test_tag` and `$check_test_tag` must be set according to:

| Variable | `UpgradeCase` | `IntegrityCase` |
| --- | --- | --- |
| `$prepare_test_tag` | `upgrade.test_prepare` | `integrity_case.test_prepare` |
| `$check_test_tag` | `upgrade.test_check` | `integrity_test.test_check` |

> **Bemerkung**
>
> `upgrade.test_prepare` also runs `IntegrityCase` tests, so you can prepare data
> for both `UpgradeCase` and `IntegrityCase` tests with only this tag.

> **Warnung**
>
> Do **not** run any `prepare` method of an `UpgradeCase` before sending your
> database for a **production** upgrade to [upgrade.odoo.com](https://upgrade.odoo.com). Doing so may risk your upgrade being blocked and marked
> as failed.

### API documentation

**`class IntegrityCase(methodName='runTest')`**

Test case for validating upgrade invariants.

Override:

- `invariant` to return a JSON-serializable value representing
  the invariant to check.

The `invariant` method is called both before and after the upgrade, and the results
are compared. If there is any difference the test fails.

> **Example**
>
> ```python
> from odoo.upgrade.testing import IntegrityCase
>
>
> class NoNewUsers(IntegrityCase):
>     def invariant(self):
>         return self.env["res.users"].search_count([])
> ```

**`class UpgradeCase(methodName='runTest')`**

Test case to verify the upgrade flow.

Override:

- `prepare` to set up data,
- `check` to assert expectations after the upgrade.

The ORM can be used in these methods to perform the functional flow under test. The
return value of `prepare` is persisted and passed as an argument to `check`. It
must be JSON-serializable.

> **Bemerkung**
>
> Since `prepare` injects or modifies data, this type of test is intended **only
> for development**. Use it to test upgrade scripts while developing them. **Do not**
> run these tests for a production upgrade. To verify that upgrades preserved
> important invariants in production, use `IntegrityCase` tests instead.

> **Example**
>
> ```python
> from odoo.upgrade.testing import UpgradeCase, change_version
>
>
> class DeactivateBobUsers(UpgradeCase):
>
>     def prepare(self):
>         u = self.env["res.users"].create({"login": "bob", "name": "Bob"})
>         return u.id  # will be passed to check
>
>     def check(self, uid):  # uid is the value returned by prepare
>         self.env.cr.execute(
>             "SELECT * FROM res_users WHERE id=%s AND NOT active", [uid]
>         )
>         self.assertEqual(self.env.cr.rowcount, 1)
> ```

**`change_version(version_str)`**

Class decorator to specify the version on which a test is relevant.

Using `@change_version(version)` indicates:

- `test_prepare` will only run if the current Odoo version is in the range
  `[next_major_version-1, version)`.
- `test_check` will only run if the current Odoo version is in the range `[version,
  next_major_version)`.

`next_major_version` is the next major version after `version`, e.g. for
`saas~17.2` it is `18.0`.

> **Bemerkung**
>
> Do not use this decorator if your upgrade is in the same major version. Otherwise,
> your tests will not run.

**`parametrize(argvalues)`**

Parametrize a test function.

Decorator for upgrade test functions to parametrize and generate multiple tests from
it. The new test functions are injected in the containing class. Inspired by the
[parameterized](https://pypi.org/project/parameterized/) package.

> **Example**
>
> ```python
> @parametrize([(1, 2), (2, 4), (-1, -2), (0, 0)])
> def test_double(self, input, expected):
>     self.assertEqual(input * 2, expected)
> ```
>
> This will generate four test methods: `test_double__0`, `test_double__1`,
> `test_double__2`, and `test_double__3`, each with different argument values.

**`Parameter`**

**argvalues** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)*(*[*tuple*](https://docs.python.org/3/library/stdtypes.html#tuple)*)*) – Arguments for each test case. Each tuple will be
unpacked and passed as arguments to the test function.
