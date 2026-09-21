import logging
import os
import threading
import time

import gevent

import odoo
from odoo.api import Environment, SUPERUSER_ID
from odoo.modules.registry import Registry
from odoo.service.db import list_dbs
from odoo.tools import config

from .index_utils import index_move_tree, index_remove_tree, index_upsert
from .path_utils import get_root, is_watcher_suppressed, to_relative
from .vendor import inotify_simple

_logger = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()

_WATCH_FLAGS = (
    inotify_simple.flags.CREATE
    | inotify_simple.flags.DELETE
    | inotify_simple.flags.MODIFY
    | inotify_simple.flags.CLOSE_WRITE
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
    dbname = _resolve_dbname()
    if dbname is None:
        return
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
                # is_watcher_suppressed(): die App macht diese Verschiebung/Umbenennung gerade
                # selbst (rename_entry()/move()-Controller, siehe path_utils.py fuer die
                # ausfuehrliche Begruendung) - Watch-Umschreibung bleibt trotzdem unbedingt
                # noetig (rein interne Buchhaltung fuer kuenftige Ereignisse, keine
                # Index-Aenderung), nur der Index-Abgleich wird der App ueberlassen.
                if not is_watcher_suppressed(old_abs) and not is_watcher_suppressed(abs_path):
                    _move(old_abs, abs_path)
                if is_dir:
                    # Rewrite the still-open watches for this subtree's own
                    # descendants to their new absolute paths.
                    prefix = old_abs + os.sep
                    for wd, path in list(wd_to_path.items()):
                        if path == old_abs or path.startswith(prefix):
                            wd_to_path[wd] = abs_path + path[len(old_abs):]
            else:
                # Moved in from outside the watched tree - treat like new. Betrifft u.a.
                # index_restore_tree() (Papierkorb -> Baum): die App unterdrueckt abs_path fuer
                # die Dauer ihrer eigenen Indexpflege - Watches fuer einen Ordner trotzdem immer
                # registrieren (sonst blieben dessen kuenftige Aenderungen unbeobachtet), nur
                # der Erstindexierungs-Aufruf entfaellt.
                if is_watcher_suppressed(abs_path):
                    if is_dir:
                        _add_watches(inotify, wd_to_path, abs_path)
                elif is_dir:
                    _bootstrap_subtree(inotify, wd_to_path, abs_path)
                else:
                    _upsert(abs_path)
        elif event.mask & flags.CREATE:
            if is_watcher_suppressed(abs_path):
                if is_dir:
                    _add_watches(inotify, wd_to_path, abs_path)
            elif is_dir:
                _bootstrap_subtree(inotify, wd_to_path, abs_path)
            else:
                _upsert(abs_path)
        elif event.mask & flags.MODIFY:
            if not is_dir and not is_watcher_suppressed(abs_path):
                _upsert(abs_path)
        elif event.mask & flags.CLOSE_WRITE:
            # Live per inotifywait am Host bestaetigt (2026-09-16): dieser CIFS-Mount liefert
            # fuer eine neu geschriebene Datei UEBERHAUPT KEIN CREATE, nur CLOSE_WRITE - ein
            # bekanntes, dateisystemabhaengiges Verhalten bei Netzwerk-Dateisystemen (inotify
            # ist urspruenglich fuer lokale Dateisysteme entworfen, Unterstuetzung/genaue
            # Ereignisauswahl bei NFS/CIFS ist unvollstaendig und variiert). Ohne diesen Zweig
            # bekam der Watcher fuer Uploads auf diese drei SMB-Freigaben gar kein
            # Indexierungs-Ereignis - live als Bug gefunden: Upload lief fehlerfrei durch, die
            # Datei blieb aber dauerhaft unindexiert (kein taeglicher Reconciler-Lauf haette das
            # zeitnah aufgeholt). Auf Dateisystemen, die zusaetzlich auch CREATE/MODIFY liefern,
            # ist dieser Zweig redundant, aber harmlos - _upsert() ist bereits idempotent
            # (dasselbe Verhalten wie beim bestehenden CREATE+MODIFY-Doppelaufruf auf lokalen
            # Dateisystemen).
            if not is_dir and not is_watcher_suppressed(abs_path):
                _upsert(abs_path)
        elif event.mask & flags.DELETE:
            if not is_watcher_suppressed(abs_path):
                _remove(abs_path)
        elif event.mask & flags.DELETE_SELF:
            wd_to_path.pop(event.wd, None)

    # Anything left here was moved outside the watched tree entirely - the
    # matching MOVED_TO, if any, would already have arrived in this same batch.
    # is_watcher_suppressed(): betrifft z.B. index_trash_tree() (Baum -> Papierkorb, siehe
    # path_utils.py) - die App verschiebt selbst und pflegt den Index selbst nach.
    for old_abs in moved_from.values():
        if is_watcher_suppressed(old_abs):
            continue
        _remove(old_abs)


def _watch_loop(root_abs):
    inotify = inotify_simple.INotify()
    wd_to_path = {}
    _add_watches(inotify, wd_to_path, root_abs)
    _logger.info("int_filemanager: watcher active for %s (%d directories)", root_abs, len(wd_to_path))

    while True:
        # A blocking read here is fine in both startup modes: in a plain
        # thread (workers=0) it just blocks that thread, and in the gevent
        # process (workers>0) it's cooperative because this loop runs
        # inside a real greenlet (gevent.spawn) - see start_watcher().
        events = inotify.read()
        try:
            _process_batch(events, inotify, wd_to_path)
        except Exception:
            _logger.exception("int_filemanager watcher: error processing event batch")


def _watcher_enabled(env):
    # Enabled unless explicitly turned off, so an unset parameter (the
    # common case) never accidentally disables production indexing - and a
    # capitalized "True"/"1" typed by hand in Settings still means enabled.
    value = env["ir.config_parameter"].sudo().get_param("int_filemanager.watcher_enabled", "true")
    return str(value).strip().lower() not in ("false", "0", "no", "off")


def _resolve_dbname():
    # config["db_name"] is only populated when Odoo was started with an
    # explicit -d/--database (or db_name= in the config file). A deployment
    # that instead relies on Odoo's normal single/multi-tenant DB discovery
    # (our production setup: db_name unset, exactly one real database on the
    # Postgres server) would otherwise IndexError here on every single
    # startup - list_dbs() is the same discovery Odoo itself uses for the
    # database-selector page; force=True bypasses the list_db config gate,
    # which only matters for that public HTTP page, not this internal check.
    names = config["db_name"]
    if names:
        return names[0]
    candidates = list_dbs(force=True)
    if len(candidates) != 1:
        _logger.error(
            "int_filemanager: watcher could not determine a single database to watch "
            "(db_name unset in config, candidates=%s), not starting",
            candidates,
        )
        return None
    return candidates[0]


def _run_watcher():
    # post_load fires while Registry.new(dbname) for this very database is
    # still on the call stack - reentering Registry(dbname) here immediately
    # returns a not-yet-finished registry. Retry until module loading has
    # actually finished and cached the ready registry. The
    # int_filemanager.watcher_enabled check has to live here rather than in
    # start_watcher() for the same reason: no cursor is available yet at
    # post_load time, only once this retry loop gets a working registry.
    dbname = _resolve_dbname()
    if dbname is None:
        return
    root = None
    for _attempt in range(30):
        try:
            reg = Registry(dbname)
            with reg.cursor() as cr:
                env = Environment(cr, SUPERUSER_ID, {})
                if not _watcher_enabled(env):
                    _logger.info(
                        "int_filemanager: watcher disabled via int_filemanager.watcher_enabled, not starting"
                    )
                    return
                root = get_root(env)
            break
        except Exception:
            time.sleep(1)
    else:
        _logger.error("int_filemanager: watcher could not resolve root path, giving up")
        return

    _watch_loop(root)


def start_watcher():
    """Started via post_load - runs once per process. Picks its startup
    strategy from the actual `workers` setting so the same code works
    unchanged on any deployment, not just this one:

    - workers=0 (single threaded process, no recycling, no gevent
      monkey-patching anywhere): a plain daemon thread is simplest and
      just works.
    - workers>0 (prefork mode): only the gevent/longpolling process
      (odoo.evented) is stable enough to anchor a persistent loop to -
      Odoo's arbiter periodically recycles the regular HTTP/cron workers
      (request-count/memory limits), which would kill a thread hanging
      off one of them. But that same gevent process has
      gevent.monkey.patch_all() applied, under which a plain
      threading.Thread doing blocking reads never gets woken up by
      gevent's event loop - verified empirically, the observer starts but
      silently never receives a single event. Needs a real greenlet
      (gevent.spawn) instead. The other, non-evented workers under
      workers>0 skip starting anything at all.

    The int_filemanager.watcher_enabled kill switch is checked later, inside
    _run_watcher() once a cursor is available - not here, see its docstring."""
    global _started
    workers = config["workers"] or 0
    if workers > 0 and not getattr(odoo, "evented", False):
        return
    with _lock:
        if _started:
            return
        _started = True
    if workers == 0:
        threading.Thread(target=_run_watcher, daemon=True).start()
    else:
        gevent.spawn(_run_watcher)
