<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/unit_testing/hoot.html · abgerufen 2026-10-02 -->

# HOOT – Teil 5/5: Mocks

## Mocks

By default, a lot of low-level features are mocked by Hoot: `clipboard`, `fetch`, `localStorage`,
etc. These mocks are intended to not produce any side-effect that would disturb the test runner
or the context of other tests, while still providing the same interface to allow tests to rely
on these features seamlessly.

There is also a need (most of the time) to force actions on these features or change their
behavior for a test, so there exist helpers to interact with these mocked features. The following
sections will list the main mocked features and the means to interact with them.

### Time

Most asynchronous features are mocked: „timers“ (`setTimeout`, `setInterval` and
`requestAnimationFrame`), `Date` and `performance` all behave normally, but can be canceled or
sped-up manually to considerably shorten the actual duration of tests. For example: all „timers“
are canceled at the end of each test to avoid side-effects for the next one.

> > **Wichtig**
> >
> > There are 2 main timing behaviors that are *NOT* mocked:
> >
> > > - `Promise` objects and related API;
> > > - OWL’s timer functions: to wait for OWL rendering functions, you’ll have
> > >   to resort to the `animationFrame` helper.

#### Related helpers

**`advanceFrame(frameCount)`**

Calls `advanceTime` with the duration it would take for a given `frameCount`
amount of frames to have rendered in the UI (i.e. (1000 / current FPS) x frame count).

**`advanceTime(ms)`**

Advances the current time by the given amount of milliseconds. This will
affect all timeouts, intervals, animations and date objects.

It returns a promise resolved after all related callbacks have been executed.

**`Rückgabe`**

`Promise<number>` time consumed by timers (in ms)

**`animationFrame()`**

Returns a promise resolved after the next animation frame, typically allowing
Owl components to render.

**`Rückgabe`**

`Promise<void>`

**`cancelAllTimers()`**

Cancels all current timeouts, intervals and animations.

**`delay()`**

Returns a promise resolved after a given amount of milliseconds (default to `0`).

```javascript
await delay(1000); // waits for 1 second
```

**`Rückgabe`**

`Promise<void>`

**`microTick()`**

Returns a promise resolved after the next microtask tick.

**`Rückgabe`**

`Promise<void>`

**`mockDate(date[, tz])`**

Mocks the current date and time, and also the time zone if any.

Date can either be an object describing the date and time to mock, or a
string in SQL or ISO format (time and millisecond values can be omitted).
See `mockTimeZone()` for the time zone params.

```javascript
mockDate("2023-12-25T20:45:00"); // 2023-12-25 20:45:00 UTC
mockDate({ year: 2023, month: 12, day: 25, hour: 20, minute: 45 }); // same as above
mockDate("2019-02-11 09:30:00.001", +2);
```

**`mockTimeZone(tz)`**

Mocks the current time zone.

Time zone can either be a locale, a time zone or an offset.

Returns a function restoring the default zone.

```javascript
mockTimeZone(+1); // UTC + 1
mockTimeZone("Europe/Brussels"); // UTC + 1 (or UTC + 2 in summer)
mockTimeZone("ja-JP"); // UTC + 9
```

**`runAllTimers([preventTimers])`**

Calculates the amount of time needed to run all current timeouts, intervals and
animations, and then advances the current time by that amount.

**`Rückgabe`**

`Promise<void>`

**`setFrameRate(frameRate)`**

Sets the current frame rate (in fps) used by animation frames (default to 60fps).

**`tick()`**

Returns a promise resolved after the next task tick.

**`Rückgabe`**

`Promise<void>`

**`waitUntil(predicate[, options])`**

Returns a promise fulfilled when the given `predicate` returns a truthy value, with the value of
the promise being the return value of the `predicate`.

The `predicate` is run once initially and then each time the DOM is mutated (see `observe` for
more information).

The promise automatically rejects after a given `timeout` (defaults to 5 seconds).

**`Rückgabe`**

`Promise<unknown>` promise with the return value of the predicate

### Network

In general, we don’t want to perform actual network calls in tests. To ensure this, all calls
to `fetch` and `XMLHttpRequest` have been re-routed to a function given to
`mockFetch()`.

> **Bemerkung**
>
> In Odoo, this is generally implicitly handled by a [MockServer](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/unit_testing/mock_server.html#mock-server-configuration)
> which is spawned by the mock environment, i.e. any time a component is rendered using the
> [mountWithCleanup](https://www.odoo.com/documentation/19.0/de/developer/reference/frontend/unit_testing/web_helpers.html#web-test-helpers-components) helper.

#### Related helpers

**`mockFetch([fetchFn])`**

Mocks the fetch function by replacing it with a given `fetchFn`.

The return value of `fetchFn` is used as the response of the mocked fetch, or
wrapped in a `MockResponse` object if it does not meet the required format.

```javascript
mockFetch((input, init) => {
    if (input === "/../web_search_read") {
        return { records: [{ id: 3, name: "john" }] };
    }
    // ...
});
mockFetch((input, init) => {
    if (input === "/translations") {
        const translations = {
            "Hello, world!": "Bonjour, monde !",
            // ...
        };
        return new Response(JSON.stringify(translations));
    }
});
```

**`mockWebSocket([onWebSocketConnected])`**

Activates mock WebSocket classe:

> - websocket connections will be handled by `window.fetch`
>   (see `mockFetch()`);
> - the `onWebSocketConnected` callback will be called after a websocket has been created.

**`mockWorker([onWorkerConnected])`**

Activates mock `Worker` and `SharedWorker` classes:

> - actual code fetched by worker URLs will then be handled by `window.fetch`
>   (see `mockFetch()`);
> - the `onWorkerConnected` callback will be called after a worker has been created.

### Notable global features

The following features may not have any specific mocked feature added, but they do work as
expected without changing the actual properties they were meant to:

- [Document](https://developer.mozilla.org/en-US/docs/Web/API/Document)

  > Both `title` and `cookie` can be set and read without changing the actual properties
  > of the current document.
- [History](https://developer.mozilla.org/en-US/docs/Web/API/History)

  > The `history` API is mocked and bound to the `mockLocation` object to return the same
  > values and provide consistency.
- [Location](https://developer.mozilla.org/en-US/docs/Web/API/Location)

  > Hoot returns a `mockLocation` object to use instead of `window.location`, but this relies on
  > the use of an indirection in the actual production code.
  >
  > > **Wichtig**
  > >
  > > This feature will only work if an indirection is set between production code and
  > > calls to `window.location`. In Odoo, it works because the `@web/core/browser` module
  > > provides such an indirection, and that module is mocked in test environments to redirect
  > > to the `mockLocation` object.
- [Navigator](https://developer.mozilla.org/en-US/docs/Web/API/Navigator)

  > Most used navigator features, such as the `clipboard` API and `userAgent`, have
  > been mocked to hijack their actual behaviors. Its `permissions` object has been bound
  > to a global mock of the permissions API.
- [Notification](https://developer.mozilla.org/en-US/docs/Web/API/Notification)

  > Notifications have been mocked, with the „notification“ permissions bound to the global
  > mocked permissions API.
- [Permissions](https://developer.mozilla.org/en-US/docs/Web/API/Permissions_API)

  > Permissions can enable or disable other APIs by being given the `"granted"`
  > or `"denied"` statuses. This can be done through the `mockPermission` helper.
- [Storage](https://developer.mozilla.org/en-US/docs/Web/API/Storage)

  > `localStorage` and `sessionStorage` both point to „virtual“ storages.
- [Touch](https://developer.mozilla.org/en-US/docs/Web/API/Touch_events)

  > Touch features can be force-activated or deactivated globally for a given test/suite
  > using the `mockTouch()` helper. It will mock both the presence
  > of touch handlers like `ontouchstart` on window, as well as the `"pointer"` media
  > being set to `fine` or `coarse`.

#### Related helpers

**`mockPermission(name[, value])`**

Sets the given value for the given permission. This allows to enable or prevent
certain APIs (see the [Permissions API](https://developer.mozilla.org/en-US/docs/Web/API/Permissions_API)).

```javascript
// Prevents the whole notification API from working
mockPermission("notifications", "denied");
```

**`mockTouch(setTouch)`**

Toggles touch features on or off in the current `Window`.
