import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(__file__))
import dfm_decode as D

src_dir = os.path.join(os.path.dirname(__file__), "forms_raw")
out_dir = os.path.join(os.path.dirname(__file__), "forms_dfm")
os.makedirs(out_dir, exist_ok=True)

ok, failed = 0, 0
fail_list = []

for fname in sorted(os.listdir(src_dir)):
    if not fname.endswith(".bin"):
        continue
    path = os.path.join(src_dir, fname)
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"TPF0":
        continue
    out_path = os.path.join(out_dir, fname[:-4] + ".dfm.txt")
    try:
        root, r = D.parse_dfm(data)
        text = "\n".join(D.render(root))
        remaining = len(data) - r.pos
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
            if remaining > 0:
                f.write(f"\n// WARNING: {remaining} trailing bytes not consumed\n")
        ok += 1
    except Exception as e:
        failed += 1
        fail_list.append((fname, str(e)))

print(f"OK: {ok}, Failed: {failed}")
for fname, err in fail_list:
    print(f"  FAIL {fname}: {err}")
