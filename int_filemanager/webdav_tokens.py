import secrets
import threading
from datetime import datetime, timedelta

_lock = threading.Lock()
_tokens = {}  # token -> (rel_path, expiry)
_locks = {}  # rel_path -> (lock_token, expiry)


def issue(rel_path, ttl_seconds=8 * 3600):
    """Create a fresh, single-purpose token bound to rel_path. Deliberately
    minted new on every open rather than reused across sessions - besides
    being the more secure default, this sidesteps a real issue found while
    testing against Excel 365: Windows caches WebDAV resource state per URL
    across separate ms-word/ms-excel "ofe" sessions, and reusing the same
    URL for a file that has since changed made Excel show a spurious
    "update required" prompt. A URL Windows has never seen before avoids it."""
    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(seconds=ttl_seconds)
    with _lock:
        _cleanup_locked(_tokens)
        _tokens[token] = (rel_path, expiry)
    return token


def resolve(token):
    """Returns rel_path, or None if the token is unknown or expired."""
    with _lock:
        entry = _tokens.get(token)
        if entry is None:
            return None
        rel_path, expiry = entry
        if expiry < datetime.now():
            del _tokens[token]
            return None
        return rel_path


def lock(rel_path, ttl_seconds=600):
    """WebDAV LOCK - single exclusive lock per path, no queueing. Not
    enforced against non-WebDAV writers (the app's own controllers, the
    filesystem watcher) - documented limitation, same as the web-filemanager
    plan's "no cross-layer lock" trade-off. Returns the lock token."""
    token = "opaquelocktoken:%s" % secrets.token_hex(16)
    expiry = datetime.now() + timedelta(seconds=ttl_seconds)
    with _lock:
        _cleanup_locked(_locks)
        _locks[rel_path] = (token, expiry)
    return token


def unlock(rel_path, lock_token):
    with _lock:
        entry = _locks.get(rel_path)
        if entry and entry[0] == lock_token:
            del _locks[rel_path]


def _cleanup_locked(store):
    now = datetime.now()
    for key in [k for k, (_, expiry) in store.items() if expiry < now]:
        del store[key]
