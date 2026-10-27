import calendar
import re
import time
import unicodedata
import uuid
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import SQL
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.misc import (
    hash_sign,
    limited_field_access_token,
    verify_hash_signed,
    verify_limited_field_access_token,
)


from ..tools.request_brake import RequestBrake

# The path of the page of a share; the token follows.
SHARE_PATH = "/int_filemanager/share"
# The default of each setting, used while it is not saved. The keys are the names of the
# parameters (``int_filemanager.<name>``), the types are those of the values.
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
    # The rate limits: "1" on, "0" off (a selection: Odoo does not save a 0 of a number, and a
    # boolean that is on by default can never be switched off). The limit on passwords has no switch.
    "share_brake": "1",
    "share_invalid_tokens": 20,
    "share_password_tries_ip": 5,
    "share_password_tries_share": 30,
    "share_requests_per_minute": 120,
    "share_uploads_per_minute": 10,
}
# How much bigger than the largest file an upload request may be: the form around the file. A
# request to a share that takes no file (any more) may not exceed this.
UPLOAD_FRAME = 64 * 1024
MEBIBYTE = 1024 * 1024
# Bytes from the start of a file that are inspected to find its type.
UPLOAD_HEAD_SIZE = 2048
# The receipt a guest gets for an uploaded file: proof, kept in their browser, that the file is
# theirs (``ir.attachment`` of ``mail`` does the same with its ownership token). It ends with the
# share, after 90 days at the latest. The pattern is checked before the token is verified,
# because the verification does not validate what it is given.
RECEIPT_SCOPE = "int_filemanager.share_receipt"
RECEIPT_DAYS = 90
RECEIPT_PATTERN = re.compile(r"[0-9a-f]{64}o0x[0-9a-f]{1,12}")
RECEIPT_MAX_LENGTH = 128
RECEIPTS_MAX = 100
# Extensions that a guest can never upload, whatever the creator of the share allows: programs and
# scripts, and files that a browser or an office program runs by itself (pages, scripts, macros,
# shortcuts, installers, disk images). The list is in the code, not in the settings: a slip there
# must not open a hole.
BLOCKED_EXTENSIONS = frozenset(
    [
        "exe",
        "com",
        "scr",
        "bat",
        "cmd",
        "msi",
        "msp",
        "mst",
        "dll",
        "sys",
        "drv",
        "ocx",
        "cpl",
        "lnk",
        "url",
        "pif",
        "scf",
        "inf",
        "reg",
        "gadget",
        "application",
        "appx",
        "appxbundle",
        "msix",
        "msixbundle",
        "vb",
        "vbs",
        "vbe",
        "js",
        "jse",
        "mjs",
        "cjs",
        "wsf",
        "wsh",
        "ps1",
        "psm1",
        "psd1",
        "ps1xml",
        "hta",
        "jar",
        "jnlp",
        "sh",
        "bash",
        "zsh",
        "csh",
        "ksh",
        "fish",
        "run",
        "bin",
        "elf",
        "out",
        "command",
        "py",
        "pyc",
        "pyw",
        "pyz",
        "pl",
        "pm",
        "rb",
        "php",
        "php3",
        "php4",
        "php5",
        "php7",
        "phtml",
        "phar",
        "asp",
        "aspx",
        "ashx",
        "asmx",
        "jsp",
        "jspx",
        "cgi",
        "htm",
        "html",
        "xhtml",
        "shtml",
        "mht",
        "mhtml",
        "svg",
        "svgz",
        "xml",
        "xsl",
        "xslt",
        "xsd",
        "swf",
        "chm",
        "hlp",
        "apk",
        "ipa",
        "dmg",
        "pkg",
        "app",
        "iso",
        "img",
        "vhd",
        "vhdx",
        "vmdk",
        "docm",
        "dotm",
        "xlsm",
        "xltm",
        "xlam",
        "pptm",
        "potm",
        "ppam",
        "ppsm",
        "sldm",
        "library-ms",
        "searchconnector-ms",
    ]
)
# Extensions whose files have a known start: the start has to match (a ``.pdf`` that is a page or
# a program is refused). The values are what ``guess_mimetype`` answers for them. Other
# extensions are not checked this way, as the answer is not reliable for them (``guess_mimetype``
# takes noise for a picture).
CONTENT_TYPES_OF = {
    "pdf": {"application/pdf"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "gif": {"image/gif"},
    "webp": {"image/webp"},
    "zip": {"application/zip"},
    "docx": {
        "application/zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    "xlsx": {
        "application/zip",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    "pptx": {
        "application/zip",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    },
    "odt": {"application/zip", "application/vnd.oasis.opendocument.text"},
    "ods": {"application/zip", "application/vnd.oasis.opendocument.spreadsheet"},
    "odp": {"application/zip", "application/vnd.oasis.opendocument.presentation"},
}
# Text extensions: a file with one of these that holds binary data is something else.
TEXT_EXTENSIONS = frozenset(["txt", "csv", "tsv", "md", "log", "rtf", "json"])
# What ``guess_mimetype`` answers for a program, whatever its extension.
EXECUTABLE_TYPES = frozenset(
    [
        "application/x-dosexec",
        "application/x-msdownload",
        "application/x-executable",
        "application/x-sharedlib",
        "application/x-pie-executable",
        "application/x-mach-binary",
    ]
)
# The longest password: the hash is computed over all of it.
PASSWORD_MAX_LENGTH = 128
# For each model that the guests of a folder share reach: the field that names the folder.
SCOPE_FOLDER_FIELD = {
    "int.filemanager.folder": "id",
    "int.filemanager.document": "folder_id",
}
# The key that opens a share with a password (``hash_sign``): its scope, and the length above
# which a key is not even checked (a real one has about 100 characters).
UNLOCK_SCOPE = "int_filemanager.share_unlock"
UNLOCK_KEY_MAX_LENGTH = 512
# Seconds that the rate limits look back: wrong passwords and made-up tokens within ten
# minutes, requests within a minute.
BRAKE_WINDOW = 600
REQUEST_WINDOW = 60
# Set by the code only, never by a user through RPC (``readonly`` holds in the interface only):
# a guessable token, a counter that is set back, an upload folder that is not the one made for
# the share.
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
    """A guest is turned away.

    Odoo answers a ``UserError`` of a route of type ``http`` with its ``http_status`` and its
    text only, no traceback; the text is meant for the guest.
    """


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


class ShareTooLarge(ShareDenied):
    http_status = 413


class ShareUnsupported(ShareDenied):
    http_status = 415


class ShareNoSpace(ShareDenied):
    http_status = 507


class IntFilemanagerShare(models.Model):
    """A link that gives a file or a folder to whoever has it, with no account.

    What the guest may do is set on the link (see, download, upload), not taken from the user
    who made it. The link ends at its expiration date, at its limit of downloads, or when it
    is blocked (archived). The password is kept as a hash that no user can read.
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
            # sudo: int.filemanager.share: only the hash is written, in a field that no user may write
            share.sudo().password_hash = crypt_context.hash(share.password)
            share.message_post(body=self.env._("The password was set."))
        # What was typed is not kept: the screen that saved it does not get it back
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

    @api.constrains("can_upload", "max_downloads", "document_id")
    def _check_target_kind(self):
        for share in self:
            if share.document_id and share.can_upload:
                raise ValidationError(self.env._("Uploading is for folders only."))
            if share.folder_id and share.max_downloads:
                raise ValidationError(self.env._("A limit of downloads is for files only."))

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
        """Check who may make a share, and of what: whatever the folders show to the user.

        A file that a user sees another way than through its folder (a record it is linked to, in
        ``int_filemanager_record``) is not theirs to pass on: the folder has to show it.
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
            .browse({vals["document_id"] for vals in vals_list if vals.get("document_id")})
            .exists()
        )
        if folders != folders._filtered_access("read") or documents != documents._filtered_folder_access("read"):
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

    def action_show_address(self):
        """Open the dialog of the button "Share" again for the saved share, with the address to copy.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Share"),
            "res_model": self._name,
            "res_id": self.id,
            "views": [(self.env.ref("int_filemanager_share.int_filemanager_share_view_form_dialog").id, "form")],
            "target": "new",
        }

    def action_remove_password(self):
        self.check_access("write")
        # sudo: int.filemanager.share: password_hash is readable by system administrators only
        shares = self.sudo().filtered("password_hash")
        shares.password_hash = False
        for share in shares:
            share.with_env(self.env).message_post(body=self.env._("The password was removed."))

    def _upload_folder_usable(self):
        self.ensure_one()
        # sudo: int.filemanager.share: the position of the folders is checked, not what the user sees
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

        It is made when the share is saved, not at the first upload: two guests who upload at once
        would both make it. Only the user who made the share and the administrators see it (the
        folder is restricted to its allowed users); the guests do not see each other's files. An
        upload folder that still exists below the target is used again.
        """
        # sudo: int.filemanager.folder: the upload folder is made for the share, whatever the
        # folder rights of its creator
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
            # sudo: int.filemanager.share: upload_folder_id is set by the code only (``SERVER_FIELDS``)
            share.sudo().upload_folder_id = folder

    @api.model
    def _setting(self, key):
        default = SHARE_DEFAULTS[key]
        # sudo: ir.config_parameter: the settings are read for every user and for guests
        value = self.env["ir.config_parameter"].sudo().get_param(f"int_filemanager.{key}", default)
        return type(default)(value)

    # === GUEST ACCESS === #

    @api.model
    def _brake(self):
        registry = self.env.registry
        brake = getattr(registry, "_int_filemanager_share_brake", None)
        if brake is None:
            brake = registry._int_filemanager_share_brake = RequestBrake()
        return brake

    @api.model
    def _brake_is_on(self):
        return self._setting("share_brake") == "1"

    def _check_upload_brake(self, ip):
        self.ensure_one()
        if self._brake_is_on():
            limit = self._setting("share_uploads_per_minute")
            if self._brake().hit(("uploads", self.id, ip), REQUEST_WINDOW) > limit:
                raise ShareBusy(self.env._("Too many files at once. Try again in a minute."))

    @api.model
    def _resolve(self, token, ip, right=None, key=None, needs_key=True, braked=True):
        """Return the share (as superuser) that a guest comes to with the token, or raise why not.

        The order is part of the contract: cheap checks come first, and the guest learns more
        with each step. A made-up token says only "not found" (and counts toward the rate
        limit of the address); a blocked or over share says so before it asks for the
        password; the password comes before the right, so nobody without it learns what the
        share allows.

        :param ip: the address of the guest, for the rate limits
        :param right: ``"view"``, ``"download"`` or ``"upload"``, or several (one is enough)
        :param key: the key that ``_unlock`` gave, for a share with a password
        :param needs_key: ``False`` for the calls that come before the password
        :param braked: ``False`` for the call that checks the password (own rate limit)
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
    def _lookup(self, token):
        """Return the share of the token (as superuser), also a blocked one, or nothing.

        Nothing is counted and nothing is raised: use it where a side effect is not wanted.
        """
        # A token is a uuid: 36 characters. Anything else is not looked up.
        if not (isinstance(token, str) and len(token) == 36):
            return self.browse()
        # sudo: int.filemanager.share: guests have no rights; the token is the proof
        share = self.sudo().with_context(active_test=False).search([("token", "=", token)], limit=1)
        # active_test=False was for the search only; what the share leads to is looked up as usual
        return share.with_context(active_test=True)

    @api.model
    def _find_by_token(self, token, ip):
        """Return the share of the token, also a blocked one (``active_test=False``).

        The guest is told that it is blocked, which is not what "not found" says. Any token that
        does not lead to a share counts toward the rate limit of the address; one that does is
        let through.
        """
        share = self._lookup(token)
        if share:
            return share
        if self._brake_is_on():
            limit = self._setting("share_invalid_tokens")
            if self._brake().hit(("tokens", ip), BRAKE_WINDOW) > limit:
                raise ShareBusy(self.env._("Too many wrong addresses. Try again later."))
        raise ShareNotFound(self.env._("This link does not exist."))

    def _unlock_secret(self):
        """Return the secret of the key of this share: the database secret and the password hash.

        A key does not outlive a change of the password.
        """
        self.ensure_one()
        # sudo: ir.config_parameter: the database secret is read for guests
        secret = self.env["ir.config_parameter"].sudo().get_param("database.secret")
        return f"{secret}:{self.password_hash}"

    def _unlock_key(self):
        self.ensure_one()
        # sudo: ``hash_sign`` reads the database secret
        return hash_sign(
            self.sudo().env,
            UNLOCK_SCOPE,
            [self.id],
            expiration_hours=self._setting("share_unlock_hours"),
            secret=self._unlock_secret(),
        )

    def _key_is_valid(self, key):
        self.ensure_one()
        if not self.password_hash or not isinstance(key, str) or len(key) > UNLOCK_KEY_MAX_LENGTH:
            return False
        # sudo: ``verify_hash_signed`` reads the database secret
        try:
            values = verify_hash_signed(
                self.sudo().env, UNLOCK_SCOPE, key, secret=self._unlock_secret()
            )
        except ValueError:  # not base64, not text, not JSON: all three raise ValueError
            return False
        return values == [self.id]

    def _unlock(self, password, ip):
        """Return the key for the password, or ``False`` if it is wrong.

        Every try is kept in the database (``int.filemanager.share.attempt``) and counts toward the
        rate limit, per address and for the share as a whole; the hash takes about half a second
        to check, so the rate limit comes first. A right password clears the tries of its
        address. The rate limit on passwords has no switch.
        """
        self.ensure_one()
        if not self.password_hash:
            return False
        self._take_a_try(ip)
        crypt_context = self.env["res.users"]._crypt_context()
        if (
            isinstance(password, str)
            and len(password) <= PASSWORD_MAX_LENGTH
            and crypt_context.verify(password, self.password_hash)
        ):
            self._clear_tries(ip)
            return self._unlock_key()
        return False

    def _take_a_try(self, ip):
        """Take one of the tries of the address for this share, or turn it away (``ShareBusy``).

        The try is written before the password is checked, in a transaction of its own.
        """
        # A lock on the table of the tries makes guests who come at the same moment queue up, and
        # each one counts what the ones before it committed. Without it they would all count the
        # same few tries, all run the hash (half a second of CPU each) and all be let through:
        # under REPEATABLE READ the request sees the table as of its first read. The lock is the
        # first statement of the transaction, so its snapshot is taken after the lock is granted.
        # It is held for the count and one INSERT, not for the hash.
        with self.env.registry.cursor() as cr:
            Attempt = self.env(cr=cr, su=True)["int.filemanager.share.attempt"]
            cr.execute(SQL("LOCK TABLE %s IN SHARE ROW EXCLUSIVE MODE", SQL.identifier(Attempt._table)))
            since = fields.Datetime.now() - timedelta(seconds=BRAKE_WINDOW)
            by_share = Attempt.search_count([("share_id", "=", self.id), ("create_date", ">", since)])
            by_ip = Attempt.search_count(
                [("share_id", "=", self.id), ("ip", "=", ip), ("create_date", ">", since)]
            )
            if by_ip >= self._setting("share_password_tries_ip") or by_share >= self._setting(
                "share_password_tries_share"
            ):
                raise ShareBusy(self.env._("Too many wrong passwords. Try again later."))
            Attempt.create({"share_id": self.id, "ip": ip})
            Attempt.env.flush_all()

    def _clear_tries(self, ip):
        with self.env.registry.cursor() as cr:
            env = self.env(cr=cr, su=True)
            env["int.filemanager.share.attempt"].search(
                [("share_id", "=", self.id), ("ip", "=", ip)]
            ).unlink()
            env.flush_all()

    # === SCOPE OF THE GUESTS === #

    def _hidden_folders(self):
        """Return the folders below the shared folder that the guests do not see, and what lies below them.

        These are the folders that say "only the users and groups allowed" (also if a folder below
        them is open again: it lies in a hidden tree), and the folders for the uploads of
        **every** share, even if somebody opened one: what a guest sent through one share is never
        seen by the guests of another (the folder of this share, and those of shares of folders
        below this one).
        """
        self.ensure_one()
        # sudo: int.filemanager.folder: the guests have no rights; the share decides what they reach
        folders = self.env["int.filemanager.folder"].sudo().with_context(active_test=False)
        hidden = folders.search(
            [
                ("id", "child_of", self.folder_id.id),
                ("id", "!=", self.folder_id.id),
                ("access_mode", "=", "restricted"),
            ]
        )
        uploads = (
            self.sudo()
            .with_context(active_test=False)
            .search([("upload_folder_id", "child_of", self.folder_id.id)])
            .upload_folder_id
        )
        return hidden | self.sudo().upload_folder_id | uploads

    def _scope_domain(self, model):
        """Return the domain on ``model`` (folders or documents) of everything that the guests may reach.

        The guests have no rights on the records: the pages read them as superuser after the token
        of the share has been checked, so this domain is all that bounds the reading. It is joined
        to every search of a page by ``&`` and used to check every id of an address. It holds the
        shared folder and the folders below it without the hidden ones; for a file, the file;
        only what is active (the search takes care of it); only the company of the share, if it
        has one.
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

    # === COUNTERS === #

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
        """Count a download; return ``False`` if the limit of the share is reached by then.

        The condition is in the statement, so two guests who download at the same time cannot both
        take the last one (the second is run again after the first and sees the new count).
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
        self.invalidate_recordset(names)
        self.modified(names)

    # === UPLOADS === #

    @api.model
    def _upload_body_limit(self, token, key):
        """Return the most that a request to the upload route of this token may carry, in bytes.

        Odoo asks for it (the ``max_content_length`` of the route) before it reads the body, so a
        body that is too big is turned away with a 413 before a byte of it is kept. It looks at
        the whole state of the share, without a side effect and without an error: a share that
        is blocked, over, full, locked by a password the request has no key for, or that takes no
        files may be sent no more than the frame of a form. A valid share takes the largest file
        it allows, or what is left of its total if that is less.
        """
        share = self._lookup(token)
        if not share or share.state != "valid" or not share.can_upload:
            return UPLOAD_FRAME
        if share.has_password and not share._key_is_valid(key):
            return UPLOAD_FRAME
        if not share._upload_folder_usable():
            return UPLOAD_FRAME
        room = share.upload_max_total_mb * MEBIBYTE - share.upload_size
        if share.upload_count >= share.upload_max_files or room <= 0:
            return UPLOAD_FRAME
        return min(share.upload_max_file_mb * MEBIBYTE, room) + UPLOAD_FRAME

    def _upload_extensions(self):
        self.ensure_one()
        return {
            part.strip().lstrip(".").lower()
            for part in (self.upload_extensions or "").split(",")
            if part.strip().lstrip(".")
        }

    @api.model
    def _upload_name(self, name):
        """Return the name that a guest's file gets.

        It is what ``_clean_name`` of the documents makes of it, without the format characters (a
        right-to-left mark turns ``cod<mark>gpj.exe`` into what looks like a picture) and without
        the dots and spaces at the end (Windows does not see them, so ``a.exe.`` is a program there).
        """
        name = "".join(char for char in (name or "") if unicodedata.category(char) != "Cf")
        return self.env["int.filemanager.document"]._clean_name(name.rstrip(". "))

    def _check_upload(self, name, head):
        """Refuse the file if its extension or its start do not fit. Nothing is stored yet.

        ``name`` is the clean name, ``head`` the first bytes of the file. The extensions of the
        block list are never taken; of the others only those that the creator of the share named
        (all, if none). A file that is a program is refused whatever its name says. For the
        extensions whose start is known the start has to match, and a text file has no binary data.
        """
        self.ensure_one()
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        allowed = self._upload_extensions()
        if extension in BLOCKED_EXTENSIONS or (allowed and extension not in allowed):
            raise ShareUnsupported(self.env._("This kind of file cannot be uploaded here."))
        if not head:  # an empty file is refused by its size
            return
        guessed = guess_mimetype(head)
        expected = CONTENT_TYPES_OF.get(extension)
        if (
            guessed in EXECUTABLE_TYPES
            or head.startswith(b"\x7fELF")
            or (expected is not None and guessed not in expected)
            or (extension in TEXT_EXTENSIONS and b"\x00" in head)
        ):
            raise ShareUnsupported(self.env._("This file is not what its name says it is."))

    def _reserve_upload(self, size):
        """Take one file of ``size`` bytes from the limits of the share, or refuse the upload.

        One ``UPDATE`` with the limits in its condition: two guests who upload at once cannot both
        take the last place (see ``_count_download``). The storage calls it after the file is
        measured and before it is kept (the ``check`` of ``_create_from_stream``): a refused file
        leaves no blob behind, which a rollback could not take back.
        """
        self.ensure_one()
        if size <= 0:
            raise ShareBadRequest(self.env._("This file is empty."))
        if size > self.upload_max_file_mb * MEBIBYTE:
            raise ShareTooLarge(self.env._("This file is too large for this link."))
        self.flush_recordset(
            ["upload_max_files", "upload_max_total_mb", "upload_count", "upload_size"]
        )
        updated = self.env.execute_query(
            SQL(
                """
                UPDATE int_filemanager_share
                   SET upload_count = upload_count + 1, upload_size = upload_size + %(size)s
                 WHERE id = %(id)s
                   AND upload_count < upload_max_files
                   AND upload_size + %(size)s <= upload_max_total_mb * %(mebibyte)s
             RETURNING id
                """,
                size=size,
                id=self.id,
                mebibyte=MEBIBYTE,
            )
        )
        if not updated:
            raise ShareTooLarge(self.env._("This link takes no more files."))
        self._after_counting(["upload_count", "upload_size"])

    def _release_upload(self, size):
        """Give back what ``_reserve_upload`` took, for a file that the guest removed again."""
        self.ensure_one()
        self.flush_recordset(["upload_count", "upload_size"])
        self.env.execute_query(
            SQL(
                """
                UPDATE int_filemanager_share
                   SET upload_count = GREATEST(upload_count - 1, 0),
                       upload_size = GREATEST(upload_size - %(size)s, 0)
                 WHERE id = %(id)s
                """,
                size=size,
                id=self.id,
            )
        )
        self._after_counting(["upload_count", "upload_size"])

    def _receipt(self, document):
        """Return the receipt of a file that was uploaded through this share.

        It proves to the share that the guest who holds it uploaded the file. It is valid for that
        file only, until the share ends or 90 days have passed.
        """
        self.ensure_one()
        end = time.time() + RECEIPT_DAYS * 86400
        if self.expiration_date:
            end = min(end, calendar.timegm(self.expiration_date.timetuple()))
        return limited_field_access_token(
            document, "id", timestamp=hex(int(end)), scope=RECEIPT_SCOPE
        )

    def _own_uploads(self, entries):
        """Return the files of this share that the receipts in ``entries`` belong to.

        ``entries`` is whatever the guest sent: a list of ``{"id", "receipt"}``. What is not in
        that form is left out, and so is every receipt that is not right (not for this file, not
        for this share, not valid any more), without a word: the guest learns nothing about other
        files. The form is checked first because the check of the token does not validate its input.
        """
        self.ensure_one()
        receipts = {}
        for entry in entries[:RECEIPTS_MAX]:
            if not isinstance(entry, dict):
                continue
            document_id, receipt = entry.get("id"), entry.get("receipt")
            if (
                isinstance(document_id, int)
                and not isinstance(document_id, bool)
                and 0 < document_id <= 2147483647
                and isinstance(receipt, str)
                and len(receipt) <= RECEIPT_MAX_LENGTH
                and RECEIPT_PATTERN.fullmatch(receipt)
            ):
                receipts[document_id] = receipt
        # sudo: int.filemanager.document: the guests have no rights; the receipt proves the ownership
        documents = (
            self.env["int.filemanager.document"]
            .sudo()
            .with_context(active_test=False)
            .search([("id", "in", list(receipts)), ("share_id", "=", self.id)])
        )
        own = documents.browse()
        for document in documents:
            try:
                valid = verify_limited_field_access_token(
                    document, "id", receipts[document.id], scope=RECEIPT_SCOPE
                )
            except (ValueError, OverflowError, OSError):  # an expiry time that cannot be converted
                continue
            if valid:
                own |= document
        return own

    def _removable_uploads(self, documents):
        """Return those of these files that the guest may still remove.

        They lie in the folder of the uploads, are not archived, and nothing refers to them (a
        user linked one to a record, say: a user took it over).
        """
        self.ensure_one()
        referenced = documents._documents_referenced()
        # sudo: int.filemanager.share: the upload folder is not readable for guests
        return documents.filtered(
            lambda document: document.active
            and document.folder_id == self.sudo().upload_folder_id
            and document not in referenced
        )
