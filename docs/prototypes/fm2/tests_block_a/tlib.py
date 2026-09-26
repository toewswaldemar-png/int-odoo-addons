"""Testbibliothek fuer Block A (laeuft im Hilfscontainer im Netz fmtest-net)."""
import configparser, hashlib, http.cookiejar, json, os, time, urllib.error, urllib.request, uuid
import psycopg2

BASE = os.environ.get('FM_BASE', 'http://fmtest_odoo:8069')
ROOT = '/mnt/hm-daten'
DATA = '/var/lib/odoo'
_c = configparser.ConfigParser(); _c.read('/etc/odoo/odoo.conf'); _o = _c['options']


def db(dbname='fmtest', autocommit=True):
    c = psycopg2.connect(host=_o['db_host'], user=_o['db_user'], password=_o['db_password'], dbname=dbname)
    c.autocommit = autocommit
    return c


def q(sql, args=None, dbname='fmtest'):
    with db(dbname) as c, c.cursor() as cr:
        cr.execute(sql, args)
        try:
            return cr.fetchall()
        except psycopg2.ProgrammingError:
            return None


class Client:
    def __init__(self, login='fmuser', password='fmtest-pw-1', timeout=60):
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.timeout = timeout
        r = self.rpc('/web/session/authenticate', {'db': 'fmtest', 'login': login, 'password': password})
        self.uid = r.get('uid') if isinstance(r, dict) else None
        assert self.uid, 'login failed %s: %s' % (login, r)

    def rpc(self, url, params):
        body = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params}).encode()
        req = urllib.request.Request(BASE + url, body, {'Content-Type': 'application/json'})
        r = json.loads(self.op.open(req, timeout=self.timeout).read())
        if 'error' in r:
            return {'ERROR': r['error'].get('data', {}).get('message') or r['error'].get('message')}
        return r['result']

    def upload(self, dir_path, filename, content):
        b = uuid.uuid4().hex
        body = (('--%s\r\nContent-Disposition: form-data; name="path"\r\n\r\n%s\r\n' % (b, dir_path)) +
                ('--%s\r\nContent-Disposition: form-data; name="ufile"; filename="%s"\r\n'
                 'Content-Type: application/octet-stream\r\n\r\n' % (b, filename))).encode() + content + \
               ('\r\n--%s--\r\n' % b).encode()
        req = urllib.request.Request(BASE + '/int_filemanager/upload', body,
                                     {'Content-Type': 'multipart/form-data; boundary=' + b})
        return self._send(req)

    def _send(self, req):
        try:
            r = self.op.open(req, timeout=self.timeout)
            return r.status, r.read()[:300]
        except urllib.error.HTTPError as e:
            return e.code, e.read()[:300]

    def http(self, method, url, data=None, headers=None):
        req = urllib.request.Request(BASE + url, data, headers or {}, method=method)
        return self._send(req)


def anon(method, url, data=None, headers=None):
    req = urllib.request.Request(BASE + url, data, headers or {}, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()[:300]


def row(path):
    r = q("select id, path, size, revision, share_state, share_token, trashed "
          "from int_filemanager_file where path=%s", [path])
    return r[0] if r else None


def versions(file_id):
    return q("select version_no, origin, size, content_sha256 from int_filemanager_version "
             "where file_id=%s order by version_no", [file_id])


def disk(rel):
    p = os.path.join(ROOT, rel)
    return open(p, 'rb').read() if os.path.isfile(p) else None


def put_file(rel, content):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        f.write(content)
    os.chmod(p, 0o666)


def wait_indexed(rel, timeout=30):
    t = time.time()
    while time.time() - t < timeout:
        if row(rel):
            return True
        time.sleep(0.5)
    return False


def fault(spec):
    p = os.path.join(DATA, 'fault.txt')
    if spec:
        open(p, 'w').write(spec)
        os.chmod(p, 0o644)
    elif os.path.exists(p):
        os.remove(p)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def out(*a):
    print('>>', *a, flush=True)
