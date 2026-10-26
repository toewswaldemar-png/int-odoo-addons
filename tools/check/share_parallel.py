"""Real parallel requests against a running instance, and timings.

    python3 share_parallel.py http://host:8069 seed.json

The test suite cannot do this (``HttpCase`` has one cursor and runs the requests one after the
other). Here the instance has several worker processes, so two requests can meet in the database
and Odoo has to run one of them again (serialization failure). Prints one RESULT line per case;
the shell script that started the instance then reads the counters from the database.
"""

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
form = {"Content-Type": "application/x-www-form-urlencoded"}
body = b"password=wrong"
results = parallel(40, lambda n: request("POST", path("password", "/unlock"), body, form))
result("password40_wrong", statuses=statuses(results), expected="4x403 and the rest 429 (5 tries per address, one was used by share_attacks.py; they are taken under a lock)")
status = request("POST", path("password", "/unlock"), b"password=a+long+password", form)[0]
result("password_right_after", status=status, expected="429 (the address is blocked)")

print("== timings: the pages on a share of 300 folders and 21000 files ==")
big = SEED["shares"]["big"]["token"]
first = re.search(r"/folder/(\d+)", request("GET", path("big"))[1].decode())
inner = first.group(1) if first else None
calls = {
    "root page (300 folders, first page)": lambda: request("GET", path("big")),
    "root page, sorted by size": lambda: request("GET", path("big", "?sortby=size")),
    "root page 10 (the last)": lambda: request("GET", path("big", f"/folder/{SEED['archive']}/page/10")),
    "a folder with 70 files": lambda: request("GET", path("big", f"/folder/{inner}")),
    "search 'Dokument 017' (below the root)": lambda: request("GET", path("big", "?search=Dokument+017")),
    "search that finds nothing": lambda: request("GET", path("big", "?search=nothing+like+it")),
}
for name, call in calls.items():
    times, codes = [], set()
    for __ in range(5):
        status, data, seconds, __h = call()
        times.append(seconds)
        codes.add(status)
    result("time", call=name, status=sorted(codes), median_ms=round(statistics.median(times) * 1000), max_ms=round(max(times) * 1000))

print("== the size of a page ==")
status, page_text, __s, __h = request("GET", path("big"))
result("page_size", status=status, kb=round(len(page_text) / 1024))
