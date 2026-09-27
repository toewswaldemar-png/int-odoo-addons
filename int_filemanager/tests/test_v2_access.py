"""ORM-level rights tests for the v2 side models (Konzept 12/16, Pruefbericht
A1): `ir.rule` is evaluated per model and only inherits from `_inherits`
parents, so `int_filemanager.revision`/`.blob`/`.upload`/`.operation`/`.scope`
need their OWN rules - inheriting the node's rule was the wrong assumption
the review disproved (Nr. 94, A1).

Written before the models exist (Kern 11, Schritt 3): expected to fail on
`self.env["int_filemanager.node"]` etc. until the data model lands, then
turn green one model at a time. Not a placeholder to relax later - this file
IS the rights specification for those models.

Konzept 12 access table this file encodes:
    node               - own rule via scope_id.{read,write}_group_ids
    revision            - own rule via node_id.scope_id.{read,write}_group_ids
    blob                - no user ACL at all; only reachable via vetted methods
    upload, operation   - own records only (create_uid = user)
    scope               - read for every internal user; write needs "manage"
"""

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestV2SideModelAccess(TransactionCase):
    def setUp(self):
        super().setUp()
        self.base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self._user_seq = 0

    def _make_group(self, name):
        return self.env["res.groups"].sudo().create({"name": name})

    def _make_user(self, groups=()):
        self._user_seq += 1
        group_ids = [g.id for g in groups] + [self.base_group.id]
        return (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": f"V2AccessUser{self._user_seq}",
                    "login": f"v2_access_user_{self._user_seq}",
                    "group_ids": [(6, 0, group_ids)],
                }
            )
        )

    def _make_scope(self, name, read_group=None, write_group=None):
        vals = {"name": name}
        if read_group:
            vals["read_group_ids"] = [(4, read_group.id)]
        if write_group:
            vals["write_group_ids"] = [(4, write_group.id)]
        return self.env["int_filemanager.scope"].sudo().create(vals)

    def _make_node(self, name, scope, is_dir=False, parent=None):
        return (
            self.env["int_filemanager.node"]
            .sudo()
            .create(
                {
                    "name": name,
                    "scope_id": scope.id,
                    "is_dir": is_dir,
                    "parent_id": parent.id if parent else False,
                }
            )
        )

    def _make_blob(self, sha256="0" * 64, size=0.0):
        return (
            self.env["int_filemanager.blob"]
            .sudo()
            .create({"sha256": sha256, "size": size})
        )

    def _make_revision(self, node, blob, revision_no=1):
        return (
            self.env["int_filemanager.revision"]
            .sudo()
            .create(
                {
                    "node_id": node.id,
                    "blob_id": blob.id,
                    "revision_no": revision_no,
                    "origin": "upload",
                }
            )
        )

    # -- node / revision: access follows the node's scope -----------------

    def test_node_denied_without_scope_group(self):
        scope = self._make_scope(
            "Scope A", read_group=self._make_group("Scope A Reader")
        )
        node = self._make_node("secret.txt", scope)
        outsider = self._make_user()
        found = (
            self.env["int_filemanager.node"]
            .with_user(outsider)
            .search([("id", "=", node.id)])
        )
        self.assertFalse(found)

    def test_node_visible_with_scope_read_group(self):
        reader_group = self._make_group("Scope B Reader")
        scope = self._make_scope("Scope B", read_group=reader_group)
        node = self._make_node("public.txt", scope)
        reader = self._make_user([reader_group])
        found = (
            self.env["int_filemanager.node"]
            .with_user(reader)
            .search([("id", "=", node.id)])
        )
        self.assertTrue(found)

    def test_revision_has_own_rule_not_inherited_from_node(self):
        """A1: `ir.rule` does not cascade from node to revision via a normal
        Many2one - without an explicit rule on `int_filemanager.revision`,
        a plain read ACL would expose every revision to every user."""
        reader_group = self._make_group("Scope C Reader")
        scope = self._make_scope("Scope C", read_group=reader_group)
        node = self._make_node("versioned.txt", scope)
        blob = self._make_blob(sha256="1" * 64)
        revision = self._make_revision(node, blob)

        outsider = self._make_user()  # not in reader_group
        found = (
            self.env["int_filemanager.revision"]
            .with_user(outsider)
            .search([("id", "=", revision.id)])
        )
        self.assertFalse(
            found, "revision must not be readable without the node's scope group"
        )

        reader = self._make_user([reader_group])
        found = (
            self.env["int_filemanager.revision"]
            .with_user(reader)
            .search([("id", "=", revision.id)])
        )
        self.assertTrue(found)

    def test_revision_write_requires_scope_write_group(self):
        write_group = self._make_group("Scope D Writer")
        scope = self._make_scope(
            "Scope D", read_group=write_group, write_group=write_group
        )
        node = self._make_node("writable.txt", scope)
        blob = self._make_blob(sha256="2" * 64)
        revision = self._make_revision(node, blob)

        reader_only = self._make_user()
        with self.assertRaises(AccessError):
            self.env["int_filemanager.revision"].with_user(reader_only).browse(
                revision.id
            ).write({"origin": "edit"})

    # -- blob: no user ACL at all, whatever the scope ----------------------

    def test_blob_not_readable_by_any_non_admin_user(self):
        """A1: blobs carry no scope of their own; a scoped rule would still
        leak content-addressed hashes across scopes, so the model gets NO
        user-facing ACL - access only via methods that already checked the
        node under the caller's identity."""
        blob = self._make_blob(sha256="3" * 64)
        member = self._make_user()
        with self.assertRaises(AccessError):
            self.env["int_filemanager.blob"].with_user(member).browse(blob.id).read(
                ["sha256"]
            )

    def test_blob_search_denied_for_non_admin(self):
        """No group grants any access at all (Konzept 12), so search() itself must
        raise rather than come back with an empty, easy-to-miss result set."""
        self._make_blob(sha256="4" * 64)
        member = self._make_user()
        with self.assertRaises(AccessError):
            self.env["int_filemanager.blob"].with_user(member).search([])

    # -- upload / operation: own records only ------------------------------

    def test_upload_visible_only_to_its_owner(self):
        owner = self._make_user()
        other = self._make_user()
        # create_uid is set from the acting user at INSERT time and ignored by write()
        # afterwards, so ownership must be established via with_user(owner), not a
        # sudo().write({"create_uid": ...}) after the fact.
        operation = (
            self.env["int_filemanager.operation"]
            .with_user(owner)
            .create({"key": "op-upload-1"})
        )
        upload = (
            self.env["int_filemanager.upload"]
            .with_user(owner)
            .create({"operation_id": operation.id})
        )

        self.assertTrue(
            self.env["int_filemanager.upload"]
            .with_user(owner)
            .search([("id", "=", upload.id)])
        )
        self.assertFalse(
            self.env["int_filemanager.upload"]
            .with_user(other)
            .search([("id", "=", upload.id)])
        )

    def test_operation_visible_only_to_its_owner(self):
        owner = self._make_user()
        other = self._make_user()
        operation = (
            self.env["int_filemanager.operation"]
            .with_user(owner)
            .create({"key": "op-key-1"})
        )

        self.assertTrue(
            self.env["int_filemanager.operation"]
            .with_user(owner)
            .search([("id", "=", operation.id)])
        )
        self.assertFalse(
            self.env["int_filemanager.operation"]
            .with_user(other)
            .search([("id", "=", operation.id)])
        )

    # -- scope: read for every internal user, write needs "manage" --------

    def test_scope_readable_by_any_internal_user(self):
        scope = self._make_scope("Scope Everyone Reads")
        member = self._make_user()
        found = (
            self.env["int_filemanager.scope"]
            .with_user(member)
            .search([("id", "=", scope.id)])
        )
        self.assertTrue(found)

    def test_scope_write_denied_without_manage_group(self):
        scope = self._make_scope("Scope Needs Manage")
        member = self._make_user()
        with self.assertRaises(AccessError):
            self.env["int_filemanager.scope"].with_user(member).browse(scope.id).write(
                {"name": "Renamed"}
            )

    def test_scope_write_allowed_with_manage_group(self):
        manage_group = self._make_group("Scope Manager")
        scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {"name": "Scope Managed", "manage_group_ids": [(4, manage_group.id)]}
            )
        )
        manager = self._make_user([manage_group])
        self.env["int_filemanager.scope"].with_user(manager).browse(scope.id).write(
            {"name": "Renamed"}
        )
        self.assertEqual(scope.sudo().name, "Renamed")
