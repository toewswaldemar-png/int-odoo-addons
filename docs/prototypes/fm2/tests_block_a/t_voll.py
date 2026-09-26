from tlib import *
import os
c = Client()
V = ROOT + "/voll"


def free():
    s = os.statvfs(V)
    return s.f_bavail * s.f_frsize


fill = V + "/fueller.bin"
if os.path.exists(fill):
    os.remove(fill)
orig = b"O" * 500_000
for n in ("up.txt", "text.txt", "dav.docx"):
    put_file("voll/" + n, orig)
    wait_indexed("voll/" + n)
time.sleep(2)
fd = os.open(fill, os.O_WRONLY | os.O_CREAT, 0o666)
try:
    while True:
        os.write(fd, b"\0" * 4096)
except OSError:
    pass
os.close(fd)
out("frei nach Auffuellen:", free(), "Bytes")

# Upload-Ueberschreiben (Durchstich 1.15.0)
out("Upload (1.15.0) ->", c.upload("voll", "up.txt", b"N" * 600_000)[0])
time.sleep(3)
r = row("voll/up.txt")
d = disk("voll/up.txt")
out("   Platte unversehrt:", d == orig, "| state", r[4], "| Temp-Reste:",
    [f for f in os.listdir(V) if f.startswith(".int_filemanager_tmp")])

# write_text (Bestandsweg, nicht atomar)
out("write_text ->", str(c.rpc("/int_filemanager/write_text", {"path": "voll/text.txt", "content": "T" * 600_000}))[:90])
d = disk("voll/text.txt")
out("   Platte:", len(d), "Bytes,", "unversehrt" if d == orig else "BESCHAEDIGT (Original: 500000 Bytes)")

# WebDAV-PUT (Bestandsweg)
t = c.rpc("/int_filemanager/webdav_token", {"path": "voll/dav.docx"})["token"]
st = anon("PUT", "/int_filemanager/webdav/%s/dav.docx" % t, b"W" * 600_000, {"Content-Type": "application/octet-stream"})[0]
d = disk("voll/dav.docx")
out("WebDAV-PUT ->", st, "| Platte:", len(d), "Bytes,", "unversehrt" if d == orig else "BESCHAEDIGT")
os.remove(fill)
out("Platz freigegeben:", free())
