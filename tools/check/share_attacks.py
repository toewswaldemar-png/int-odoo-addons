"""Attacks on the pages and the file routes of a share, from outside, against a running instance.

    python3 share_attacks.py http://host:8069 seed.json

The attacks of the spike (docs/spike_gast_ui) that still have a target, and those that the server
rendered pages bring: the folder of the address, the text of the search, the sorting, the page
number, the cookie with the key. Every answer is read for what a guest must never get: a name that
starts with SECRET-, a checksum, a traceback, a status 5xx, a session cookie. One line per attack is
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
PASSWORD_TOKEN = SEED["shares"]["password"]["token"]
OUTSIDE, HIDDEN, PARENT, ROOT = SEED["outside"], SEED["hidden"], SEED["parent"], SEED["root"]
INSIDE_DOC = SEED["documents"]["single"]
CHECKSUM = re.compile(r"[0-9a-f]{64}")
SECRETS = ("SECRET-PARENT", "SECRET-HIDDEN", "SECRET-OUTSIDE", "SECRET-TAG")
problems = []


def request(method, path, body=None, headers=None):
    req = urllib.request.Request(
        BASE + urllib.parse.quote(path, safe="/?=&%:;+"), body, headers or {}, method=method
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=60) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read(), dict(error.headers)


def show(title, status, body, headers=None, allow_cookie=(), echoed=""):
    text = body.decode(errors="replace") if isinstance(body, bytes) else body
    flags = []
    # What the guest typed comes back in the page (the search box, the links): not a leak.
    scanned_for_secrets = text
    for form in {echoed, urllib.parse.quote(echoed), urllib.parse.quote_plus(echoed)} - {""}:
        scanned_for_secrets = scanned_for_secrets.replace(form, "")
    if any(marker in scanned_for_secrets for marker in SECRETS):
        flags.append("LEAK(secret name)")
    # the hash of the registry is in the session information of every Odoo page: not a checksum
    scanned = re.sub(r'"registry_hash": "[0-9a-f]{64}"', "", text)
    found = CHECKSUM.search(scanned)
    if found:
        flags.append("LEAK(checksum)")
        print("   64 hex characters at:", repr(scanned[max(0, found.start() - 60) : found.end() + 10]))
    if "Traceback" in text or status >= 500:
        flags.append(f"FAIL(status {status} / traceback)")
    cookies = (headers or {}).get("Set-Cookie", "")
    if "session_id" in cookies or ("int_filemanager_share_key" in cookies and "key" not in allow_cookie):
        flags.append("FAIL(session or key cookie)")
    if flags:
        problems.append((title, flags))
    print(f"{title:<64} -> {status} {text[:110]!r} {' '.join(flags)}")
    return status, text


def get(title, path, headers=None, echoed=""):
    status, body, answer = request("GET", path, None, headers)
    return show(title, status, body, answer, echoed=echoed)


def page(tail="", token=TOKEN, **query):
    return f"/int_filemanager/share/{token}{tail}" + (f"?{urllib.parse.urlencode(query)}" if query else "")


print("== token ==")
for title, token in [
    ("garbage token", "x"),
    ("36 characters, unknown", "a" * 36),
    ("the token cut", TOKEN[:-1]),
    ("sql in the token", "' or '1'='1"),
    ("path traversal", ".."),
    ("a token of the length of a uuid with a slash", "a" * 20 + "/" + "b" * 15),
]:
    get(f"page, {title}", page(token=token))
    get(f"folder, {title}", page(f"/folder/{ROOT}", token=token))
print("== the request itself ==")
for title, method, body, headers in [
    ("POST on the page", "POST", b"", {}),
    ("PUT on the page", "PUT", b"x", {}),
    ("unlock: not a form", "POST", b"not a form", {"Content-Type": "application/json"}),
    ("unlock: body over 64 KiB", "POST", b"password=" + b"x" * 70000, {"Content-Type": "application/x-www-form-urlencoded"}),
    ("uploads: not json", "POST", b"not json", {"Content-Type": "application/json"}),
    ("uploads: json list", "POST", b"[1,2]", {"Content-Type": "application/json"}),
]:
    path = page("/unlock" if title.startswith("unlock") else "/uploads" if title.startswith("uploads") else "")
    status, text, h = request(method, path, body, headers)
    show(title, status, text, h)
print("== the folder of the address ==")
for title, folder in [
    ("the outside folder", OUTSIDE),
    ("the hidden folder", HIDDEN),
    ("the parent of the root", PARENT),
    ("folder 0", 0),
    ("folder -1", -1),
    ("folder beyond int4", 99999999999),
    ("folder 'abc'", "abc"),
    ("folder '1 or 1=1'", "1 or 1=1"),
]:
    get(title, page(f"/folder/{folder}"))
# (A NUL byte in the path is no attack of ours: any address that no route matches goes to
# ``ir.http._serve_fallback``, which looks it up as the URL of an attachment, and the database
# refuses the NUL there: a 500 of the core for every unmatched path.)
get("the root", page(f"/folder/{ROOT}"))
print("== the page of the root says nothing of what lies above it ==")
status, text = get("root page", page())
if "SECRET" in text or f"/folder/{PARENT}" in text:
    problems.append(("root page names the parent", ["LEAK(parent)"]))
print("== the text of the search ==")
for title, search in [
    ("a name from outside", "SECRET-OUTSIDE"),
    ("a name from a hidden folder", "SECRET-HIDDEN"),
    ("the parent's name", "SECRET-PARENT"),
    ("a percent sign", "%"),
    ("an underscore", "_"),
    ("a backslash", "\\"),
    ("sql", "' OR 1=1 --"),
    ("sql, a semicolon", "x'; select pg_sleep(5); --"),
    ("500 characters", "x" * 500),
    ("a null byte", "a\x00b"),
    ("unicode", "‮\u0000�"),
]:
    get(f"search {title}", page(f"/folder/{ROOT}", search=search), echoed=search)
get("search twice", page(f"/folder/{ROOT}") + "?search=a&search=b")
get("search as a list", page(f"/folder/{ROOT}") + "?search[]=a")
print("== sorting and pages ==")
for title, query in [
    ("sortby injection", {"sortby": "name; select pg_sleep(5)"}),
    ("sortby a field", {"sortby": "create_uid"}),
    ("sortby an order", {"sortby": "id desc"}),
    ("sortby size", {"sortby": "size"}),
    ("sortby date", {"sortby": "date"}),
    ("sortby empty", {"sortby": ""}),
]:
    get(title, page(f"/folder/{ROOT}", **query))
for number in ["0", "-1", "99999999999", "abc", "1e9", "2147483647", "2147483648"]:
    get(f"page {number}", page(f"/folder/{ROOT}/page/{number}"))
print("== the cookie with the key ==")
for title, cookie in [
    ("empty key", ""),
    ("garbage key", "garbage"),
    ("a long key", "x" * 600),
    ("key with quotes", '"a";b=c'),
]:
    headers = {"Cookie": f"int_filemanager_share_key_{PASSWORD_TOKEN}={cookie}"}
    status, text = get(f"password share, {title}", page(token=PASSWORD_TOKEN), headers)
    if "type=\"password\"" not in text:
        problems.append((f"password share opens with {title}", ["LEAK(page without the key)"]))
    get(f"password share folder, {title}", page(f"/folder/{ROOT}", token=PASSWORD_TOKEN), headers)
    get(f"password share file, {title}", page(f"/content/{INSIDE_DOC}", token=PASSWORD_TOKEN), headers)
status, text = get("password share, no cookie", page(token=PASSWORD_TOKEN))
if "Gastbereich" in text:
    problems.append(("password page names the share", ["LEAK(name)"]))
print("== the wrong passwords are an answer ==")
status, body, headers = request(
    "POST", page("/unlock", token=PASSWORD_TOKEN), b"password=wrong", {"Content-Type": "application/x-www-form-urlencoded"}
)
show("unlock, a wrong password", status, body, headers)
print("== the file routes ==")
for title, path in [
    ("content of an outside document", page(f"/content/{SEED['outside_doc']}")),
    ("download of an outside document (GET)", page(f"/content/{SEED['outside_doc']}", download=1)),
    ("thumbnail of an outside document", page(f"/thumbnail/{SEED['outside_doc']}")),
    ("image of an outside document", page(f"/image/{SEED['outside_doc']}/512")),
    ("image, a size that does not exist", page(f"/image/{INSIDE_DOC}/9999")),
    ("document id beyond int4", page("/content/99999999999")),
    ("document id 0", page("/content/0")),
    ("document id negative", page("/content/-1")),
    ("the old gateway", page("/rpc")),
    ("a key in the address is no key", page(f"/content/{INSIDE_DOC}", token=PASSWORD_TOKEN, k="x")),
    ("web content route (no access token)", f"/web/content/int.filemanager.document/{INSIDE_DOC}/content"),
    ("web image route (no access token)", f"/web/image/int.filemanager.document/{INSIDE_DOC}/thumbnail/256x256"),
]:
    status, body, headers = request("GET", path)
    show(title, status, body if status != 200 or b"<html" in body[:200].lower() else f"[{len(body)} bytes]", headers)
status, body, headers = request(
    "POST",
    "/web/dataset/call_kw/int.filemanager.document/web_search_read",
    json.dumps({"jsonrpc": "2.0", "method": "call", "params": {"model": "int.filemanager.document", "method": "web_search_read", "args": [[]], "kwargs": {"specification": {"name": {}}}}}).encode(),
    {"Content-Type": "application/json"},
)
# Odoo's own answer to a call without a session: an error, with no result
print(f"{'call_kw as a guest (POST)':<64} -> {status} {body[:90]!r}")
if b'"result"' in body:
    problems.append(("call_kw as a guest (POST)", ["LEAK(result)"]))
# the core's routes for a guest without a login: they must answer as for a record that is not there
missing = request("GET", "/web/image/int.filemanager.document/999999/thumbnail/256x256")
existing = request("GET", f"/web/image/int.filemanager.document/{INSIDE_DOC}/thumbnail/256x256")
same = missing[0] == existing[0] and missing[1] == existing[1]
print(f"{'web image of a file with a picture, as for a missing record':<64} -> {existing[0]} same as for a missing record: {same}")
if not same:
    problems.append(("web image route answers differently for a record that exists", ["LEAK(picture)"]))
status, body, headers = request("POST", page(f"/download/{INSIDE_DOC}"), b"", {})
show("POST download on a folder share of a document in scope", status, f"[{len(body)} bytes]" if status == 200 else body, headers)
print("== the end ==")
if problems:
    print(f"{len(problems)} ATTACK(S) GOT THROUGH:")
    for title, flags in problems:
        print("  ", title, flags)
    sys.exit(1)
print("no attack got through")
