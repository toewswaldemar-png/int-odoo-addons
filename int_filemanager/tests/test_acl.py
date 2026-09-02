import os
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAclRules(TransactionCase):
    """Phase 2: generierte Read/Write/Unlink-Regeln aus acl_rules.py + der
    zentrale Authorization-Service in authz.py."""

    def setUp(self):
        super().setUp()
        self.Model = self.env["int_filemanager.file"].sudo()
        self.ProtectedFolder = self.env["int_filemanager.protected_folder"].sudo()
        self._user_seq = 0

    def _make_group(self, name):
        return self.env["res.groups"].sudo().create({"name": name})

    def _make_user(self, groups):
        self._user_seq += 1
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        group_ids = [g.id for g in groups] + [base_group.id]
        return (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "TestUser%d" % self._user_seq,
                    "login": "acl_test_user_%d" % self._user_seq,
                    "group_ids": [(6, 0, group_ids)],
                }
            )
        )

    def _make_file(self, path, is_dir=False):
        parent = os.path.dirname(path)
        return self.Model.create(
            {
                "name": os.path.basename(path),
                "path": path,
                "folder_path": parent or False,
                "is_dir": is_dir,
            }
        )

    # ------------------------------------------------------------------

    def test_unprotected_path_open_to_base_group(self):
        self._make_file("Offen/a.txt")
        member = self._make_user([])
        rec = self.env["int_filemanager.file"].with_user(member).search([("path", "=", "Offen/a.txt")])
        self.assertTrue(rec)

    def test_protected_path_denied_without_group(self):
        read_group = self._make_group("FM Buchhaltung Leser")
        self.ProtectedFolder.create({"path": "Buchhaltung", "read_group_ids": [(4, read_group.id)]})
        self._make_file("Buchhaltung/geheim.txt")
        outsider = self._make_user([])
        rec = self.env["int_filemanager.file"].with_user(outsider).search([("path", "=", "Buchhaltung/geheim.txt")])
        self.assertFalse(rec)

    def test_protected_path_visible_with_group(self):
        read_group = self._make_group("FM Buchhaltung Leser 2")
        self.ProtectedFolder.create({"path": "Buchhaltung2", "read_group_ids": [(4, read_group.id)]})
        self._make_file("Buchhaltung2/geheim.txt")
        reader = self._make_user([read_group])
        rec = self.env["int_filemanager.file"].with_user(reader).search([("path", "=", "Buchhaltung2/geheim.txt")])
        self.assertTrue(rec)

    def test_read_write_unlink_are_independent(self):
        read_group = self._make_group("FM RG3")
        write_group = self._make_group("FM WG3")
        self.ProtectedFolder.create(
            {
                "path": "Ordner3",
                "read_group_ids": [(4, read_group.id)],
                "write_group_ids": [(4, write_group.id)],
            }
        )
        self._make_file("Ordner3/x.txt")
        reader_only = self._make_user([read_group])
        rec = self.env["int_filemanager.file"].with_user(reader_only).search([("path", "=", "Ordner3/x.txt")])
        self.assertTrue(rec)
        with self.assertRaises(AccessError):
            rec.check_access("write")

    def test_admin_bypass(self):
        read_group = self._make_group("FM RG4")
        self.ProtectedFolder.create({"path": "Ordner4", "read_group_ids": [(4, read_group.id)]})
        self._make_file("Ordner4/x.txt")
        admin_group = self.env.ref("int_filemanager.group_filemanager_admin")
        admin_user = self._make_user([admin_group])
        rec = self.env["int_filemanager.file"].with_user(admin_user).search([("path", "=", "Ordner4/x.txt")])
        self.assertTrue(rec)

    def test_nested_override_deepest_wins(self):
        group_a = self._make_group("FM Gruppe A")
        group_b = self._make_group("FM Gruppe B")
        self.ProtectedFolder.create({"path": "Buchhaltung5", "read_group_ids": [(4, group_a.id)]})
        self.ProtectedFolder.create({"path": "Buchhaltung5/Gehalt", "read_group_ids": [(4, group_b.id)]})
        self._make_file("Buchhaltung5/normal.txt")
        self._make_file("Buchhaltung5/Gehalt/geheim.txt")

        user_a = self._make_user([group_a])
        user_b = self._make_user([group_b])

        File = self.env["int_filemanager.file"]
        # Gruppe A sieht den normalen Bereich, NICHT den Gehalt-Unterordner -
        # der spezifischste Eintrag gewinnt, keine Kumulation.
        self.assertTrue(File.with_user(user_a).search([("path", "=", "Buchhaltung5/normal.txt")]))
        self.assertFalse(File.with_user(user_a).search([("path", "=", "Buchhaltung5/Gehalt/geheim.txt")]))
        # Gruppe B sieht NUR den Gehalt-Unterordner, nicht den Rest von Buchhaltung5.
        self.assertFalse(File.with_user(user_b).search([("path", "=", "Buchhaltung5/normal.txt")]))
        self.assertTrue(File.with_user(user_b).search([("path", "=", "Buchhaltung5/Gehalt/geheim.txt")]))

    def test_sql_wildcard_folder_name_escaped(self):
        group = self._make_group("FM Wildcard Gruppe")
        self.ProtectedFolder.create({"path": "Plan_2026", "read_group_ids": [(4, group.id)]})
        self._make_file("Plan_2026/a.txt")
        self._make_file("PlanX2026/a.txt")  # NICHT geschützt - darf durch die Escape-Lücke nicht mitgetroffen werden

        outsider = self._make_user([])
        visible = (
            self.env["int_filemanager.file"]
            .with_user(outsider)
            .search([("path", "in", ["Plan_2026/a.txt", "PlanX2026/a.txt"])])
        )
        self.assertEqual(visible.mapped("path"), ["PlanX2026/a.txt"])

    def test_subtree_deletable_denies_when_child_more_protected(self):
        from odoo.addons.int_filemanager import authz

        group = self._make_group("FM Delete Child Gruppe")
        self.ProtectedFolder.create(
            {"path": "Ordner7/Kind", "read_group_ids": [(4, group.id)], "unlink_group_ids": [(4, group.id)]}
        )
        self._make_file("Ordner7", is_dir=True)
        self._make_file("Ordner7/Kind", is_dir=True)
        self._make_file("Ordner7/Kind/geheim.txt")
        outsider = self._make_user([])
        with self.assertRaises(AccessError):
            authz.require_subtree_deletable(self.env(user=outsider), "Ordner7")

    def test_rename_protected_root_denied_even_for_admin(self):
        from odoo.addons.int_filemanager import authz

        self.ProtectedFolder.create({"path": "GeschuetzterRoot8"})
        admin_group = self.env.ref("int_filemanager.group_filemanager_admin")
        admin_user = self._make_user([admin_group])
        with self.assertRaises(AccessError):
            authz.require_rename_or_move_allowed(self.env(user=admin_user), "GeschuetzterRoot8", "")

    def test_move_across_boundary_requires_admin(self):
        from odoo.addons.int_filemanager import authz

        group_a = self._make_group("FM Boundary A")
        self.ProtectedFolder.create({"path": "BoundaryA9", "write_group_ids": [(4, group_a.id)]})
        member = self._make_user([group_a])
        with self.assertRaises(AccessError):
            authz.require_rename_or_move_allowed(self.env(user=member), "BoundaryA9/x.txt", "")
        admin_group = self.env.ref("int_filemanager.group_filemanager_admin")
        admin_user = self._make_user([admin_group])
        # Admin darf über die Schutzgrenze hinweg verschieben - wirft nicht.
        authz.require_rename_or_move_allowed(self.env(user=admin_user), "BoundaryA9/x.txt", "")

    def test_broken_generation_keeps_previous_domain_force(self):
        from odoo.addons.int_filemanager import acl_rules

        rule = self.env.ref("int_filemanager.rule_file_protected_read")
        original_domain = rule.domain_force

        with patch(
            "odoo.addons.int_filemanager.acl_rules._internal_branch_text",
            return_value="this is not valid python !!!",
        ):
            with self.assertRaises(Exception):
                acl_rules.rebuild_rules(self.env)

        rule.invalidate_recordset()
        self.assertEqual(rule.domain_force, original_domain)
