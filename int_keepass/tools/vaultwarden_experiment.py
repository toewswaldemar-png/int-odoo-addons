"""Builds a test account on a throwaway Vaultwarden and reads it back with vaultwarden.read_vaultwarden.

    python3 vaultwarden_experiment.py BASE_URL MODULE_DIR

Only for a Vaultwarden that can be thrown away (SIGNUPS_ALLOWED=true). It plays the part of the
Bitwarden clients: it makes the keys, encrypts the names and fields, and registers the account.
"""

import os
import sys
import uuid

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

BASE = sys.argv[1].rstrip("/")
sys.path.insert(0, sys.argv[2])
import vaultwarden as vw  # noqa: E402

SECRET = "SECRET-PASSWORD"
NOTE = "SECRET-NOTE"
results = []


def check(name, condition, detail=""):
    results.append(condition)
    print(("PASS " if condition else "FAIL ") + name + (f"  [{detail}]" if detail and not condition else ""))


def register(email, password, kdf, iterations, memory=None, parallelism=None):
    master_key = vw.derive_master_key(password, email, kdf, iterations, memory, parallelism)
    stretched = vw.stretch_key(master_key)
    user_key = os.urandom(64)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    der_private = private.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    der_public = private.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    import base64

    body = {
        "email": email,
        "name": "Test",
        "masterPasswordHash": vw.master_password_hash(master_key, password),
        "masterPasswordHint": None,
        "key": vw.encrypt(user_key, stretched),
        "kdf": kdf,
        "kdfIterations": iterations,
        "keys": {
            "encryptedPrivateKey": vw.encrypt(der_private, user_key),
            "publicKey": base64.b64encode(der_public).decode(),
        },
    }
    if kdf == vw.KDF_ARGON2ID:
        body.update(kdfMemory=memory, kdfParallelism=parallelism)
    for path in ("/identity/accounts/register", "/api/accounts/register"):
        response = requests.post(BASE + path, json=body)
        print(f"register {email} via {path}: HTTP {response.status_code}")
        if response.status_code in (200, 204):
            return user_key
        print("   ", response.text[:300])
    raise SystemExit("could not register")


def add_items(email, password):
    session = requests.Session()
    token, user_key = vw.login(session, BASE, email, password)
    headers = {"Authorization": f"Bearer {token}"}

    def folder(name):
        response = session.post(BASE + "/api/folders", json={"name": vw.encrypt(name.encode(), user_key)}, headers=headers)
        response.raise_for_status()
        return response.json()["id"]

    def item(title, user, url, folder_id):
        enc = lambda text: vw.encrypt(text.encode(), user_key) if text else None  # noqa: E731
        body = {
            "type": 1,
            "folderId": folder_id,
            "name": enc(title),
            "notes": enc(NOTE),
            "favorite": False,
            "reprompt": 0,
            "login": {
                "username": enc(user),
                "password": enc(SECRET),
                "uris": [{"uri": enc(url), "match": None}] if url else [],
                "totp": None,
            },
        }
        response = session.post(BASE + "/api/ciphers", json=body, headers=headers)
        response.raise_for_status()
        return response.json()["id"]

    server = folder("Server")
    router = folder("Server/Router")
    web = folder("Web")
    item("Firewall", "admin", "https://fw.example", router)
    item("Backup", "root", None, server)
    item("Shop", "shop", "https://shop.example", web)
    item("Loose", "x", None, None)
    deleted = item("Deleted", "gone", None, web)
    response = session.put(BASE + f"/api/ciphers/{deleted}/delete", headers=headers)
    response.raise_for_status()


def verify(label, email, password):
    result = vw.read_vaultwarden(BASE, email, password)
    names = {g["uuid"]: g["name"] for g in result["groups"]}
    parents = {g["name"]: names.get(g["parent"]) for g in result["groups"]}
    entries = {e["title"]: (names.get(e["group"]), e["username"], e["url"]) for e in result["entries"]}
    print(label, "groups:", sorted(parents.items()))
    print(label, "entries:", sorted(entries.items()))
    check(f"{label}: groups and nesting", parents == {"Server": None, "Router": "Server", "Web": None}, str(parents))
    check(
        f"{label}: entries with group, user name and address",
        entries
        == {
            "Firewall": ("Router", "admin", "https://fw.example"),
            "Backup": ("Server", "root", None),
            "Shop": ("Web", "shop", "https://shop.example"),
            "Loose": (None, "x", None),
        },
        str(entries),
    )
    check(f"{label}: the trashed item is left out", "Deleted" not in entries)
    check(f"{label}: no password or note in the result", SECRET not in str(result) and NOTE not in str(result))
    try:
        vw.read_vaultwarden(BASE, email, password + "x")
    except vw.BadCredentials:
        check(f"{label}: wrong password is refused", True)
    else:
        check(f"{label}: wrong password is refused", False)


for _ in range(60):
    try:
        if requests.get(BASE + "/alive", timeout=2).ok:
            break
    except requests.RequestException:
        pass
    import time

    time.sleep(1)

tag = sys.argv[3] if len(sys.argv) > 3 else uuid.uuid4().hex[:6]
for label, kdf, iterations, memory, parallelism in (
    ("pbkdf2", vw.KDF_PBKDF2, 600000, None, None),
    ("argon2id", vw.KDF_ARGON2ID, 3, 64, 4),
):
    email = f"{label}-{tag}@example.test"
    password = "pässwörd-€-" + tag
    register(email, password, kdf, iterations, memory, parallelism)
    add_items(email, password)
    verify(label, email, password)

print(f"{sum(results)} of {len(results)} checks passed")
sys.exit(0 if all(results) else 1)
