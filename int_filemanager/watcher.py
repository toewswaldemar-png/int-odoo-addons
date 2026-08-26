import logging
import os
import threading
import time

import gevent
import inotify_simple

import odoo
from odoo.api import Environment, SUPERUSER_ID
from odoo.modules.registry import Registry
from odoo.tools import config

from .index_utils import index_move_tree, index_remove_tree, index_upsert
from .path_utils import get_root, to_relative

_logger = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()

_WATCH_FLAGS = (
    inotify_simple.flags.CREATE
    | inotify_simple.flags.DELETE
    | inotify_simple.flags.MODIFY
    | inotify_simple.flags.MOVED_FROM
    | inotify_simple.flags.MOVED_TO
    | inotify_simple.flags.DELETE_SELF
)


def _is_hidden(name):
    return name.startswith(".")


def _run(fn):
    """Open a fresh cursor/env for one event, run fn(env), commit, close.
    There's no request.env outside an HTTP request, and event handling must
    not share a single long-lived cursor across the watcher's lifetime."""
    dbname = config["db_name"][0]
    reg = Registry(dbname)
    with reg.cursor() as cr:
        env = Environment(cr, SUPERUSER_ID, {})
        try:
            fn(env)
            cr.commit()
        except FileNotFoundError:
            # Transient entries (editor lock files, atomic-save temp files)
            # can vanish between the event firing and us reading them.
            pass
        except Exception:
            _logger.exception("int_filemanager watcher: failed to process filesystem event")


def _upsert(abs_path):
    _run(lambda env: index_upsert(env, abs_path))


def _move(old_abs, new_abs):
    _run(lambda env: index_move_tree(env, to_relative(env, old_abs), to_relative(env, new_abs)))


def _remove(abs_path):
    _run(lambda env: index_remove_tree(env, to_relative(env, abs_path)))


def _add_watches(inotify, wd_to_path, root_abs):
    """Register watches for root_abs and every subdirectory, without
    touching the index - used once at startup, where the existing full
    scan (manual or the daily cron) is already the source of truth."""
    for dirpath, dirnames, _filenames in os.walk(root_abs):
        dirnames[:] = [d for d in dirnames if not _is_hidden(d)]
        wd = inotify.add_watch(dirpath, _WATCH_FLAGS)
        wd_to_path[wd] = dirpath


def _bootstrap_subtree(inotify, wd_to_path, root_abs):
    """Like _add_watches, but also indexes everything found - used when a
    subtree appears live (a directory CREATE/MOVED_TO event) and may already
    contain content nothing else has indexed yet."""
    _upsert(root_abs)
    for dirpath, dirnames, filenames in os.walk(root_abs):
        dirnames[:] = [d for d in dirnames if not _is_hidden(d)]
        wd = inotify.add_watch(dirpath, _WATCH_FLAGS)
        wd_to_path[wd] = dirpath
        for name in dirnames + [f for f in filenames if not _is_hidden(f)]:
            _upsert(os.path.join(dirpath, name))


def _process_batch(events, inotify, wd_to_path):
    flags = inotify_simple.flags
    moved_from = {}

    for event in events:
        if event.mask & flags.IGNORED:
            wd_to_path.pop(event.wd, None)
            continue

        dir_path = wd_to_path.get(event.wd)
        if dir_path is None or _is_hidden(event.name):
            continue
        abs_path = os.path.join(dir_path, event.name)
        is_dir = bool(event.mask & flags.ISDIR)

        if event.mask & flags.MOVED_FROM:
            moved_from[event.cookie] = abs_path
        elif event.mask & flags.MOVED_TO:
            old_abs = moved_from.pop(event.cookie, None)
            if old_abs is not None:
                _move(old_abs, abs_path)
                if is_dir:
                    # Rewrite the still-open watches for this subtree's own
                    # descendants to their new absolute paths.
                    prefix = old_abs + os.sep
                    for wd, path in list(wd_to_path.items()):
                        if path == old_abs or path.startswith(prefix):
                            wd_to_path[wd] = abs_path + path[len(old_abs):]
            else:
                # Moved in from outside the watched tree - treat like new.
                if is_dir:
                    _bootstrap_subtree(inotify, wd_to_path, abs_path)
                else:
                    _upsert(abs_path)
        elif event.mask & flags.CREATE:
            if is_dir:
                _bootstrap_subtree(inotify, wd_to_path, abs_path)
            else:
                _upsert(abs_path)
        elif event.mask & flags.MODIFY:
            if not is_dir:
                _upsert(abs_path)
        elif event.mask & flags.DELETE:
            _remove(abs_path)
        elif event.mask & flags.DELETE_SELF:
            wd_to_path.pop(event.wd, None)

    # Anything left here was moved outside the watched tree entirely - the
    # matching MOVED_TO, if any, would already have arrived in this same batch.
    for old_abs in moved_from.values():
        _remove(old_abs)


def _watch_loop(root_abs):
    inotify = inotify_simple.INotify()
    wd_to_path = {}
    _add_watches(inotify, wd_to_path, root_abs)
    _logger.info("int_filemanager: watcher active for %s (%d directories)", root_abs, len(wd_to_path))

    while True:
        # A blocking read here is fine - gevent's monkey patching makes it
        # cooperative *because* this whole loop runs inside a real greenlet
        # (gevent.spawn), unlike a plain threading.Thread, which is exactly
        # what silently never received events in this same process.
        events = inotify.read()
        try:
            _process_batch(events, inotify, wd_to_path)
        except Exception:
            _logger.exception("int_filemanager watcher: error processing event batch")


def _run_watcher():
    # post_load fires while Registry.new(dbname) for this very database is
    # still on the call stack - reentering Registry(dbname) here immediately
    # returns a not-yet-finished registry. Retry until module loading has
    # actually finished and cached the ready registry.
    dbname = config["db_name"][0]
    root = None
    for _attempt in range(30):
        try:
            reg = Registry(dbname)
            with reg.cursor() as cr:
                env = Environment(cr, SUPERUSER_ID, {})
                root = get_root(env)
            break
        except Exception:
            time.sleep(1)
    else:
        _logger.error("int_filemanager: watcher could not resolve root path, giving up")
        return

    _watch_loop(root)


def start_watcher():
    """Started via post_load - runs once per process. Only actually starts
    in the gevent/longpolling process (odoo.evented), the one process
    Odoo's prefork arbiter never recycles.

    Must run as a gevent greenlet (gevent.spawn), not a plain
    threading.Thread: this process has gevent.monkey.patch_all() applied,
    and a plain OS thread doing blocking reads never gets woken up by
    gevent's event loop - verified empirically, the observer starts but
    silently never receives a single event."""
    global _started
    if not getattr(odoo, "evented", False):
        return
    with _lock:
        if _started:
            return
        _started = True
    gevent.spawn(_run_watcher)
