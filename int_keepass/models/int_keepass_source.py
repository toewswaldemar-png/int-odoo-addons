import base64
import binascii
import hashlib
import logging
import uuid

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.http import request

from ..cache import MetadataCache, account_key, cache_key
from ..kdbx import read_kdbx

_logger = logging.getLogger(__name__)

ID_MODULUS = 2**31 - 1
# The browser sends the master password (and, for Vaultwarden, the e-mail address) in these
# headers, as base64 of the UTF-8 bytes (a header value cannot hold every character). The
# password is never stored: not in the session, not in the database.
PASSWORD_HEADER = "X-Int-Keepass-Password"
EMAIL_HEADER = "X-Int-Keepass-Email"
DEFAULT_CACHE_SECONDS = 300
SOURCES = ("kdbx", "vaultwarden")
CACHE = MetadataCache()


class IntKeepassSource(models.AbstractModel):
    """Reads a KeePass file or a Vaultwarden account and hands out its groups and entries by integer id.

    Nothing is stored in the database. A worker keeps the groups and entries (no passwords) for
    a few minutes, so the key derivation, which takes about a second, runs once per password
    and worker and not once per request.
    """

    _name = "int.keepass.source"
    _description = "KeePass Database Reader"

    @api.model
    def _header(self, name):
        encoded = request.httprequest.headers.get(name) if request else None
        if not encoded:
            return None
        try:
            return base64.b64decode(encoded, validate=True).decode()
        except (binascii.Error, UnicodeDecodeError) as error:
            raise UserError(_("The KeePass login was sent in a wrong form.")) from error

    @api.model
    def _password(self):
        """The master password of this call: the context (tests, server code) or the request header."""
        return self.env.context.get("int_keepass_password") or self._header(PASSWORD_HEADER)

    @api.model
    def _email(self):
        """The e-mail address of the Vaultwarden account: given by the browser, else the user's own."""
        return (
            self.env.context.get("int_keepass_email")
            or self._header(EMAIL_HEADER)
            or self.env.user.email
            or self.env.user.login
        )

    @api.model
    def _param(self, name):
        return self.env["ir.config_parameter"].sudo().get_param("int_keepass." + name)

    @api.model
    def _source(self):
        source = self._param("source") or "kdbx"
        if source not in SOURCES:
            raise UserError(_("The system parameter int_keepass.source must be one of: %s", ", ".join(SOURCES)))
        return source

    @api.model
    def _cache_seconds(self):
        value = self._param("cache_seconds")
        return int(value) if value and value.isdigit() else DEFAULT_CACHE_SECONDS

    @api.model
    def _path(self):
        path = self._param("kdbx_path")
        if not path:
            raise UserError(_("The system parameter int_keepass.kdbx_path is not set."))
        return path

    @api.model
    def _url(self):
        url = self._param("vaultwarden_url")
        if not url:
            raise UserError(_("The system parameter int_keepass.vaultwarden_url is not set."))
        return url

    @api.model
    def _key(self, password):
        """Key of the worker's cache for the configured source and this login."""
        if self._source() == "vaultwarden":
            return account_key(self._url(), self._email(), password)
        return cache_key(self._path(), password)

    @api.model
    def _read_database(self):
        """Return the raw content of the configured source, see :func:`read_kdbx`."""
        password = self._password()
        if not password:
            raise UserError(_("KeePass is locked. Open it from the KeePass menu and enter the master password."))
        ttl = self._cache_seconds()
        try:
            key = self._key(password)
            raw = CACHE.get(key) if ttl else None
            if raw is None:
                raw = self._read_vaultwarden(password) if self._source() == "vaultwarden" else self._read_kdbx(password)
                if ttl:
                    CACHE.put(key, raw, ttl)
            return raw
        except FileNotFoundError as error:
            raise UserError(_("The KeePass database %s was not found.", self._path())) from error

    @api.model
    def _read_kdbx(self, password):
        try:
            from pykeepass.exceptions import CredentialsError
        except ImportError as error:
            raise UserError(_("The Python library pykeepass is not installed.")) from error
        try:
            return read_kdbx(self._path(), password)
        except CredentialsError as error:
            raise UserError(_("The KeePass password is wrong.")) from error

    @api.model
    def _read_vaultwarden(self, password):
        import requests

        from .. import vaultwarden

        pin = self._param("vaultwarden_cert_sha256")
        session = vaultwarden.pinned_session(pin) if pin else None
        try:
            return vaultwarden.read_vaultwarden(self._url(), self._email(), password, session=session)
        except vaultwarden.BadCredentials as error:
            raise UserError(_("The e-mail address or the master password of the Vaultwarden account is wrong.")) from error
        except vaultwarden.TwoFactorRequired as error:
            raise UserError(_("The Vaultwarden account asks for a second step, which is not supported yet.")) from error
        except requests.exceptions.SSLError as error:
            raise UserError(
                _("The certificate of the Vaultwarden server is not trusted. Set int_keepass.vaultwarden_cert_sha256 to its fingerprint.")
            ) from error
        except requests.exceptions.HTTPError as error:
            if error.response is not None and error.response.status_code == 429:
                raise UserError(_("Vaultwarden is slowing down logins. Try again in a minute.")) from error
            raise UserError(_("Vaultwarden answered with an error (HTTP %s).", getattr(error.response, "status_code", "?"))) from error
        except requests.exceptions.RequestException as error:
            _logger.warning("Vaultwarden request failed: %s (%s)", type(error).__name__, getattr(error.request, "url", "?"))
            raise UserError(_("The Vaultwarden server cannot be reached.")) from error

    @api.model
    def _forget(self):
        """Drop what this worker holds for the current login; the password stays with the caller."""
        password = self._password()
        if password:
            try:
                CACHE.drop(self._key(password))
            except (FileNotFoundError, UserError):
                pass

    @api.model
    def _id_of(self, uuid_text):
        """Integer id for a KeePass or Vaultwarden uuid; Odoo's web client needs integers."""
        return uuid.UUID(uuid_text).int % ID_MODULUS + 1

    @api.model
    def _data(self):
        """``{"groups": {id: row}, "entries": {id: row}}`` with ``parent_id`` and ``group_id`` as ids."""
        # per transaction and per login: one request reads the source (or the worker's cache) once
        login = (self._password() or "") + "\0" + (self._email() or "")
        cache_name = "int_keepass.data." + hashlib.sha256(login.encode()).hexdigest()
        cache = self.env.cr.cache
        if cache_name not in cache:
            raw = self._read_database()
            groups = self._index(raw["groups"], lambda row: {"name": row["name"], "parent_id": self._ref(row["parent"])})
            entries = self._index(
                raw["entries"],
                lambda row: {
                    "title": row["title"],
                    "username": row["username"],
                    "url": row["url"],
                    "group_id": self._ref(row["group"]),
                },
            )
            cache[cache_name] = {"groups": groups, "entries": entries}
        return cache[cache_name]

    @api.model
    def _ref(self, uuid_text):
        return self._id_of(uuid_text) if uuid_text else False

    @api.model
    def _index(self, rows, to_values):
        indexed = {}
        for row in rows:
            record_id = self._id_of(row["uuid"])
            if record_id in indexed:
                raise UserError(_("Two uuids map to the same record id: %s", row["uuid"]))
            indexed[record_id] = to_values(row)
        return indexed
