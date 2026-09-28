"""The German translation of the v2 code is complete.

de.po is generated with tools/v2check/i18n_export.sh; this test makes sure a new
message cannot slip in untranslated.
"""

import ast
import glob
import os
import re

from odoo.tests.common import BaseCase, tagged

MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2_PY = [
    *glob.glob(os.path.join(MODULE, "models", "int_filemanager_*.py")),
    os.path.join(MODULE, "zip_stream.py"),
    os.path.join(MODULE, "controllers", "int_filemanager_v2.py"),
]
# JS terms Odoo's own web module already translates (its export leaves them out, and the
# JS translation table is shared by all modules).
CORE_TRANSLATED = {"Bytes", "Delete"}
V2_JS = glob.glob(
    os.path.join(MODULE, "static", "src", "int_filemanager", "v2", "*.js")
)


def po_entries():
    with open(os.path.join(MODULE, "i18n", "de.po"), encoding="utf-8") as f:
        text = f.read()
    entries = {}
    for block in re.split(r"\n\n(?=#\. module:)", text)[1:]:
        msgid = re.search(r"msgid ((?:\".*\"\n)+)msgstr", block)
        msgstr = re.search(r"msgstr ((?:\".*\"\n?)+)", block)
        key = "".join(re.findall(r'"(.*)"', msgid.group(1)))
        value = "".join(re.findall(r'"(.*)"', msgstr.group(1)))
        entries[key] = value
    return entries


def python_messages(path):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        first = node.args[0]
        if (
            name == "_"
            and isinstance(first, ast.Constant)
            and isinstance(first.value, str)
        ):
            yield first.value


@tagged("post_install", "-at_install")
class TestV2Translations(BaseCase):
    def test_no_entry_is_left_untranslated(self):
        empty = [k for k, v in po_entries().items() if k and not v]
        self.assertEqual(empty, [])

    def test_every_python_message_is_translated(self):
        entries = po_entries()
        missing = {
            (os.path.basename(path), message)
            for path in V2_PY
            for message in python_messages(path)
            if entries.get(message.replace("\\", "\\\\").replace('"', '\\"')) is None
        }
        self.assertEqual(missing, set())

    def test_every_js_message_is_translated(self):
        entries = po_entries()
        missing = set()
        for path in V2_JS:
            with open(path, encoding="utf-8") as f:
                source = f.read()
            for match in re.finditer(r'\b_t\(\s*"((?:[^"\\]|\\.)*)"', source):
                message = match.group(1)
                if entries.get(message) is None and message not in CORE_TRANSLATED:
                    missing.add((os.path.basename(path), message))
        self.assertEqual(missing, set())
