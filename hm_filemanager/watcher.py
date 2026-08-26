import logging
import os
import threading
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import odoo
from odoo.api import Environment, SUPERUSER_ID
from odoo.modules.registry import Registry
from odoo.tools import config

from .index_utils import index_move_tree, index_remove_tree, index_upsert
from .path_utils import get_root, to_relative

_logger = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()


def _is_hidden(abs_path):
    return any(part.startswith(".") for part in abs_path.split(os.sep) if part)


def _run(fn):
    """Open a fresh cursor/env for one event, run fn(env), commit, close.
    There's no request.env outside an HTTP request, and event handling must
    not share a single long-lived cursor across the watcher thread's life."""
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
            _logger.exception("hm_filemanager watcher: failed to process filesystem event")


class _Handler(FileSystemEventHandler):

    def on_created(self, event):
        self._upsert(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._upsert(event.src_path)

    def on_moved(self, event):
        if _is_hidden(event.src_path) and _is_hidden(event.dest_path):
            return
        _run(lambda env: index_move_tree(
            env, to_relative(env, event.src_path), to_relative(env, event.dest_path)
        ))

    def on_deleted(self, event):
        if _is_hidden(event.src_path):
            return
        _run(lambda env: index_remove_tree(env, to_relative(env, event.src_path)))

    def _upsert(self, abs_path):
        if _is_hidden(abs_path):
            return
        _run(lambda env: index_upsert(env, abs_path))


def _delayed_start():
    # post_load fires while Registry.new(dbname) for this very database is
    # still on the call stack - reentering Registry(dbname) here immediately
    # returns a not-yet-finished registry. Retry from a separate thread until
    # module loading has actually finished and cached the ready registry.
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
        _logger.error("hm_filemanager: watcher could not resolve root path, giving up")
        return

    observer = Observer()
    observer.schedule(_Handler(), root, recursive=True)
    observer.daemon = True
    observer.start()
    _logger.info("hm_filemanager: watcher started for %s", root)


def start_watcher():
    """Started via post_load - runs once per process. Only actually starts
    the observer in the gevent/longpolling process (odoo.evented), which is
    the one process Odoo's prefork arbiter never recycles; a thread hanging
    off one of the regular HTTP workers would die whenever that worker gets
    recycled (request-count/memory limits)."""
    global _started
    if not getattr(odoo, "evented", False):
        return
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_delayed_start, daemon=True).start()
