"""Prototyp-Tests int_filemanager 2: Blob-Speicher, Upload in Stuecken, Auslieferung ueber nginx/x_sendfile."""
import hashlib, http.client, http.cookiejar, json, os, subprocess, sys, time, urllib.request, uuid
import psycopg2, configparser

BASE_HOST, BASE_PORT = "fmv2_nginx", 8081
SRC = "/src"
BLOBS = "/blobs"
CHUNK = 4 * 1024 * 1024
_c = configparser.ConfigParser(); _c.read("/etc/odoo/odoo.conf"); _o = _c["options"]


def q(sql, args=None):
    with psycopg2.connect(host=_o["db_host"], user=_o["db_user"], password=_o["db_password"], dbname="fmv2") as c:
        c.autocommit = True
        with c.cursor() as cr:
            cr.execute(sql, args)
            try:
                return cr.fetchall()
            except psycopg2.ProgrammingError:
                return None


def out(*a):
    print(">>", *a, flush=True)


class C:
    def __init__(self, login="admin", pw="admin"):
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        r = self.rpc("/web/session/authenticate", {"db": "fmv2", "login": login, "password": pw})
        assert r.get("uid"), r

    def rpc(self, url, params):
        req = urllib.request.Request("http://%s:%d%s" % (BASE_HOST, BASE_PORT, url),
                                     json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}).encode(),
                                     {"Content-Type": "application/json"})
        r = json.loads(self.op.open(req, timeout=1800).read())
        return r.get("result", {"ERROR": (r.get("error") or {}).get("data", {}).get("message")})

    def cookie(self):
        return "; ".join("%s=%s" % (c.name, c.value) for c in self.cj)

    def put_chunk(self, key, offset, data):
        hc = http.client.HTTPConnection(BASE_HOST, BASE_PORT, timeout=600)
        hc.request("PUT", "/fmp/upload/chunk?operation_key=%s&offset=%d" % (key, offset), body=data,
                   headers={"Cookie": self.cookie(), "Content-Type": "application/octet-stream"})
        r = hc.getresponse(); body = r.read(); hc.close()
        return r.status, json.loads(body or b"{}")

    def get(self, path, headers=None):
        hc = http.client.HTTPConnection(BASE_HOST, BASE_PORT, timeout=600)
        h = {"Cookie": self.cookie()}; h.update(headers or {})
        hc.request("GET", path, headers=h)
        r = hc.getresponse(); hdrs = dict(r.getheaders())
        n = 0; hsh = hashlib.sha256()
        while b := r.read(CHUNK):
            n += len(b); hsh.update(b)
        hc.close()
        return r.status, hdrs, n, hsh.hexdigest()

    def upload(self, path, name, stop_after=None, key=None):
        key = key or uuid.uuid4().hex
        size = os.path.getsize(path)
        st = self.rpc("/fmp/upload/init", {"operation_key": key, "name": name, "size": size})
        off = st["received"]
        with open(path, "rb") as f:
            f.seek(off)
            n = 0
            while off < size:
                data = f.read(CHUNK)
                s, r = self.put_chunk(key, off, data)
                assert s == 200, (s, r)
                off = r["received"]; n += 1
                if stop_after and n >= stop_after:
                    return key, off
        return key, off

    def finish(self, key):
        return self.rpc("/fmp/upload/finish", {"operation_key": key})


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while b := f.read(CHUNK):
            h.update(b)
    return h.hexdigest()


def fault(spec):
    p = "/var/lib/odoo/fault.txt"
    if spec:
        open(p, "w").write(spec); os.chmod(p, 0o644)
    elif os.path.exists(p):
        os.remove(p)


def blob_exists(sha):
    return os.path.exists(os.path.join(BLOBS, sha[0:2], sha[2:4], sha))


if __name__ == "__main__":
    step = sys.argv[1]
    c = C() if step not in ("mkfiles",) else None
    if step == "mkfiles":
        os.makedirs(SRC, exist_ok=True)
        for name, mb in (("gross_3gb.bin", 3072), ("mittel_200mb.bin", 200), ("klein_1mb.bin", 1)):
            p = os.path.join(SRC, name)
            if not os.path.exists(p):
                with open(p, "wb") as f:
                    for _i in range(mb):
                        f.write(os.urandom(1024 * 1024))
            out(name, os.path.getsize(p), sha_file(p)[:12])
    elif step == "big":
        p = os.path.join(SRC, "gross_3gb.bin"); src_sha = sha_file(p)
        t = time.time(); key, off = c.upload(p, "gross_3gb.bin"); t_up = time.time() - t
        t = time.time(); r = c.finish(key); t_fin = time.time() - t
        out("3-GB-Upload in 16-MB-Stuecken: %.1f s (%.0f MB/s), finish %.1f s -> %s" % (t_up, 3072 / t_up, t_fin, r))
        out("   Hash gleich Quelle:", r.get("sha256") == src_sha, "| Blob auf Platte:", blob_exists(src_sha))
        t = time.time(); s, h, n, dsha = c.get("/fmp/download/%d" % r["node_id"])
        out("   Download ueber nginx: %s, %d Bytes in %.1f s, Hash gleich: %s, X-Accel sichtbar: %s" % (
            s, n, time.time() - t, dsha == src_sha, "X-Accel-Redirect" in h))
        s, h, n, _ = c.get("/fmp/download/%d" % r["node_id"], {"Range": "bytes=1000-1999"})
        with open(p, "rb") as f:
            f.seek(1000); want = hashlib.sha256(f.read(1000)).hexdigest()
        _, _, _, got = c.get("/fmp/download/%d" % r["node_id"], {"Range": "bytes=1000-1999"})
        out("   Range 1000-1999:", s, n, "Bytes, Inhalt korrekt:", got == want, "| Content-Range:", h.get("Content-Range"))
        s, h, n, _ = c.get("/fmp/download/%d" % r["node_id"], {"If-None-Match": '"%s"' % src_sha})
        out("   If-None-Match (ETag):", s, "| ETag-Header:", h.get("ETag"))
    elif step == "resume":
        p = os.path.join(SRC, "mittel_200mb.bin"); src_sha = sha_file(p)
        key, off = c.upload(p, "mittel.bin", stop_after=5)
        out("abgebrochen nach 5 Stuecken bei", off)
        s, r = c.put_chunk(key, 0, open(p, "rb").read(CHUNK))
        out("   erstes Stueck erneut gesendet (Wiederholung):", s, r)
        s, r = c.put_chunk(key, off + CHUNK, b"x" * 10)
        out("   Stueck mit Luecke:", s, r)
        key, off = c.upload(p, "mittel.bin", key=key)
        r1 = c.finish(key); r2 = c.finish(key)
        out("   fortgesetzt bis", off, "| finish:", r1.get("sha256") == src_sha, "| zweites finish repeated:", r2.get("repeated"),
            "gleiche Revision:", r1.get("revision_id") == r2.get("revision_id"))
        cnt = q("select count(*) from fm_revision where operation_key=%s", [key])[0][0]
        out("   Revisionen fuer diesen Vorgang:", cnt)
    elif step == "dedup":
        p = os.path.join(SRC, "mittel_200mb.bin")
        k, _ = c.upload(p, "kopie_von_mittel.bin"); r = c.finish(k)
        out("gleicher Inhalt unter anderem Namen: deduped =", r.get("deduped"), "| Blobs mit diesem Hash:",
            q("select count(*) from fm_blob where sha256=%s", [r["sha256"]])[0][0], "| Knoten:",
            q("select count(*) from fm_node n join fm_revision rv on rv.id=n.current_revision_id join fm_blob b on b.id=rv.blob_id where b.sha256=%s", [r["sha256"]])[0][0])
    elif step.startswith("crash_"):
        stage = step[len("crash_"):]
        p = os.path.join(SRC, "klein_1mb.bin")
        # eigener Inhalt je Test, damit der Blob neu ist
        tmp = os.path.join(SRC, "crash_%s.bin" % stage)
        with open(tmp, "wb") as f:
            f.write(open(p, "rb").read() + stage.encode())
        sha = sha_file(tmp)
        key, _ = c.upload(tmp, "crash_%s.bin" % stage)
        fault(stage + ":exit")
        try:
            r = c.finish(key); out("finish ->", r)
        except Exception as e:
            out("finish -> Verbindung abgebrochen:", type(e).__name__)
        fault(None)
        open("/src/crash_state.txt", "w").write("%s %s" % (key, sha))
    elif step == "after_crash":
        key, sha = open("/src/crash_state.txt").read().split()
        out("nach Neustart: Blob auf Platte:", blob_exists(sha), "| fm_blob-Zeile:",
            bool(q("select 1 from fm_blob where sha256=%s", [sha])), "| Upload-Status:",
            q("select state from fm_upload where operation_key=%s", [key]))
        r = c.finish(key)
        out("   finish nach Neustart:", r.get("sha256") == sha, "| Revisionen:",
            q("select count(*) from fm_revision where operation_key=%s", [key])[0][0])
    elif step == "orphan":
        # Blob anlegen, dann DB-Commit verhindern (Fehler vor dem Commit) -> verwaister Blob
        tmp = os.path.join(SRC, "orphan.bin")
        with open(tmp, "wb") as f:
            f.write(os.urandom(2 * 1024 * 1024))
        sha = sha_file(tmp)
        key, _ = c.upload(tmp, "orphan.bin")
        fault("before_commit")
        r = c.finish(key); fault(None)
        out("finish mit Fehler vor Commit ->", str(r)[:80])
        out("   verwaister Blob auf Platte:", blob_exists(sha), "| fm_blob-Zeile:", bool(q("select 1 from fm_blob where sha256=%s", [sha])))
        open("/src/orphan_sha.txt", "w").write(sha)
    elif step == "after_gc":
        sha = open("/src/orphan_sha.txt").read().strip()
        big = q("select b.sha256 from fm_blob b join fm_revision r on r.blob_id=b.id limit 1")[0][0]
        out("nach Aufraeumjob: verwaister Blob noch da:", blob_exists(sha), "| referenzierter Blob noch da:", blob_exists(big))
