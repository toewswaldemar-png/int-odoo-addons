"""Check the reader against a real Vaultwarden account, without Odoo. It only reads.

    python int_keepass/tools/vaultwarden_check.py BASE_URL [--insecure]

E-mail address and master password are asked for on the terminal. Only counts and folder names
are printed, no item names, user names, addresses or passwords. With --insecure the certificate
is not checked (a self-signed one): the fingerprint of the one the server shows is printed so
that it can be compared with the server's own.
"""

import argparse
import getpass
import hashlib
import importlib.util
import pathlib
import ssl
import urllib.parse
from collections import Counter

spec = importlib.util.spec_from_file_location("vaultwarden", pathlib.Path(__file__).parent.parent / "vaultwarden.py")
vw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--insecure", action="store_true", help="do not check the certificate")
    args = parser.parse_args()

    import requests

    session = requests.Session()
    if args.insecure:
        import urllib3

        urllib3.disable_warnings()
        session.verify = False
        parts = urllib.parse.urlparse(args.base_url)
        pem = ssl.get_server_certificate((parts.hostname, parts.port or 443))
        print("certificate SHA-256:", hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest())

    email = input("E-mail address: ").strip()
    password = getpass.getpass("Master password: ")
    try:
        result = vw.read_vaultwarden(args.base_url, email, password, session=session)
    except vw.TwoFactorRequired as error:
        raise SystemExit(f"STOP: {error}")
    except vw.BadCredentials as error:
        raise SystemExit(f"STOP: {error}")

    groups, entries = result["groups"], result["entries"]
    children = {}
    for group in groups:
        children.setdefault(group["parent"], []).append(group)
    per_group = Counter(entry["group"] for entry in entries)
    print(f"{len(groups)} folders, {len(entries)} items")

    def show(parent, depth):
        for group in sorted(children.get(parent, []), key=lambda g: g["name"].lower()):
            print(f"{'  ' * depth}{group['name']} ({per_group[group['uuid']]})")
            show(group["uuid"], depth + 1)

    show(None, 0)
    if per_group[None]:
        print(f"(without folder: {per_group[None]} items)")
    print("left out:", result["skipped"])
    known = {group["uuid"] for group in groups}
    print("every item points to a known folder:", all(e["group"] in known or e["group"] is None for e in entries))
    print("items without a name:", sum(1 for e in entries if not e["title"]))


if __name__ == "__main__":
    main()
