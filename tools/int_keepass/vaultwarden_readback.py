"""Reads an account with vaultwarden.read_vaultwarden and checks the item that the official CLI added.

    python3 vaultwarden_readback.py BASE_URL MODULE_DIR EMAIL PASSWORD
"""

import sys

base, module_dir, email, password = sys.argv[1:5]
sys.path.insert(0, module_dir)
import vaultwarden as vw  # noqa: E402

result = vw.read_vaultwarden(base, email, password)
entries = {e["title"]: e for e in result["entries"]}
added = entries.get("FromBw")
ok = (
    added is not None
    and added["username"] == "bwuser"
    and added["url"] == "https://bw.example"
    and "BWSECRET" not in str(result)
)
print("read back an item made by the official CLI:", "PASS" if ok else f"FAIL {added}")
print("all titles:", sorted(entries))
sys.exit(0 if ok else 1)
