from tlib import *
u = open("/var/lib/odoo/davtoken.txt").read().strip()
out("WebDAV-Token nach Server-Neustart:", anon("PUT", u, b"x", {"Content-Type": "application/octet-stream"})[0])
c = Client()
t = c.rpc("/int_filemanager/webdav_token", {"path": "dav2/b.docx"})["token"]
out("neues Token funktioniert:", anon("HEAD", "/int_filemanager/webdav/%s/b.docx" % t)[0])
