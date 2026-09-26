from tlib import *
import os
c = Client()
# B6: Datei auf Platte, aber nicht im Index (z.B. nach Ueberlauf) -> Upload gleichen Namens
put_file("b6/vertrag.pdf", b"WICHTIGES-ORIGINAL-nur-auf-Platte"); wait_indexed("b6/vertrag.pdf"); time.sleep(1)
q("delete from int_filemanager_file where path=%s", ["b6/vertrag.pdf"])
out("B6 Upload ->", c.upload("b6", "vertrag.pdf", b"neue-Fassung-aus-Upload")[0])
r = row("b6/vertrag.pdf"); out("   Platte:", disk("b6/vertrag.pdf"), "| Versionen:", versions(r[0]) if r else None)
# B13 Vorbereitung: Unterordner mit Dateien, spaeter unlesbar
for i in range(5): put_file("b13/geheim/f%d.txt" % i, b"x")
put_file("b13/offen.txt", b"y"); time.sleep(4)
q("update int_filemanager_file set share_token=%s where path=%s", ["TOK-B13", "b13/geheim/f0.txt"])
out("B13 vorher:", q("select count(*) from int_filemanager_file where path like %s", ["b13/%"]))
