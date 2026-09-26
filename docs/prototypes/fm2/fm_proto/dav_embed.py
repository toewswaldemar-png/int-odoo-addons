"""Prototyp (Konzept 19.12): `odoo fmdav` ohne eigenen Container, gestartet aus Odoo selbst.

Aktiv nur, wenn fm_proto als server-weites Modul geladen wird (`--load=base,rpc,web,fm_proto`) und FM_DAV_EMBED=1.
post_load (odoo/modules/module.py:512) ruft `start()` in jedem Prozess, der die server-weiten Module laedt.

- workers=0 (ThreadedServer): WebDAV-Server als Thread im Odoo-Prozess, nach dem Muster von bus.ImDispatch
  (addons/bus/models/bus.py: eigener Thread, Wiederanlauf-Schleife, CommonServer.on_stop).
- workers>0 (PreforkServer): `odoo fmdav` als Kindprozess des Masters (wie long_polling_spawn, server.py:944), Stopp
  ueber CommonServer.on_stop. Threads im Master waeren wegen fork() der Worker gefaehrlich.
"""
import logging
import os
import subprocess
import sys
import threading
import time

_logger = logging.getLogger("odoo.fmdav.embed")
_state = {"thread": None, "proc": None, "server": None, "stop": threading.Event()}


def _opts():
    return {
        "port": int(os.environ.get("FM_DAV_EMBED_PORT", "8080")),
        "root": int(os.environ.get("FM_DAV_ROOT_ID", "0")),
        "accel": os.environ.get("FM_DAV_ACCEL", ""),
        "anon_ips": [ip for ip in os.environ.get("FM_DAV_ANON_IPS", "").split(",") if ip],
        "anon_login": os.environ.get("FM_DAV_ANON_LOGIN", ""),
    }


def start():
    import odoo
    import odoo.cli
    from odoo.tools import config
    if os.environ.get("FM_DAV_EMBED") != "1":
        return
    # nur im eigentlichen Server-Prozess: nicht in odoo shell / -u --stop-after-init / fmdav selbst / gevent-Prozess
    if getattr(odoo.cli, "COMMAND", None) != "server" or odoo.evented or config.get("stop_after_init"):
        return
    from odoo.service.server import CommonServer
    CommonServer.on_stop(_stop)
    if config["workers"]:
        _spawn_process()
    else:
        t = threading.Thread(target=_thread_loop, name="odoo.fmdav.embedded", daemon=True)
        _state["thread"] = t
        t.start()


# ---------- workers=0: Thread im Odoo-Prozess ----------

def _thread_loop():
    from odoo.tools import config
    time.sleep(2)                       # Registry-Vorladen durch den Server abwarten
    o = _opts()
    while not _state["stop"].is_set():
        try:
            import werkzeug.serving
            from odoo.addons.fm_proto import dav_server
            db = config["db_name"][0]
            app = dav_server.FmDavApplication(db, root_id=o["root"], accel_prefix=o["accel"],
                                              anon_ips=o["anon_ips"], anon_login=o["anon_login"],
                                              proxy_mode=bool(config.get("proxy_mode")))
            srv = werkzeug.serving.make_server("0.0.0.0", o["port"], app, threaded=True)
            srv.daemon_threads = True
            _state["server"] = srv
            _logger.info("fmdav eingebettet (Thread) auf Port %s", o["port"])
            srv.serve_forever()
        except Exception:
            _logger.exception("fmdav eingebettet: Fehler, Neustart in 5 s")
        finally:
            srv = _state.pop("server", None)
            if srv is not None:
                srv.server_close()
        _state["stop"].wait(5)


# ---------- workers>0: Kindprozess des Masters ----------

def _spawn_process():
    from odoo.tools import config
    o = _opts()
    cmd = [sys.executable, sys.argv[0], "--addons-path=" + config["addons_path"] if isinstance(config["addons_path"], str)
           else "--addons-path=" + ",".join(config["addons_path"]),
           "fmdav", "-c", config["config"], "-d", config["db_name"][0],
           "--dav-port=%s" % o["port"], "--dav-root=%s" % o["root"]]
    if o["accel"]:
        cmd.append("--dav-accel=" + o["accel"])
    if o["anon_ips"]:
        cmd += ["--dav-anon-ips=" + ",".join(o["anon_ips"]), "--dav-anon-login=" + o["anon_login"]]
    env = dict(os.environ, FM_DAV_EMBED="0")
    _state["proc"] = subprocess.Popen(cmd, env=env)
    _logger.info("fmdav eingebettet (Kindprozess %s) gestartet", _state["proc"].pid)


def _stop():
    _state["stop"].set()
    srv = _state.get("server")
    if srv is not None:
        srv.shutdown()
    proc = _state.get("proc")
    if proc is not None and proc.poll() is None:
        _logger.info("fmdav eingebettet: Kindprozess %s wird beendet", proc.pid)
        proc.terminate()
