"""Builds merged.xml for compile.mjs: every OWL template of int_filemanager's v2 UI as the
browser would see it. Templates that inherit an Odoo template (t-inherit, primary mode) are
applied to a copy of the core template first - the xpath subset the module uses (`//x[@a='b']`
with an optional trailing `/*[1]`, positions replace / inside / before / after) - so what
OWL later compiles is the merged result, not the fragment.

usage: python merge_templates.py <int_filemanager dir> <out merged.xml>
"""

import copy
import glob
import os
import sys
from xml.etree import ElementTree

HERE = os.path.dirname(os.path.abspath(__file__))


def load_core():
    core = {}
    for path in glob.glob(os.path.join(HERE, "core_templates", "*.xml")):
        for element in ElementTree.parse(path).iter():
            name = element.get("t-name")
            if name:
                core[name] = element
    return core


def parent_map(root):
    return {child: parent for parent in root.iter() for child in parent}


def resolve(root, expr):
    first_child = expr.endswith("/*[1]")
    if first_child:
        expr = expr[: -len("/*[1]")]
    if not expr.startswith("//"):
        raise ValueError(f"unsupported xpath: {expr}")
    target = root.find("." + expr)
    if target is None:
        raise ValueError(f"xpath matches nothing: {expr}")
    return target[0] if first_child else target


def apply_xpath(root, xpath):
    target = resolve(root, xpath.get("expr"))
    position = xpath.get("position", "inside")
    children = list(xpath)
    parents = parent_map(root)
    if position == "inside":
        target.extend(children)
        return
    parent = parents[target]
    index = list(parent).index(target)
    if position == "replace":
        parent.remove(target)
        for offset, child in enumerate(children):
            parent.insert(index + offset, child)
    elif position == "before":
        for offset, child in enumerate(children):
            parent.insert(index + offset, child)
    elif position == "after":
        for offset, child in enumerate(children):
            parent.insert(index + 1 + offset, child)
    else:
        raise ValueError(f"unsupported position: {position}")


def main():
    module_dir, out_path = sys.argv[1], sys.argv[2]
    core = load_core()
    merged = ElementTree.Element("templates")
    v2_dir = os.path.join(module_dir, "static", "src", "int_filemanager", "v2")
    for path in sorted(glob.glob(os.path.join(v2_dir, "*.xml"))):
        for template in ElementTree.parse(path).getroot():
            base_name = template.get("t-inherit")
            if not base_name:
                merged.append(template)
                continue
            base = copy.deepcopy(core[base_name])
            base.set("t-name", template.get("t-name"))
            for xpath in template.iter("xpath"):
                apply_xpath(base, xpath)
            merged.append(base)
    own_names = [t.get("t-name") for t in merged]
    # Core templates the merged ones call into must be present for OWL to compile them.
    for name, element in core.items():
        if name not in own_names:
            merged.append(element)
    ElementTree.ElementTree(merged).write(out_path, encoding="utf-8")
    with open(out_path + ".own", "w", encoding="utf-8") as f:
        f.write(chr(10).join(own_names))
    print(f"{len(own_names)} own template(s) written to {out_path}")


if __name__ == "__main__":
    main()
