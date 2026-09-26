"""`odoo fmdav`: WebDAV-Server fuer int_filemanager 2 (Prototyp, Konzept 19.10).

Aufruf (Odoo findet Befehle aus Addons nur ueber --addons-path VOR dem Befehlsnamen, odoo/cli/command.py:112):
    odoo --addons-path=<pfade> fmdav -c odoo.conf -d <db> --dav-root=<knoten-id> [--dav-port=8080]
         [--dav-accel=/web/filestore] [--dav-anon-ips=a,b --dav-anon-login=<login>]   (anonym: nur Testinstanz)
Diese Datei wird als odoo.cli.fmdav geladen, nicht als Teil des Addons; das Addon wird erst in run() importiert.
"""
import logging
import optparse
import signal
import sys

from odoo.cli.command import Command
from odoo.service import server
from odoo.tools import config

_logger = logging.getLogger("odoo.fmdav")


class Fmdav(Command):
    """WebDAV-Server fuer int_filemanager (WsgiDAV, direkter ORM-Zugriff)"""
    name = "fmdav"

    def run(self, args):
        config.parser.prog = self.prog
        group = optparse.OptionGroup(config.parser, "fmdav")
        group.add_option("--dav-host", dest="dav_host", my_default="0.0.0.0", help="Adresse")
        group.add_option("--dav-port", dest="dav_port", type="int", my_default=8080, help="Port")
        group.add_option("--dav-root", dest="dav_root", type="int", my_default=0, help="ID des Wurzelknotens")
        group.add_option("--dav-accel", dest="dav_accel", my_default="",
                         help="Praefix fuer X-Accel-Redirect (nginx), z. B. /web/filestore")
        group.add_option("--dav-anon-ips", dest="dav_anon_ips", my_default="", help="NUR TEST: anonyme IPs")
        group.add_option("--dav-anon-login", dest="dav_anon_login", my_default="", help="NUR TEST: Login dafuer")
        config.parser.add_option_group(group)
        config.parse_config(args, setup_logging=True)
        # Nur die server-weiten Module laden. server.start(stop=True) wie in `odoo shell` wuerde mit workers>0 kurz
        # einen Prefork-Server an den HTTP-Port binden - scheitert neben einem laufenden Odoo im selben Container.
        server.load_server_wide_modules()
        signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))

        dbnames = config["db_name"]
        if len(dbnames) != 1:
            sys.exit("fmdav: genau eine Datenbank mit -d angeben")
        opts = config.options
        # my_default greift fuer nachtraeglich hinzugefuegte Optionen nicht (Odoo 19) -> Standardwerte hier
        if not opts.get("dav_root"):
            sys.exit("fmdav: --dav-root fehlt")
        from odoo.addons.fm_proto import dav_server   # noqa: PLC0415 (erst nach dem Laden der Konfiguration)
        dav_server.serve(
            dbnames[0], opts.get("dav_host") or "0.0.0.0", int(opts.get("dav_port") or 8080),
            root_id=int(opts.get("dav_root")), accel_prefix=opts.get("dav_accel") or "",
            anon_ips=[ip for ip in (opts.get("dav_anon_ips") or "").split(",") if ip],
            anon_login=opts.get("dav_anon_login") or "", proxy_mode=bool(opts.get("proxy_mode")),
        )
        return 0
