<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/unit_testing/hoot.html · abgerufen 2026-10-02 -->

# HOOT – Teil 4/5: DOM: interaction helpers

## DOM: interaction helpers

Along with querying elements, it is often required to interact with them.
As such, Hoot provides helpers to simulate various user interactions on elements.

These can be split into 2 types based on their parameters: **pointer-based** interaction
helpers, and the **other** ones.

### Pointer interaction helpers:

Pointer interaction helpers (such as `click()` or `drag()`) will simulate
actual pointer movements and events on the given target, and on any previous element
the pointer was *supposed* to have been.

**`check(target[, options])`**

Ensures that the given `Target` is checked.

If it is not checked, a `click()` is simulated on the input.
If the input is still not checked after the click, an error is thrown.

**`Rückgabe`**

`Promise<Event[]>`

```javascript
check("input[type=checkbox]"); // Checks the first <input> checkbox element
```

**`click(target[, options])`**

Performs a click sequence on the given `Target`.

The event sequence is as follows:

> - `pointerdown`
> - [desktop] `mousedown`
> - [touch] `touchstart`
> - [target is not active element] `blur`
> - [target is focusable] `focus`
> - `pointerup`
> - [desktop] `mouseup`
> - [touch] `touchend`
> - `click`
> - `dblclick` if click is not prevented & current click count is even

**`Rückgabe`**

`Promise<Event[]>`

```javascript
click("button"); // Clicks on the first <button> element
```

**`dblclick(target[, options])`**

Performs two `click()` sequences on the given `Target`.

**`Rückgabe`**

`Promise<Event[]>`

```javascript
dblclick("button"); // Double-clicks on the first <button> element
```

**`drag(target[, options])`**

Starts a drag sequence on the given `Target`.

Returns a set of helper functions to direct the sequence:

> - `moveTo`: moves the pointer to the given target;
> - `drop`: drops the dragged element on the given target (if any);
> - `cancel`: cancels the drag sequence.

**`Rückgabe`**

`Promise<DragHelpers>`

```javascript
drag(".card:first").drop(".card:last"); // Drags the first card onto the last one

drag(".card:first").moveTo(".card:last").drop(); // Same as above

const { cancel, moveTo } = await drag(".card:first"); // Starts the drag sequence
moveTo(".card:eq(3)"); // Moves the dragged card to the 4th card
cancel(); // Cancels the drag sequence
```

**`hover(target[, options])`**

Performs a hover sequence on the given `Target`.

The event sequence is as follows:

> - `pointerover`
> - [desktop] `mouseover`
> - `pointerenter`
> - [desktop] `mouseenter`
> - `pointermove`
> - [desktop] `mousemove`
> - [touch] `touchmove`

**`Rückgabe`**

`Promise<Event[]>`

```javascript
hover("button"); // Hovers the first <button> element
```

**`pointerDown(target[, options])`**

Performs a pointer down on the given `Target`.

The event sequence is as follows:

> - `pointerdown`
> - [desktop] `mousedown`
> - [touch] `touchstart`
> - [target is not active element] `blur`
> - [target is focusable] `focus`

**`Rückgabe`**

`Promise<Event[]>`

```javascript
pointerDown("button"); // Focuses to the first <button> element
```

**`pointerUp(target[, options])`**

Performs a pointer up on the given `Target`.

The event sequence is as follows:

> - `pointerup`
> - [desktop] `mouseup`
> - [touch] `touchend`

**`Rückgabe`**

`Promise<Event[]>`

```javascript
pointerUp("body"); // Triggers a pointer up on the <body> element
```

**`scroll(target, position[, options])`**

Performs a scroll event sequence on the given `Target`.

The event sequence is as follows:

> - [desktop] `wheel`
> - `scroll`

**`Rückgabe`**

`Promise<Event[]>`

```javascript
scroll("body", { y: 0 }); // Scrolls to the top of <body>
```

**`setInputRange(target, value[, options])`**

Sets the given value to the current „input[type=range]“ `Target`.

The event sequence is as follows:

> - `pointerdown`
> - `input`
> - `change`
> - `pointerup`

**`Rückgabe`**

`Promise<Event[]>`

**`uncheck(target[, options])`**

Ensures that the given `Target` is unchecked.

If it is checked, a `click()` is triggered on the input.
If the input is still checked after the click, an error is thrown.

**`Rückgabe`**

`Promise<Event[]>`

```javascript
uncheck("input[type=checkbox]"); // Unchecks the first <input> checkbox element
```

### Other interaction helpers:

Other interaction helpers will not have a `target` parameter. It is not needed,
since pressing keys on a keyboard (for example) is done on the current *active element*.

**`clear([options])`**

Clears the value of the current *active element*.

This is done using the following sequence:

> - pressing `"Control"` & `"A"` to select the whole value;
> - pressing `"Backspace"` to delete the value;
> - (optional) triggering a `"change"` event by pressing `"Enter"`.

**`Rückgabe`**

`Promise<Event[]>`

```javascript
clear(); // Clears the value of the current active element
```

**`edit(value[, options])`**

Combination of `clear()` and `fill()`:

> - first, clears the input value (if any)
> - then fills the input with the given value

**`Rückgabe`**

`Promise<Event[]>`

```javascript
fill("foo"); // Types "foo" in the active element
edit("Hello World"); // Replaces "foo" by "Hello World"
```

**`fill(value[, options])`**

Fills the current *active element* with the given `value`. This helper is intended
for `<input>` and `<textarea>` elements, with the exception of `"checkbox"` and
`"radio"` types, which should be selected using the `check` helper.

If the target is an editable input, its string `value` will be input one character
at a time, each generating its corresponding keyboard event sequence. This behavior
can be overridden by passing the `instantly` option, which will instead simulate
a `control` + `v` keyboard sequence, resulting in the whole text being pasted.

Note that the given value is appended to the current value of the element.

If the active element is a `<input type="file"/>`, the `value` should be a
`File`/list of `File` object(s).

**`Rückgabe`**

`Promise<Event[]>`

```javascript
fill("Hello World"); // Types "Hello World" in the active element
fill("Hello World", { instantly: true }); // Pastes "Hello World" in the active element
fill(new File(["Hello World"], "hello.txt")); // Uploads a file named "hello.txt" with "Hello World" as content
```

**`keyDown(keyStrokes[, options])`**

Performs a key down sequence on the current *active element*.

The event sequence is as follows:

> - `keydown`

Additional actions will be performed depending on the key pressed:

> - `Tab`: focus next (or previous with `shift`) focusable element;
> - `c`: copy current selection to clipboard;
> - `v`: paste current clipboard content to current element;
> - `Enter`: submit the form if the target is a `<button type="button">` or
>   a `<form>` element, or trigger a `change` event on the target if it is
>   an `<input>` element;
> - `Space`: trigger a `click` event on the target if it is an `<input type="checkbox">`
>   element.

**`Rückgabe`**

`Promise<Event[]>`

```javascript
keyDown(" "); // Space key
```

**`keyUp(keyStrokes[, options])`**

Performs a key up sequence on the current *active element*.

The event sequence is as follows:

> - `keyup`

**`Rückgabe`**

`Promise<Event[]>`

```javascript
keyUp("Enter");
```

**`leave([options])`**

Performs a leave sequence on the current `Window`.

The event sequence is as follows:

> - `pointermove`
> - [desktop] `mousemove`
> - [touch] `touchmove`
> - `pointerout`
> - [desktop] `mouseout`
> - `pointerleave`
> - [desktop] `mouseleave`

**`Rückgabe`**

`Promise<Event[]>`

```javascript
leave("button"); // Moves out of <button>
```

**`press(keyStrokes[, options])`**

Performs a keyboard event sequence on the current *active element*.

The event sequence is as follows:

> - `keydown`
> - `keyup`

**`Rückgabe`**

`Promise<Event[]>`

```javascript
pointerDown("button[type=submit]"); // Moves focus to <button>
keyDown("Enter"); // Submits the form

keyDown("Shift+Tab"); // Focuses previous focusable element

keyDown(["ctrl", "v"]); // Pastes current clipboard content
```

**`resize([dimensions[, options]])`**

Performs a resize event sequence on the current `Window`.

The event sequence is as follows:

> - `resize`

The target will be resized to the given dimensions, enforced by `!important` style
attributes.

**`Rückgabe`**

`Promise<Event[]>`

```javascript
resize("body", { width: 1000, height: 500 }); // Resizes <body> to 1000x500
```

**`select(value[, options])`**

Performs a selection event sequence on the current active element. This helper
is intended for `<select>` elements only.

The event sequence is as follows:

> - `change`

**`Rückgabe`**

`Promise<Event[]>`

```javascript
click("select[name=country]"); // Focuses <select> element
select("belgium"); // Selects the <option value="belgium"> element
```

**`setInputFiles(files[, options])`**

Gives the given `File` list to the current file input. This helper only
works if a file input has been previously interacted with (by clicking on it).

**`Rückgabe`**

`Promise<Event[]>`

**`unload([options])`**

Triggers a „beforeunload“ event on the current `Window`.

**`Rückgabe`**

`Promise<Event[]>`
