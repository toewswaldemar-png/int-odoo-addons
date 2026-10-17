import uuid
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import SQL
from odoo.tools.misc import hash_sign, verify_hash_signed

from ..tools.request_brake import RequestBrake
from .int_filemanager_link import FOLDER_ONLY_KEY

# The path of the page of a share; the token follows.
SHARE_PATH = "/int_filemanager/share"
# What the settings say when they are not saved. The names are those of the parameters
# (``int_filemanager.<name>``), the types those of the values.
SHARE_DEFAULTS = {
    "share_creators": "user",
    "share_default_file_mb": 25,
    "share_default_total_mb": 500,
    "share_default_files": 100,
    "share_default_extensions": "",
    "share_max_file_mb": 200,
    "share_max_total_mb": 5 * 1024,
    "share_max_files": 1000,
    "share_password_length": 8,
    "share_unlock_hours": 12,
    # The brakes: "1" on, "0" off (a selection: Odoo does not save a 0 of a number, and a boolean
    # that is on by default can never be switched off). The brake on passwords has no switch.
    "share_brake": "1",
    "share_invalid_tokens": 20,
    "share_password_tries_ip": 5,
    "share_password_tries_share": 30,
    "share_requests_per_minute": 120,
}
# The longest password: the hash is made of all of it.
PASSWORD_MAX_LENGTH = 128
# What the guests of a folder share reach, per model: the field that names the folder.
SCOPE_FOLDER_FIELD = {
    "int.filemanager.folder": "id",
    "int.filemanager.document": "folder_id",
}
# The key that opens a share with a password (``hash_sign``): its scope, and how long a key may
# be before it is not looked at (a real one is about 100 characters).
UNLOCK_SCOPE = "int_filemanager.share_unlock"
UNLOCK_KEY_MAX_LENGTH = 512
# Seconds that the brakes look back: wrong passwords and made-up tokens within ten minutes,
# requests within a minute.
BRAKE_WINDOW = 600
REQUEST_WINDOW = 60
# What the code alone sets, never a user through RPC (``readonly`` holds in the interface only):
# a token that is guessable, a counter that is set back, an upload folder that is not the one made
# for the share.
SERVER_FIELDS = (
    "token",
    "view_count",
    "download_count",
    "last_access",
    "upload_count",
    "upload_size",
    "upload_folder_id",
)


class ShareDenied(UserError):
    """A guest is turned away. Odoo answers a ``UserError`` of a route of type ``http`` with its
    ``http_status`` and its text only, no traceback; the text is meant for the guest."""


class ShareBadRequest(ShareDenied):
    http_status = 400


class ShareNotFound(ShareDenied):
    http_status = 404


class ShareForbidden(ShareDenied):
    http_status = 403


class ShareGone(ShareDenied):
    http_status = 410


class ShareBusy(ShareDenied):
    http_status = 429


class IntFilemanagerShare(models.Model):
    """A link that gives a file or a folder to whoever has it, with no account.

    What the guest may do is set on the link (see, download, upload), not taken from the user who
    made it. The link ends at its expiration date, at its limit of downloads, or when it is
    blocked (archived). The password is kept as a hash that no user can read.
    """

    _name = "int.filemanager.share"
    _description = "Filemanager share"
    _inherit = ["mail.thread"]
    _order = "id desc"

    @api.model
    def _default_token(self):
        return str(uuid.uuid4())

    name = fields.Char(
        required=True,
        compute="_compute_name",
        store=True,
        precompute=True,
        readonly=False,
        tracking=True,
    )
    folder_id = fields.Many2one(
        "int.filemanager.folder", ondelete="cascade", index="btree_not_null"
    )
    document_id = fields.Many2one(
        "int.filemanager.document", ondelete="cascade", index="btree_not_null"
    )
    token = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._default_token(),
        help="The secret part of the address. Whoever has the address has the share.",
    )
    url = fields.Char(string="Address", compute="_compute_url")
    expiration_date = fields.Datetime(
        help="After this moment the link does not work any more. Empty: it never ends.",
        tracking=True,
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
        help="A blocked link (archived) does not work, and can be unblocked.",
    )
    can_view = fields.Boolean(string="See", default=True, tracking=True)
    can_download = fields.Boolean(string="Download", default=True, tracking=True)
    can_upload = fields.Boolean(
        string="Upload",
        tracking=True,
        help="Folders only. The guests put files into a folder of their own below the shared "
        "folder, which only you and the administrators see.",
    )
    can_search_text = fields.Boolean(
        string="Search in the text",
        tracking=True,
        help="Folders only. The guests may search in the text of the files that they see.",
    )
    password_hash = fields.Char(groups="base.group_system", copy=False)
    password = fields.Char(
        compute="_compute_password",
        inverse="_inverse_password",
        copy=False,
        help="Whoever opens the link has to type it. It is never shown again; leave it empty "
        "to keep the one that is set.",
    )
    has_password = fields.Boolean(compute="_compute_has_password", compute_sudo=True)
    max_downloads = fields.Integer(
        string="Downloads allowed",
        default=0,
        tracking=True,
        help="Files only. The link ends after this many downloads. 0: no limit. Only the "
        "download button counts: a file that the guest may see in the browser can be saved "
        "without it.",
    )
    view_count = fields.Integer(string="Visits", default=0, readonly=True, copy=False)
    download_count = fields.Integer(string="Downloads", default=0, readonly=True, copy=False)
    last_access = fields.Datetime(readonly=True, copy=False)
    upload_max_file_mb = fields.Integer(
        string="Largest file (MB)",
        default=lambda self: self._setting("share_default_file_mb"),
        tracking=True,
    )
    upload_max_total_mb = fields.Integer(
        string="All files together (MB)",
        default=lambda self: self._setting("share_default_total_mb"),
        tracking=True,
    )
    upload_max_files = fields.Integer(
        string="Number of files",
        default=lambda self: self._setting("share_default_files"),
        tracking=True,
    )
    upload_extensions = fields.Char(
        string="Allowed endings",
        default=lambda self: self._setting("share_default_extensions") or False,
        tracking=True,
        help="Separated by commas: pdf, jpg. Empty: every ending, except those that can run "
        "as a program or a page.",
    )
    upload_count = fields.Integer(string="Files uploaded", default=0, readonly=True, copy=False)
    # Float, not Integer: an int4 column overflows above 2 GiB.
    upload_size = fields.Float(string="Bytes uploaded", default=0, readonly=True, copy=False)
    upload_folder_id = fields.Many2one(
        "int.filemanager.folder",
        string="Upload folder",
        readonly=True,
        copy=False,
        ondelete="set null",
        index="btree_not_null",
    )
    company_id = fields.Many2one(
        "res.company",
        compute="_compute_company_id",
        store=True,
        index=True,
        help="The company of the folder or the file; empty if it has none.",
    )
    state = fields.Selection(
        [
            ("valid", "Valid"),
            ("expired", "Expired"),
            ("blocked", "Blocked"),
            ("limit", "Limit reached"),
            ("archived", "Target archived"),
        ],
        compute="_compute_state",
    )

    _token_uniq = models.UniqueIndex("(token)", "This token is taken.")
    _target = models.Constraint(
        "CHECK((folder_id IS NULL) != (document_id IS NULL))",
        "A share has a folder or a file as its target, not both and not none.",
    )
    _max_downloads_positive = models.Constraint(
        "CHECK(max_downloads >= 0)", "The downloads allowed cannot be negative."
    )
    _upload_limits_positive = models.Constraint(
        "CHECK(upload_max_file_mb > 0 AND upload_max_total_mb > 0 AND upload_max_files > 0)",
        "The limits of the uploads have to be at least 1.",
    )
    _upload_use_positive = models.Constraint(
        "CHECK(upload_count >= 0 AND upload_size >= 0)", "What was uploaded cannot be negative."
    )

    @api.depends("folder_id", "document_id")
    def _compute_name(self):
        # The name of the target is the start of the name of the share; it can be changed.
        for share in self:
            if not share.name:
                share.name = (share.folder_id or share.document_id).name

    @api.depends("token")
    def _compute_url(self):
        for share in self:
            share.url = f"{share.get_base_url()}{SHARE_PATH}/{share.token}" if share.token else False

    def _compute_password(self):
        # Never readable; the field is for typing.
        self.password = False

    def _inverse_password(self):
        minimum = self._setting("share_password_length")
        crypt_context = self.env["res.users"]._crypt_context()
        for share in self:
            if not share.password:
                continue
            if not minimum <= len(share.password) <= PASSWORD_MAX_LENGTH:
                raise UserError(
                    self.env._(
                        "The password needs between %(minimum)s and %(maximum)s characters.",
                        minimum=minimum,
                        maximum=PASSWORD_MAX_LENGTH,
                    )
                )
            # sudo: only the hash is written, in a field that no user may write.
            share.sudo().password_hash = crypt_context.hash(share.password)
            share.message_post(body=self.env._("The password was set."))
        # What was typed is not kept: the screen that saved it does not get it back.
        self.invalidate_recordset(["password"])

    @api.depends("password_hash")
    def _compute_has_password(self):
        for share in self:
            share.has_password = bool(share.password_hash)

    @api.depends("folder_id.company_id", "document_id.company_id")
    def _compute_company_id(self):
        for share in self:
            share.company_id = (share.folder_id or share.document_id).company_id

    @api.depends(
        "active",
        "expiration_date",
        "max_downloads",
        "download_count",
        "folder_id.active",
        "document_id.active",
    )
    def _compute_state(self):
        now = fields.Datetime.now()
        for share in self:
            if not share.active:
                share.state = "blocked"
            elif share.expiration_date and share.expiration_date <= now:
                share.state = "expired"
            elif share.max_downloads and share.download_count >= share.max_downloads:
                share.state = "limit"
            elif not (share.folder_id or share.document_id).active:
                share.state = "archived"
            else:
                share.state = "valid"

    @api.constrains("can_view", "can_download", "can_upload")
    def _check_a_right(self):
        for share in self:
            if not (share.can_view or share.can_download or share.can_upload):
                raise ValidationError(
                    self.env._("A share has to allow at least one of: see, download, upload.")
                )

    @api.constrains("can_upload", "can_search_text", "max_downloads", "document_id", "can_view", "can_download")
    def _check_target_kind(self):
        for share in self:
            if share.document_id and (share.can_upload or share.can_search_text):
                raise ValidationError(
                    self.env._("Uploading and searching in the text are for folders only.")
                )
            if share.folder_id and share.max_downloads:
                raise ValidationError(self.env._("A limit of downloads is for files only."))
            if share.can_search_text and not (share.can_view or share.can_download):
                raise ValidationError(
                    self.env._("To search in the text the guests have to see or download.")
                )

    @api.constrains("expiration_date")
    def _check_expiration_date(self):
        now = fields.Datetime.now()
        for share in self:
            if share.expiration_date and share.expiration_date <= now:
                raise ValidationError(self.env._("The expiration date has to be in the future."))

    @api.constrains("upload_max_file_mb", "upload_max_total_mb", "upload_max_files")
    def _check_upload_ceilings(self):
        ceilings = {
            "upload_max_file_mb": "share_max_file_mb",
            "upload_max_total_mb": "share_max_total_mb",
            "upload_max_files": "share_max_files",
        }
        for share in self:
            for field, key in ceilings.items():
                ceiling = self._setting(key)
                if share[field] > ceiling:
                    raise ValidationError(
                        self.env._(
                            "%(field)s: at most %(ceiling)s, the limit that the administrators set.",
                            field=share._fields[field]._description_string(self.env),
                            ceiling=ceiling,
                        )
                    )

    @api.model
    def _check_may_share(self, vals_list):
        """Who may make a share, and of what: whatever the folders show to the user.

        A file that a user sees only through a record that it is linked to (the rule of the
        document, ``access_via_record``) is not theirs to pass on: the folder has to show it. As
        for ``int.filemanager.link``.
        """
        if self._setting("share_creators") == "admin" and not self.env.user.has_group(
            "int_filemanager.int_filemanager_group_admin"
        ):
            raise AccessError(self.env._("Only the filemanager administrators may make shares."))
        folders = (
            self.env["int.filemanager.folder"]
            .browse({vals["folder_id"] for vals in vals_list if vals.get("folder_id")})
            .exists()
        )
        documents = (
            self.env["int.filemanager.document"]
            .with_context(**{FOLDER_ONLY_KEY: True})
            .browse({vals["document_id"] for vals in vals_list if vals.get("document_id")})
            .exists()
        )
        if folders != folders._filtered_access("read") or documents != documents._filtered_access("read"):
            raise AccessError(
                self.env._("You may only share a folder or a file that the folders show to you.")
            )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            self._check_may_share(vals_list)
            vals_list = [
                {key: value for key, value in vals.items() if key not in SERVER_FIELDS}
                for vals in vals_list
            ]
        shares = super().create(vals_list)
        shares._ensure_upload_folder()
        return shares

    def write(self, vals):
        # A share keeps its target: the upload folder, the rights and the limits fit the target.
        # Who wants another target makes a new share.
        for key in ("folder_id", "document_id"):
            if key in vals and any(share[key].id != vals[key] for share in self):
                raise UserError(
                    self.env._("The target of a share cannot be changed. Make a new share.")
                )
        if not self.env.su:
            vals = {key: value for key, value in vals.items() if key not in SERVER_FIELDS}
        result = super().write(vals)
        self._ensure_upload_folder()
        return result

    def action_remove_password(self):
        """Let the link work without a password."""
        self.check_access("write")
        shares = self.sudo().filtered("password_hash")
        shares.password_hash = False
        for share in shares:
            share.with_env(self.env).message_post(body=self.env._("The password was removed."))

    def _upload_folder_usable(self):
        """Whether the guests can still upload: the folder is there, is active and below the target."""
        self.ensure_one()
        # sudo: how the folders lie is not what the user sees.
        share = self.sudo()
        folder = share.upload_folder_id
        return bool(
            folder
            and folder.active
            and folder != share.folder_id
            and folder.parent_path.startswith(share.folder_id.parent_path)
        )

    def _ensure_upload_folder(self):
        """Make the folder for the uploads of the guests, below the shared folder.

        When the share is saved, not at the first upload: two guests that upload at once would
        both make it. Only the user who made the share, and the administrators, see it (as a
        folder is restricted to its allowed users); the guests do not see each other's files.
        An upload folder that is still there and below the target is used again.
        """
        Folder = self.env["int.filemanager.folder"].sudo().with_context(mail_create_nosubscribe=True)
        for share in self.filtered(lambda share: share.active and share.can_upload and share.folder_id):
            if share._upload_folder_usable():
                continue
            parent = share.folder_id.sudo()
            folder = Folder._create_numbered(
                self.env._("Uploads - %(name)s", name=share.name),
                parent,
                access_mode="restricted",
                access_user_ids=[Command.set(share.create_uid.ids)],
                company_id=parent.company_id.id,
            )
            share.sudo().upload_folder_id = folder

    @api.model
    def _setting(self, key):
        """The value of a setting of the shares (``SHARE_DEFAULTS`` says which type it has)."""
        default = SHARE_DEFAULTS[key]
        value = self.env["ir.config_parameter"].sudo().get_param(f"int_filemanager.{key}", default)
        return type(default)(value)

    # --- the guest: finding the share, the password, the brakes --------------------------------

    @api.model
    def _brake(self):
        """The counters of the brakes in memory (one per registry, so one per database)."""
        registry = self.env.registry
        brake = getattr(registry, "_int_filemanager_share_brake", None)
        if brake is None:
            brake = registry._int_filemanager_share_brake = RequestBrake()
        return brake

    @api.model
    def _brake_is_on(self):
        return self._setting("share_brake") == "1"

    @api.model
    def _resolve(self, token, ip, right=None, key=None, needs_key=True, braked=True):
        """The share (as superuser) that a guest comes to with the token, or why not.

        The order is part of what it promises: what is cheap to check comes first, and what the
        guest may learn grows with each step. A made-up token says nothing but "not found" (and
        counts toward the brake of the address); a share that is blocked or over says so before
        it asks for the password; the password comes before the right, so that nobody without it
        learns what the share allows.

        :param ip: the address of the guest, for the brakes
        :param right: ``"view"``, ``"download"`` or ``"upload"``, or several of them (one of them
            is enough); empty: any
        :param key: the key that ``_unlock`` gave, for a share with a password
        :param needs_key: ``False`` for the calls that come before the password: the page that
            asks for it, and the call that checks it
        :param braked: ``False`` for the call that checks the password (its brake is its own)
        """
        share = self._find_by_token(token, ip)
        if braked and self._brake_is_on():
            limit = self._setting("share_requests_per_minute")
            if self._brake().hit(("requests", share.id, ip), REQUEST_WINDOW) > limit:
                raise ShareBusy(self.env._("Too many requests. Try again in a minute."))
        messages = {
            "blocked": self.env._("This link has been blocked."),
            "expired": self.env._("This link has expired."),
            "limit": self.env._("This link has reached its limit of downloads."),
            "archived": self.env._("What this link shared is not available any more."),
        }
        if share.state != "valid":
            raise ShareGone(messages[share.state])
        if share.has_password and needs_key and not share._key_is_valid(key):
            raise ShareForbidden(self.env._("This link needs its password."))
        rights = (right,) if isinstance(right, str) else (right or ())
        if rights and not any(share[f"can_{name}"] for name in rights):
            raise ShareForbidden(self.env._("This link does not allow that."))
        return share

    @api.model
    def _find_by_token(self, token, ip):
        """The share of the token, also a blocked one (``active_test=False``): the guest is told
        that it is blocked, which is not what "not found" says. Any token that does not lead to
        a share counts toward the brake of the address; one that does is let through."""
        share = self.browse()
        # A token is a uuid: 36 characters. Anything else is not looked up.
        if isinstance(token, str) and len(token) == 36:
            share = (
                self.sudo().with_context(active_test=False).search([("token", "=", token)], limit=1)
            )
        if share:
            # active_test=False was for the search; what the share leads to is looked up as usual
            return share.with_context(active_test=True)
        if self._brake_is_on():
            limit = self._setting("share_invalid_tokens")
            if self._brake().hit(("tokens", ip), BRAKE_WINDOW) > limit:
                raise ShareBusy(self.env._("Too many wrong addresses. Try again later."))
        raise ShareNotFound(self.env._("This link does not exist."))

    def _unlock_secret(self):
        """The secret of the key of this share: the one of the database and the hash of the
        password. A key does not outlive a change of the password."""
        self.ensure_one()
        secret = self.env["ir.config_parameter"].sudo().get_param("database.secret")
        return f"{secret}:{self.password_hash}"

    def _unlock_key(self):
        """The key that a guest who knew the password keeps, for the hours of the settings."""
        self.ensure_one()
        return hash_sign(
            self.sudo().env,
            UNLOCK_SCOPE,
            [self.id],
            expiration_hours=self._setting("share_unlock_hours"),
            secret=self._unlock_secret(),
        )

    def _key_is_valid(self, key):
        """Whether the key is one that ``_unlock_key`` made for this share, and is still good."""
        self.ensure_one()
        if not self.password_hash or not isinstance(key, str) or len(key) > UNLOCK_KEY_MAX_LENGTH:
            return False
        try:
            values = verify_hash_signed(
                self.sudo().env, UNLOCK_SCOPE, key, secret=self._unlock_secret()
            )
        except ValueError:  # not base64, not text, not JSON: the errors of all three are ValueErrors
            return False
        return values == [self.id]

    def _unlock(self, password, ip):
        """The key for the password, or ``False`` if it is wrong.

        A wrong password is kept in the database (``int.filemanager.share.attempt``) and counts
        toward the brake, per address and for the share as a whole; the hash takes about half a
        second to check, so the brake comes first. A right password clears the tries of its
        address. The brake on passwords has no switch.
        """
        self.ensure_one()
        if not self.password_hash:
            return False
        Attempt = self.env["int.filemanager.share.attempt"].sudo()
        since = fields.Datetime.now() - timedelta(seconds=BRAKE_WINDOW)
        by_share = Attempt.search_count([("share_id", "=", self.id), ("create_date", ">", since)])
        by_ip = Attempt.search_count(
            [("share_id", "=", self.id), ("ip", "=", ip), ("create_date", ">", since)]
        )
        if by_ip >= self._setting("share_password_tries_ip") or by_share >= self._setting(
            "share_password_tries_share"
        ):
            raise ShareBusy(self.env._("Too many wrong passwords. Try again later."))
        crypt_context = self.env["res.users"]._crypt_context()
        if (
            isinstance(password, str)
            and len(password) <= PASSWORD_MAX_LENGTH
            and crypt_context.verify(password, self.password_hash)
        ):
            Attempt.search([("share_id", "=", self.id), ("ip", "=", ip)]).unlink()
            return self._unlock_key()
        Attempt.create({"share_id": self.id, "ip": ip})
        return False

    # --- what the guests reach -----------------------------------------------------------------

    def _hidden_folders(self):
        """The folders below the shared folder that the guests do not see, and what lies below them.

        Those that say "only the users and groups allowed" (also if a folder below them is open
        again: it lies in a hidden tree), and the folder for the uploads of this share, also if
        somebody opened it.
        """
        self.ensure_one()
        folders = self.env["int.filemanager.folder"].sudo().with_context(active_test=False)
        hidden = folders.search(
            [
                ("id", "child_of", self.folder_id.id),
                ("id", "!=", self.folder_id.id),
                ("access_mode", "=", "restricted"),
            ]
        )
        return hidden | self.sudo().upload_folder_id

    def _scope_domain(self, model):
        """The domain on ``model`` (folders or documents) of everything that the guests may reach.

        The rules of records do not apply to the guests' reading (it runs as superuser), so this
        domain is all that bounds them: it is joined to every search by ``&``, whatever they
        ask for, and used to check every id they name. The shared folder and the folders below
        it, without the hidden ones; for a file, the file; only what is active (the search
        takes care of it); only the company of the share, if it has one.
        """
        self.ensure_one()
        if self.document_id:
            if model == "int.filemanager.document":
                return Domain("id", "=", self.document_id.id)
            return Domain.FALSE
        field = SCOPE_FOLDER_FIELD[model]
        domain = Domain(field, "child_of", self.folder_id.id)
        hidden = self._hidden_folders()
        if hidden:
            domain &= ~Domain(field, "child_of", hidden.ids)
        if self.company_id:
            domain &= Domain("company_id", "in", [False, self.company_id.id])
        return domain

    # --- the counters --------------------------------------------------------------------------

    def _count_visit(self):
        """Count a visit of the page: at most one a minute, which is what ``view_count`` means.

        One ``UPDATE`` of the two columns, no ``write`` (no chatter, no new ``write_date``). A
        share that many guests open at once is a hot row: under ``REPEATABLE READ`` a statement
        on a row that another transaction has changed fails and the whole request is run again.
        The condition on ``last_access`` keeps all but one of them from changing it.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        self.flush_recordset(["view_count", "last_access"])
        updated = self.env.execute_query(
            SQL(
                """
                UPDATE int_filemanager_share
                   SET view_count = view_count + 1, last_access = %(now)s
                 WHERE id = %(id)s AND (last_access IS NULL OR last_access < %(since)s)
             RETURNING id
                """,
                now=now,
                id=self.id,
                since=now - timedelta(minutes=1),
            )
        )
        if updated:
            self._after_counting(["view_count", "last_access"])
        return bool(updated)

    def _count_download(self):
        """Count a download; ``False`` if the limit of the share is reached by then.

        Exact: the condition is in the statement, so two guests that download at the same time
        cannot both take the last one (the second one is run again after the first and sees the
        new count).
        """
        self.ensure_one()
        self.flush_recordset(["max_downloads", "download_count", "last_access"])
        updated = self.env.execute_query(
            SQL(
                """
                UPDATE int_filemanager_share
                   SET download_count = download_count + 1, last_access = %(now)s
                 WHERE id = %(id)s AND (max_downloads = 0 OR download_count < max_downloads)
             RETURNING id
                """,
                now=fields.Datetime.now(),
                id=self.id,
            )
        )
        if updated:
            self._after_counting(["download_count", "last_access"])
        return bool(updated)

    def _after_counting(self, names):
        """What the ORM has to know after a counter was changed in SQL: the cache, and the state
        that depends on the download count."""
        self.invalidate_recordset(names)
        self.modified(names)
