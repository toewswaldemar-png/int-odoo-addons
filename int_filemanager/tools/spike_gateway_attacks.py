"""SPIKE (throw-away): attacks on the guest gateway, run from outside against a test instance.

    python spike_gateway_attacks.py http://host:8089 <token> <outside_folder_id> <hidden_folder_id>

Prints one line per attack: what was sent and what the gateway answered.
"""

import json
import sys
import urllib.error
import urllib.request

BASE, TOKEN, OUTSIDE, HIDDEN = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
DOC = "int.filemanager.document"
FOLDER = "int.filemanager.folder"
TAG = "int.filemanager.tag"
SPEC = {"name": {}, "folder_id": {"fields": {"display_name": {}}}}


def post(payload, token=TOKEN):
    params = dict(payload)
    if token is not None:
        params["token"] = token
    body = json.dumps({"jsonrpc": "2.0", "method": "call", "id": 1, "params": params}).encode()
    request = urllib.request.Request(BASE + "/int_filemanager/spike/rpc", body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request) as response:
            answer = json.load(response)
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}"
    if "error" in answer:
        data = answer["error"].get("data", {})
        return f"ERROR {data.get('name', '')}: {str(data.get('message', answer['error'].get('message')))[:90]}"
    return answer["result"]


def call(model, method, args=None, token=TOKEN, **kwargs):
    return post({"model": model, "method": method, "args": args or [], "kwargs": kwargs}, token)


def names(result):
    if isinstance(result, dict) and "records" in result:
        return {"length": result.get("length"), "names": sorted(str(record.get("name", record)) for record in result["records"])}
    return result


def show(title, result):
    text = json.dumps(result, ensure_ascii=False, default=str)
    print(f"{title:<62} -> {text[:230]}")


def search(domain, spec=SPEC, **kwargs):
    return names(call(DOC, "web_search_read", domain=domain, specification=spec, **kwargs))


def count(result):
    return len(result["records"]) if isinstance(result, dict) else result


print("== baseline ==")
show("web_search_read, no domain", search([]))
print("== token ==")
show("no token", post({"model": DOC, "method": "web_search_read", "kwargs": {"domain": [], "specification": {"name": {}}}}, None))
show("garbage token", call(DOC, "web_search_read", token="x", domain=[], specification=SPEC))
show("token of another folder (id swapped)", call(DOC, "web_search_read", token=f"{OUTSIDE}-{TOKEN.split('-')[1]}", domain=[], specification=SPEC))
show("token with a negative id", call(DOC, "web_search_read", token=f"-1-{TOKEN.split('-')[1]}", domain=[], specification=SPEC))
print("== methods and models ==")
for method, kw in [
    ("unlink", {}), ("write", {"vals": {"name": "x"}}), ("create", {"vals_list": [{"name": "x"}]}),
    ("search_read", {"domain": [], "fields": ["name"]}), ("read", {}), ("action_archive", {}), ("web_save", {}),
    ("copy", {}), ("check_access", {}), ("with_user", {}), ("_search", {}), ("sudo", {}), ("export_data", {}),
    ("name_create", {"name": "x"}), ("message_post", {"body": "x"}),
]:
    show(f"{DOC}.{method}", call(DOC, method, [[1]], **kw))
for model in ["res.users", "ir.config_parameter", "ir.attachment", "int.filemanager.text.page", "int.filemanager.link", "res.partner", "ir.model.data"]:
    show(f"{model}.web_search_read", call(model, "web_search_read", domain=[], specification={"id": {}}))
print("== domain attacks (the scope must hold) ==")
show("folder_id = outside folder", search([("folder_id", "=", OUTSIDE)]))
show("folder_id = hidden folder (in scope, hidden by rules)", search([("folder_id", "=", HIDDEN)]))
show("['|', ('id','>',0), ('name','=','x')]", search(["|", ("id", ">", 0), ("name", "=", "x")]))
show("[(1,'=',1)]", search([(1, "=", 1)]))
show("[('id','in',[7,8])] (ids outside / hidden)", search([("id", "in", [7, 8])]))
show("folder_id child_of outside", search([("folder_id", "child_of", OUTSIDE)]))
show("folder_id parent_of outside", search([("folder_id", "parent_of", OUTSIDE)]))
show("['!', ('id','=',0)]", search(["!", ("id", "=", 0)]))
show("folder_id.access_user_ids.login = admin (path)", search([("folder_id.access_user_ids.login", "=", "admin")]))
show("create_uid.login (not in whitelist)", search([("create_uid.login", "=", "admin")]))
show("folder_id any [access_user_ids.login] (any)", search([("folder_id", "any", [("access_user_ids.login", "=", "admin")])]))
show("folder_id any [(create_uid..)] (field of the comodel)", search([("folder_id", "any", [("create_uid", "=", 1)])]))
show("content_search ilike (full text)", search([("content_search", "ilike", "secret")]))
show("active = False (archived)", search([("active", "=", False)]))
show("origin_path ilike (field with groups)", search([("origin_path", "ilike", "a")]))
show("bad operator '=?'", search([("name", "=?", "a")]))
show("bad operator 'sqli'", search([("name", "; drop table x;--", "a")]))
show("domain is a string", search("[(1,'=',1)]"))
show("domain value is a dict", search([("name", "=", {"a": 1})]))
deep = [("name", "=", "x")]
for _ in range(8):
    deep = [("parent_id", "any", deep)]
show("deep nested any (8 levels)", search([("folder_id", "any", deep)]))
show("nested any (2 levels, legal)", search([("folder_id", "any", [("parent_id", "any", [("name", "=", "Gastbereich")])])]))
show("context active_test=False in kwargs.context", search([], context={"active_test": False}))
print("== read specification attacks ==")
for field in ["create_uid", "message_ids", "origin_path", "content", "thumbnail", "activity_ids", "company_id", "access_user_ids", "write_uid", "message_follower_ids"]:
    show(f"specification {field}", search([], {field: {}}))
show("nested spec: folder_id.access_user_ids", search([], {"folder_id": {"fields": {"access_user_ids": {}}}}))
show("nested spec: tag_ids.create_uid", search([], {"tag_ids": {"fields": {"create_uid": {}}}}))
show("nested spec with context key (dropped)", search([], {"tag_ids": {"fields": {"name": {}}, "context": {"active_test": False}}}))
show("nested spec with domain key (dropped)", search([], {"tag_ids": {"fields": {"name": {}}, "domain": [("id", ">", 0)]}}))
show("nested spec with unknown key", search([], {"tag_ids": {"fields": {"name": {}}, "foo": 1}}))
print("== order / group / aggregate attacks ==")
for order in ["create_uid", "name; select pg_sleep(5)", "(select 1)", "folder_id.name", "name asc, create_uid desc", "name desc nulls last", "id desc"]:
    show(f"order {order!r}", search([], order=order))
for groupby in [["create_uid"], ["folder_id.name"], ["name", "mimetype", "folder_id", "tag_ids"], ["write_date:month"], ["write_date:evil"], ["checksum"]]:
    show(f"formatted_read_group groupby {groupby}", call(DOC, "formatted_read_group", domain=[], groupby=groupby, aggregates=["__count"]))
for aggregates in [["size:sum"], ["create_uid:count"], ["size:evil"], ["id:array_agg"], ["(select 1):sum"]]:
    show(f"formatted_read_group aggregates {aggregates}", call(DOC, "formatted_read_group", domain=[], groupby=["mimetype"], aggregates=aggregates))
show("formatted_read_group with having", call(DOC, "formatted_read_group", domain=[], groupby=["mimetype"], aggregates=["__count"], having=[("__count", ">", 0)]))
show("web_read_group groupby folder_id (counts only the scope)", call(DOC, "web_read_group", domain=[], groupby=["folder_id"], aggregates=["__count"]))
print("== limit and offset ==")
show("limit 100000 (clamped to 80)", count(call(DOC, "web_search_read", domain=[], specification={"name": {}}, limit=100000)))
show("limit -1", count(call(DOC, "web_search_read", domain=[], specification={"name": {}}, limit=-1)))
show("limit 'abc'", count(call(DOC, "web_search_read", domain=[], specification={"name": {}}, limit="abc")))
show("limit 2 and offset 1", names(call(DOC, "web_search_read", domain=[], specification={"name": {}}, limit=2, offset=1)))
show("offset -5", count(call(DOC, "web_search_read", domain=[], specification={"name": {}}, offset=-5)))
print("== ids (web_read) ==")
show("web_read ids [1] (in scope)", call(DOC, "web_read", [[1]], specification={"name": {}}))
show("web_read ids [7, 8] (outside, hidden)", call(DOC, "web_read", [[7, 8]], specification={"name": {}}))
show("web_read ids as strings", call(DOC, "web_read", [["1"]], specification={"name": {}}))
show("web_read 1000 ids", call(DOC, "web_read", [list(range(1, 1001))], specification={"name": {}}))
print("== search panel ==")
panel = dict(category_domain=[], filter_domain=[], enable_counters=False, expand=True, hierarchize=True, limit=0, search_domain=[])


def values(result):
    return sorted(v["display_name"] for v in result["values"]) if isinstance(result, dict) and "values" in result else result


show("folder panel (expand, hierarchize)", values(call(DOC, "search_panel_select_range", ["folder_id"], comodel_domain=[], **panel)))
show("folder panel, comodel_domain id = outside", values(call(DOC, "search_panel_select_range", ["folder_id"], **{**panel, "comodel_domain": [("id", "=", OUTSIDE)]})))
show("folder panel, search_domain on the outside folder", values(call(DOC, "search_panel_select_range", ["folder_id"], **{**panel, "expand": False, "search_domain": [("folder_id", "=", OUTSIDE)]})))
show("panel for create_uid (not in whitelist)", call(DOC, "search_panel_select_range", ["create_uid"], **panel))
show("tag panel (multi, expand)", values(call(DOC, "search_panel_select_multi_range", ["tag_ids"], comodel_domain=[], **panel)))
show("tag panel with group_by create_uid", call(DOC, "search_panel_select_multi_range", ["tag_ids"], group_by="create_uid", comodel_domain=[], **panel))
show("tag panel with counters", values(call(DOC, "search_panel_select_multi_range", ["tag_ids"], comodel_domain=[], **{**panel, "enable_counters": True, "expand": False})))
print("== other models ==")
show("folders web_search_read (the rules hide the private one)", sorted(r["display_name"] for r in call(FOLDER, "web_search_read", domain=[], specification={"display_name": {}})["records"]))
show("folders name_search ''", call(FOLDER, "name_search", name=""))
show("folders name_search 'Intern'", call(FOLDER, "name_search", name="Intern"))
show("folders web_search_read access_user_ids", call(FOLDER, "web_search_read", domain=[], specification={"access_user_ids": {}}))
show("tags web_search_read", sorted(r["name"] for r in call(TAG, "web_search_read", domain=[], specification={"name": {}})["records"]))
show("tags name_search 'Geheim'", call(TAG, "name_search", name="Geheim"))
show("fields_get (document)", sorted(call(DOC, "fields_get")))
show("fields_get allfields create_uid", call(DOC, "fields_get", [["create_uid"]]))
show("get_views form", call(DOC, "get_views", views=[[False, "form"]], options={}))
views = call(DOC, "get_views", views=[[1, "list"]], options={"toolbar": True, "load_filters": True, "action_id": 1})
show("get_views with an own view id, toolbar, filters", {"views": list(views["views"]), "toolbar": "toolbar" in views["views"]["list"], "models": sorted(views["models"])} if isinstance(views, dict) else views)

print("== binary routes (cookie) ==")


def get(path, cookie=True):
    request = urllib.request.Request(BASE + path)
    if cookie:
        request.add_header("Cookie", f"fm_spike_token={TOKEN}")
    try:
        with urllib.request.urlopen(request) as response:
            return f"HTTP {response.status}, {response.headers.get('Content-Type')}, {len(response.read())} bytes"
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}"


for label, path, cookie in [
    ("doc 1 content, with cookie", "/web/content/int.filemanager.document/1/content", True),
    ("doc 1 content, WITHOUT cookie", "/web/content/int.filemanager.document/1/content", False),
    ("doc 4 image 256x256, with cookie", "/web/image/int.filemanager.document/4/content/256x256", True),
    ("doc 1 thumbnail, with cookie", "/web/image/int.filemanager.document/1/thumbnail/256x256", True),
    ("doc 7 (outside folder), with cookie", "/web/content/int.filemanager.document/7/content", True),
    ("doc 8 (hidden folder), with cookie", "/web/content/int.filemanager.document/8/content", True),
    ("doc 1 field 'checksum', with cookie", "/web/content/int.filemanager.document/1/checksum", True),
    ("doc 1 field 'write_date', with cookie", "/web/content/int.filemanager.document/1/write_date", True),
]:
    show(label, get(path, cookie))
