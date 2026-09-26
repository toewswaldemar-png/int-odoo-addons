import mimetypes
import os

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from . import blobstore

CHUNK_LIMIT = 32 * 1024 * 1024


class FmProto(http.Controller):

    @http.route("/fmp/upload/init", type="jsonrpc", auth="user")
    def upload_init(self, operation_key, name, size, parent_id=None):
        Up = request.env["fm.upload"]
        up = Up.search([("operation_key", "=", operation_key)], limit=1)
        if not up:
            up = Up.create({"operation_key": operation_key, "name": name, "size_expected": size,
                            "parent_id": parent_id or False})
        return {"received": up._received(), "state": up.state}

    @http.route("/fmp/upload/chunk", type="http", auth="user", methods=["PUT", "POST"], csrf=False,
                max_content_length=CHUNK_LIMIT)
    def upload_chunk(self, operation_key, offset, **kw):
        up = request.env["fm.upload"].search([("operation_key", "=", operation_key)], limit=1)
        if not up or up.state != "open":
            return request.make_json_response({"error": "unknown or finished upload"}, status=409)
        offset = int(offset)
        path = up._tmp_path()
        have = up._received()
        length = int(request.httprequest.headers.get("Content-Length", 0))
        if offset + length <= have:
            # Wiederholung eines schon geschriebenen Stuecks: nichts tun (idempotent)
            return request.make_json_response({"received": have, "skipped": True})
        if offset != have:
            return request.make_json_response({"error": "offset mismatch", "received": have}, status=409)
        # Odoo gibt den rohen Eingabestrom nicht heraus (HTTPREQUEST_ATTRIBUTES, http.py:1498ff; wsgi.input
        # wird aus environ gefiltert). get_data() liest den Body ganz in den RAM - begrenzt durch
        # max_content_length dieser Route (ein Stueck), deshalb Upload in Stuecken.
        data = request.httprequest.get_data()
        with open(path, "ab") as out:
            out.write(data)
        blobstore.fault("after_chunk")
        return request.make_json_response({"received": up._received()})

    @http.route("/fmp/upload/finish", type="jsonrpc", auth="user")
    def upload_finish(self, operation_key):
        up = request.env["fm.upload"].search([("operation_key", "=", operation_key)], limit=1)
        if not up:
            raise UserError("unknown upload")
        up.lock_for_update()
        if up.state == "done":
            return {"node_id": up.node_id.id, "revision_id": up.revision_id.id, "sha256": up.node_id.sha256,
                    "repeated": True}
        tmp = up._tmp_path()
        if up._received() != int(up.size_expected):
            raise UserError("upload incomplete: %s of %s" % (up._received(), int(up.size_expected)))
        # Temp erst NACH dem Commit loeschen: wiederholt Odoo den Request (retrying), findet der zweite
        # Versuch die Temp-Datei noch vor (Konzept 4.4).
        sha, size, deduped = blobstore.adopt_temp(request.env, tmp, keep_tmp=True)
        request.env.cr.postcommit.add(lambda: os.path.exists(tmp) and os.unlink(tmp))
        blob = request.env["fm.blob"]._get_or_create(sha, size)
        Node = request.env["fm.node"]
        node = Node.search([("parent_id", "=", up.parent_id.id), ("name", "=", up.name)], limit=1)
        if not node:
            node = Node.create({"name": up.name, "parent_id": up.parent_id.id or False})
        rev = node._add_revision(blob, "upload", operation_key)
        up.write({"state": "done", "node_id": node.id, "revision_id": rev.id})
        blobstore.fault("before_commit")
        return {"node_id": node.id, "revision_id": rev.id, "sha256": sha, "deduped": deduped, "repeated": False}

    @http.route("/fmp/download/<int:node_id>", type="http", auth="user")
    def download(self, node_id, **kw):
        node = request.env["fm.node"].browse(node_id).exists()
        if not node:
            raise request.not_found()
        node.check_access("read")
        sha = node.sudo().current_revision_id.blob_id.sha256
        path = blobstore.blob_path(request.env, sha)
        stream = http.Stream(
            type="path", path=path, mimetype=mimetypes.guess_type(node.name)[0] or "application/octet-stream",
            download_name=node.name, etag=sha, size=os.path.getsize(path),
            last_modified=os.path.getmtime(path), immutable=False,
        )
        return stream.get_response(as_attachment=bool(kw.get("download")))


class FmProtoDiag(http.Controller):
    """Diagnose: Speicherverhalten beim Lesen grosser Request-Koerper."""

    @http.route("/fmp/diag/getdata", type="http", auth="user", methods=["PUT"], csrf=False, max_content_length=CHUNK_LIMIT)
    def diag_getdata(self, **kw):
        n = len(request.httprequest.get_data())
        return request.make_json_response({"n": n, "rss_kb": _rss()})

    @http.route("/fmp/diag/append", type="http", auth="user", methods=["PUT"], csrf=False, max_content_length=CHUNK_LIMIT)
    def diag_append(self, **kw):
        data = request.httprequest.get_data()
        with open(os.path.join(blobstore.tmp_dir(request.env), "diag_%d.part" % os.getpid()), "ab") as out:
            out.write(data)
        return request.make_json_response({"rss": _rss()})

    @http.route("/fmp/diag/rss", type="http", auth="user")
    def diag_rss(self, **kw):
        import gc
        gc.collect()
        return request.make_json_response({"rss_kb": _rss(), "pid": os.getpid()})


def _rss():
    out = {}
    with open("/proc/self/status") as f:
        for line in f:
            if line.split(":")[0] in ("VmRSS", "RssAnon", "RssFile", "RssShmem"):
                out[line.split(":")[0]] = int(line.split()[1])
    return out


class FmProtoTrace(http.Controller):
    @http.route("/fmp/diag/trace", type="http", auth="user")
    def diag_trace(self, **kw):
        import gc, tracemalloc
        if not tracemalloc.is_tracing():
            tracemalloc.start(15)
            return request.make_json_response({"started": os.getpid()})
        gc.collect()
        snap = tracemalloc.take_snapshot()
        stats = snap.statistics("traceback")[:3]
        res = []
        for st in stats:
            res.append({"size_mb": round(st.size / 1048576, 1), "count": st.count,
                        "tb": [str(fr) for fr in st.traceback.format()[-12:]]})
        # wer referenziert grosse bytes-Objekte?
        big = [o for o in gc.get_objects() if isinstance(o, (bytes, bytearray)) and len(o) > 1000000]
        owners = []
        for o in big[:3]:
            owners.append([type(r).__name__ + ":" + (str(list(r.keys())[:6]) if isinstance(r, dict) else repr(r)[:120]) for r in gc.get_referrers(o)[:4]])
        return request.make_json_response({"pid": os.getpid(), "top": res, "big_bytes": len(big), "owners": owners})
