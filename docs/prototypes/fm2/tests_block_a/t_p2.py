from tlib import *
import threading
out("P5 nach Nachholen:", disk("p/p5_neu.txt"), row("p/p5_neu.txt")[3:5], "| alter Pfad existiert:", disk("p/p5.txt"))
out("P9 nach Nachholen:", disk("p/rofolder/datei.txt"), row("p/rofolder/datei.txt")[3:5])
c1, c2 = Client(), Client()
put_file("p/p2b.txt", b"V1"); wait_indexed("p/p2b.txt"); time.sleep(1)
res = []; bar = threading.Barrier(2)
def up(n, cl):
    bar.wait(); res.append((n, cl.upload("p", "p2b.txt", ("P2-" + n).encode())))
ths = [threading.Thread(target=up, args=(n, cl)) for n, cl in (("A", c1), ("B", c2))]
[t.start() for t in ths]; [t.join() for t in ths]; time.sleep(4)
r = row("p/p2b.txt")
out("P2 gleichzeitig (2 Sitzungen):", [(n, s, b[:90]) for n, (s, b) in res])
out("   Platte:", disk("p/p2b.txt"), "| rev/state", r[3:5], "| Versionen:", [(v[0], v[1], int(v[2])) for v in versions(r[0])])
