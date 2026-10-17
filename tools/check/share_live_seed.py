"""Seed for tools/check/share_live.sh: runs in ``odoo shell`` of the throw-away instance.

Makes the folders, files and shares that the attacks and the parallel runs work on, and writes
their tokens and ids as JSON to /out/seed.json. Names that start with SECRET- are what a guest
must never see: the attack script looks for them in every answer.
"""

import base64
import io
import json

from PIL import Image

env = env  # noqa: F821, PLW0127 - injected by odoo shell
context = {"tracking_disable": True, "mail_create_nosubscribe": True, "mail_create_nolog": True}
Folder = env["int.filemanager.folder"].sudo().with_context(**context)
Document = env["int.filemanager.document"].sudo().with_context(**context)
Tag = env["int.filemanager.tag"].sudo()
Share = env["int.filemanager.share"].sudo()
env["ir.config_parameter"].sudo().set_param("int_filemanager.share_brake", "0")


def png(color):
    stream = io.BytesIO()
    Image.new("RGB", (60, 40), color).save(stream, "PNG")
    return stream.getvalue()


def pdf(text):
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n% " + text.encode() + b"\n" + b"x" * 200


def document(folder, name, data, tags=()):
    created = Document._create_from_stream(io.BytesIO(data), name, folder)
    if tags:
        created.tag_ids = [(6, 0, [tag.id for tag in tags])]
    return created


seed = {}
public_tag = Tag.create({"name": "Public-Tag"})
secret_tag = Tag.create({"name": "SECRET-TAG"})

# the shared folder lies below a folder that the guests must not learn about
parent = Folder.create({"name": "SECRET-PARENT", "access_mode": "restricted"})
root = Folder.create({"name": "Gastbereich", "parent_id": parent.id, "access_mode": "open"})
contracts = Folder.create({"name": "Vertraege", "parent_id": root.id})
hidden = Folder.create({"name": "SECRET-HIDDEN", "parent_id": root.id, "access_mode": "restricted"})
outside = Folder.create({"name": "SECRET-OUTSIDE", "access_mode": "open"})
document(root, "Notiz.txt", b"plain note", [public_tag])
document(contracts, "Vertrag.pdf", pdf("contract"), [public_tag])
document(contracts, "Foto.png", png("red"))
document(hidden, "SECRET-HIDDEN-doc.pdf", pdf("hidden"), [secret_tag])
outside_doc = document(outside, "SECRET-OUTSIDE-doc.pdf", pdf("outside"), [secret_tag])
seed.update(parent=parent.id, root=root.id, hidden=hidden.id, outside=outside.id, outside_doc=outside_doc.id)

mailbox = Folder.create({"name": "Briefkasten", "access_mode": "open"})
single = document(root, "Einzeln.pdf", pdf("single"))
visited = document(root, "Besucht.pdf", pdf("visited"))
# a picture of the first page, so that the core's own routes have something to give away
single.write({"thumbnail": base64.b64encode(png("blue")), "thumbnail_state": "done"})

shares = {
    "view": Share.create({"name": "view", "folder_id": root.id}),
    "upload": Share.create(
        {
            "name": "upload",
            "folder_id": mailbox.id,
            "can_upload": True,
            "upload_max_file_mb": 1,
            "upload_max_total_mb": 3,
            "upload_max_files": 3,
        }
    ),
    "file": Share.create({"name": "file", "document_id": single.id, "max_downloads": 5}),
    "visits": Share.create({"name": "visits", "document_id": visited.id}),
    "password": Share.create({"name": "password", "folder_id": root.id}),
}
shares["password"].password = "a long password"
seed["shares"] = {name: {"id": share.id, "token": share.token} for name, share in shares.items()}
seed["documents"] = {"single": single.id, "visited": visited.id}

# a large tree for the timings: 300 folders with 70 files each (rows only, no blobs)
archive = Folder.create({"name": "Archiv", "access_mode": "open"})
subfolders = Folder.create([{"name": f"Ordner {n:03d}", "parent_id": archive.id} for n in range(300)])
env.cr.commit()
rows = [
    {
        "name": f"Dokument {folder.name[-3:]}-{k:03d}.pdf",
        "folder_id": folder.id,
        "checksum": "0" * 64,
        "size": 1000 + k,
        "mimetype": "application/pdf",
    }
    for folder in subfolders
    for k in range(70)
]
for start in range(0, len(rows), 2000):
    Document.create(rows[start : start + 2000])
    env.cr.commit()
big = Share.create({"name": "big", "folder_id": archive.id})
seed["shares"]["big"] = {"id": big.id, "token": big.token}
env.cr.commit()
with open("/out/seed.json", "w") as out:
    json.dump(seed, out)
print("SEED ok", len(rows), "rows")
