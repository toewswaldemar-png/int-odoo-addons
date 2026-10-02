"""Helpers around int_filemanager/i18n/de.po (Konzept: Oberflaechentexte englisch + de.po).

  python po_tool.py owned <pot>             list the terms of the v2 code (what de.po must cover)
  python po_tool.py build <pot> <dict.json> write de.po from the pot: v2 terms translated from
                                            the dictionary, everything else left out; fails if a
                                            v2 term has no translation

A term is "v2" when any of its references points to v2 code: the v2 JS/QWeb folder, the v2
views file, the v2 Python files, or a v2 model (model names, field labels, selections).
"""

import json
import re
import sys

V2_MODELS = (
    "int_filemanager_node",
    "int_filemanager_revision",
    "int_filemanager_blob",
    "int_filemanager_derivative",
    "int_filemanager_scope",
    "int_filemanager_upload",
    "int_filemanager_operation",
    "int_filemanager_zip_job",
    "int_filemanager_share",
    "int_filemanager_extraction_field",
    "int_filemanager_extraction_rule",
    "int_filemanager_field_value",
    "int_filemanager_extraction_hint",
    "int_filemanager_value_recognition",
)
V2_PATH_HINTS = (
    "static/src/int_filemanager/v2/",
    "views/int_filemanager_node_views.xml",
    "models/int_filemanager_",
    "controllers/int_filemanager_v2.py",
    "zip_stream.py",
    "data/int_filemanager_",
    "int_filemanager.int_filemanager_node_",
    "int_filemanager.action_int_filemanager_node",
    "int_filemanager.menu_int_filemanager_v2",
    "int_filemanager.ir_cron_int_filemanager_",
    # names of the starting set of extraction fields (translated data)
    "model:int_filemanager.extraction_field,name:",
)
# The v1 file model (and its siblings) is not v2 even though some names look alike.
V1_EXCLUDE = ("model:ir.model,name:int_filemanager.model_int_filemanager_file",)


def parse(path):
    text = open(path, encoding="utf-8").read()
    header, *blocks = re.split(r"\n\n(?=#\. module:)", text)
    entries = []
    for block in blocks:
        refs = re.findall(r"^#: (.*)$", block, re.M)
        msgid = re.search(r"msgid ((?:\".*\"\n)+)msgstr", block)
        if not msgid:
            continue
        text_id = "".join(re.findall(r'"(.*)"', msgid.group(1)))
        entries.append({"block": block, "refs": refs, "msgid": text_id})
    return header, entries


def is_v2(entry):
    refs = " ".join(entry["refs"])
    if any(hint in refs for hint in V2_PATH_HINTS):
        return True
    return any(
        f"int_filemanager.field_{m}__" in refs
        or f"int_filemanager.model_{m}" in refs
        or f"selection__{m}__" in refs
        or f"constraint_{m}_" in refs
        for m in V2_MODELS
    )


def unescape(s):
    return s.encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")


def main():
    mode, pot = sys.argv[1], sys.argv[2]
    header, entries = parse(pot)
    owned = [e for e in entries if is_v2(e)]
    if mode == "owned":
        for e in owned:
            print(f"{e['msgid']!r:80.80}  <- {e['refs'][0][:70]}")
        print(len(owned), "terms")
        return
    dictionary = json.load(open(sys.argv[3], encoding="utf-8"))
    # Terms of the v1 code that were translated by hand stay as long as the dictionary has them.
    owned += [e for e in entries if not is_v2(e) and e["msgid"] in dictionary]
    missing = sorted({e["msgid"] for e in owned if e["msgid"] not in dictionary})
    if missing:
        print("MISSING:")
        for m in missing:
            print("  ", repr(m))
        sys.exit(1)
    team = '"Language-Team: \\n"'
    out = [header.replace(team, '"Language: de\\n"' + chr(10) + team)]
    for e in owned:
        block = e["block"]
        translation = dictionary[e["msgid"]]
        translation = translation.replace("\\", "\\\\").replace('"', '\\"')
        block = re.sub(r"msgstr \"\"", f'msgstr "{translation}"', block, count=1)
        out.append(block)
    open(sys.argv[4], "w", encoding="utf-8", newline="").write("\n\n".join(out) + "\n")
    print(f"{len(owned)} terms written")


if __name__ == "__main__":
    main()
