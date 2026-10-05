"""Mine conventions from Odoo source: python (AST), XML, CSV, JS, SCSS, manifests.
usage: mine.py <label> <addons_dir> [skip_regex]   -> writes JSON to stdout"""
import ast, csv, json, os, re, statistics, sys
from collections import Counter

label, root = sys.argv[1], sys.argv[2]
skip = re.compile(sys.argv[3]) if len(sys.argv) > 3 else None
C = Counter()
L = {}  # lists for medians


def add(key, n=1):
    C[key] += n


def modules():
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if os.path.isfile(os.path.join(p, "__manifest__.py")) and not (skip and skip.search(name)):
            yield name, p


def walk(p, exts, exclude=("lib", "node_modules", "__pycache__", "i18n", "tests", "tours")):
    for d, dirs, files in os.walk(p):
        dirs[:] = [x for x in dirs if x not in exclude]
        for f in files:
            if f.endswith(exts):
                yield os.path.join(d, f)


def rd(p):
    try:
        return open(p, encoding="utf-8").read()
    except Exception:
        return ""


FIELD_TYPES = {"Char", "Text", "Html", "Integer", "Float", "Monetary", "Boolean", "Date", "Datetime", "Binary", "Image",
               "Selection", "Many2one", "One2many", "Many2many", "Json", "Reference", "Many2oneReference", "Properties"}
PRIV = ("_name", "_description", "_inherit", "_inherits", "_order", "_rec_name", "_parent_name", "_parent_store",
        "_table", "_auto", "_log_access", "_check_company_auto", "_abstract", "_transient", "_sql_constraints")


def call_name(n):
    f = n.func
    return f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")


def deco_names(fn):
    out = []
    for d in fn.decorator_list:
        t = d.func if isinstance(d, ast.Call) else d
        out.append(t.attr if isinstance(t, ast.Attribute) else (t.id if isinstance(t, ast.Name) else ""))
    return out


def label_default(name, ftype):
    base = name
    if ftype == "Many2one" and name.endswith("_id"):
        base = name[:-3]
    elif ftype in ("One2many", "Many2many") and name.endswith("_ids"):
        base = name[:-4]
    return base.replace("_", " ").capitalize()


def category(item):
    if isinstance(item, ast.Assign):
        t = item.targets[0]
        tn = t.id if isinstance(t, ast.Name) else ""
        if tn in PRIV:
            return 0
        v = item.value
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and isinstance(v.func.value, ast.Name) and v.func.value.id == "fields":
            return 2
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr in ("Constraint", "Index", "UniqueIndex"):
            return 3
        return -1
    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
        n = item.name
        d = deco_names(item)
        if n.startswith("_default_"):
            return 1
        if n.startswith(("_compute_", "_inverse_", "_search_")):
            return 4
        if "constrains" in d or "onchange" in d or n.startswith(("_check_", "_onchange_")):
            return 5
        if n in ("create", "write", "unlink", "copy", "copy_data", "default_get", "_auto_init", "init", "name_create", "_search", "read", "fields_get", "_read_group"):
            return 6
        if n.startswith("action_"):
            return 7
        return 8
    return -1


def py_stats(path, mod):
    src = rd(path)
    if not src.strip():
        return
    try:
        tree = ast.parse(src)
    except Exception:
        add("py_unparsable")
        return
    add("py_files")
    lines = src.count("\n") + 1
    L.setdefault("py_lines", []).append(lines)
    fname = os.path.basename(path)[:-3]
    in_models = "/models/" in path.replace("\\", "/") or "/wizard/" in path.replace("\\", "/") or "/report/" in path.replace("\\", "/")
    # imports
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            if n.module == "odoo.orm" or n.module.startswith("odoo.orm."):
                add("import_from_odoo.orm")
            if n.module == "odoo" and any(a.name == "_" for a in n.names):
                add("import_underscore_gettext")
            if n.module in ("odoo.fields",) and any(a.name == "Domain" for a in n.names):
                add("import_Domain")
            if n.module == "odoo.tools" and any(a.name == "SQL" for a in n.names):
                add("import_SQL")
        if isinstance(n, ast.Call):
            cn = call_name(n)
            if cn in ("sudo", "with_user", "with_company", "with_context", "with_env", "filtered", "mapped", "sorted", "grouped",
                      "ensure_one", "search_count", "search_fetch", "_read_group", "read_group", "formatted_read_group", "web_read_group",
                      "flush_model", "flush_recordset", "flush_all", "invalidate_model", "invalidate_recordset", "invalidate_all",
                      "execute_query", "cr.execute", "browse", "exists", "check_access", "has_access", "filtered_domain",
                      "message_post", "sql_tracking", "get_param", "ref", "unlink", "bus_send", "_send", "_commit_progress",
                      "try_lock_for_update", "ormcache", "savepoint", "cursor", "make_response", "render", "get_xml_id", "_get_eval_context",
                      "safe_eval", "literal_eval", "eval", "exec", "getattr", "setattr", "print", "format_amount", "html_escape", "Markup"):
                add("call_" + cn)
            if cn in ("commit", "rollback") and isinstance(n.func, ast.Attribute):
                add("call_cr_" + cn)
            if cn == "execute" and isinstance(n.func, ast.Attribute):
                a0 = n.args[0] if n.args else None
                if isinstance(a0, ast.Call) and call_name(a0) == "SQL":
                    add("cr_execute_SQL")
                elif isinstance(a0, ast.JoinedStr) or (isinstance(a0, ast.BinOp)):
                    add("cr_execute_formatted_string")
                else:
                    add("cr_execute_plain")
            if cn == "search" and isinstance(n.func, ast.Attribute):
                add("call_search")
                if n.args and isinstance(n.args[0], ast.List) and not n.args[0].elts and not any(k.arg == "limit" for k in n.keywords):
                    add("search_all_no_limit")
            if cn == "_" and isinstance(n.func, ast.Name):
                add("gettext__func")
            if cn == "_" and isinstance(n.func, ast.Attribute):
                add("gettext_env_underscore")
            if cn in ("UserError", "ValidationError", "AccessError", "MissingError", "RedirectWarning", "AccessDenied"):
                add("raise_" + cn)
                if n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                    add("error_static_string_without_gettext")
            if cn == "getLogger":
                add("getLogger")
        if isinstance(n, ast.ExceptHandler):
            if n.type is None:
                add("except_bare")
            elif isinstance(n.type, ast.Name) and n.type.id in ("Exception", "BaseException"):
                add("except_Exception")
            else:
                add("except_specific")
            if len(n.body) == 1 and isinstance(n.body[0], ast.Pass):
                add("except_pass")
        if isinstance(n, (ast.JoinedStr,)):
            pass
    if "getLogger(__name__)" in src:
        add("logger_getLogger___name__")
    if re.search(r"^_logger\s*=", src, re.M):
        add("logger_named__logger")
    # models
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    models_in_file = 0
    for cls in classes:
        attrs = {}
        for item in cls.body:
            if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name):
                attrs[item.targets[0].id] = item.value
        bases = [ast.unparse(b) for b in cls.bases]
        is_model = any(b in ("models.Model", "models.AbstractModel", "models.TransientModel", "Model", "AbstractModel", "TransientModel") or b.endswith((".Model", ".AbstractModel", ".TransientModel")) for b in bases)
        if not is_model:
            continue
        models_in_file += 1
        add("model_classes")
        kind = "Transient" if any("TransientModel" in b for b in bases) else ("Abstract" if any("AbstractModel" in b for b in bases) else "Model")
        add("model_" + kind)
        name = ast.literal_eval(attrs["_name"]) if "_name" in attrs and isinstance(attrs["_name"], ast.Constant) else None
        inh = None
        if "_inherit" in attrs:
            v = attrs["_inherit"]
            if isinstance(v, ast.Constant):
                inh = v.value
            elif isinstance(v, ast.List) and v.elts and isinstance(v.elts[0], ast.Constant):
                inh = "LIST"
        if name:
            add("model_with__name")
            if "_description" in attrs or kind != "Model":
                add("model_with__description_or_not_required")
            if "_description" in attrs:
                add("model_has__description")
            if in_models:
                if fname == name.replace(".", "_"):
                    add("file_named_after_model")
                else:
                    add("file_not_named_after_model")
                    L.setdefault("file_not_named_examples", []).append(f"{mod}/{fname} <- {name}")
        elif inh and inh != "LIST":
            add("model_extension")
            if in_models:
                add("extension_file_named_after_inherited" if fname == inh.replace(".", "_") else "extension_file_other_name")
        # order of class body
        cats = [category(i) for i in cls.body]
        cats = [c for c in cats if c >= 0]
        if len(cats) >= 5:
            add("order_classes")
            if cats == sorted(cats):
                add("order_monotonic")
            # private attrs first
            first_non_priv = next((i for i, c in enumerate(cats) if c != 0), len(cats))
            if all(c != 0 for c in cats[first_non_priv:]):
                add("order_private_attrs_first")
            # fields before methods
            seen_method = False; ok = True
            for c in cats:
                if c >= 4:
                    seen_method = True
                if c == 2 and seen_method:
                    ok = False
            add("order_fields_before_methods" if ok else "order_fields_after_methods")
            cats_m = [c for c in cats if c >= 4]
            if 6 in cats_m and 7 in cats_m:
                add("order_crud_before_actions" if cats_m.index(6) < cats_m.index(7) else "order_crud_after_actions")
        # fields
        for item in cls.body:
            if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Attribute) \
                    and isinstance(item.value.func.value, ast.Name) and item.value.func.value.id == "fields" and item.value.func.attr in FIELD_TYPES:
                ft = item.value.func.attr
                fname_ = item.targets[0].id if isinstance(item.targets[0], ast.Name) else ""
                kw = {k.arg: k.value for k in item.value.keywords if k.arg}
                add("field_total"); add("field_type_" + ft)
                if ft == "Many2one":
                    add("m2o_total")
                    add("m2o_name_endswith__id" if fname_.endswith("_id") else "m2o_name_other")
                    if "ondelete" in kw: add("m2o_has_ondelete")
                    if "index" in kw: add("m2o_has_index")
                    if "comodel_name" in kw or item.value.args:
                        pass
                    if "check_company" in kw: add("m2o_check_company")
                if ft in ("One2many", "Many2many"):
                    add("x2m_total")
                    add("x2m_name_endswith__ids" if fname_.endswith("_ids") else "x2m_name_other")
                if "string" in kw and isinstance(kw["string"], ast.Constant):
                    add("field_with_string")
                    if kw["string"].value == label_default(fname_, ft):
                        add("field_string_redundant")
                if ft not in ("Many2one", "One2many", "Many2many") and item.value.args and isinstance(item.value.args[0], ast.Constant) and ft in ("Char", "Text", "Html", "Integer", "Float", "Boolean", "Date", "Datetime", "Binary", "Selection"):
                    add("field_string_positional")
                for k in ("index", "copy", "groups", "tracking", "readonly", "required", "store", "compute_sudo", "default", "translate", "help", "company_dependent", "precompute", "ondelete", "domain", "context", "related", "compute", "inverse", "search", "aggregator", "sanitize", "default_export_compatible", "export_string_translation"):
                    if k in kw:
                        add("field_kw_" + k)
                if "compute" in kw and "store" in kw:
                    add("computed_stored")
                if "compute" in kw and "store" not in kw:
                    add("computed_not_stored")
                if "compute" in kw and "compute_sudo" in kw:
                    add("computed_with_compute_sudo")
                if "index" in kw and isinstance(kw["index"], ast.Constant):
                    add("index_value_" + str(kw["index"].value))
                if "default" in kw and isinstance(kw["default"], ast.Lambda):
                    add("default_lambda")
                if "default" in kw and isinstance(kw["default"], ast.Constant):
                    add("default_constant")
                if "compute" in kw and isinstance(kw["compute"], ast.Constant):
                    cname = kw["compute"].value
                    add("compute_name_pattern_ok" if cname == "_compute_" + fname_ or cname.startswith("_compute_") else "compute_name_pattern_other")
        # constraints
        for item in cls.body:
            if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name):
                if item.targets[0].id == "_sql_constraints":
                    add("sql_constraints_old_style")
                if isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Attribute) and item.value.func.attr in ("Constraint", "UniqueIndex", "Index"):
                    add("constraint_new_style_" + item.value.func.attr)
                    if not item.targets[0].id.startswith("_"):
                        add("constraint_attr_without_underscore")
        # methods
        for item in cls.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            n = item.name; d = deco_names(item)
            add("method_total")
            if n.startswith("_") and not n.startswith("__"):
                add("method_private")
            elif not n.startswith("__"):
                add("method_public")
                if "private" in d: add("method_public_api_private")
                if "model" in d or "model_create_multi" in d: add("method_public_api_model")
                if "readonly" in d: add("method_api_readonly")
                params = [a.arg for a in item.args.args + item.args.kwonlyargs]
                if "ids" in params or "context" in params:
                    add("method_param_ids_or_context")
            for dn in d:
                if dn in ("depends", "depends_context", "constrains", "onchange", "model", "model_create_multi", "private", "readonly", "autovacuum", "ondelete", "returns", "deprecated", "model_cr", "ormcache", "ormcache_context", "ormcache_ids"):
                    add("deco_" + dn)
            doc = ast.get_docstring(item)
            if doc is not None:
                add("method_with_docstring")
                L.setdefault("docstring_lines", []).append(doc.count("\n") + 1)
                if n.startswith("_") is False: add("public_method_with_docstring")
            if n in ("create",) and "model_create_multi" not in d:
                add("create_override_without_model_create_multi")
            if n in ("create",) and "model_create_multi" in d:
                add("create_override_model_create_multi")
            if n == "unlink":
                add("unlink_override")
                if any(isinstance(x, ast.Raise) for x in ast.walk(item)):
                    add("unlink_override_with_raise")
            if n.startswith("action_"):
                add("action_method")
                if any(isinstance(x, ast.Call) and call_name(x) == "ensure_one" for x in ast.walk(item)):
                    add("action_method_ensure_one")
            if n.startswith("_compute_"):
                add("compute_method")
    if models_in_file > 1:
        add("file_with_multiple_models")
    if models_in_file >= 1:
        add("files_with_models")
    # comments
    comment_lines = len(re.findall(r"^\s*#", src, re.M))
    add("py_comment_lines", comment_lines); add("py_code_lines", lines)
    if re.search(r"^\s*#\s*(def |class |import |return |self\.|print\()", src, re.M):
        add("files_with_commented_out_code")
    add("py_todo_fixme", len(re.findall(r"\b(TODO|FIXME|XXX|HACK)\b", src)))
    add("py_lines_over_120", sum(1 for l in src.split("\n") if len(l) > 120))
    add("py_lines_total", lines)


def xml_stats(path, mod):
    src = rd(path)
    if not src.strip():
        return
    add("xml_files")
    for m in re.finditer(r'<record\s+id="([^"]+)"\s+model="ir\.ui\.view"', src):
        add("view_records")
        rid = m.group(1)
        if re.search(r"_view_(list|tree|form|search|kanban|pivot|graph|calendar|activity|qweb|hierarchy|gantt|cohort|map)(_|$)", rid):
            add("view_id_follows_model_view_type")
        else:
            add("view_id_other")
    add("tag_tree", len(re.findall(r"<tree[\s>]", src)))
    add("tag_list", len(re.findall(r"<list[\s>]", src)))
    add("attr_attrs", len(re.findall(r"\sattrs=\"", src)))
    add("attr_states", len(re.findall(r"\sstates=\"", src)))
    add("attr_invisible_expr", len(re.findall(r"\sinvisible=\"", src)))
    add("t_raw", len(re.findall(r"\bt-raw=", src)))
    add("t_esc", len(re.findall(r"\bt-esc=", src)))
    add("t_out", len(re.findall(r"\bt-out=", src)))
    add("position_replace", len(re.findall(r'position="replace"', src)))
    add("position_attributes", len(re.findall(r'position="attributes"', src)))
    add("position_inside", len(re.findall(r'position="inside"', src)))
    add("position_after", len(re.findall(r'position="after"', src)))
    add("position_before", len(re.findall(r'position="before"', src)))
    add("xml_noupdate", len(re.findall(r'noupdate="1"', src)))
    add("xml_data_tag", len(re.findall(r"<data[\s>]", src)))
    add("xml_odoo_root", len(re.findall(r"<odoo[\s>]", src)))
    add("xml_menuitem", len(re.findall(r"<menuitem\b", src)))
    add("xml_record_menu", len(re.findall(r'model="ir\.ui\.menu"', src)))
    add("xml_ir_rule_records", len(re.findall(r'model="ir\.rule"', src)))
    add("xml_ir_cron_records", len(re.findall(r'model="ir\.cron"', src)))
    add("xml_groups_attr", len(re.findall(r'\sgroups="', src)))
    add("xml_widget_attr", len(re.findall(r'\swidget="', src)))
    add("xml_optional_attr", len(re.findall(r'\soptional="', src)))
    add("xml_string_attr_on_field", len(re.findall(r"<field[^>]*\sstring=\"", src)))
    add("xml_field_tags", len(re.findall(r"<field\b", src)))
    for m in re.finditer(r'<record\s+id="([^"]+)"\s+model="ir\.rule"', src):
        rid = m.group(1)
        add("rule_id_with__rule_" if "_rule" in rid or "rule_" in rid else "rule_id_other")
    for m in re.finditer(r'<record\s+id="([^"]+)"\s+model="ir\.actions\.act_window"', src):
        add("window_action_records")
        rid = m.group(1)
        add("action_id_suffix__action" if "_action" in rid else ("action_id_prefix_action_" if rid.startswith("action_") else "action_id_other"))
    # comment before replace
    for m in re.finditer(r'position="replace"', src):
        before = src[max(0, m.start() - 400):m.start()]
        add("replace_with_comment_nearby" if "<!--" in before and before.rfind("<!--") > before.rfind(">") - 380 else "replace_without_comment")
    # mixed indentation: 4 spaces vs 2
    ind = Counter(len(l) - len(l.lstrip(" ")) for l in src.split("\n") if l.startswith("  "))
    if ind:
        add("xml_indent_4_files" if ind.get(4, 0) >= ind.get(2, 0) else "xml_indent_2_files")


def csv_stats(path, mod):
    if os.path.basename(path) != "ir.model.access.csv":
        return
    add("acl_csv_files")
    try:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
    except Exception:
        return
    for r in rows:
        add("acl_rows")
        rid, gid = r.get("id", ""), r.get("group_id:id", r.get("group_id/id", ""))
        if not gid:
            add("acl_group_empty")
        mid = r.get("model_id:id", r.get("model_id/id", ""))
        if rid.startswith("access_"):
            add("acl_id_starts_access_")
        if mid.startswith("model_") or ".model_" in mid:
            add("acl_model_ref_ok")
        perms = tuple(r.get(k, "0") for k in ("perm_read", "perm_write", "perm_create", "perm_unlink"))
        add("acl_perm_" + "".join(perms))


def manifest_stats(p, mod):
    src = rd(os.path.join(p, "__manifest__.py"))
    try:
        d = ast.literal_eval(src.strip())
    except Exception:
        add("manifest_unparsable")
        return
    add("manifests")
    for k in d:
        add("manifest_key_" + k)
    add("manifest_license_" + str(d.get("license", "none")).replace(" ", "_"))
    if "base" in d.get("depends", []) or mod == "base":
        add("manifest_depends_has_base")
    if d.get("application"):
        add("manifest_application_true")
    if "installable" in d:
        add("manifest_installable_" + str(d["installable"]))
    if "assets" in d:
        for b in d["assets"]:
            add("asset_bundle_" + b)
    v = str(d.get("version", ""))
    add("manifest_version_pattern_" + re.sub(r"\d+", "N", v))
    if d.get("author"):
        add("manifest_author_" + ("Odoo S.A." if "Odoo S.A." in d["author"] else "other"))
    add("manifest_has_module_dirs_" + ("tests" if os.path.isdir(os.path.join(p, "tests")) else "no_tests"))


JS_COMP = re.compile(r"class\s+(\w+)\s+extends\s+([\w.]+)")


def js_stats(path, mod):
    src = rd(path)
    if not src.strip():
        return
    add("js_files")
    first = src.lstrip().split("\n", 1)[0]
    if "@odoo-module" in first:
        add("js_header_odoo_module")
    L.setdefault("js_lines", []).append(src.count("\n") + 1)
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)  # block comments
    code = re.sub(r"(?m)(?<![:'\"])//.*$", "", code)  # line comments, one line only
    add("js_setTimeout_bare", len(re.findall(r"(?<![\w.])setTimeout\(", code)))
    add("js_browser_setTimeout", len(re.findall(r"browser\.setTimeout\(", code)))
    add("js_fetch_bare", len(re.findall(r"(?<![\w.])fetch\(", code)))
    add("js_browser_fetch", len(re.findall(r"browser\.fetch\(", code)))
    add("js_localStorage_bare", len(re.findall(r"(?<![\w.])localStorage\b", code)))
    add("js_browser_localStorage", len(re.findall(r"browser\.localStorage", code)))
    add("js_window_open_bare", len(re.findall(r"window\.open\(", code)))
    add("js_document_direct", len(re.findall(r"(?<![\w.])document\.", code)))
    add("js_window_direct", len(re.findall(r"(?<![\w.])window\.", code)))
    add("js_useService", len(re.findall(r"useService\(", code)))
    add("js_orm_call", len(re.findall(r"orm\.(call|read|searchRead|webSearchRead|create|write|unlink)\(", code)))
    add("js_rpc_calls", len(re.findall(r"(?<![\w.])rpc\(", code)))
    add("js_patch_calls", len(re.findall(r"(?<![\w.])patch\(", code)))
    add("js_t_func", len(re.findall(r"(?<![\w.])_t\(", code)))
    add("js_optional_chaining", len(re.findall(r"\?\.[\w\[(]", code)))
    add("js_nullish", len(re.findall(r"\?\?", code)))
    add("js_console_log", len(re.findall(r"console\.log\(", code)))
    add("js_throw_new_Error", len(re.findall(r"throw new \w*Error\(", code)))
    add("js_throw_other", len(re.findall(r"throw (?!new )", code)))
    add("js_async_functions", len(re.findall(r"\basync\b", code)))
    add("js_var_decl", len(re.findall(r"(?<![\w.])var\s", code)))
    add("js_odoo_define", len(re.findall(r"odoo\.define\(", code)))
    add("js_registry_category", len(re.findall(r"registry\.category\(", code)))
    add("js_useState", len(re.findall(r"useState\(", code)))
    add("js_useEffect", len(re.findall(r"useEffect\(", code)))
    add("js_onWillStart", len(re.findall(r"onWillStart\(", code)))
    add("js_useBus", len(re.findall(r"useBus\(", code)))
    add("js_addEventListener_bare", len(re.findall(r"addEventListener\(", code)))
    add("js_useExternalListener", len(re.findall(r"useExternalListener\(", code)))
    for m in JS_COMP.finditer(code):
        base = m.group(2)
        if base in ("Component",) or base.endswith("Component"):
            add("js_component_classes")
            body = code[m.end(): m.end() + 6000]
            nxt = JS_COMP.search(body)
            if nxt:
                body = body[:nxt.start()]
            if re.search(r"static\s+template\s*=", body): add("js_component_static_template")
            if re.search(r"static\s+props\s*=", body): add("js_component_static_props")
            if re.search(r"\n\s+constructor\(", body): add("js_component_constructor")
            if re.search(r"\n\s+setup\(\)", body): add("js_component_setup")


def scss_stats(path, mod):
    src = rd(path)
    if not src.strip():
        return
    add("scss_files")
    add("scss_id_selectors", len(re.findall(r"(?m)^\s*#[\w-]+\s*[{,]", src)))
    add("scss_root_selector", len(re.findall(r":root\b", src)))
    add("scss_important", len(re.findall(r"!important", src)))
    add("scss_global_vars_o", len(re.findall(r"^\$o-[\w-]+\s*:", src, re.M)))
    add("scss_global_vars_other", len(re.findall(r"^\$(?!o-)[\w-]+\s*:", src, re.M)))
    add("scss_class_o_prefix", len(re.findall(r"\.o_[\w-]+", src)))
    add("scss_class_other", len(re.findall(r"(?<![\w-])\.(?!o_)[a-zA-Z][\w-]*(?=[\s{,.:>+~)\[])", src)))


def test_stats(p, mod):
    tdir = os.path.join(p, "tests")
    if not os.path.isdir(tdir):
        return
    for f in walk(tdir, (".py",), exclude=("__pycache__",)):
        src = rd(f)
        if not src.strip():
            continue
        add("test_files")
        if "@tagged" in src or "tagged(" in src:
            add("test_files_with_tagged")
        add("test_methods", len(re.findall(r"def test_", src)))
        for b in ("TransactionCase", "HttpCase", "SingleTransactionCase", "BaseCase", "SavepointCase", "MailCommon", "AccountTestInvoicingCommon", "SaleCommon"):
            add("test_base_" + b, len(re.findall(r"class\s+\w+\((?:[\w.]*,\s*)*[\w.]*" + b + r"[\w.,\s]*\)", src)))
        add("test_new_test_user", len(re.findall(r"new_test_user\(|mail_new_test_user\(", src)))
        add("test_res_users_create", len(re.findall(r"\[['\"]res\.users['\"]\]\.(with_context\([^)]*\)\.)?create\(", src)))
        add("test_freeze_time", len(re.findall(r"freeze_time|freezegun", src)))
        add("test_Form", len(re.findall(r"\bForm\(", src)))
        add("test_assertQueryCount", len(re.findall(r"assertQueryCount", src)))
        add("test_subTest", len(re.findall(r"subTest\(", src)))
        add("test_mock_patch", len(re.findall(r"patch\(|patch\.object", src)))
        add("test_start_tour", len(re.findall(r"start_tour\(", src)))
        add("test_setUpClass", len(re.findall(r"def setUpClass", src)))
        add("test_setUp", len(re.findall(r"def setUp\(", src)))


for mod, p in modules():
    add("modules")
    manifest_stats(p, mod)
    for f in walk(p, (".py",)):
        py_stats(f, mod)
    for f in walk(p, (".xml",)):
        if "/static/" in f.replace("\\", "/"):
            continue
        xml_stats(f, mod)
    for f in walk(p, (".csv",)):
        csv_stats(f, mod)
    for f in walk(os.path.join(p, "static", "src"), (".js",), exclude=("lib", "node_modules")) if os.path.isdir(os.path.join(p, "static", "src")) else []:
        js_stats(f, mod)
    for f in walk(os.path.join(p, "static", "src"), (".scss",), exclude=("lib", "node_modules")) if os.path.isdir(os.path.join(p, "static", "src")) else []:
        scss_stats(f, mod)
    for f in walk(os.path.join(p, "static", "src"), (".xml",), exclude=("lib", "node_modules")) if os.path.isdir(os.path.join(p, "static", "src")) else []:
        s = rd(f)
        add("owl_xml_t_esc", len(re.findall(r"\bt-esc=", s)))
        add("owl_xml_t_out", len(re.findall(r"\bt-out=", s)))
        add("owl_xml_t_raw", len(re.findall(r"\bt-raw=", s)))
    test_stats(p, mod)

out = dict(C)
for k, v in L.items():
    if v and isinstance(v[0], int):
        out["median_" + k] = statistics.median(v)
        out["mean_" + k] = round(statistics.mean(v), 1)
        out["p90_" + k] = sorted(v)[int(len(v) * 0.9)]
    elif k == "file_not_named_examples":
        out["file_not_named_examples"] = v[:12]
out["_label"] = label
print(json.dumps(out, sort_keys=True))
