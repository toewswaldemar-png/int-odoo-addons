import os, re, sys, json
from collections import Counter
root = sys.argv[1]; skip = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None
C = Counter(); lens = []
for mod in sorted(os.listdir(root)):
    p = os.path.join(root, mod)
    if not os.path.isfile(os.path.join(p, "__manifest__.py")) or (skip and skip.search(mod)): continue
    for d, ds, fs in os.walk(p):
        ds[:] = [x for x in ds if x not in ("lib", "node_modules", "tests", "i18n", "__pycache__", "migrations")]
        for f in fs:
            fp = os.path.join(d, f)
            if f.endswith(".py"):
                for l in open(fp, encoding="utf-8", errors="ignore"):
                    n = len(l.rstrip("\n")); C["py_lines"] += 1
                    if n > 88: C["py_gt88"] += 1
                    if n > 100: C["py_gt100"] += 1
                    if n > 120: C["py_gt120"] += 1
            elif f.endswith(".xml") and "/static/" not in fp.replace("\\", "/"):
                s = open(fp, encoding="utf-8", errors="ignore").read()
                for m in re.finditer(r'<record\s+id="([^"]+)"\s+model="ir\.ui\.view"', s):
                    i = m.group(1); C["view_total"] += 1
                    if re.match(r"view_", i): C["view_prefix_view_"] += 1
                    elif re.search(r"_view_", i): C["view_infix__view_"] += 1
                    elif i.endswith(("_form", "_list", "_tree", "_search", "_kanban")): C["view_suffix_type"] += 1
                    else: C["view_other"] += 1
                for m in re.finditer(r'<record\s+id="([^"]+)"\s+model="ir\.ui\.menu"', s): C["menu_record"] += 1
                for m in re.finditer(r'<menuitem[^>]*\sid="([^"]+)"', s):
                    i = m.group(1); C["menu_total"] += 1
                    if "_menu" in i: C["menu_id_has__menu"] += 1
                    elif i.startswith("menu_"): C["menu_id_prefix_menu_"] += 1
                    else: C["menu_id_other"] += 1
                for m in re.finditer(r'<record\s+id="([^"]+)"\s+model="res\.groups"', s):
                    i = m.group(1); C["group_total"] += 1
                    if "group_" in i: C["group_id_has_group_"] += 1
print(json.dumps(dict(C)))
