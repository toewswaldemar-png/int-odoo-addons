from tlib import *
import threading, os
c = Client()
def scenario(label, prep, call, after_paths):
    prep()
    rel = after_paths[0]
    wait_indexed(rel)
    rid = row(rel)[0]
    blocker = db(autocommit=False); bc = blocker.cursor()
    bc.execute("select id from int_filemanager_file where id=%s for update", [rid])
    res = {}
    t = threading.Thread(target=lambda: res.update(r=call())); t.start()
    time.sleep(2.0)                     # Request hat Snapshot, Plattenaenderung gemacht und wartet auf die Zeilensperre
    bc.execute("update int_filemanager_file set write_date=now() where id=%s", [rid]); blocker.commit()
    t.join(60)
    time.sleep(4)
    out(label, "Antwort:", res.get("r"))
    for p in after_paths:
        r = row(p); out("   Index", p, "->", r[:2] if r else None, "| Platte:", os.path.exists(os.path.join(ROOT, p)))
put_file("b2/x.txt", b"x")
scenario("B2 rename", lambda: None, lambda: c.rpc("/int_filemanager/rename", {"path": "b2/x.txt", "new_name": "y.txt"}), ["b2/x.txt", "b2/y.txt"])
put_file("b2/m.txt", b"m"); os.makedirs(ROOT + "/b2/ziel", exist_ok=True)
scenario("B2 move", lambda: None, lambda: c.rpc("/int_filemanager/move", {"path": "b2/m.txt", "dest_path": "b2/ziel"}), ["b2/m.txt", "b2/ziel/m.txt"])
put_file("b2/d.txt", b"d")
scenario("B2 delete", lambda: None, lambda: c.rpc("/int_filemanager/delete", {"path": "b2/d.txt"}), ["b2/d.txt"])
out("   Papierkorb-Zeilen:", q("select path, trashed from int_filemanager_file where original_path=%s", ["b2/d.txt"]), "Platte .trash:", [f for f in os.listdir(ROOT + "/.trash") if "d.txt" in f] if os.path.isdir(ROOT + "/.trash") else None)
