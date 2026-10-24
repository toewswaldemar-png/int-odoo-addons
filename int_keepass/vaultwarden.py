"""Reads folders and logins of one Vaultwarden (Bitwarden) account; no Odoo imports.

Experiment. The server keeps only what the clients encrypted, so the reading happens here: the
master key comes from the master password (PBKDF2 or Argon2id, the salt is the e-mail address),
it is stretched with HKDF, opens the account's user key, and that key opens every name, user
name and address. The master password hash that logs in is derived from the master key and
cannot open the vault.

Not covered yet: organizations and collections (their items are skipped), two-step login.
"""

import base64
import hashlib
import hmac
import os
import uuid
import warnings

import requests
from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
from requests.adapters import HTTPAdapter

KDF_PBKDF2 = 0
KDF_ARGON2ID = 1
LOGIN_TYPE = 1
DEVICE_TYPE_CLI = 23
# Vaultwarden answers 401 to clients that do not say which Bitwarden client version they speak.
CLIENT_HEADERS = {"Bitwarden-Client-Name": "cli", "Bitwarden-Client-Version": "2025.8.0"}


class VaultwardenError(Exception):
    pass


class BadCredentials(VaultwardenError):
    pass


class TwoFactorRequired(VaultwardenError):
    pass


def _get(data, name, default=None):
    """Value of a JSON key whatever its case (Bitwarden answers in camelCase and PascalCase)."""
    for key, value in data.items():
        if key.lower() == name.lower():
            return value
    return default


def derive_master_key(password, email, kdf, iterations, memory=None, parallelism=None):
    salt = email.strip().lower().encode()
    if kdf == KDF_PBKDF2:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations, 32)
    if kdf == KDF_ARGON2ID:
        return hash_secret_raw(
            password.encode(),
            hashlib.sha256(salt).digest(),
            time_cost=iterations,
            memory_cost=memory * 1024,
            parallelism=parallelism,
            hash_len=32,
            type=Type.ID,
        )
    raise VaultwardenError(f"unknown KDF type {kdf}")


def master_password_hash(master_key, password):
    """What the server gets to log in: one more PBKDF2 round, salted with the password."""
    return base64.b64encode(hashlib.pbkdf2_hmac("sha256", master_key, password.encode(), 1, 32)).decode()


def stretch_key(master_key):
    """64 bytes: 32 to encrypt, 32 to sign (HKDF-Expand with the labels "enc" and "mac")."""
    return b"".join(HKDFExpand(hashes.SHA256(), 32, info).derive(master_key) for info in (b"enc", b"mac"))


def decrypt(enc_string, key):
    """Open an EncString of type 2 (``2.iv|data|mac``): check the MAC first, then AES-256-CBC."""
    kind, _, rest = enc_string.partition(".")
    if kind != "2":
        raise VaultwardenError(f"unsupported EncString type {kind!r}")
    iv, data, mac = (base64.b64decode(part) for part in rest.split("|"))
    expected = hmac.new(key[32:], iv + data, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, mac):
        raise VaultwardenError("the MAC of an encrypted value does not match")
    decryptor = Cipher(algorithms.AES(key[:32]), modes.CBC(iv)).decryptor()
    unpadder = padding.PKCS7(128).unpadder()
    padded = decryptor.update(data) + decryptor.finalize()
    return unpadder.update(padded) + unpadder.finalize()


def encrypt(plain, key):
    """The counterpart of :func:`decrypt` (the tests build their account with it)."""
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    encryptor = Cipher(algorithms.AES(key[:32]), modes.CBC(iv)).encryptor()
    data = encryptor.update(padder.update(plain) + padder.finalize()) + encryptor.finalize()
    mac = hmac.new(key[32:], iv + data, hashlib.sha256).digest()
    return "2." + "|".join(base64.b64encode(part).decode() for part in (iv, data, mac))


def _text(enc_string, key):
    return decrypt(enc_string, key).decode() if enc_string else None


def login(session, base_url, email, password):
    """Log in and return ``(access_token, user_key)``; the user key is 64 bytes."""
    base = base_url.rstrip("/")
    session.headers.update(CLIENT_HEADERS)
    response = session.post(f"{base}/identity/accounts/prelogin", json={"email": email})
    response.raise_for_status()
    prelogin = response.json()
    master_key = derive_master_key(
        password,
        email,
        _get(prelogin, "kdf", KDF_PBKDF2),
        _get(prelogin, "kdfIterations"),
        _get(prelogin, "kdfMemory"),
        _get(prelogin, "kdfParallelism"),
    )
    response = session.post(
        f"{base}/identity/connect/token",
        data={
            "grant_type": "password",
            "username": email,
            "password": master_password_hash(master_key, password),
            "scope": "api offline_access",
            "client_id": "cli",
            "deviceType": DEVICE_TYPE_CLI,
            "deviceName": "odoo",
            "deviceIdentifier": str(uuid.uuid5(uuid.NAMESPACE_URL, base + "/" + email.lower())),
        },
    )
    body = response.json() if response.content else {}
    if response.status_code != 200:
        if _get(body, "TwoFactorProviders"):
            raise TwoFactorRequired("the account asks for a second step; not supported")
        if response.status_code == 400:
            raise BadCredentials("the e-mail address or the master password is wrong")
        response.raise_for_status()
    protected_key = _get(body, "Key")
    if not protected_key:
        raise VaultwardenError("the answer of the login holds no user key")
    return body["access_token"], decrypt(protected_key, stretch_key(master_key))


def read_vaultwarden(base_url, email, password, session=None, timeout=30):
    """Return the raw content like :func:`kdbx.read_kdbx`: folders as groups, logins as entries.

    Passwords and notes are never decrypted. A folder named ``A/B`` is the group ``B`` in ``A``
    (the Bitwarden clients nest folders that way). Items in the trash and items of an
    organization are left out.
    """
    session = session or requests.Session()
    session.headers.update(CLIENT_HEADERS)
    session.request = _with_timeout(session.request, timeout)
    token, user_key = login(session, base_url, email, password)
    response = session.get(
        f"{base_url.rstrip('/')}/api/sync",
        params={"excludeDomains": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    sync = response.json()

    names = {_get(folder, "id"): _text(_get(folder, "name"), user_key) for folder in _get(sync, "folders", [])}
    by_name = {name: folder_id for folder_id, name in names.items()}
    groups = []
    for folder_id, name in names.items():
        parent_name, _, short = name.rpartition("/")
        parent = by_name.get(parent_name) if parent_name else None
        groups.append({"uuid": folder_id, "name": short if parent else name, "parent": parent})

    entries = []
    skipped = {"organization": 0, "trash": 0}
    for cipher in _get(sync, "ciphers", []):
        if _get(cipher, "deletedDate"):
            skipped["trash"] += 1
            continue
        if _get(cipher, "organizationId"):
            skipped["organization"] += 1
            continue
        key = decrypt(_get(cipher, "key"), user_key) if _get(cipher, "key") else user_key
        login_data = _get(cipher, "login") or {}
        uris = _get(login_data, "uris") or []
        entries.append(
            {
                "uuid": _get(cipher, "id"),
                "title": _text(_get(cipher, "name"), key),
                "username": _text(_get(login_data, "username"), key) if _get(cipher, "type") == LOGIN_TYPE else None,
                "url": _text(_get(uris[0], "uri"), key) if uris else None,
                "group": _get(cipher, "folderId"),
            }
        )
    return {"groups": groups, "entries": entries, "skipped": skipped}


def pinned_session(fingerprint):
    """A session that trusts exactly one certificate, given by its SHA-256 fingerprint.

    For a server with a self-signed certificate: the chain and the host name are not checked,
    the fingerprint is. A different certificate (a man in the middle) ends the connection.
    """
    pinned = fingerprint.replace(":", "").strip().lower()

    class PinnedAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            kwargs["assert_fingerprint"] = pinned
            super().init_poolmanager(*args, **kwargs)

    session = requests.Session()
    session.mount("https://", PinnedAdapter())
    session.verify = False  # the fingerprint replaces the check of the chain
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    return session


def _with_timeout(request, timeout):
    def wrapper(*args, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return request(*args, **kwargs)

    return wrapper
