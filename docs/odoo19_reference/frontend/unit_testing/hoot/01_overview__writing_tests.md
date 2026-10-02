<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/unit_testing/hoot.html · abgerufen 2026-10-02 -->

# HOOT – Teil 1/5: Overview / Running tests / Writing tests

## Overview

HOOT is a testing framework written with Owl whose
key features are:

- to register and run tests and test suites;
- to display an intuitive interface to view and filter test results;
- to provide ways to interact with the DOM to simulate user actions;
- to provide low-level helpers allowing to mock various global objects.

As such, it has been integrated as a `lib/` in the Odoo codebase and exports 2 main modules:

- `@odoo/hoot-dom`: (can be used in tours) helpers to:

  > - **interact** with the DOM, such as `click()` and `press()`;
  > - **query** elements from the DOM, such as `queryAll()` and `waitFor()`;
- `@odoo/hoot`: (only to be used in unit tests) all the test framework features:

  > - `test`, `describe` and `expect`
  > - test hooks like `after` and `afterEach`
  > - fixture handling with `getFixture`
  > - date and time handling like `mockDate` or `advanceTime`
  > - mocking network responses through `mockFetch()` or `mockWebSocket()`
  > - every helper exported by `@odoo/hoot-dom`

> **Bemerkung**
>
> This section of the documentation is not meant to list *all* helpers available
> in Hoot (the full list can be found in the [@odoo/hoot](https://github.com/odoo/odoo/blob/19.0/addons/web/static/lib/hoot/hoot.js)
> module itself). The goal here is to showcase the most used helpers and to justify
> some of the decisions that have led to the current shape of the testing framework.

## Running tests

In Odoo, frontend unit tests can be run by going to the `/web/tests` URL. Most of
the setup for calling the test runner is already in place:

- the `web.assets_unit_tests` bundle is already defined, and picks up all tests
  defined in most addons;
- a `start.hoot.js` file takes care of calling the test runner with its exported
  `start` entry point function.

When going to the test page, tests will be run sequentially and the results will
be displayed in the console and in the GUI (if not running in `headless` mode).

### Runner options

The runner can be configured either:

- through the interface (with the configuration dropdown and the search bar);
- or through the URL query parameters (e.g. `?headless` to run in headless mode).

Here is the list of available options for the runner:

- **`bail`**

  Amount of failed tests after which the test runner will be stopped. A falsy value
  (including 0) means that the runner should never be aborted. (default: `0`)
- **`debugTest`**

  Same as the `FILTER_SCHEMA.test` filter, while also putting the test runner in
  „debug“ mode. See `TestRunner.debug` for more info. (default: `false`)
- **`fps`**

  Sets the value of frames per seconds (this will be transformed to milliseconds and used in
  `advanceFrame`)
- **`filter`**

  Search string that will filter matching tests/suites, based on their full name (including
  their parent suite(s)) and their tags. (default: `""`)
- **`frameRate`**

  *Estimated* amount of frames rendered per second, used when mocking animation frames. (default:
  `60` fps)
- **`fun`**

  Lightens the mood. (default: `false`)
- **`headless`**

  Whether to render the test runner user interface. (default: `false`)
- **`id`**

  IDs of the suites OR tests to run exclusively. The ID of a job is generated
  deterministically based on its full name.
- **`loglevel`**

  Log level used by the test runner. The higher the level, the more logs will be displayed:

  - `0`: only runner logs are displayed (default)
  - `1`: all suite results are also logged
  - `2`: all test results are also logged
  - `3`: debug information for each test is also logged
- **`manual`**

  Whether the test runner must be manually started after page load (defaults to starting
  automatically). (default: `false`)
- **`notrycatch`**

  Removes the safety of `try .. catch` statements around each test’s run function to let errors
  bubble to the browser. (default: `false`)
- **`order`**

  Determines the order of test execution:

  - `"fifo"`: tests will be run sequentially as declared in the file system;
  - `"lifo"`: tests will be run sequentially in the reverse order;
  - `"random"`: shuffles tests and suites within their parent suite.
- **`preset`**

  Environment in which the test runner is running. This parameter is used to
  determine the default value of other features, namely:

  - the user agent;
  - touch support;
  - expected size of the viewport.
- **`showdetail`**

  Determines how the failed tests must be unfolded in the UI. (default: `"first-fail"`)
- **`tag`**

  Tag names of tests and suites to run exclusively (case insensitive). (default: empty)
- **`timeout`**

  Duration (in milliseconds) at the end of which a test will automatically fail.
  (default: `5` seconds)

> **Bemerkung**
>
> When selecting tests and suites to run, an implicit `OR` is applied between
> the *including* filters. This means that adding more inclusive filters will
> result in more tests being run. This applies to the `filter`, `id` and `tag`
> filters (*excluding* filters however will remove matching tests from the list
> of tests to run).

## Writing tests

### Test

Writing a test can be very straightforward, as it is just a matter of calling the `test` function
with a name and a function that will contain the test logic.

Here is a simple example:

```javascript
import { expect, test } from "@odoo/hoot";

test("My first test", () => {
    expect(2 + 2).toBe(4);
});
```

### Describe

Most of the time, tests are not that simple. They often require some setup and teardown,
and sometimes they need to be grouped together in a suite. This is where the `describe`
function comes into play.

Here is how you would declare a suite and a test within it:

```javascript
import { describe, expect, test } from "@odoo/hoot";

describe("My first suite", () => {
    test("My first test", () => {
        expect(2 + 2).toBe(4);
    });
});
```

> **Wichtig**
>
> In Odoo, all test files are run in an isolated environment and are wrapped within a global
> `describe` block (with the name of the suite being the *path* of the test file).
>
> With that in
> mind you should not need to declare a suite in your test files, although you can still declare
> sub-suites in the same file if you still want to split the file’s suite, for organization
> or tagging purposes.
