<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/unit_testing/hoot.html · abgerufen 2026-10-02 -->

# HOOT – Teil 3/5: DOM: queries

## DOM: queries

### Custom DOM selectors

Here’s a brief section on DOM selectors in Hoot, as they support additional pseudo-classes
that can be used to target elements based on non-standard features, such as their
text content or their global position in the document.

- **`:contains(text)`**

  matches nodes whose text content matches the given `text`

  - given *text* supports regular expression syntax (e.g. `:contains(/^foo.+/)`) and is
    case-insensitive (unless using the `i` flag at the end of the regex)
- **`:displayed`**

  matches nodes that are *„displayed“* (see `isDisplayed`)
- **`:empty`**

  matches nodes that have an empty content (value or text content)
- **`:eq(n)`**

  returns the *nth* node based on its global position (0-based index);
- **`:first`**

  returns the first node matching the selector (in the whole document)
- **`:focusable`**

  matches nodes that can be *„focused“* (see `isFocusable`)
- **`:hidden`**

  matches nodes that are *not* *„visible“* (see `isVisible`)
- **`:iframe`**

  matches nodes that are `<iframe>` elements, and returns their `body` if it is ready
- **`:last`**

  returns the last node matching the selector (in the whole document)
- **`:selected`**

  matches nodes that are selected (e.g. `<option>` elements)
- **`:shadow`**

  matches nodes that have shadow roots, and returns their shadow root
- **`:scrollable`**

  matches nodes that are scrollable (see `isScrollable`)
- **`:value(text)`**

  matches nodes whose value matches the given `text`

  - given *text* supports regular expression syntax (e.g. `:value(/^foo.+/)`) and is
    case-insensitive (unless using the `i` flag at the end of the regex)
- **`:visible`**

  matches nodes that are *„visible“* (see `isVisible`)

### Query & node properties helpers

Hoot provides helpers to query nodes and some of their properties in a streamlined
and elegant way. This can mainly be done through the use of `queryX` helpers:

**`queryAll(target[, options])`**

Returns a list of nodes matching the given `Target`.
This function can either be used as a [template literal tag](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Template_literals#tagged_templates)
(only supports string selector without options) or invoked the usual way.

The target can be:

> - a `Node` (or an iterable of nodes), or `Window` object;
> - a `Document` object (which will be converted to its body);
> - a string representing a custom selector
>   (which will be queried from the `root` option).

An `options` object can be specified to filter 1 the results:

> - `count`: the exact number of nodes to match (throws an error if the number of nodes
>   doesn’t match);
> - `displayed`: whether the nodes must be „displayed“ (see `isDisplayed`);
> - `focusable`: whether the nodes must be „focusable“ (see `isFocusable`);
> - `root`: the root node to query the selector in (defaults to the current fixture);
> - `visible`: whether the nodes must be „visible“ (see `isVisible`).
>   * This option implies `displayed`

**`1`**

these filters (except for `count` and `root`) achieve the same result as using their homonym
pseudo-classes on the final group of the given selector string, e.g.:

```javascript
// These 2 will return the same result
queryAll`ul > li:visible`;
queryAll("ul > li", { visible: true });
```

**`Rückgabe`**

`Node[]`

**`queryAllAttributes(target, attribute[, options])`**

Performs a `queryAll()` on the given `target` and returns
a list of attribute values.

**`Rückgabe`**

`string[]` list of attribute values

**`queryAllProperties(target, property[, options])`**

Performs a `queryAll()` on the given `target` and returns
a list of property values.

**`Rückgabe`**

`unknown[]` list of property values

**`queryAllTexts(target[, options])`**

Performs a `queryAll()` on the given `target` and returns
a list of text contents.

**`Rückgabe`**

`string[]` list of text contents

**`queryAllValues(target[, options])`**

Performs a `queryAll()` on the given `target` and returns
a list of values.

**`Rückgabe`**

`string[]` a list of values

**`queryAttribute(target, attribute[, options])`**

Performs a `queryOne()` with the given arguments and returns
the value of the given `attribute` of the matching node.

**`Rückgabe`**

`string` the attribute value

**`queryFirst(target[, options])`**

Performs a `queryAll()` with the given arguments and returns
the first result or `null`.

**`Rückgabe`**

`Node` | `null` the first matching node

**`queryOne(target[, options])`**

Performs a `queryAll()` with the given arguments, along with
a forced `count: 1` option to ensure only one node matches the given `Target`.

The returned value is a single node instead of a list of nodes.

**`Rückgabe`**

`Node` a single node

**`queryText(target[, options])`**

Performs a `queryOne()` with the given arguments and returns
the *text* of the matching node.

**`Rückgabe`**

`string` text of the matching node

**`queryValue(target[, options])`**

Performs a `queryOne()` with the given arguments and returns
the *value* of the matching node.

**`Rückgabe`**

`string` value of the matching node

All of the above helpers are synchronous, meaning that they will attempt to query
nodes instantly. Although some use cases require the element to be awaited for an
arbitrary amount of time, unknown in advance due to UI fetching and rendering complexity.

Hoot provides 2 methods to wait for an element to appear / disappear within a certain
time frame (by default: `200` milliseconds) for such cases:

**`waitFor(target[, options])`**

Combination of `queryAll()` and `waitUntil()`:
waits for a given target to match elements in the DOM and returns the first
matching node when it appears (or immediately if it is already present).

**`Rückgabe`**

`Promise<Node>` containing the first matching node

**`waitForNone(target[, options])`**

Opposite of `waitFor()` waits for a given target to disappear from the DOM.

**`Rückgabe`**

`Promise<number>` containing the number of matching nodes
