"""Fixture bootstrap for race_scenarios.py (Konzept 16, Pruefbericht A3).

Not a test module, not imported by anything - meant to be piped into
`odoo shell -d <db>` against the disposable fmtest database race_scenarios.py
targets (see README "Prerequisites"), once with `int_filemanager.watcher_enabled`
already flipped to false (Konzept 19.5, N5 - a shell session against the watcher
DB starts a second watcher otherwise).

Creates one scope, one write group, one writer user + API key, and one
dedicated node per A3 scenario (never shared - see load_fixtures() in
race_scenarios.py for why), then prints the resulting ids as JSON on stdout
so `--fixtures-json` can load them straight through.

Usage:
    cat bootstrap_fixtures.py | odoo shell -d fmtest_pg --no-http > fixtures.json
"""

# ruff: noqa: F821 - env/model_names are injected by `odoo shell` at exec time,
# not imported; nothing here is meant to run outside that REPL.

import base64
import datetime
import json

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
            "group_ids": [(6, 0, [base_group.id, write_group.id])],
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
lock_node_id, _ = _seed_file("race-lock-seed.txt")

env.cr.commit()  # pylint: disable=unknown-option-value,invalid-commit

fixtures = {
    "api_key": api_key,
    "parent_id": parent.id,
    "revision_node_id": revision_node_id,
    "revision_base_revision_id": revision_base_revision_id,
    "rename_node_a_id": rename_node_a_id,
    "rename_node_b_id": rename_node_b_id,
    "move_node_id": move_node_id,
    "move_new_parent_id": move_target_folder.id,
    "lock_node_id": lock_node_id,
}
# pylint: disable-next=print-used
print(json.dumps(fixtures))
