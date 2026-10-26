"""Counts events per key in a window of time, in memory, for the brakes of the share links.

Built like the login cooldown of the core (``res.users._assert_can_auth``): the counters lie in
the memory of the process, so they hold for one worker and are lost at a restart. They protect
against overload, they do not account for anything. Unlike the core's, the counters here are
guarded by a lock, and their number is bounded: a key is made for every address that sends a
request, also for made-up ones.
"""

import collections
import threading
import time

# The most keys kept (the longest unused go first) and the most events kept per key. A limit is
# always lower than the events kept per key, or it could never be reached.
MAX_KEYS = 10_000
MAX_EVENTS = 1_000


class RequestBrake:
    """Events per key within a window of seconds. The window slides: only the last events count."""

    def __init__(self, max_keys=MAX_KEYS, max_events=MAX_EVENTS, clock=time.monotonic):
        self._max_keys = max_keys
        self._max_events = max_events
        self._clock = clock
        self._events = collections.OrderedDict()
        self._lock = threading.Lock()

    def hit(self, key, window):
        """Count one event of the key; the number of events of the key within ``window`` seconds."""
        now = self._clock()
        with self._lock:
            events = self._events.pop(key, None)
            if events is None:
                events = collections.deque(maxlen=self._max_events)
            self._drop_old(events, now - window)
            events.append(now)
            self._events[key] = events  # the newest key goes last, the unused ones first
            while len(self._events) > self._max_keys:
                self._events.popitem(last=False)
            return len(events)

    def count(self, key, window):
        """The events of the key within ``window`` seconds, without counting one."""
        now = self._clock()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                return 0
            self._drop_old(events, now - window)
            return len(events)

    def clear(self, key):
        """Forget the events of the key."""
        with self._lock:
            self._events.pop(key, None)

    @staticmethod
    def _drop_old(events, since):
        while events and events[0] <= since:
            events.popleft()
