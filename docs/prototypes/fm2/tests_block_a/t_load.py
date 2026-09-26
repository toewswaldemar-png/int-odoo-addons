import os, random, threading, statistics, urllib.parse
os.environ['FM_BASE'] = 'http://fmreal_odoo:8069'
import tlib; tlib.BASE = 'http://fmreal_odoo:8069'
from tlib import *
class RC(Client):
    def __init__(self):
        import http.cookiejar, urllib.request
        self.cj = http.cookiejar.CookieJar(); self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj)); self.timeout = 120
        r = self.rpc('/web/session/authenticate', {'db': 'fmreal', 'login': 'fmuser_real', 'password': 'fmreal-pw-1'}); self.uid = r['uid']
folders = [r[0] for r in q("select path from int_filemanager_file where is_dir order by random() limit 300", dbname='fmreal')]
files = [r[0] for r in q("select path from int_filemanager_file where not is_dir and size between 10000 and 500000 order by random() limit 300", dbname='fmreal')]
terms = ['rechnung', 'IMG_20', 'Vertrag', '2024', 'foto', 'pdf', 'Protokoll', 'Andreas']
def op(c, kind):
    t = time.time()
    if kind == 'tree':
        r = c.rpc('/int_filemanager/tree', {'path': random.choice(folders)})
    elif kind == 'liste':
        r = c.rpc('/web/dataset/call_kw/int_filemanager.file/web_search_read', {'model': 'int_filemanager.file', 'method': 'web_search_read', 'args': [], 'kwargs': {'domain': [['folder_path', '=', random.choice(folders)]], 'specification': {'name': {}, 'size': {}, 'is_dir': {}, 'mtime': {}}, 'limit': 80}})
    elif kind == 'suche':
        r = c.rpc('/web/dataset/call_kw/int_filemanager.file/web_search_read', {'model': 'int_filemanager.file', 'method': 'web_search_read', 'args': [], 'kwargs': {'domain': [['name', 'ilike', random.choice(terms)]], 'specification': {'name': {}, 'path': {}}, 'limit': 80}})
    else:
        r = c.http('GET', '/int_filemanager/download?path=' + urllib.parse.quote(random.choice(files)))
    ok = not (isinstance(r, dict) and 'ERROR' in r) and not (isinstance(r, tuple) and r[0] != 200)
    return kind, (time.time() - t) * 1000, ok
for n in (1, 5, 10, 20):
    clients = [RC() for _ in range(n)]; res = []; stop = time.time() + 30
    def worker(c):
        while time.time() < stop:
            res.append(op(c, random.choice(['tree', 'liste', 'liste', 'suche', 'download'])))
    ths = [threading.Thread(target=worker, args=(c,)) for c in clients]; [t.start() for t in ths]; [t.join() for t in ths]
    line = []
    for k in ('tree', 'liste', 'suche', 'download'):
        v = sorted(x[1] for x in res if x[0] == k)
        if v: line.append('%s p50=%d p95=%d ms' % (k, v[len(v)//2], v[int(len(v)*0.95)-1]))
    errs = sum(1 for x in res if not x[2])
    out('%2d Nutzer: %4d Anfragen in 30 s (%.1f/s), Fehler %d | %s' % (n, len(res), len(res)/30, errs, ' | '.join(line)))
