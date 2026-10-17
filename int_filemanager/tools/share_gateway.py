"""The reading of the guests of a folder share: a fixed list of ORM methods, nothing else.

The page of the guests runs the views of the core (list, kanban, search). Their ``orm`` service
talks to this gateway instead of ``/web/dataset/call_kw``. Nothing the client sends reaches the
ORM unchecked; the calls run as superuser, so the records rules do not help, and the checks here
are all that bounds a guest:

* model and method come from a table (``METHODS``), never from ``getattr``;
* every field name of a domain, an order, a group, an aggregate and a specification is in the
  list of its model (``FIELDS``), paths are one step long, ``parent_id`` is a plain field only;
* the domain of the guest is joined with the scope of the share by ``&``
  (``int.filemanager.share._scope_domain``), also in the search panel and for every id;
* values of conditions are numbers for relations, scalars for the rest, never texts that the ORM
  would look up by name;
* the context is built here (the language, the folder that the share gives); nothing writes.

Everything refused is a ``ShareForbidden`` or a ``ShareBadRequest``: an answer with a status and
a short text, no traceback.
"""

import json
import re

import psycopg2.errors

from odoo.fields import Domain
from odoo.tools import SQL

from ..models.int_filemanager_folder import SHARE_ROOT_KEY
from ..models.int_filemanager_share import ShareBadRequest, ShareForbidden, ShareUnprocessable

# The most that one call of a guest may take in the database. The size of an answer is limited, but a
# search over a very large tree is work for the database whatever comes back.
QUERY_SECONDS = 5
DOCUMENT = "int.filemanager.document"
FOLDER = "int.filemanager.folder"
TAG = "int.filemanager.tag"

# What a guest may read, filter, sort and group by, per model. No checksum: it would show which
# files are the same, across shares.
FIELDS = {
    DOCUMENT: {"id", "display_name", "name", "folder_id", "mimetype", "size", "thumbnail_state", "tag_ids", "write_date"},
    FOLDER: {"id", "display_name", "name", "parent_id"},
    TAG: {"id", "display_name", "name", "color"},
}
# The widgets of the views ask for these two (they build the address of a picture from them). A
# guest gets the field in the definitions and the value ``False`` in the answers, and cannot
# filter, sort or group by them: the checksum would show which files are the same.
MASKED = {DOCUMENT: ("checksum", "ocr_checksum")}
OPERATORS = {
    "=", "!=", "in", "not in", "like", "not like", "ilike", "not ilike", "=like", "=ilike",
    "<", "<=", ">", ">=", "child_of", "any", "not any",
}  # fmt: skip
AGGREGATORS = {"sum", "avg", "min", "max", "count", "count_distinct"}
GRANULARITIES = {"day", "week", "month", "quarter", "year"}
ORDER_RE = re.compile(r"^\s*([a-z_0-9]+)(\s+(asc|desc))?(\s+nulls\s+(first|last))?\s*$", re.I)
GROUP_ORDER_RE = re.compile(r"^[a-z_0-9:]+( (asc|desc))?( nulls (first|last))?$", re.I)

MAX_LIMIT = 80
MAX_OFFSET = 10_000
MAX_COUNT_LIMIT = 1_000
MAX_DEPTH = 6
MAX_DOMAIN_LENGTH = 20_000
MAX_VALUES = 200
MAX_IDS = 500
TAG_LIMIT = 500
PARENT = "parent_id"
SCALARS = (str, int, float, bool, type(None))


def refuse(message):
    raise ShareForbidden(message)


def bad(message):
    raise ShareBadRequest(message)


class ShareGateway:
    """One call of a guest: the environment, the checks and the handlers of the methods."""

    def __init__(self, share, lang=None):
        self.share = share.sudo()
        self.root = self.share.folder_id
        context = {"lang": lang or "en_US", "bin_size": True, SHARE_ROOT_KEY: self.root.id}
        self.env = self.share.env(context=context)

    def call(self, model, method, args, kwargs):
        handler = METHODS.get((model, method))
        if not handler:
            refuse(f"{model}.{method} is not open")
        if not isinstance(args, list) or not isinstance(kwargs, dict):
            bad("arguments")
        return self.timed(handler, model, args, kwargs)

    def timed(self, handler, model, args, kwargs):
        """Run the call with a limit of time in the database. A call that takes longer is stopped
        (``QueryCanceled``, which Odoo does not handle: it would be a 500) and answered with a
        text; the savepoint gives the transaction back, and the limit is set back."""
        cr = self.env.cr
        cr.execute("SHOW statement_timeout")
        previous = cr.fetchone()[0]
        try:
            with cr.savepoint():
                cr.execute(SQL("SELECT set_config('statement_timeout', %s, true)", f"{int(QUERY_SECONDS * 1000)}ms"))
                return handler(self, model, args, kwargs)
        except psycopg2.errors.QueryCanceled:
            raise ShareUnprocessable(self.env._("This takes too long. Ask for less.")) from None
        finally:
            cr.execute(SQL("SELECT set_config('statement_timeout', %s, true)", previous))

    # -- the checks ---------------------------------------------------------------------------

    def model(self, name):
        if name not in FIELDS:
            refuse(f"model {name!r} is not open")
        return self.env[name]

    def scope_domain(self, model):
        if model == TAG:
            # The tags of the files in the scope, not all: the name of a tag of a hidden file
            # would give it away. One grouped query, not one per file.
            groups = self.env[DOCUMENT]._read_group(
                self.share._scope_domain(DOCUMENT), ["tag_ids"], ["__count"], limit=TAG_LIMIT
            )
            return Domain("id", "in", [tag.id for tag, _count in groups if tag])
        return self.share._scope_domain(model)

    def field(self, model, name):
        if not isinstance(name, str) or name not in FIELDS[model]:
            refuse(f"field {model}.{name} is not open")
        return name

    @staticmethod
    def defined(model):
        """The fields whose definition a guest gets (the list, and the masked fields)."""
        return FIELDS[model] | set(MASKED.get(model, ()))

    def relation(self, model, name):
        """The model behind a relational field of the list (``None`` for a plain field)."""
        field = self.env[model]._fields[name]
        return field.comodel_name if field.relational else None

    def path(self, model, expression, inner=False):
        """A path of one step (``folder_id.name``): every step in the list of its model."""
        steps = expression.split(".") if isinstance(expression, str) else bad("field")
        if len(steps) > 2:
            refuse(f"path {expression!r} is too long")
        for index, step in enumerate(steps):
            self.field(model, step)
            if step == PARENT and (index > 0 or inner or len(steps) > 1):
                refuse("the parent of a folder is not open there")
            comodel = self.relation(model, step)
            if index < len(steps) - 1:
                if not comodel or comodel not in FIELDS:
                    refuse(f"path {expression!r} leaves the list")
                model = comodel
        return model

    def domain(self, model, raw, scoped=True):
        """``Domain(client) & Domain(scope)``, every condition checked."""
        raw = [] if raw is None else raw
        if not isinstance(raw, (list, tuple)):
            bad("a domain is a list")
        if len(json.dumps(raw)) > MAX_DOMAIN_LENGTH:
            bad("domain too long")
        try:
            client = Domain(list(raw))
        except (ValueError, TypeError):
            bad("bad domain")
        self._check_conditions(model, client)
        if model == FOLDER and any(c.field_expr == PARENT for c in client.iter_conditions()):
            # a condition on the parent could show where the shared folder lies
            client &= Domain("id", "!=", self.root.id)
        return client & self.scope_domain(model) if scoped else client

    def _check_conditions(self, model, domain, depth=0, inner=False):
        if depth > MAX_DEPTH:
            bad("domain too deep")
        for condition in domain.iter_conditions():
            operator = condition.operator
            if operator not in OPERATORS:
                refuse(f"operator {operator!r} is not open")
            last = self.path(model, condition.field_expr, inner)
            name = condition.field_expr.rpartition(".")[2]
            if operator in ("any", "not any"):
                if name == PARENT:
                    refuse("the parent of a folder is not open there")
                comodel = self.relation(last, name)
                if not comodel or comodel not in FIELDS:
                    refuse("any on a field that is not a relation of the list")
                value = condition.value
                try:
                    sub = value if isinstance(value, Domain) else Domain(value)
                except (ValueError, TypeError):
                    bad("bad domain")
                self._check_conditions(comodel, sub, depth + 1, inner=True)
            else:
                self._check_value(last, name, operator, condition.value)

    def _check_value(self, model, name, operator, value):
        """Relations and ids take numbers only (a text would be looked up by name, as superuser);
        the rest takes scalars, in lists of at most ``MAX_VALUES``."""
        field = self.env[model]._fields[name]
        values = value if isinstance(value, (list, tuple)) else [value]
        if isinstance(value, (list, tuple)) and len(value) > MAX_VALUES:
            bad("too many values")
        if not all(isinstance(v, SCALARS) for v in values):
            bad("value of a condition")
        if field.relational or name == "id":
            if not all(isinstance(v, int) or v is None for v in values):
                bad("a relation takes numbers")
        if operator == "child_of":
            ids = {v for v in values if v}
            if not field.relational and name != "id":
                refuse("child_of on a field without a tree")
            visible = self.env[FOLDER].search_count(
                Domain("id", "in", list(ids)) & self.share._scope_domain(FOLDER)
            )
            if visible != len(ids):
                refuse("child_of takes the folders that the share shows")

    def order(self, model, order):
        if not order:
            return None
        if not isinstance(order, str):
            bad("order")
        parts = []
        for part in order.split(","):
            match = ORDER_RE.match(part)
            if not match:
                bad("order")
            name = self.field(model, match.group(1))
            if name == PARENT:
                refuse("order by the parent is not open")
            parts.append(part.strip())
        return ", ".join(parts)

    def order_group(self, model, order):
        """The order of groups: ``name asc``, ``__count desc`` or ``size:sum desc``."""
        if not order:
            return None
        if not isinstance(order, str):
            bad("order")
        parts = []
        for part in order.split(","):
            part = part.strip()
            if not GROUP_ORDER_RE.match(part):
                bad("order")
            token = part.split(" ")[0]
            if token != "__count" and self.field(model, token.partition(":")[0]) == PARENT:
                refuse("order by the parent is not open")
            parts.append(part)
        return ", ".join(parts)

    @staticmethod
    def limit(limit, default=MAX_LIMIT):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            return default
        return min(limit, MAX_LIMIT)

    @staticmethod
    def offset(offset):
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            return 0
        return min(offset, MAX_OFFSET)

    def specification(self, model, spec, depth=0):
        if depth > 3 or not isinstance(spec, dict):
            bad("specification")
        result = {}
        for name, sub in spec.items():
            if name in MASKED.get(model, ()):
                continue
            self.field(model, name)
            comodel = self.relation(model, name)
            clean = {}
            if comodel:
                if comodel not in FIELDS or not isinstance(sub, dict):
                    bad("specification")
                for key, value in sub.items():
                    if key == "fields":
                        if name == PARENT:
                            refuse("the parent of a folder is a plain field")
                        clean["fields"] = self.specification(comodel, value, depth + 1)
                    elif key == "limit":
                        clean["limit"] = self.limit(value)
                    elif key == "order":
                        clean["order"] = self.order(comodel, value)
                    elif key in ("context", "domain"):
                        continue  # dropped: the gateway sets its own
                    else:
                        bad(f"key {key!r} of a specification")
            result[name] = clean
        return result

    @staticmethod
    def masked_names(model, spec):
        """The masked fields that a specification asks for (they are not read)."""
        return [name for name in MASKED.get(model, ()) if isinstance(spec, dict) and name in spec]

    @staticmethod
    def fill_masked(records, names):
        """Answer the masked fields with ``False``, as a field without a value is answered."""
        for record in records:
            for name in names:
                record[name] = False
        return records

    def groupby(self, model, specs):
        if not isinstance(specs, (list, tuple)) or len(specs) > 3:
            bad("groupby")
        for spec in specs:
            if not isinstance(spec, str):
                bad("groupby")
            name, _separator, granularity = spec.partition(":")
            if self.field(model, name) == PARENT:
                refuse("grouping by the parent is not open")
            if granularity and granularity not in GRANULARITIES:
                refuse(f"granularity {granularity!r} is not open")
        return list(specs)

    def aggregates(self, model, specs):
        if not isinstance(specs, (list, tuple)) or len(specs) > 6:
            bad("aggregates")
        for spec in specs:
            if spec == "__count":
                continue
            if not isinstance(spec, str):
                bad("aggregates")
            name, _separator, aggregator = spec.partition(":")
            self.field(model, name)
            if aggregator not in AGGREGATORS:
                refuse(f"aggregator {aggregator!r} is not open")
        return list(specs)

    def ids_in_scope(self, model, ids):
        if not isinstance(ids, (list, tuple)) or len(ids) > MAX_IDS:
            bad("ids")
        if not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
            bad("ids")
        return self.model(model).search(Domain("id", "in", list(ids)) & self.scope_domain(model))

    def opening_info(self, info, depth=0):
        """The open groups of a reload, cut down to what is harmless: the group, folded or not,
        offset and limit (clamped), the groups below. Not the domain of the progress bar."""
        if info is None:
            return None
        if depth > 3 or not isinstance(info, list) or len(info) > 100:
            bad("opening info")
        clean = []
        for item in info:
            if not isinstance(item, dict):
                bad("opening info")
            value = item.get("value")
            values = value if isinstance(value, list) else [value]
            if len(values) > 3 or not all(isinstance(v, SCALARS) for v in values):
                bad("opening info")
            entry = {"value": value, "folded": bool(item.get("folded"))}
            if "offset" in item:
                entry["offset"] = self.offset(item["offset"])
            if "limit" in item:
                entry["limit"] = self.limit(item["limit"])
            if "groups" in item:
                entry["groups"] = self.opening_info(item["groups"], depth + 1)
            clean.append(entry)
        return clean

    # -- the handlers, one per method of the table ---------------------------------------------

    def get_views(self, model, args, kwargs):
        views = kwargs.get("views") or []
        names = {"list": "list", "kanban": "kanban", "search": "search"}
        ids = {
            view_type: self.env["ir.model.data"]._xmlid_to_res_id(
                f"int_filemanager.int_filemanager_document_view_guest_{name}"
            )
            for view_type, name in names.items()
        }
        chosen = []
        for item in views:
            view_type = item[1] if isinstance(item, (list, tuple)) and len(item) == 2 else None
            if view_type not in ids:
                refuse(f"view type {view_type!r} is not open")
            chosen.append([ids[view_type], view_type])
        # No toolbar (action menus), no stored filters, no action: the architecture of the views.
        options = {"action_id": False, "toolbar": False, "load_filters": False}
        result = self.model(model).get_views(chosen, options=options)
        # The definitions of all fields of a model come with the views (the custom grouping
        # lists them): cut down to the list, and leave out the models that are not open.
        result["models"] = {
            name: {**info, "fields": {key: value for key, value in info["fields"].items() if key in self.defined(name)}}
            for name, info in result["models"].items()
            if name in FIELDS
        }
        return result

    def fields_get(self, model, args, kwargs):
        names = (args[0] if args else kwargs.get("allfields")) or sorted(self.defined(model))
        if not isinstance(names, list):
            bad("fields")
        names = [name if name in MASKED.get(model, ()) else self.field(model, name) for name in names]
        attributes = (args[1] if len(args) > 1 else kwargs.get("attributes")) or None
        if attributes is not None and not (
            isinstance(attributes, list) and all(isinstance(a, str) for a in attributes)
        ):
            bad("attributes")
        return self.model(model).fields_get(names, attributes)

    def web_search_read(self, model, args, kwargs):
        count_limit = kwargs.get("count_limit")
        valid = isinstance(count_limit, int) and not isinstance(count_limit, bool) and count_limit > 0
        spec = kwargs.get("specification", {})
        result = self.model(model).web_search_read(
            self.domain(model, kwargs.get("domain", args[0] if args else [])),
            self.specification(model, spec),
            offset=self.offset(kwargs.get("offset")),
            limit=self.limit(kwargs.get("limit")),
            order=self.order(model, kwargs.get("order")),
            count_limit=min(count_limit, MAX_COUNT_LIMIT) if valid else MAX_COUNT_LIMIT,
        )
        self.fill_masked(result["records"], self.masked_names(model, spec))
        return result

    def web_read(self, model, args, kwargs):
        records = self.ids_in_scope(model, args[0] if args else [])
        spec = kwargs.get("specification", {})
        result = records.web_read(self.specification(model, spec))
        return self.fill_masked(result, self.masked_names(model, spec))

    def formatted_read_group(self, model, args, kwargs):
        if kwargs.get("having"):
            refuse("having is not open")
        return self.model(model).formatted_read_group(
            self.domain(model, kwargs.get("domain")),
            groupby=self.groupby(model, kwargs.get("groupby", [])),
            aggregates=self.aggregates(model, kwargs.get("aggregates", [])),
            offset=self.offset(kwargs.get("offset")),
            limit=self.limit(kwargs.get("limit")),
            order=self.order_group(model, kwargs.get("order")),
        )

    def web_read_group(self, model, args, kwargs):
        unfold = kwargs.get("unfold_read_specification")
        masked = self.masked_names(model, unfold)
        result = self.model(model).web_read_group(
            self.domain(model, kwargs.get("domain")),
            self.groupby(model, kwargs.get("groupby", [])),
            self.aggregates(model, kwargs.get("aggregates", [])),
            limit=self.limit(kwargs.get("limit")),
            offset=self.offset(kwargs.get("offset")),
            order=self.order_group(model, kwargs.get("order")),
            auto_unfold=bool(kwargs.get("auto_unfold")),
            opening_info=self.opening_info(kwargs.get("opening_info")),
            unfold_read_specification=self.specification(model, unfold) if unfold else None,
            unfold_read_default_limit=self.limit(kwargs.get("unfold_read_default_limit")),
            groupby_read_specification=None,
        )
        for group in result["groups"]:
            self.fill_masked(group.get("__records", []), masked)
        return result

    def search_panel_select_range(self, model, args, kwargs):
        return self._search_panel(model, args, kwargs, "search_panel_select_range")

    def search_panel_select_multi_range(self, model, args, kwargs):
        return self._search_panel(model, args, kwargs, "search_panel_select_multi_range")

    def _search_panel(self, model, args, kwargs, method):
        field_name = self.field(model, args[0] if args else kwargs.get("field_name"))
        if field_name == PARENT:
            refuse("the parent is not open")
        comodel = self.relation(model, field_name)
        clean = {
            key: list(self.domain(model, kwargs.get(key), scoped=False))
            for key in ("category_domain", "filter_domain")
        }
        # The base domain carries the scope of the files, the domain of the values the scope of
        # the folders (or the tags): the panel reads the values with ``search_read`` and shows
        # all it finds.
        clean["search_domain"] = list(self.domain(model, kwargs.get("search_domain")))
        if comodel:
            clean["comodel_domain"] = list(self.domain(comodel, kwargs.get("comodel_domain")))
        for key in ("enable_counters", "expand", "hierarchize"):
            if key in kwargs:
                clean[key] = bool(kwargs[key])
        clean["limit"] = self.limit(kwargs.get("limit"), default=500) if kwargs.get("limit") else None
        if kwargs.get("group_by"):
            refuse("group_by of the panel is not open")
        return getattr(self.model(model), method)(field_name, **clean)

    def name_search(self, model, args, kwargs):
        name = kwargs.get("name", args[0] if args else "")
        operator = kwargs.get("operator", "ilike")
        if operator not in ("ilike", "=", "like", "=ilike"):
            refuse("operator of name_search is not open")
        domain = self.domain(model, kwargs.get("args", kwargs.get("domain")))
        return self.model(model).name_search(
            name if isinstance(name, str) else "", domain, operator, self.limit(kwargs.get("limit"), default=8)
        )

    def web_name_search(self, model, args, kwargs):
        return [{"id": id_, "display_name": name} for id_, name in self.name_search(model, args, kwargs)]


# Model and method come from this table; nothing else is called.
METHODS = {
    (DOCUMENT, "get_views"): ShareGateway.get_views,
    (DOCUMENT, "fields_get"): ShareGateway.fields_get,
    (DOCUMENT, "web_search_read"): ShareGateway.web_search_read,
    (DOCUMENT, "web_read"): ShareGateway.web_read,
    (DOCUMENT, "formatted_read_group"): ShareGateway.formatted_read_group,
    (DOCUMENT, "web_read_group"): ShareGateway.web_read_group,
    (DOCUMENT, "search_panel_select_range"): ShareGateway.search_panel_select_range,
    (DOCUMENT, "search_panel_select_multi_range"): ShareGateway.search_panel_select_multi_range,
    (FOLDER, "fields_get"): ShareGateway.fields_get,
    (FOLDER, "web_search_read"): ShareGateway.web_search_read,
    (FOLDER, "web_read"): ShareGateway.web_read,
    (FOLDER, "name_search"): ShareGateway.name_search,
    (FOLDER, "web_name_search"): ShareGateway.web_name_search,
    (TAG, "fields_get"): ShareGateway.fields_get,
    (TAG, "web_search_read"): ShareGateway.web_search_read,
    (TAG, "web_read"): ShareGateway.web_read,
    (TAG, "name_search"): ShareGateway.name_search,
    (TAG, "web_name_search"): ShareGateway.web_name_search,
}
