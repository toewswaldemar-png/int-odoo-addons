from tlib import *
import os, threading, shutil, subprocess
c = Client(); c2 = Client("admin", "admin")
def prep(rel, content=b"V1"):
    put_file(rel, content); assert wait_indexed(rel); time.sleep(1)
def recover():
    # entspricht dem Cron-Aufruf, ueber einen Hilfsaufruf auf dem Server (siehe exitrun.sh); hier: warten bis synced oder 400 s
    pass
# P2: zwei gleichzeitige Uploads derselben Datei (gleiche Basisrevision)
prep("p/p2.txt")
res = []
ths = [threading.Thread(target=lambda n=n, cl=cl: res.append((n, cl.upload("p", "p2.txt", ("P2-von-" + n).encode())[0]))) for n, cl in (("fmuser", c), ("admin", c2))]
[t.start() for t in ths]; [t.join() for t in ths]; time.sleep(4)
r = row("p/p2.txt"); out("P2 gleichzeitig:", res, "| Platte:", disk("p/p2.txt"), "| rev", r[3], r[4], "| Versionen:", [(v[0], v[1], int(v[2])) for v in versions(r[0])])
# P3: identischer Request zweimal (Doppelklick / erneutes Senden nach Timeout)
prep("p/p3.txt")
a = c.upload("p", "p3.txt", b"P3-gleich")[0]; b = c.upload("p", "p3.txt", b"P3-gleich")[0]; time.sleep(4)
r = row("p/p3.txt"); out("P3 doppelt:", a, b, "| rev", r[3], "| Versionen:", [(v[0], v[1], int(v[2])) for v in versions(r[0])])
# P5: Umbenennen waehrend pending (Hook scheitert per Injektion)
prep("p/p5.txt"); fault("hook_before_snapshot")
out("P5 upload:", c.upload("p", "p5.txt", b"P5-APP")[0]); fault(None)
out("   pending:", row("p/p5.txt")[4], "| rename ->", c.rpc("/int_filemanager/rename", {"path": "p/p5.txt", "new_name": "p5_neu.txt"}))
time.sleep(3); out("   nach rename: Platte p5_neu:", disk("p/p5_neu.txt"), "| Index:", row("p/p5_neu.txt") and row("p/p5_neu.txt")[3:5])
# P10: Elternordner wird extern (Explorer) verschoben, waehrend ein Kind pending ist
prep("p/ordner/kind.txt"); fault("hook_before_snapshot")
out("P10 upload:", c.upload("p/ordner", "kind.txt", b"P10-APP")[0]); fault(None)
os.makedirs(ROOT + "/p/ziel", exist_ok=True); os.rename(ROOT + "/p/ordner", ROOT + "/p/ziel/ordner"); time.sleep(5)
out("   nach externem Move: Index:", q("select path, share_state from int_filemanager_file where path like %s", ["p/%kind.txt"]))
# P9: Zielordner nicht beschreibbar
prep("p/rofolder/datei.txt"); os.chmod(ROOT + "/p/rofolder", 0o555)
out("P9 upload in nicht beschreibbaren Ordner:", c.upload("p/rofolder", "datei.txt", b"P9-APP")[0]); time.sleep(3)
out("   Zustand:", row("p/rofolder/datei.txt")[3:5], "| Platte:", disk("p/rofolder/datei.txt"))
open("/var/lib/odoo/pend_state.txt", "w").write("ok")
