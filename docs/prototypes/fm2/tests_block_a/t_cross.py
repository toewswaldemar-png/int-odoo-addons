from tlib import *
import os
c = Client()
r0 = row("voll/up.txt"); q("update int_filemanager_file set share_token='TOK-CROSS' where id=%s", [r0[0]])
out("Cross-FS-Move voll/up.txt -> p ->", c.rpc("/int_filemanager/move", {"path": "voll/up.txt", "dest_path": "p"}))
time.sleep(4); r = row("p/up.txt")
out("   Zeile:", r[0] if r else None, "(vorher %d)" % r0[0], "| Token:", r[5] if r else None, "| Versionen:", len(versions(r[0])) if r else None, "| alt auf Platte:", disk("voll/up.txt") is not None, "| neu:", (disk("p/up.txt") or b"")[:3])
out("Nested vorher:", q("select path from int_filemanager_file where path like %s order by path", ["p/nested/%"]))
q("update int_filemanager_file set share_token='TOK-NESTED' where path=%s", ["p/nested/sub/n1.txt"])
