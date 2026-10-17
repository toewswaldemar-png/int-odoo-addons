"""Real parallel requests against a running instance, and timings.

    python3 share_parallel.py http://host:8069 seed.json

The test suite cannot do this (``HttpCase`` has one cursor and runs the requests one after the
other). Here the instance has several worker processes, so two requests can meet in the database
and Odoo has to run one of them again (serialization failure). Prints one RESULT line per case;
the shell script that started the instance then reads the counters from the database.
"""

import gzip
import http.client
import json
import re
import statistics
import sys
import threading
import time
import urllib.parse
import uuid

BASE, SEED = sys.argv[1], json.load(open(sys.argv[2]))
HOST = urllib.parse.urlparse(BASE).netloc
SHARES = SEED["shares"]
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n" + b"x" * 100


def request(method, path, body=None, headers=None):
    connection = http.client.HTTPConnection(HOST, timeout=120)
    try:
        started = time.time()
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        data = response.read()
        return response.status, data, time.time() - started, dict(response.getheaders())
    finally:
        connection.close()


def parallel(count, work):
    """Run ``work(n)`` in ``count`` threads that start at the same moment; the results in order."""
    barrier = threading.Barrier(count)
    results = [None] * count

    def run(n):
        barrier.wait()
        try:
            results[n] = work(n)
        except Exception as error:  # a broken connection is a result too
            results[n] = (f"EXC {type(error).__name__}", b"", 0, {})

    threads = [threading.Thread(target=run, args=(n,)) for n in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def statuses(results):
    counts = {}
    for status, *_ in results:
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: str(item[0])))


def multipart(name, data):
    boundary = "----s10" + uuid.uuid4().hex
    head = f'--{boundary}\r\nContent-Disposition: form-data; name="ufile"; filename="{name}"\r\n'
    head += "Content-Type: application/octet-stream\r\n\r\n"
    body = head.encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def path(name, tail=""):
    return f"/int_filemanager/share/{SHARES[name]['token']}{tail}"


def result(name, **values):
    print("RESULT", name, json.dumps(values, sort_keys=True))


print("== uploads at the limit: 8 files at once into a share that takes 3 ==")


def upload(n):
    body, headers = multipart(f"p{n}.txt", f"content {n} {uuid.uuid4().hex}".encode())
    return request("POST", path("upload", "/upload"), body, headers)


results = parallel(8, upload)
result("upload8_into_3", statuses=statuses(results), expected="3x200 and 5x413")

print("== downloads at the limit: 12 at once from a file that may be downloaded 5 times ==")
document = SEED["documents"]["single"]
results = parallel(12, lambda n: request("POST", path("file", f"/download/{document}"), b"", {}))
result("download12_of_5", statuses=statuses(results), expected="5x200 and 7x410")

print("== visits: 40 at once on the page of one share (the hot row) ==")
results = parallel(40, lambda n: request("GET", path("visits")))
result("visit40", statuses=statuses(results), max_seconds=round(max(r[2] for r in results), 2), expected="40x200, view_count 1")

print("== wrong passwords: 40 at once (limit 5 per address, 30 per share, in 10 minutes) ==")
body = json.dumps({"password": "wrong"}).encode()
results = parallel(40, lambda n: request("POST", path("password", "/unlock"), body, {"Content-Type": "application/json"}))
result("password40_wrong", statuses=statuses(results), expected="exactly 5x403 (the tries are taken under a lock), the rest 429")
status = request("POST", path("password", "/unlock"), json.dumps({"password": "a long password"}).encode(), {"Content-Type": "application/json"})[0]
result("password_right_after", status=status, expected="429 (the address is blocked)")

print("== timings: the page and the gateway on a share of 300 folders and 21000 files ==")


def gateway(payload):
    return request("POST", path("big", "/rpc"), json.dumps(payload).encode(), {"Content-Type": "application/json"})


calls = {
    "page": lambda: request("GET", path("big")),
    "web_search_read (80 rows)": lambda: gateway(
        {"model": "int.filemanager.document", "method": "web_search_read", "args": [],
         "kwargs": {"domain": [], "specification": {"name": {}, "size": {}, "mimetype": {}, "write_date": {}, "folder_id": {"fields": {"display_name": {}}}}, "limit": 80, "order": "name asc"}}),
    "web_search_read, name ilike 'Dokument 017'": lambda: gateway(
        {"model": "int.filemanager.document", "method": "web_search_read", "args": [],
         "kwargs": {"domain": [["name", "ilike", "Dokument 017"]], "specification": {"name": {}}, "limit": 80}}),
    "search_panel_select_range (300 folders)": lambda: gateway(
        {"model": "int.filemanager.document", "method": "search_panel_select_range", "args": ["folder_id"],
         "kwargs": {"category_domain": [], "filter_domain": [], "enable_counters": False, "expand": True,
                    "hierarchize": True, "limit": 0, "search_domain": [], "comodel_domain": []}}),
    "web_read_group by folder (counts)": lambda: gateway(
        {"model": "int.filemanager.document", "method": "web_read_group", "args": [],
         "kwargs": {"domain": [], "groupby": ["folder_id"], "aggregates": ["__count"]}}),
}
for name, call in calls.items():
    times, codes = [], set()
    for __ in range(5):
        status, data, seconds, __h = call()
        times.append(seconds)
        codes.add(status)
    result("time", call=name, status=sorted(codes), median_ms=round(statistics.median(times) * 1000), max_ms=round(max(times) * 1000))

print("== the bundle of the guest page ==")
status, page, __s, __h = request("GET", path("view"))
text = page.decode()
total_raw = total_gz = 0
for url in re.findall(r'(?:src|href)="(/web/assets/[^"]+)"', text):
    status, data, __s, headers = request("GET", url, None, {"Accept-Encoding": "gzip"})
    raw = len(gzip.decompress(data)) if headers.get("Content-Encoding") == "gzip" else len(data)
    total_raw += raw
    total_gz += len(data)
    result("asset", url=url.split("/")[-1], status=status, raw_kb=round(raw / 1024), sent_kb=round(len(data) / 1024))
result("bundle_total", raw_kb=round(total_raw / 1024), sent_kb=round(total_gz / 1024))
