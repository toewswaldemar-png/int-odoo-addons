from tlib import *
c = Client()
H = {"Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
put_file("dav2/b.docx", b"V1-original"); wait_indexed("dav2/b.docx"); time.sleep(2)
t = c.rpc("/int_filemanager/webdav_token", {"path": "dav2/b.docx"})["token"]; u = "/int_filemanager/webdav/%s/b.docx" % t
rid = row("dav2/b.docx")[0]
out("PUT (Word-Content-Type)", anon("PUT", u, b"V2-aus-Word", H)[0]); time.sleep(4)
out("   Platte:", disk("dav2/b.docx"), "| Versionen:", versions(rid), "| Index size:", row("dav2/b.docx")[2])
out("PUT form-urlencoded", anon("PUT", u, b"V3", {"Content-Type": "application/x-www-form-urlencoded"})[0], "| Platte:", disk("dav2/b.docx"))
out("PUT ohne Content-Type-Header (http.client)")
import http.client, urllib.parse
p = urllib.parse.urlparse(BASE); hc = http.client.HTTPConnection(p.hostname, p.port); hc.putrequest("PUT", u); hc.putheader("Content-Length", "2"); hc.endheaders(); hc.send(b"V4"); r = hc.getresponse(); out("   ->", r.status, "| Platte:", disk("dav2/b.docx"))
