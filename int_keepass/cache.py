"""What was read from a database, kept for a while in the memory of one worker; no Odoo imports."""

import hashlib
import os
import threading
import time


def cache_key(path, password):
    """Key of a database in its current state, opened with this password.

    The state (path, modification time, size) is part of the key: a changed file is read again.
    Raises ``FileNotFoundError`` when the file does not exist.
    """
    stat = os.stat(path)
    digest = hashlib.sha256()
    for part in (os.path.realpath(path), str(stat.st_mtime_ns), str(stat.st_size), password):
        digest.update(part.encode())
        digest.update(b"\0")
    return digest.hexdigest()


def account_key(url, email, password):
    """Key of a Vaultwarden account opened with this password; the server has no file state to add."""
    digest = hashlib.sha256()
    for part in (url.rstrip("/"), email.strip().lower(), password):
        digest.update(part.encode())
        digest.update(b"\0")
    return digest.hexdigest()


class MetadataCache:
    """Entries expire ``ttl`` seconds after they were put in, however often they are used; the number is bounded.

    Only the groups and entries without passwords are put in, never the decrypted database.
    Each worker has its own cache: a request that lands in another worker reads the file once.
    """

    def __init__(self, max_items=8, clock=time.monotonic):
        self._items = {}
        self._max_items = max_items
        self._clock = clock
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            self._expire()
            item = self._items.get(key)
            return None if item is None else item[1]

    def put(self, key, value, ttl):
        with self._lock:
            self._expire()
            self._items[key] = (self._clock() + ttl, value)
            while len(self._items) > self._max_items:
                del self._items[min(self._items, key=lambda k: self._items[k][0])]

    def drop(self, key):
        with self._lock:
            self._items.pop(key, None)

    def clear(self):
        with self._lock:
            self._items.clear()

    def __len__(self):
        with self._lock:
            self._expire()
            return len(self._items)

    def _expire(self):
        now = self._clock()
        for key in [key for key, (expires, _value) in self._items.items() if expires <= now]:
            del self._items[key]
