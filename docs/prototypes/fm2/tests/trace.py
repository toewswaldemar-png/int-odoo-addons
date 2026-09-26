import sys; sys.path.insert(0, '/tests')
from t_v2 import C, BASE_HOST, BASE_PORT
import http.client, json, os
c = C()
def req(m, path, data=None):
    hc = http.client.HTTPConnection(BASE_HOST, BASE_PORT, timeout=600)
    hc.request(m, path, body=data, headers={"Cookie": c.cookie(), "Content-Type": "application/octet-stream"})
    r = hc.getresponse(); b = r.read(); hc.close(); return json.loads(b)
# alle Worker in Tracing versetzen (mehrfach aufrufen)
pids = set()
for i in range(20):
    r = req("GET", "/fmp/diag/trace")
    pids.add(r.get("started") or r.get("pid"))
data = os.urandom(16 * 1024 * 1024)
for i in range(30):
    req("PUT", "/fmp/diag/getdata", data)
seen = {}
for i in range(20):
    r = req("GET", "/fmp/diag/trace")
    if "top" in r and r["pid"] not in seen:
        seen[r["pid"]] = r
for pid, r in seen.items():
    print(">> PID", pid, "grosse bytes:", r["big_bytes"])
    for t in r["top"][:2]:
        print(">>   %s MB in %d Objekten" % (t["size_mb"], t["count"]))
        for line in t["tb"]:
            print(">>      ", line.strip()[:150])
    print(">>   Referenzen:", r["owners"])
