import pefile
import sys

exe_path = r"C:\Users\waldemar.toews\Desktop\Herrman Work Test\Herrmann_Work\Herrmann.exe"
pe = pefile.PE(exe_path, fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])

RT_RCDATA = 10

count = 0
forms = []
for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
    type_id = entry.id if entry.name is None else str(entry.name)
    if entry.id != RT_RCDATA:
        continue
    for name_entry in entry.directory.entries:
        name = str(name_entry.name) if name_entry.name is not None else str(name_entry.id)
        for lang_entry in name_entry.directory.entries:
            data_rva = lang_entry.data.struct.OffsetToData
            size = lang_entry.data.struct.Size
            data = pe.get_memory_mapped_image()[data_rva:data_rva+size]
            count += 1
            is_dfm = data[:4] == b'TPF0'
            forms.append((name, size, is_dfm))

forms.sort(key=lambda x: -x[1])
print(f"Total RCDATA resources: {count}")
dfm_forms = [f for f in forms if f[2]]
print(f"DFM (TPF0) resources: {len(dfm_forms)}")
print()
for name, size, is_dfm in forms:
    marker = "DFM " if is_dfm else "    "
    print(f"{marker}{size:>8}  {name}")
