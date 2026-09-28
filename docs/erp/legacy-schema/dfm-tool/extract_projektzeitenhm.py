import pefile
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import dfm_decode as D

exe_path = r"C:\Users\waldemar.toews\Desktop\Herrman Work Test\Herrmann_Work\ProjektzeitenHM.exe"
out_dir = os.path.join(os.path.dirname(__file__), "..", "forms-dfm-projektzeitenhm")
os.makedirs(out_dir, exist_ok=True)

pe = pefile.PE(exe_path, fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])

RT_RCDATA = 10
forms = []
for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
    if entry.id != RT_RCDATA:
        continue
    for name_entry in entry.directory.entries:
        name = str(name_entry.name) if name_entry.name is not None else str(name_entry.id)
        for lang_entry in name_entry.directory.entries:
            data_rva = lang_entry.data.struct.OffsetToData
            size = lang_entry.data.struct.Size
            data = pe.get_memory_mapped_image()[data_rva:data_rva+size]
            safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
            forms.append((safe_name, data))

print(f"Total RCDATA: {len(forms)}, DFM (TPF0): {sum(1 for _, d in forms if d[:4] == b'TPF0')}")

ok, failed = 0, 0
fail_list = []
for safe_name, data in forms:
    if data[:4] != b'TPF0':
        continue
    out_path = os.path.join(out_dir, f"{safe_name}.dfm.txt")
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
        fail_list.append((safe_name, str(e)))

print(f"Decoded OK: {ok}, Failed: {failed}")
for name, err in fail_list[:20]:
    print(f"  FAIL {name}: {err}")
