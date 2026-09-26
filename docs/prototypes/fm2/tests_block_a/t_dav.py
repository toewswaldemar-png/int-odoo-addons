from tlib import *
import os
c = Client(); c2 = Client("admin", "admin")
put_file("dav/brief.docx", b"V1-original"); wait_indexed("dav/brief.docx"); time.sleep(1)
tok = c.rpc("/int_filemanager/webdav_token", {"path": "dav/brief.docx"}); t = tok["token"]
u = "/int_filemanager/webdav/%s/brief.docx" % t
rid = row("dav/brief.docx")[0]
# B5: PUT ohne Version
st, h, _ = anon("PUT", u, b"V2-aus-Word"); time.sleep(4)
out("B5 PUT", st, "| Platte:", disk("dav/brief.docx"), "| Versionen:", versions(rid), "| Index:", row("dav/brief.docx")[:3])
# B5: PUT trotz fremder Sperre
lk1 = anon("LOCK", u)[1].get("Lock-Token"); 
st2, _, _ = anon("PUT", u, b"V3-ohne-Locktoken"); out("B5 PUT waehrend LOCK (ohne Token)", st2, "| Platte:", disk("dav/brief.docx"))
# B5: ETag aus ganzzahliger mtime
e1 = anon("HEAD", u)[1].get("ETag"); anon("PUT", u, b"V4-a"); e2 = anon("HEAD", u)[1].get("ETag")
out("B5 ETag vor/nach PUT in derselben Sekunde:", e1, e2, "GLEICH (Aenderung unsichtbar)" if e1 == e2 else "verschieden")
st3, _, b3 = anon("GET", u, headers={"If-None-Match": e1}); out("   GET If-None-Match altes ETag ->", st3)
# B7: Umbenennen in der App, dann Save mit altem Token
out("B7 rename ->", c.rpc("/int_filemanager/rename", {"path": "dav/brief.docx", "new_name": "brief_neu.docx"}))
time.sleep(2)
st4, _, _ = anon("PUT", u, b"V5-spaeter-Save-nach-Rename"); time.sleep(4)
out("B7 PUT alter Token", st4, "| brief.docx:", disk("dav/brief.docx"), "| brief_neu.docx:", disk("dav/brief_neu.docx"))
out("   Index:", q("select id, path from int_filemanager_file where path like %s order by id", ["dav/%"]))
# 128 MiB
big = b"0" * (129 * 1024 * 1024)
tokb = c.rpc("/int_filemanager/webdav_token", {"path": "dav/brief_neu.docx"})["token"]
out("128MiB WebDAV-PUT 129 MiB ->", anon("PUT", "/int_filemanager/webdav/%s/brief_neu.docx" % tokb, big)[0])
out("128MiB Upload 129 MiB ->", c.upload("dav", "gross.bin", big)[0], "| Platte:", os.path.exists(ROOT + "/dav/gross.bin"))
open("/var/lib/odoo/davtoken.txt", "w").write("/int_filemanager/webdav/%s/brief_neu.docx" % tokb)
