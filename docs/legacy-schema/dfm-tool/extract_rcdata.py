import pefile
import os

exe_path = r"C:\Users\waldemar.toews\Desktop\Herrman Work Test\Herrmann_Work\Herrmann.exe"
out_dir = r"C:\Users\WALDEM~1.TOE\AppData\Local\Temp\claude\C--Users-waldemar-toews-Documents-GitHub\384dd27f-f08a-4235-8977-2d696057690b\scratchpad\forms_raw"
os.makedirs(out_dir, exist_ok=True)

pe = pefile.PE(exe_path, fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])

RT_RCDATA = 10
count = 0
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
            with open(os.path.join(out_dir, f"{safe_name}.bin"), "wb") as f:
                f.write(data)
            count += 1

print(f"Extracted {count} resources to {out_dir}")
