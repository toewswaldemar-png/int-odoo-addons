import hashlib, os, random
from odoo.addons.fm_proto import blobstore
revs = env["fm.revision"].search([("origin", "=", "import")])
sample = random.Random(7).sample(revs.ids, 300)
bad = 0
def path_of(node):
    parts = []
    n = node
    while n.parent_id:
        parts.append(n.name); n = n.parent_id
    return "/".join(reversed(parts))
for r in env["fm.revision"].browse(sample):
    sha = r.blob_id.sha256
    h = hashlib.sha256()
    with open(blobstore.blob_path(env, sha), "rb") as f:
        while b := f.read(1 << 20): h.update(b)
    h2 = hashlib.sha256()
    with open(os.path.join("/mnt/live-ro", path_of(r.node_id)), "rb") as f:
        while b := f.read(1 << 20): h2.update(b)
    if not (h.hexdigest() == sha == h2.hexdigest()):
        bad += 1
print(">> Stichprobe 300 Dateien: Blob-Inhalt = Blob-Name = Quelle:", 300 - bad, "ok,", bad, "abweichend")
