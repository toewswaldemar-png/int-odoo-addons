from tlib import *
import os
c = Client()
put_file("b14c/rechnung.pdf", b"PDF-INHALT"); wait_indexed("b14c/rechnung.pdf"); time.sleep(1)
out("in Papierkorb:", c.rpc("/int_filemanager/delete", {"path": "b14c/rechnung.pdf"}))
time.sleep(2)
r = q("select id, path from int_filemanager_file where original_path=%s and trashed", ["b14c/rechnung.pdf"])[0]
rid, tpath = r; out("Papierkorb-Zeile", rid, tpath, "| Bytes da:", os.path.exists(ROOT + "/" + tpath))
q("""create or replace function zz_fail() returns trigger as $$ begin if old.id = %d then raise exception 'simulierter DB-Fehler beim Loeschen'; end if; return old; end $$ language plpgsql;
     drop trigger if exists zz_fail on int_filemanager_file; create trigger zz_fail before delete on int_filemanager_file for each row execute function zz_fail();""" % rid)
res = c.rpc("/web/dataset/call_kw/int_filemanager.file/unlink", {"model": "int_filemanager.file", "method": "unlink", "args": [[rid]], "kwargs": {}})
out("endgueltig loeschen ->", str(res)[:120])
out("   Zeile noch da:", bool(q("select 1 from int_filemanager_file where id=%s", [rid])), "| Bytes noch da:", os.path.exists(ROOT + "/" + tpath))
q("drop trigger zz_fail on int_filemanager_file; drop function zz_fail();")
out("   Wiederherstellen danach ->", c.rpc("/web/dataset/call_kw/int_filemanager.file/action_restore", {"model": "int_filemanager.file", "method": "action_restore", "args": [[rid]], "kwargs": {}}))
