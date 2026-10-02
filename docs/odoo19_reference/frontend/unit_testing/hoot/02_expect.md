<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/unit_testing/hoot.html · abgerufen 2026-10-02 -->

# HOOT – Teil 2/5: Expect

## Expect

The `expect` function is the main assertion function of the framework. It is used
to assert that a value or an object is what it is expected to be or in the state
it is supposed to be. To do so, it provides a few modifiers and a wide range of
matchers.

### Modifiers

An `expect` modifier is a getter that returns another set of *altered* matchers that will behave in
a specific way.

- **`not`**

  Inverts the result of the following matcher: it will succeed if the matcher fails.

  ```javascript
  expect(true).not.toBe(false);
  ```
- **`resolves`**

  Waits for the value (`Promise`) to be *„resolved“* before running the following
  matcher with the resolved value.

  ```javascript
  await expect(Promise.resolve(42)).resolves.toBe(42);
  ```
- **`rejects`**

  Waits for the value (`Promise`) to be *„rejected“* before running the following
  matcher with the rejected reason.

  ```javascript
  await expect(Promise.reject("error")).rejects.toBe("error");
  ```

> **Bemerkung**
>
> The `resolves` and `rejects` modifiers are only available when the value is
> a promise, and will return a promise that will resolve once the assertion is
> done.

### Regular matchers

The matchers dictate what to do on the value being tested. Some will take that value
as-is, while others will *transform* that value before performing the assertion
on it (i.e. DOM matchers).

Note that the last argument parameter of all matchers is an optional dictionary with additional
options, in which a custom assertion `message` can be given for added context/specificity.

The first list of matchers are primitive or object based and are the most common ones:

**`toBe(expected[, options])`**

Expects the received value to be *strictly equal* to the `expected` value.

- Parameters

  > - `expected`: `any`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect("foo").toBe("foo");
  > expect({ foo: 1 }).not.toBe({ foo: 1 });
  > ```

**`toBeCloseTo(expected[, options])`**

Expects the received value to be *close to* the `expected` value up to a given
amount of digits (default is 2).

- Parameters

  > - `expected`: `any`
  > - `options`: `{ message?: string, digits?: number }`
- Examples

  > ```javascript
  > expect(0.2 + 0.1).toBeCloseTo(0.3);
  > expect(3.51).toBeCloseTo(3.5, { digits: 1 });
  > ```

**`toBeEmpty([options])`**

Expects the received value to be empty:

> - `iterable`: no items
> - `object`: no keys
> - `node`: no content (i.e. no value or text)
> - anything else: falsy value (`false`, `0`, `""`, `null`, `undefined`)

- Parameters

  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect({}).toBeEmpty();
  > expect(["a", "b"]).not.toBeEmpty();
  > expect(queryOne("input")).toBeEmpty();
  > ```

**`toBeGreaterThan(min[, options])`**

Expects the received value to be *strictly greater* than `min`.

- Parameters

  > - `min`: `number`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect(5).toBeGreaterThan(-1);
  > expect(4 + 2).toBeGreaterThan(5);
  > ```

**`toBeInstanceOf(cls[, options])`**

Expects the received value to be an instance of the given `cls`.

- Parameters

  > - `cls`: `Function`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect({ foo: 1 }).not.toBeInstanceOf(Object);
  > expect(document.createElement("div")).toBeInstanceOf(HTMLElement);
  > ```

**`toBeLessThan(max[, options])`**

Expects the received value to be *strictly less* than `max`.

- Parameters

  > - `max`: `number`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect(5).toBeLessThan(10);
  > expect(8 - 6).toBeLessThan(3);
  > ```

**`toBeOfType(type[, options])`**

Expects the received value to be of the given `type`.

- Parameters

  > - `type`: `string`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect("foo").toBeOfType("string");
  > expect({ foo: 1 }).toBeOfType("object");
  > ```

**`toBeWithin(min, max[, options])`**

Expects the received value to be *between* `min` and `max` (both inclusive).

- Parameters

  > - `min`: `number`
  > - `max`: `number`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect(3).toBeWithin(3, 9);
  > expect(-8.5).toBeWithin(-20, 0);
  > expect(100).toBeWithin(50, 100);
  > ```

**`toEqual(expected[, options])`**

Expects the received value to be *deeply equal* to the `expected` value.

- Parameters

  > - `expected`: `any`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect(["foo"]).toEqual(["foo"]);
  > expect({ foo: 1 }).toEqual({ foo: 1 });
  > ```

**`toHaveLength(length[, options])`**

Expects the received value to have a length of the given `length`.
Received value can be any `Iterable` or `Object`.

- Parameters

  > - `length`: `number`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect("foo").toHaveLength(3);
  > expect([1, 2, 3]).toHaveLength(3);
  > expect({ foo: 1, bar: 2 }).toHaveLength(2);
  > expect(new Set([1, 2])).toHaveLength(2);
  > ```

**`toInclude(item[, options])`**

Expects the received value to include an `item` of a given shape.

Received value can be an iterable or an object (in case it is an object,
the `item` should be a key or a tuple representing an entry in that object).

Note that it is NOT a strict comparison: the item will be matched for deep
equality against each item of the iterable.

- Parameters

  > - `item`: `any`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect([1, 2, 3]).toInclude(2);
  > expect({ foo: 1, bar: 2 }).toInclude("foo");
  > expect({ foo: 1, bar: 2 }).toInclude(["foo", 1]);
  > expect(new Set([{ foo: 1 }, { bar: 2 }])).toInclude({ bar: 2 });
  > ```

**`toMatch(matcher[, options])`**

Expects the received value to match the given `matcher`.

- Parameters

  > - `matcher`: `string | number | RegExp`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect(new Error("foo")).toMatch("foo");
  > expect("a foo value").toMatch(/fo.*ue/);
  > ```

**`toThrow(matcher[, options])`**

Expects the received `Function` to throw an error after being called.

- Parameters

  > - `matcher`: `string | number | RegExp`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect(() => { throw new Error("Woops!") }).toThrow(/woops/i);
  > await expect(Promise.reject("foo")).rejects.toThrow("foo");
  > ```

### DOM matchers

This next list of matchers are node-based and are used to assert the state of a
node or a list of nodes. They generally take a custom selector
as the argument of the `expect` function (although a `Node` or an iterable of `Node`
is also accepted).

**`toBeChecked([options])`**

Expects the received `Target` to be `"checked"`, or to be `"indeterminate"`
if the homonymous option is set to `true`.

- Parameters

  > - `options`: `{ message?: string, indeterminate?: boolean }`
- Examples

  > ```javascript
  > expect("input[type=checkbox]").toBeChecked();
  > ```

**`toBeDisplayed([options])`**

Expects the received `Target` to be *„displayed“*, meaning that:

> - it has a bounding box;
> - it is contained in the root document.

- Parameters

  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect(document.body).toBeDisplayed();
  > expect(document.createElement("div")).not.toBeDisplayed();
  > ```

**`toBeEnabled([options])`**

Expects the received `Target` to be *„enabled“*, meaning that it
matches the `:enabled` pseudo-selector.

- Parameters

  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect("button").toBeEnabled();
  > expect("input[type=radio]").not.toBeEnabled();
  > ```

**`toBeFocused([options])`**

Expects the received `Target` to be *„focused“* in its owner document.

- Parameters

  > - `options`: `{ message?: string }`

**`toBeVisible([options])`**

Expects the received `Target` to be *„visible“*, meaning that:

> - it has a bounding box;
> - it is contained in the root document;
> - it is not hidden by CSS properties.

- Parameters

  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect(document.body).toBeVisible();
  > expect("[style='opacity: 0']").not.toBeVisible();
  > ```

**`toHaveAttribute(attribute, value[, options])`**

Expects the received `Target` to have the given attribute set, and for that
attribute value to match the given `value` if any.

- Parameters

  > - `attribute`: `string`
  > - `value`: `string | number | RegExp`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect("a").toHaveAttribute("href");
  > expect("script").toHaveAttribute("src", "./index.js");
  > ```

**`toHaveClass(className[, options])`**

Expects the received `Target` to have the given class name(s).

- Parameters

  > - `className`: `string | string[]`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect("button").toHaveClass("btn btn-primary");
  > expect("body").toHaveClass(["o_webclient", "o_dark"]);
  > ```

**`toHaveCount(amount[, options])`**

Expects the received `Target` to contain exactly `amount` element(s).
Note that the `amount` parameter can be omitted, in which case the function
will expect *at least* one element.

- Parameters

  > - `amount`: `number`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect(".o_webclient").toHaveCount(1);
  > expect(".o_form_view .o_field_widget").toHaveCount();
  > expect("ul > li").toHaveCount(4);
  > ```

**`toHaveInnerHTML(expected[, options])`**

Expects the `innerHTML` of the received `Target` to match the `expected`
value (upon formatting).

- Parameters

  > - `expected`: `string | RegExp`
  > - `options`: `{ message?: string, type?: "html" | "xml", tabSize?: number, keepInlineTextNodes?: boolean }`
- Examples

  > ```javascript
  > expect(".my_element").toHaveInnerHTML(`
  >     Some <strong>text</strong>
  > `);
  > ```

**`toHaveOuterHTML(expected[, options])`**

Expects the `outerHTML` of the received `Target` to match the `expected`
value (upon formatting).

- Parameters

  > - `expected`: `string | RegExp`
  > - `options`: `{ message?: string, type?: "html" | "xml", tabSize?: number, keepInlineTextNodes?: boolean }`
- Examples

  > ```javascript
  > expect(".my_element").toHaveOuterHTML(`
  >     <div class="my_element">
  >         Some <strong>text</strong>
  >     </div>
  > `);
  > ```

**`toHaveProperty(property, value[, options])`**

Expects the received `Target` to have its given property value match
the given `value`. If no value is given: the matcher will instead check that
the given property exists on the target.

- Parameters

  > - `property`: `string`
  > - `value`: `any`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect("button").toHaveProperty("tabIndex", 0);
  > expect("input").toHaveProperty("ontouchstart");
  > expect("script").toHaveProperty("src", "./index.js");
  > ```

**`toHaveRect(rect[, options])`**

Expects the `DOMRect` of the received `Target` to match the given `rect` object.
The `rect` object can either be:

> - a `DOMRect` object;
> - a CSS selector string (to get the rect of the *only* matching element);
> - a node.

If the resulting `rect` value is a node, then both nodes‘ rects will be compared.

- Parameters

  > - `rect`: `Partial<DOMRect> | Target`
  > - `options`: `{ message?: string, trimPadding?: boolean }`
- Examples

  > ```javascript
  > expect("button").toHaveRect({ x: 20, width: 100, height: 50 });
  > expect("button").toHaveRect(".container");
  > ```

**`toHaveStyle(style[, options])`**

Expects the received `Target` to match the given style properties.

- Parameters

  > - `style`: `string | Record<string, string | RegExp>`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect("button").toHaveStyle({ color: "red" });
  > expect("p").toHaveStyle("text-align: center");
  > ```

**`toHaveText(text[, options])`**

Expects the `text` content of the received `Target` to either:

> - be strictly equal to a given string;
> - match a given regular expression.

Note: `innerHTML` is used to retrieve the text content to take CSS visibility
into account. This also means that text values from child elements will be
joined using a line-break as separator.

- Parameters

  > - `text`: `string | RegExp`
  > - `options`: `{ message?: string, raw?: boolean }`
- Examples

  > ```javascript
  > expect("p").toHaveText("lorem ipsum dolor sit amet");
  > expect("header h1").toHaveText(/odoo/i);
  > ```

**`toHaveValue(value[, options])`**

Expects the value of the received `Target` to either:

> - be strictly equal to a given string or number;
> - match a given regular expression;
> - contain file objects matching the given `files` list.

- Parameters

  > - `value`: `any`
  > - `options`: `{ message?: string }`
- Examples

  > ```javascript
  > expect("input[type=email]").toHaveValue("john@doe.com");
  > expect("input[type=file]").toHaveValue(new File(["foo"], "foo.txt"));
  > expect("select[multiple]").toHaveValue(["foo", "bar"]);
  > ```

### Static methods

The `expect` helper function also contains static methods that can be used to run
through a detached testing flow that isn’t bound to one specific value at a certain
moment.

These methods are mainly used to register steps or errors in the scope of the current
test, and to evaluate them later on.

**`expect.assertions(expected)`**

**`Parameter`**

- **expected** (`number()`) –

Expects the current test to have the `expected` amount of assertions. This
number cannot be less than 1.

> **Bemerkung**
>
> It is generally preferred to use `expect.step()` and `expect.verifySteps()`
> instead as it is more reliable and allows to test more extensively.

**`expect.errors(expected)`**

**`Parameter`**

- **expected** (`number()`) –

Expects the current test to have the `expected` amount of errors.

This also means that from the moment this function is called, the test will
accept that amount of errors before being considered as failed.

**`expect.step(value)`**

**`Parameter`**

- **value** (`unknown()`) –

Registers a step for the current test, that can be consumed by `expect.verifySteps()`.
Unconsumed steps will fail the test.

**`expect.verifyErrors(errors[, options])`**

**`Parameter`**

- **errors** (`unknown[]()`) –
- **options** (`{ message?: string }()`) –

**`Rückgabe`**

`boolean`

Expects the received matchers to match the errors thrown since the start of
the test or the last call to `expect.verifyErrors()`. Calling this matcher
will reset the list of current errors.

```javascript
expect.verifyErrors([/RPCError/, /Invalid domain AST/]);
```

**`expect.verifySteps(steps[, options])`**

**`Parameter`**

- **steps** (`unknown[]()`) –
- **options** (`{ ignoreOrder?: boolean, message?: string, partial?: boolean }()`) –

**`Rückgabe`**

`boolean`

Expects the received steps to be equal to the steps emitted since the start
of the test or the last call to `expect.verifySteps()`. Calling this
matcher will reset the list of current steps.

```javascript
expect.step("web_read_group");
expect.step([1, 2]);
expect.verifySteps(["web_read_group", [1, 2]]);
```

**`expect.waitForErrors(errors[, options])`**

**`Parameter`**

- **errors** (`unknown[]()`) –
- **options** (`{ message?: string }()`) –

**`Rückgabe`**

`Promise<boolean>`

Same as `expect.verifyErrors()`, but will not immediatly fail if errors
are not caught yet, and will instead wait for a certain timeout (default: 2000ms)
to allow errors to be caught later.

Checks are performed initially, at the end of the timeout, and each time an
error is detected.

```javascript
fetch("invalid/url");
await expect.waitForErrors([/RPCError/]);
```

**`expect.waitForSteps(steps[, options])`**

**`Parameter`**

- **steps** (`unknown[]()`) –
- **options** (`{ ignoreOrder?: boolean, message?: string, partial?: boolean }()`) –

**`Rückgabe`**

`Promise<boolean>`

Same as `expect.verifySteps()`, but will not immediatly fail if steps
have not been registered yet, and will instead wait for a certain timeout (default:
2000ms) to allow steps to be registered later.

Checks are performed initially, at the end of the timeout, and each time
a step is registered.

```javascript
// ... step on each 'web_read_group' call
fetch(".../call_kw/web_read_group");
await expect.waitForSteps(["web_read_group"]);
```
