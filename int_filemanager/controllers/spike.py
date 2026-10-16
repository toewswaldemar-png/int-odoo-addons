"""SPIKE (throw-away): token-checked gateway for the guest UI.

The page runs the real list / kanban / search views of the core for a visitor without an
account. The `orm` service of the page talks to ``/int_filemanager/spike/rpc`` instead of
``/web/dataset/call_kw``. The gateway knows a fixed list of methods; each has its own handler
that builds the arguments itself, so nothing the client sends reaches the ORM unchecked:

* model and method come from a table, not from ``getattr``;
* every field name (read, domain, order, group, aggregate) must be in the whitelist of its model;
* the domain of the client is ``Domain(client) & Domain(scope)``; the scope is the folder tree
  that the token opens;
* the limit is clamped, nothing writes, the context is rebuilt from two keys;
* the call runs ``with_user(<creator of the folder>)``, so the record rules still apply.
"""

import logging
import re

import odoo.service.common
from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
from odoo.http import request
from odoo.tools import consteq, hmac

_logger = logging.getLogger(__name__)

TOKEN_SCOPE = "int_filemanager.spike"
ROOT_PARAMETER = "int_filemanager.spike_folder_id"
MAX_LIMIT = 80
MAX_DEPTH = 6

DOCUMENT = "int.filemanager.document"
FOLDER = "int.filemanager.folder"
TAG = "int.filemanager.tag"

# Fields a guest may read, filter, sort and group by, per model.
FIELDS = {
    DOCUMENT: {
        "id",
        "display_name",
        "name",
        "folder_id",
        "mimetype",
        "size",
        "checksum",
        "ocr_checksum",
        "thumbnail_state",
        "tag_ids",
        "write_date",
    },
    FOLDER: {"id", "display_name", "name", "parent_id"},
    TAG: {"id", "display_name", "name", "color"},
}
OPERATORS = {
    "=",
    "!=",
    "in",
    "not in",
    "like",
    "not like",
    "ilike",
    "not ilike",
    "=like",
    "=ilike",
    "<",
    "<=",
    ">",
    ">=",
    "child_of",
    "parent_of",
    "any",
    "not any",
}
AGGREGATORS = {"sum", "avg", "min", "max", "count", "count_distinct"}
GRANULARITIES = {"day", "week", "month", "quarter", "year"}
ORDER_RE = re.compile(r"^\s*([a-z_0-9]+)(\.[a-z_0-9]+)?(\s+(asc|desc))?(\s+nulls\s+(first|last))?\s*$", re.I)


class GatewayDenied(AccessError):
    """The call is not in the list, or leaves the scope of the token."""


def _scope(token):
    """The folder the token opens and the user who runs the calls, or None."""
    if not isinstance(token, str) or "-" not in token:
        return None
    folder_id, _sep, signature = token.partition("-")
    if not folder_id.isdigit():
        return None
    env = request.env(su=True)
    expected = hmac(env, TOKEN_SCOPE, folder_id)
    if not consteq(signature, expected):
        return None
    folder = env[FOLDER].browse(int(folder_id)).exists()
    if not folder:
        return None
    return folder


def spike_token(env, folder):
    return f"{folder.id}-{hmac(env(su=True), TOKEN_SCOPE, str(folder.id))}"


class Gateway:
    """One call: the checked environment and the handlers of the methods."""

    def __init__(self, folder):
        self.root = folder
        self.user = folder.create_uid

    # -- helpers -----------------------------------------------------------------------------

    def model(self, name, context=None):
        if name not in FIELDS:
            raise GatewayDenied(f"model {name!r} is not open")
        env = request.env(user=self.user.id, context={"lang": request.env.lang or "en_US", "bin_size": True})
        env = env(context={**env.context, **(context or {})})
        return env[name]

    def scope_domain(self, model_name):
        if model_name == DOCUMENT:
            return Domain("folder_id", "child_of", self.root.id)
        if model_name == FOLDER:
            return Domain("id", "child_of", self.root.id)
        if model_name == TAG:
            # Only the tags that a document of the scope carries.
            tag_ids = request.env(su=True)[DOCUMENT].search([("folder_id", "child_of", self.root.id)]).tag_ids.ids
            return Domain("id", "in", tag_ids)
        raise GatewayDenied(model_name)

    def field(self, model_name, name):
        if name not in FIELDS[model_name]:
            raise GatewayDenied(f"field {model_name}.{name} is not open")
        return name

    def comodel(self, model_name, name):
        """The model behind a relational field of the whitelist (None for a plain field)."""
        field = request.env[model_name]._fields[name]
        return field.comodel_name if field.relational else None

    def path(self, model_name, expr):
        """A field path 'a.b' whose every step is in the whitelist of its model."""
        current = model_name
        steps = expr.split(".")
        for index, step in enumerate(steps):
            self.field(current, step)
            comodel = self.comodel(current, step)
            if index < len(steps) - 1:
                if not comodel or comodel not in FIELDS:
                    raise GatewayDenied(f"path {expr!r} leaves the whitelist")
                current = comodel
        return expr

    def domain(self, model_name, raw, *, scoped=True, depth=0):
        """``Domain(client) & Domain(scope)``, with every condition checked."""
        if depth > MAX_DEPTH:
            raise GatewayDenied("domain too deep")
        if raw is None:
            raw = []
        if not isinstance(raw, (list, tuple)):
            raise GatewayDenied("domain must be a list")
        try:
            client = Domain(list(raw))
        except Exception as error:  # a malformed domain is the client's mistake
            raise GatewayDenied(f"bad domain: {error}") from None
        client = self._check_conditions(model_name, client, depth)
        return client & self.scope_domain(model_name) if scoped else client

    def _check_conditions(self, model_name, domain, depth):
        for condition in domain.iter_conditions():
            if condition.operator not in OPERATORS:
                raise GatewayDenied(f"operator {condition.operator!r} is not open")
            self.path(model_name, condition.field_expr)
            if condition.operator in ("any", "not any"):
                value = condition.value
                comodel = self._comodel_of_path(model_name, condition.field_expr)
                sub = value if isinstance(value, Domain) else Domain(value)
                self._check_conditions(comodel, sub, depth + 1)
                # The sub-domain of 'any' is not scoped by itself: the scope applies to the
                # model of the outer search, and the comodel's own record rules to the rest.
        return domain

    def _comodel_of_path(self, model_name, expr):
        current = model_name
        for step in expr.split("."):
            comodel = self.comodel(current, step)
            if not comodel or comodel not in FIELDS:
                raise GatewayDenied(f"{expr!r} is not a relation of the whitelist")
            current = comodel
        return current

    def order(self, model_name, order):
        if not order:
            return None
        parts = []
        for part in str(order).split(","):
            match = ORDER_RE.match(part)
            if not match:
                raise GatewayDenied(f"bad order {part!r}")
            name = match.group(1)
            if match.group(2):
                raise GatewayDenied("order by a path is not open")
            self.field(model_name, name)
            parts.append(part.strip())
        return ", ".join(parts)

    def limit(self, limit, default=MAX_LIMIT):
        if limit is None or not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            return default
        return min(limit, MAX_LIMIT)

    def offset(self, offset):
        return offset if isinstance(offset, int) and not isinstance(offset, bool) and offset > 0 else 0

    def specification(self, model_name, spec, depth=0):
        if depth > 3 or not isinstance(spec, dict):
            raise GatewayDenied("bad specification")
        result = {}
        for name, sub in spec.items():
            self.field(model_name, name)
            comodel = self.comodel(model_name, name)
            clean = {}
            if comodel:
                if comodel not in FIELDS:
                    raise GatewayDenied(f"relation {name} leaves the whitelist")
                if not isinstance(sub, dict):
                    raise GatewayDenied("bad sub specification")
                for key, value in sub.items():
                    if key == "fields":
                        clean["fields"] = self.specification(comodel, value, depth + 1)
                    elif key == "limit":
                        clean["limit"] = self.limit(value)
                    elif key == "order":
                        clean["order"] = self.order(comodel, value)
                    elif key in ("context", "domain"):
                        continue  # dropped: the gateway sets its own
                    else:
                        raise GatewayDenied(f"key {key!r} of a sub specification is not open")
            result[name] = clean
        return result

    def groupby(self, model_name, specs):
        if not isinstance(specs, (list, tuple)) or len(specs) > 3:
            raise GatewayDenied("bad groupby")
        clean = []
        for spec in specs:
            if not isinstance(spec, str):
                raise GatewayDenied("bad groupby")
            name, _sep, granularity = spec.partition(":")
            self.field(model_name, name)
            if granularity and granularity not in GRANULARITIES:
                raise GatewayDenied(f"granularity {granularity!r} is not open")
            clean.append(spec)
        return clean

    def aggregates(self, model_name, specs):
        if not isinstance(specs, (list, tuple)) or len(specs) > 6:
            raise GatewayDenied("bad aggregates")
        clean = []
        for spec in specs:
            if spec == "__count":
                clean.append(spec)
                continue
            if not isinstance(spec, str):
                raise GatewayDenied("bad aggregate")
            name, _sep, aggregator = spec.partition(":")
            self.field(model_name, name)
            if aggregator not in AGGREGATORS:
                raise GatewayDenied(f"aggregator {aggregator!r} is not open")
            clean.append(spec)
        return clean

    def ids_in_scope(self, model_name, ids):
        if not isinstance(ids, (list, tuple)) or len(ids) > 500 or not all(isinstance(i, int) for i in ids):
            raise GatewayDenied("bad ids")
        Model = self.model(model_name)
        return Model.search(Domain("id", "in", list(ids)) & self.scope_domain(model_name))

    # -- handlers (one per method of the table) ----------------------------------------------

    def get_views(self, model_name, args, kwargs):
        types = {"list", "kanban", "search"}
        views = kwargs.get("views") or []
        forced = request.env(su=True)["ir.model.data"]
        ids = {
            "list": forced._xmlid_to_res_id("int_filemanager.int_filemanager_document_view_guest_list"),
            "kanban": forced._xmlid_to_res_id("int_filemanager.int_filemanager_document_view_guest_kanban"),
            "search": forced._xmlid_to_res_id("int_filemanager.int_filemanager_document_view_guest_search"),
        }
        clean = []
        for item in views:
            view_type = item[1] if isinstance(item, (list, tuple)) and len(item) == 2 else None
            if view_type not in types:
                raise GatewayDenied(f"view type {view_type!r} is not open")
            clean.append([ids[view_type], view_type])
        # No toolbar (action menus), no stored filters, no action: only the arch of three views.
        options = {"action_id": False, "toolbar": False, "load_filters": False}
        return self.model(model_name).get_views(clean, options=options)

    def fields_get(self, model_name, args, kwargs):
        allfields = (args[0] if args else kwargs.get("allfields")) or list(FIELDS[model_name])
        allfields = [self.field(model_name, name) for name in allfields]
        attributes = (args[1] if len(args) > 1 else kwargs.get("attributes")) or None
        return self.model(model_name).fields_get(allfields, attributes)

    def web_search_read(self, model_name, args, kwargs):
        domain = self.domain(model_name, kwargs.get("domain", args[0] if args else []))
        spec = self.specification(model_name, kwargs.get("specification", {}))
        limit = self.limit(kwargs.get("limit"))
        count_limit = kwargs.get("count_limit")
        count_limit = min(count_limit, 1000) if isinstance(count_limit, int) and count_limit > 0 else 1000
        return self.model(model_name).web_search_read(
            domain,
            spec,
            offset=self.offset(kwargs.get("offset")),
            limit=limit,
            order=self.order(model_name, kwargs.get("order")),
            count_limit=count_limit,
        )

    def web_read(self, model_name, args, kwargs):
        records = self.ids_in_scope(model_name, args[0] if args else [])
        return records.web_read(self.specification(model_name, kwargs.get("specification", {})))

    def formatted_read_group(self, model_name, args, kwargs):
        if kwargs.get("having"):
            raise GatewayDenied("having is not open")
        return self.model(model_name).formatted_read_group(
            self.domain(model_name, kwargs.get("domain")),
            groupby=self.groupby(model_name, kwargs.get("groupby", [])),
            aggregates=self.aggregates(model_name, kwargs.get("aggregates", [])),
            offset=self.offset(kwargs.get("offset")),
            limit=self.limit(kwargs.get("limit")),
            order=self.order_group(model_name, kwargs.get("order")),
        )

    def web_read_group(self, model_name, args, kwargs):
        groupby = self.groupby(model_name, kwargs.get("groupby", []))
        unfold = kwargs.get("unfold_read_specification")
        return self.model(model_name).web_read_group(
            self.domain(model_name, kwargs.get("domain")),
            groupby,
            self.aggregates(model_name, kwargs.get("aggregates", [])),
            limit=self.limit(kwargs.get("limit")),
            offset=self.offset(kwargs.get("offset")),
            order=self.order_group(model_name, kwargs.get("order")),
            auto_unfold=bool(kwargs.get("auto_unfold")),
            opening_info=None,  # TODO(spike): sanitise the opening info of reloads
            unfold_read_specification=self.specification(model_name, unfold) if unfold else None,
            unfold_read_default_limit=self.limit(kwargs.get("unfold_read_default_limit")),
            groupby_read_specification=None,
        )

    def order_group(self, model_name, order):
        """The order of groups: 'name asc', '__count desc' or 'size:sum desc'."""
        if not order:
            return None
        parts = []
        for part in str(order).split(","):
            token = part.strip().split(" ")[0]
            if token != "__count":
                self.field(model_name, token.partition(":")[0])
            if not re.match(r"^[a-z_0-9:]+( (asc|desc))?( nulls (first|last))?$", part.strip(), re.I):
                raise GatewayDenied(f"bad order {part!r}")
            parts.append(part.strip())
        return ", ".join(parts)

    def search_panel_select_range(self, model_name, args, kwargs):
        return self._search_panel(model_name, args, kwargs, "search_panel_select_range")

    def search_panel_select_multi_range(self, model_name, args, kwargs):
        return self._search_panel(model_name, args, kwargs, "search_panel_select_multi_range")

    def _search_panel(self, model_name, args, kwargs, method):
        field_name = self.field(model_name, args[0] if args else kwargs.get("field_name"))
        comodel = self.comodel(model_name, field_name)
        clean = {}
        for key in ("category_domain", "filter_domain"):
            clean[key] = list(self.domain(model_name, kwargs.get(key), scoped=False))
        # The base domain carries the scope of the documents, the domain of the values the scope of
        # the comodel: the panel reads the folders with ``search_read`` and shows all it finds.
        clean["search_domain"] = list(self.domain(model_name, kwargs.get("search_domain")))
        if comodel:
            clean["comodel_domain"] = list(self.domain(comodel, kwargs.get("comodel_domain")))
        for key in ("enable_counters", "expand", "hierarchize"):
            if key in kwargs:
                clean[key] = bool(kwargs[key])
        clean["limit"] = self.limit(kwargs.get("limit"), default=500) if kwargs.get("limit") else None
        if kwargs.get("group_by"):
            raise GatewayDenied("group_by of the panel is not open")
        return getattr(self.model(model_name), method)(field_name, **clean)

    def name_search(self, model_name, args, kwargs):
        name = kwargs.get("name", args[0] if args else "")
        domain = self.domain(model_name, kwargs.get("args", kwargs.get("domain")))
        operator = kwargs.get("operator", "ilike")
        if operator not in ("ilike", "=", "like", "=ilike"):
            raise GatewayDenied("operator of name_search is not open")
        return self.model(model_name).name_search(
            name if isinstance(name, str) else "", domain, operator, self.limit(kwargs.get("limit"), default=8)
        )

    def web_name_search(self, model_name, args, kwargs):
        pairs = self.name_search(model_name, args, kwargs)
        return [{"id": id_, "display_name": name} for id_, name in pairs]


# Model and method come from this table; nothing else is called.
METHODS = {
    (DOCUMENT, "get_views"): Gateway.get_views,
    (DOCUMENT, "fields_get"): Gateway.fields_get,
    (DOCUMENT, "web_search_read"): Gateway.web_search_read,
    (DOCUMENT, "web_read"): Gateway.web_read,
    (DOCUMENT, "formatted_read_group"): Gateway.formatted_read_group,
    (DOCUMENT, "web_read_group"): Gateway.web_read_group,
    (DOCUMENT, "search_panel_select_range"): Gateway.search_panel_select_range,
    (DOCUMENT, "search_panel_select_multi_range"): Gateway.search_panel_select_multi_range,
    (FOLDER, "fields_get"): Gateway.fields_get,
    (FOLDER, "web_search_read"): Gateway.web_search_read,
    (FOLDER, "web_read"): Gateway.web_read,
    (FOLDER, "name_search"): Gateway.name_search,
    (FOLDER, "web_name_search"): Gateway.web_name_search,
    (TAG, "fields_get"): Gateway.fields_get,
    (TAG, "web_search_read"): Gateway.web_search_read,
    (TAG, "web_read"): Gateway.web_read,
    (TAG, "name_search"): Gateway.name_search,
    (TAG, "web_name_search"): Gateway.web_name_search,
}


class IntFilemanagerSpike(http.Controller):
    @http.route("/int_filemanager/spike/<string:token>", type="http", auth="public", website=False)
    def page(self, token, **kwargs):
        folder = _scope(token)
        if not folder:
            return request.not_found()
        # What the webclient puts into session_info() for a login, minus everything about a user:
        # the views need view_info, the core needs the version and the context for the language.
        version_info = odoo.service.common.exp_version()
        session_info = request.env["ir.http"].get_frontend_session_info()
        session_info.update(
            {
                "is_frontend": False,
                "db": request.env.cr.dbname,
                "server_version": version_info.get("server_version"),
                "server_version_info": version_info.get("server_version_info"),
                "user_context": {"lang": request.env.lang, "tz": request.env.context.get("tz") or "UTC"},
                "view_info": request.env["ir.ui.view"].get_view_info(),
                "max_file_upload_size": 0,
                "active_ids_limit": 0,
                "groups": {},
            }
        )
        response = request.render(
            "int_filemanager.spike_page",
            {
                "token": token,
                "session_info": session_info,
                "folder_name": folder.sudo().display_name,
                "debug": request.session.debug,
                "lang": request.env.lang,
            },
        )
        # The binary routes (/web/content, /web/image) read the same token from the cookie.
        response.set_cookie("fm_spike_token", token, httponly=True, samesite="Strict", path="/")
        return response

    @http.route("/int_filemanager/spike/rpc", type="jsonrpc", auth="public", methods=["POST"], csrf=False)
    def rpc(self, token, model, method, args=None, kwargs=None, **_ignored):
        folder = _scope(token)
        if not folder:
            raise AccessError(request.env._("This link is not valid."))
        handler = METHODS.get((model, method))
        args = list(args or [])
        kwargs = dict(kwargs or {})
        _logger.info("spike gateway: %s.%s kwargs=%s", model, method, sorted(kwargs))
        if not handler:
            _logger.warning("spike gateway DENIED (not in the table): %s.%s", model, method)
            raise GatewayDenied(f"{model}.{method} is not open")
        try:
            return handler(Gateway(folder), model, args, kwargs)
        except GatewayDenied as error:
            _logger.warning("spike gateway DENIED: %s.%s: %s", model, method, error)
            raise
        except UserError:
            raise


GUEST_BINARY_FIELDS = {"content", "ocr_content", "thumbnail"}


def guest_document(env, res_id, field):
    """The document, if the cookie of a link opens it and the field is one the page shows."""
    token = request.httprequest.cookies.get("fm_spike_token")
    if not token or field not in GUEST_BINARY_FIELDS:
        return None
    folder = _scope(token)
    if not folder:
        return None
    gateway = Gateway(folder)
    document = gateway.model(DOCUMENT).search(Domain("id", "=", res_id) & gateway.scope_domain(DOCUMENT))
    return document.sudo() if document else None
