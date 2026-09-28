"""Fixture bootstrap for race_scenarios.py (Konzept 16, Pruefbericht A3).

Not a test module, not imported by anything - meant to be piped into
`odoo shell -d <db>` against the disposable fmtest database race_scenarios.py
targets (see README "Prerequisites"), once with `int_filemanager.watcher_enabled`
already flipped to false (Konzept 19.5, N5 - a shell session against the watcher
DB starts a second watcher otherwise).

Creates one scope, one write group, one writer user + API key, one
dedicated node per A3 scenario (never shared - see load_fixtures() in
race_scenarios.py for why) and one stale blob for A4, then prints the resulting ids
as JSON on stdout so `--fixtures-json` can load them straight through.

Usage:
    cat bootstrap_fixtures.py | odoo shell -d fmtest_pg --no-http > fixtures.json
"""

# ruff: noqa: F821 - env/model_names are injected by `odoo shell` at exec time,
# not imported; nothing here is meant to run outside that REPL.

import base64
import datetime
import importlib
import io
import json

# A script piped into `odoo shell` is no module of the addon, so a relative import is
# impossible there - and the absolute form is what pylint-odoo flags.
blobstore = importlib.import_module("odoo.addons.int_filemanager.blobstore")

write_group = env["res.groups"].sudo().create({"name": "Race driver writer"})
scope = (
    env["int_filemanager.scope"]
    .sudo()
    .create(
        {
            "name": "Race driver scope",
            "read_group_ids": [(4, write_group.id)],
            "write_group_ids": [(4, write_group.id)],
        }
    )
)
base_group = env.ref("int_filemanager.group_filemanager_user")
writer = (
    env["res.users"]
    .sudo()
    .create(
        {
            "name": "Race driver writer",
            "login": "race_driver_writer",
            "password": "race_driver_pw_1",
            # base.group_user: a real file manager user is an internal user; without it
            # the web client sends the login to the portal (/my).
            "group_ids": [
                (6, 0, [env.ref("base.group_user").id, base_group.id, write_group.id])
            ],
        }
    )
)
api_key = (
    env["res.users.apikeys"]
    .with_user(writer)
    ._generate(
        scope="rpc",
        name="race driver",
        expiration_date=datetime.datetime.now() + datetime.timedelta(hours=6),
    )
)

parent = (
    env["int_filemanager.node"]
    .sudo()
    .create({"name": "race-root", "scope_id": scope.id, "is_dir": True})
)
move_target_folder = (
    env["int_filemanager.node"]
    .sudo()
    .create({"name": "race-move-target", "scope_id": scope.id, "is_dir": True})
)

Node = env["int_filemanager.node"].with_user(writer)


def _seed_file(name, content=b"seed"):
    """Real create_file() call (not a raw ORM create) so the resulting node has
    an actual blob on disk under this instance's own filestore, the same way
    a real client's first write would - the race scenarios then act on real
    content, not a hand-assembled row."""
    result = Node.create_file(
        parent.id, name, base64.b64encode(content).decode(), f"bootstrap-{name}"
    )
    return result["node_id"], result["revision_id"]


revision_node_id, revision_base_revision_id = _seed_file("race-revision-seed.txt")
rename_node_a_id, _ = _seed_file("race-rename-a-seed.txt")
rename_node_b_id, _ = _seed_file("race-rename-b-seed.txt")
move_node_id, _ = _seed_file("race-move-seed.txt")
lock_node_id, lock_base_revision_id = _seed_file("race-lock-seed.txt")

# A4: a blob that is past the cleanup job's grace period and referenced by no revision
# (exactly what the job deletes), with its file present on disk. The scenario then has a
# writer reuse this very content while the job runs.
a4_content = b"a4-stale-blob-content"
a4_tmp = blobstore.write_stream_to_temp(env, io.BytesIO(a4_content), "bootstrap_a4")
a4_sha256, a4_size = blobstore.hash_file(a4_tmp)
blobstore.adopt_hashed(env, a4_tmp, a4_sha256)
env["int_filemanager.blob"].sudo().create(
    {
        "sha256": a4_sha256,
        "size": a4_size,
        "last_used": datetime.datetime.now() - datetime.timedelta(days=2),
    }
)

env.cr.commit()  # pylint: disable=unknown-option-value,invalid-commit

fixtures = {
    "api_key": api_key,
    "login": "race_driver_writer",
    "password": "race_driver_pw_1",
    "parent_id": parent.id,
    "revision_node_id": revision_node_id,
    "revision_base_revision_id": revision_base_revision_id,
    "rename_node_a_id": rename_node_a_id,
    "rename_node_b_id": rename_node_b_id,
    "move_node_id": move_node_id,
    "move_new_parent_id": move_target_folder.id,
    "lock_node_id": lock_node_id,
    "lock_base_revision_id": lock_base_revision_id,
    "a4_content_b64": base64.b64encode(a4_content).decode(),
    "a4_sha256": a4_sha256,
}
# pylint: disable-next=print-used
print(json.dumps(fixtures))
