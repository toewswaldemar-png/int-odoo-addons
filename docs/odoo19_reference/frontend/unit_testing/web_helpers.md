<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/unit_testing/web_helpers.html · abgerufen 2026-10-02 -->

# Web test helpers

## Overview

After the [„@odoo/hoot“](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/unit_testing/hoot.html) module, the second most-solicited module
in test files should be `"@web/../tests/web_test_helpers"`.

This module contains all the helpers that combine the low-level helpers provided
by Hoot, with all the most common features that are used in tests in Odoo.

These helpers are many, and this section of the documentation will only highlight
the most common ones, and the way they interact with one another.

For a full list of available helpers, you may refer to the [web_test_helpers file](https://github.com/odoo/odoo/blob/19.0/addons/web/static/tests/web_test_helpers.js).

## Mock environment

The `makeMockEnv` helper is the lowest helper that can spawn an `env`.

It will take care of

- creating the `env` object itself, pre-configured with all the required properties
  for the proper functioning of web components, such as `getTemplate` or `translateFn`;
- spawning a `MockServer` (if one did not exist already for that test);
- starting all registered [services](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/services.html), and awaiting until they are all ready;
- initiating other features that are not tied to a service, such as the web `router`;
- guaranteeing the teardown of all the features in its setup at the end of the test.

This method is great for testing low-level features, such as [services](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/services.html) that are
not tied to a [Component](https://github.com/odoo/owl/blob/master/doc/v2/reference/component.md):

```javascript
// Can be further configured, but is already packed with all the necessary stuff
const env = await makeMockEnv();

expect(env.isSmall).toBe(false);
```

> **Bemerkung**
>
> Like [makeMockServer](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/unit_testing/mock_server.html#mock-server-spawning), only one `env` can be active for a given test.
> It is not necessary to call `makeMockEnv` manually to retrieve the current environment
> instance; the `getMockEnv` helper can be called instead.

> **Example**
>
> - [DateTime input tests](https://github.com/odoo/odoo/blob/19.0/addons/web/static/tests/core/components/datetime/datetime_input.test.js)
> - [Name service tests](https://github.com/odoo/odoo/blob/19.0/addons/web/static/tests/core/name_service.test.js)

## Mounting components

Instantiating and appending [components](https://github.com/odoo/owl/blob/master/doc/v2/reference/component.md) to the DOM is meant to be easy,
through the use of the `mountWithCleanup` helper. It will prepare an `env` internally
(if one does not exist yet), which in turn also makes sure that a `MockServer` is
running.

It takes a `Component` class as its first argument, and an *optional* parameters
second argument, used to specify `props` or a custom `target`:

```javascript
await mountWithCleanup(Checkbox, {
    props: {
        value: false
    },
});
```

This helper will return the active `Component` instance.

> **Wichtig**
>
> It is generally *ill-advised* to retrieve the `Component` instance to directly
> interact with it or to perform assertions on its internal variables. The only
> „accepted“ use cases are when the `Component` is displaying hard-to-retrieve information
> in the DOM, such as graphs in a [canvas](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API).
> For most cases, it is highly preferred to query derived information in the DOM.

> **Example**
>
> - [Checkbox tests](https://github.com/odoo/odoo/blob/19.0/addons/web/static/tests/core/checkbox.test.js)
> - [Popover tests](https://github.com/odoo/odoo/blob/19.0/addons/web/static/tests/core/popover/popover.test.js)
> - [DateTimePicker tests](https://github.com/odoo/odoo/blob/19.0/addons/web/static/tests/core/components/datetime/datetime_picker.test.js)

## Mounting views

Mounting a view is simply a matter of using mountWithCleanup
with the [View](https://github.com/odoo/odoo/blob/19.0/addons/web/static/src/views/view.js) component and the correct properties.

For that purpose, web test helpers export a `mountView` helper, taking a parameters
object determining the view `type`, `resModel`, and other optional properties such
as an XML `arch`:

```javascript
// Resolves when the view is fully ready
await mountView({
    type: "list",
    resModel: "res.partner",
    arch: /* xml */ `
        <list>
            <field name="display_name" />
        </list>
    `,
});
```

Like the previous helpers on top of which `mountView` is built, it will ensure that
both an `env` and a `MockServer` are running for the current test.

> **Bemerkung**
>
> Like mountWithCleanup, it is *NOT*
> recommended to retrieve the returned [View](https://github.com/odoo/odoo/blob/19.0/addons/web/static/src/views/view.js) component instance. It can however
> be done, for cases like the [Graph view](https://github.com/odoo/odoo/blob/19.0/addons/web/static/src/views/graph/graph_view.js).

> **Example**
>
> - [Calendar view tests](https://github.com/odoo/odoo/blob/19.0/addons/web/static/tests/views/calendar/calendar_view.test.js)
> - [Graph view tests](https://github.com/odoo/odoo/blob/19.0/addons/web/static/tests/views/graph/graph_view.test.js)
> - [Kanban view tests](https://github.com/odoo/odoo/blob/19.0/addons/web/static/tests/views/kanban/kanban_view.test.js)

## Interacting with components

Hoot provides helpers to interact with the DOM (e.g. `click`, `press`, etc.). However,
these helpers present 2 issues when interacting with more complex components:

1. helpers try to interact instantly, while sometimes the element has yet to be
   appended to the document (in an unknown amount of time);
2. helpers only wait a single micro-task tick per dispatched event, while most
   Owl-based UIs take at least a full animation frame to update.

```javascript
// Edit record name
await click(".o_field_widget[name=name]");
await edit("Gaston Lagaffe");

// Potential error 1: button may not be in the DOM yet
await click(".btn:contains(Save)");

// Potential error 2: view is not yet updated
expect(".o_field_widget[name=name]").toHaveText("Gaston Lagaffe");
```

With these constraints in mind, web test helpers provide the `contains` helper:

```javascript
// Combines 'click' + 'edit' + 'animationFrame' calls
await contains(".o_field_widget[name=name]").edit("Gaston Lagaffe");
// Waits for (at least) a full animation frame after the click
await contains(".btn:contains(Save)").click();
expect(".o_field_widget[name=name]").toHaveText("Gaston Lagaffe");
```

This approach, while seemingly drifting a bit further away from the concept of „unit
testing“, is still a nice and convenient way to test more complex units such as [views](https://github.com/odoo/odoo/blob/19.0/addons/web/static/src/views/view.js),
the [WebClient](https://github.com/odoo/odoo/blob/19.0/addons/web/static/src/webclient/webclient.js), or
interactions between couples of [services](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/services.html) and components.

It should however not become the default for all interactions, as some of them still
need to happen *precisely* within a given time frame, which is a concept completely
ignored by `contains`.

> **Bemerkung**
>
> Most helpers in Hoot are available as methods of a `contains` instance, with
> (generally) the same shape and API.
