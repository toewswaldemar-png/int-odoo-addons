from tlib import *
import os, sys
cmd, stage = sys.argv[1], sys.argv[2]
rel = "exit/%s.txt" % stage
if cmd == "prep":
    fault(None); put_file(rel, b"V1-" + stage.encode()); out("indexed", wait_indexed(rel)); time.sleep(1)
    fault(stage + ":exit")
elif cmd == "upload":
    try:
        out("upload ->", Client(timeout=20).upload("exit", stage + ".txt", b"V2-APP-" + stage.encode())[0])
    except Exception as e:
        out("upload -> Verbindung abgebrochen:", type(e).__name__)
elif cmd == "check":
    fault(None)
    r = row(rel)
    temps = [f for f in os.listdir(ROOT + "/exit") if f.startswith(".int_filemanager_tmp_") and stage in open(ROOT + "/exit/" + f, "rb").read().decode(errors="ignore") or (f.startswith(".int_filemanager_tmp_%s_" % (r[0] if r else 0)))]
    v = versions(r[0]) if r else None
    out("%-28s Platte=%s | state=%s rev=%s | Versionen=%s | Temp-Reste=%s" % (stage, disk(rel), r[4] if r else None, r[3] if r else None, [(x[0], x[1], int(x[2])) for x in v] if v else v, temps))
