import sys; sys.path.insert(0, '/tests')
from t_v2 import C, BASE_HOST, BASE_PORT
import http.client, json, os
c = C()
def put(path, data):
    hc = http.client.HTTPConnection(BASE_HOST, BASE_PORT, timeout=600)
    hc.request("PUT", path, body=data, headers={"Cookie": c.cookie(), "Content-Type": "application/octet-stream"})
    r = hc.getresponse(); b = r.read(); hc.close(); return json.loads(b)
data = os.urandom(16 * 1024 * 1024)
seen = {}
for i in range(60):
    r = put("/fmp/diag/getdata", data)
for i in range(10):
    hc = http.client.HTTPConnection(BASE_HOST, BASE_PORT); hc.request("GET", "/fmp/diag/rss", headers={"Cookie": c.cookie()}); r = json.loads(hc.getresponse().read()); seen[r["pid"]] = r["rss_kb"]
print(">> nach 60 x 16 MB get_data: RSS je Worker:", seen)
