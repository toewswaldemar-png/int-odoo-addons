"""Attacks on the gateway and the file routes of a share, from outside, against a running instance.

    python3 share_attacks.py http://host:8069 seed.json

The same attacks as the first spike (docs/spike_gast_ui), against the routes that were built
(``/int_filemanager/share/<token>/...``). Every answer is read for what a guest must never get:
a name that starts with SECRET-, a checksum, a traceback, a status 5xx. One line per attack is
printed; the exit status is 1 if any attack got through.
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE, SEED = sys.argv[1], json.load(open(sys.argv[2]))
TOKEN = SEED["shares"]["view"]["token"]
OUTSIDE, HIDDEN, PARENT = SEED["outside"], SEED["hidden"], SEED["parent"]
DOC, FOLDER, TAG = "int.filemanager.document", "int.filemanager.folder", "int.filemanager.tag"
SPEC = {"name": {}, "folder_id": {"fields": {"display_name": {}}}}
CHECKSUM = re.compile(r"[0-9a-f]{64}")
problems = []


def request(method, path, body=None, headers=None, raw=False):
    data = body if raw else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + urllib.parse.quote(path, safe="/?=&%:"), data, headers or {"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read(), dict(error.headers)


def show(title, status, text, headers=None):
    flags = []
    if any(marker in text for marker in ("SECRET-PARENT", "SECRET-HIDDEN", "SECRET-OUTSIDE", "SECRET-TAG")):
        flags.append("LEAK(secret name)")
    # the hash of the registry is in the session information of every Odoo page: not a checksum
    scanned = re.sub(r'"registry_hash": "[0-9a-f]{64}"', "", text)
    found = CHECKSUM.search(scanned)
    if found:
        flags.append("LEAK(checksum)")
        print("   64 hex characters at:", repr(scanned[max(0, found.start() - 60) : found.end() + 10]))
    if "Traceback" in text or status >= 500:
        flags.append(f"FAIL(status {status} / traceback)")
    if headers and "Set-Cookie" in headers:
        flags.append("FAIL(cookie)")
    if flags:
        problems.append((title, flags))
    print(f"{title:<64} -> {status} {text[:150]!r} {' '.join(flags)}")


def rpc(token, payload, key=None, title=None, **kwargs):
    status, body, headers = request(
        "POST", f"/int_filemanager/share/{token}/rpc", {"k": key, **payload}, **kwargs
    )
    show(title or f"{payload.get('model')}.{payload.get('method')}", status, body.decode(errors="replace"), headers)
    return status, body


def call(model, method, args=None, title=None, token=TOKEN, **kwargs):
    return rpc(token, {"model": model, "method": method, "args": args or [], "kwargs": kwargs}, title=title)


def search(title, domain, spec=SPEC, **kwargs):
    return call(DOC, "web_search_read", title=title, domain=domain, specification=spec, **kwargs)


print("== baseline ==")
search("web_search_read, no domain", [])
print("== token ==")
for title, token in [("garbage token", "x"), ("36 characters, unknown", "a" * 36), ("another share's token cut", TOKEN[:-1]),
                     ("empty-ish", "%20"), ("sql in the token", "' or '1'='1")]:
    rpc(token, {"model": DOC, "method": "web_search_read", "args": [], "kwargs": {"domain": [], "specification": {"name": {}}}}, title=title)
print("== the request itself ==")
for title, method, body, headers in [
    ("GET on rpc", "GET", None, None),
    ("not json", "POST", b"not json", {"Content-Type": "application/json"}),
    ("json list", "POST", b"[1,2]", {"Content-Type": "application/json"}),
    ("json null", "POST", b"null", {"Content-Type": "application/json"}),
    ("jsonrpc envelope", "POST", json.dumps({"jsonrpc": "2.0", "method": "call", "params": {"model": DOC}}).encode(), {"Content-Type": "application/json"}),
    ("body over 1 MiB", "POST", b"x" * (1024 * 1024 + 5000), {"Content-Type": "application/json"}),
]:
    status, text, h = request(method, f"/int_filemanager/share/{TOKEN}/rpc", body, headers, raw=True)
    show(title, status, text.decode(errors="replace"), h)
print("== methods and models ==")
for method, kw in [
    ("unlink", {}), ("write", {"vals": {"name": "x"}}), ("create", {"vals_list": [{"name": "x"}]}),
    ("search_read", {"domain": [], "fields": ["name"]}), ("read", {}), ("action_archive", {}), ("web_save", {}),
    ("copy", {}), ("check_access", {}), ("with_user", {}), ("_search", {}), ("sudo", {}), ("export_data", {}),
    ("name_create", {"name": "x"}), ("message_post", {"body": "x"}), ("action_share", {}), ("action_open_shares", {}),
]:
    call(DOC, method, [[1]], **kw)
for model in ["res.users", "ir.config_parameter", "ir.attachment", "int.filemanager.text.page", "int.filemanager.link",
              "res.partner", "ir.model.data", "int.filemanager.share", "int.filemanager.share.attempt"]:
    call(model, "web_search_read", title=f"{model}.web_search_read", domain=[], specification={"id": {}})
print("== domain attacks (the scope must hold) ==")
search("folder_id = outside folder", [("folder_id", "=", OUTSIDE)])
search("folder_id = hidden folder", [("folder_id", "=", HIDDEN)])
search("folder_id = the parent of the root", [("folder_id", "=", PARENT)])
search("['|', ('id','>',0), ('name','=','x')]", ["|", ("id", ">", 0), ("name", "=", "x")])
search("[(1,'=',1)]", [(1, "=", 1)])
search("id in the outside document", [("id", "in", [SEED["outside_doc"]])])
search("folder_id child_of outside", [("folder_id", "child_of", OUTSIDE)])
search("folder_id child_of the parent of the root", [("folder_id", "child_of", PARENT)])
search("folder_id child_of hidden", [("folder_id", "child_of", HIDDEN)])
search("folder_id parent_of outside", [("folder_id", "parent_of", OUTSIDE)])
search("['!', ('id','=',0)]", ["!", ("id", "=", 0)])
search("folder_id.access_user_ids.login (path)", [("folder_id.access_user_ids.login", "=", "admin")])
search("folder_id.parent_id.name ilike SECRET (the parent's name)", [("folder_id.parent_id.name", "ilike", "SECRET")])
search("folder_id any [parent_id = parent]", [("folder_id", "any", [("parent_id", "=", PARENT)])])
search("folder_id any [parent_id.name ilike SECRET]", [("folder_id", "any", [("parent_id.name", "ilike", "SECRET")])])
search("create_uid.login (not in the whitelist)", [("create_uid.login", "=", "admin")])
search("tag_ids.name ilike SECRET (the tag of hidden files)", [("tag_ids.name", "ilike", "SECRET")])
search("content_search ilike (full text)", [("content_search", "ilike", "secret")])
search("active = False (archived)", [("active", "=", False)])
search("origin_path ilike (field with groups)", [("origin_path", "ilike", "a")])
search("bad operator '=?'", [("name", "=?", "a")])
search("bad operator 'sqli'", [("name", "; drop table x;--", "a")])
search("domain is a string", "[(1,'=',1)]")
search("domain value is a dict", [("name", "=", {"a": 1})])
deep = [("name", "=", "x")]
for _ in range(8):
    deep = [("parent_id", "any", deep)]
search("deep nested any (8 levels)", [("folder_id", "any", deep)])
search("context active_test=False", [], context={"active_test": False})
print("== read specification attacks ==")
for field in ["create_uid", "message_ids", "origin_path", "content", "thumbnail", "activity_ids", "company_id",
              "access_user_ids", "write_uid", "message_follower_ids", "checksum", "ocr_checksum", "share_id"]:
    search(f"specification {field}", [], {field: {}})
search("spec: folder_id.access_user_ids", [], {"folder_id": {"fields": {"access_user_ids": {}}}})
search("spec: folder_id.parent_id (the parent of the root)", [], {"folder_id": {"fields": {"parent_id": {"fields": {"display_name": {}}}}}})
search("spec: folder_id.parent_id.parent_id", [], {"folder_id": {"fields": {"parent_id": {"fields": {"parent_id": {}}}}}})
search("spec: tag_ids.create_uid", [], {"tag_ids": {"fields": {"create_uid": {}}}})
search("spec with context key", [], {"tag_ids": {"fields": {"name": {}}, "context": {"active_test": False}}})
search("spec with domain key", [], {"tag_ids": {"fields": {"name": {}}, "domain": [("id", ">", 0)]}})
print("== order / group / aggregate attacks ==")
for order in ["create_uid", "name; select pg_sleep(5)", "(select 1)", "folder_id.name", "folder_id.parent_id.name", "checksum", "id desc"]:
    search(f"order {order!r}", [], order=order)
for groupby in [["create_uid"], ["folder_id.name"], ["folder_id.parent_id"], ["checksum"], ["name", "mimetype", "folder_id", "tag_ids"], ["write_date:evil"]]:
    call(DOC, "formatted_read_group", title=f"formatted_read_group {groupby}", domain=[], groupby=groupby, aggregates=["__count"])
for aggregates in [["size:sum"], ["create_uid:count"], ["size:evil"], ["id:array_agg"], ["checksum:count_distinct"]]:
    call(DOC, "formatted_read_group", title=f"aggregates {aggregates}", domain=[], groupby=["mimetype"], aggregates=aggregates)
call(DOC, "web_read_group", title="web_read_group by folder_id (counts the scope only)", domain=[], groupby=["folder_id"], aggregates=["__count"])
print("== limit, offset, ids ==")
search("limit 100000", [], limit=100000)
search("limit -1", [], limit=-1)
search("limit 'abc'", [], limit="abc")
search("offset 10**12", [], offset=10**12)
search("offset -5", [], offset=-5)
call(DOC, "web_read", [[SEED["outside_doc"]]], title="web_read the outside document", specification={"name": {}})
call(DOC, "web_read", [[SEED["outside_doc"], SEED["documents"]["single"]]], title="web_read outside + inside", specification={"name": {}})
call(DOC, "web_read", [["1"]], title="web_read ids as strings", specification={"name": {}})
call(DOC, "web_read", [list(range(1, 1001))], title="web_read 1000 ids", specification={"name": {}})
call(FOLDER, "web_read", [[PARENT]], title="web_read the parent of the root", specification={"display_name": {}})
call(FOLDER, "web_read", [[SEED["root"]]], title="web_read the root (parent_id must be False)", specification={"parent_id": {"fields": {"display_name": {}}}})
print("== search panel ==")
panel = dict(category_domain=[], filter_domain=[], enable_counters=False, expand=True, hierarchize=True, limit=0, search_domain=[])
call(DOC, "search_panel_select_range", ["folder_id"], title="folder panel (expand, hierarchize)", comodel_domain=[], **panel)
call(DOC, "search_panel_select_range", ["folder_id"], title="folder panel, comodel_domain = outside", **{**panel, "comodel_domain": [("id", "=", OUTSIDE)]})
call(DOC, "search_panel_select_range", ["folder_id"], title="folder panel, comodel_domain = the parent", **{**panel, "comodel_domain": [("id", "=", PARENT)]})
call(DOC, "search_panel_select_range", ["create_uid"], title="panel for create_uid", comodel_domain=[], **panel)
call(DOC, "search_panel_select_multi_range", ["tag_ids"], title="tag panel (multi)", comodel_domain=[], **panel)
call(DOC, "search_panel_select_multi_range", ["tag_ids"], title="tag panel, group_by create_uid", group_by="create_uid", comodel_domain=[], **panel)
print("== other models ==")
call(FOLDER, "web_search_read", title="folders web_search_read", domain=[], specification={"display_name": {}, "parent_id": {"fields": {"display_name": {}}}})
call(FOLDER, "name_search", title="folders name_search ''", name="")
call(FOLDER, "name_search", title="folders name_search 'SECRET'", name="SECRET")
call(TAG, "web_search_read", title="tags web_search_read", domain=[], specification={"name": {}})
call(TAG, "name_search", title="tags name_search 'SECRET'", name="SECRET")
call(DOC, "fields_get", title="fields_get (document)")
call(DOC, "get_views", title="get_views form", views=[[False, "form"]], options={})
call(DOC, "get_views", title="get_views list with toolbar", views=[[False, "list"]], options={"toolbar": True, "load_filters": True})
print("== the file routes ==")
inside_doc = SEED["documents"]["single"]
for title, path in [
    ("content of an outside document", f"/int_filemanager/share/{TOKEN}/content/{SEED['outside_doc']}"),
    ("download of an outside document (GET)", f"/int_filemanager/share/{TOKEN}/content/{SEED['outside_doc']}?download=1"),
    ("thumbnail of an outside document", f"/int_filemanager/share/{TOKEN}/thumbnail/{SEED['outside_doc']}"),
    ("image of an outside document", f"/int_filemanager/share/{TOKEN}/image/{SEED['outside_doc']}/512"),
    ("image, a size that does not exist", f"/int_filemanager/share/{TOKEN}/image/{inside_doc}/9999"),
    ("document id beyond int4", f"/int_filemanager/share/{TOKEN}/content/99999999999"),
    ("document id 0", f"/int_filemanager/share/{TOKEN}/content/0"),
    ("document id negative", f"/int_filemanager/share/{TOKEN}/content/-1"),
    ("the page of the share", f"/int_filemanager/share/{TOKEN}"),
    ("web content route (no access token)", f"/web/content/int.filemanager.document/{inside_doc}/content"),
    ("web image route (no access token)", f"/web/image/int.filemanager.document/{inside_doc}/thumbnail/256x256"),
]:
    status, body, headers = request("GET", path)
    show(title, status, body.decode(errors="replace") if status != 200 or "html" in headers.get("Content-Type", "") else f"[{len(body)} bytes]", headers)
# the core's routes for a guest without a login: they must answer as for a record that is not there
missing = request("GET", "/web/image/int.filemanager.document/999999/thumbnail/256x256")
existing = request("GET", f"/web/image/int.filemanager.document/{inside_doc}/thumbnail/256x256")
same = missing[0] == existing[0] and missing[1] == existing[1]
print(f"{'web image of a file with a picture, as for a missing record':<64} -> {existing[0]} same as for a missing record: {same}")
if not same:
    problems.append(("web image route answers differently for a record that exists", ["LEAK(picture)"]))
status, body, headers = request("POST", f"/int_filemanager/share/{TOKEN}/download/{inside_doc}", b"", {}, raw=True)
show("POST download on a folder share of a document in scope", status, f"[{len(body)} bytes]" if status == 200 else body.decode(errors="replace")[:200], headers)
print("== the end ==")
if problems:
    print(f"{len(problems)} ATTACK(S) GOT THROUGH:")
    for title, flags in problems:
        print("  ", title, flags)
    sys.exit(1)
print("no attack got through")
