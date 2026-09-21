import os
import shutil
import tempfile

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTrash(TransactionCase):
    """docs/int_filemanager_papierkorb_konzept.md - Rundlauf loeschen -> Papierkorb ->
    wiederherstellen, plus die Sichtbarkeitsregel (rule_file_trash_visibility)."""

    def setUp(self):
        super().setUp()
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="int_filemanager_trash_test_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.root_path", self.root)
        self.Model = self.env["int_filemanager.file"].sudo()

    def _write(self, rel_path, content=b"hello"):
        abs_path = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(content)
        return abs_path

    def test_trash_and_restore_round_trip_for_a_file(self):
        from ..index_utils import index_restore_tree, index_trash_tree, index_upsert, trash_destination

        abs_path = self._write("a.txt", b"content")
        rec = index_upsert(self.env, abs_path)
        self.assertFalse(rec.trashed)

        trash_rel = trash_destination(self.env, "a.txt")
        trash_abs = os.path.join(self.root, trash_rel)
        shutil.move(abs_path, trash_abs)
        trashed = index_trash_tree(self.env, "a.txt", trash_rel)

        self.assertEqual(trashed.id, rec.id, "sollte denselben Datensatz umschreiben, nicht duplizieren")
        self.assertTrue(trashed.trashed)
        self.assertEqual(trashed.original_path, "a.txt")
        self.assertEqual(trashed.path, trash_rel)
        self.assertEqual(trashed.trashed_by.id, self.env.uid)
        self.assertFalse(os.path.exists(abs_path))
        self.assertTrue(os.path.exists(trash_abs))
        # Der .trash-Container-Ordner selbst ist ebenfalls trashed - sonst bliebe er als leerer,
        # aber sichtbarer Ordner im normalen Baum stehen (siehe Konzeptdoc, "Nachtrag").
        trash_folder = self.Model.search([("path", "=", ".trash")], limit=1)
        self.assertTrue(trash_folder.trashed)

        restored = index_restore_tree(self.env, trashed)

        self.assertEqual(restored.id, rec.id)
        self.assertFalse(restored.trashed)
        self.assertFalse(restored.original_path)
        self.assertEqual(restored.path, "a.txt")
        self.assertTrue(os.path.exists(abs_path))
        self.assertFalse(os.path.exists(trash_abs))

    def test_trash_folder_moves_descendants_together(self):
        from ..index_utils import index_trash_tree, index_upsert, trash_destination

        self._write("Ordner/a.txt")
        self._write("Ordner/Unterordner/b.txt")
        folder_abs = os.path.join(self.root, "Ordner")
        folder_rec = index_upsert(self.env, folder_abs)
        index_upsert(self.env, os.path.join(folder_abs, "a.txt"))
        index_upsert(self.env, os.path.join(folder_abs, "Unterordner"))
        index_upsert(self.env, os.path.join(folder_abs, "Unterordner", "b.txt"))

        trash_rel = trash_destination(self.env, "Ordner")
        trash_abs = os.path.join(self.root, trash_rel)
        shutil.move(folder_abs, trash_abs)
        index_trash_tree(self.env, "Ordner", trash_rel)

        self.assertFalse(os.path.exists(folder_abs))
        self.assertTrue(os.path.exists(os.path.join(trash_abs, "Unterordner", "b.txt")))
        child = self.Model.search([("path", "=", trash_rel + "/Unterordner/b.txt")], limit=1)
        self.assertTrue(child, "Nachfahre sollte unter dem neuen Pfad wiederauffindbar sein")
        self.assertTrue(child.trashed)
        self.assertEqual(child.original_path, "Ordner/Unterordner/b.txt")
        self.assertEqual(folder_rec.parent_id.path, ".trash")

    def test_restore_blocks_hard_on_collision(self):
        from odoo.exceptions import UserError

        from ..index_utils import index_restore_tree, index_trash_tree, index_upsert, trash_destination

        abs_path = self._write("a.txt", b"content")
        index_upsert(self.env, abs_path)
        trash_rel = trash_destination(self.env, "a.txt")
        trash_abs = os.path.join(self.root, trash_rel)
        shutil.move(abs_path, trash_abs)
        trashed = index_trash_tree(self.env, "a.txt", trash_rel)

        # Ein neuer Eintrag belegt inzwischen denselben Ursprungsort.
        self._write("a.txt", b"neuer Inhalt")
        index_upsert(self.env, abs_path)

        with self.assertRaises(UserError):
            index_restore_tree(self.env, trashed)

    def test_non_admin_only_sees_own_trashed_items(self):
        from ..index_utils import index_trash_tree, index_upsert, trash_destination

        user_group = self.env.ref("int_filemanager.group_filemanager_user")
        alice = self.env["res.users"].create({
            "name": "Alice", "login": "trash_alice", "group_ids": [(6, 0, [user_group.id])],
        })
        bob = self.env["res.users"].create({
            "name": "Bob", "login": "trash_bob", "group_ids": [(6, 0, [user_group.id])],
        })

        abs_path = self._write("a.txt", b"content")
        index_upsert(self.env, abs_path)
        trash_rel = trash_destination(self.env, "a.txt")
        shutil.move(abs_path, os.path.join(self.root, trash_rel))
        index_trash_tree(self.env(user=alice), "a.txt", trash_rel)

        Model = self.env["int_filemanager.file"]
        self.assertTrue(
            Model.with_user(alice).search([("path", "=", trash_rel)]),
            "Alice sollte ihren eigenen Papierkorb-Eintrag sehen",
        )
        self.assertFalse(
            Model.with_user(bob).search([("path", "=", trash_rel)]),
            "Bob sollte Alices Papierkorb-Eintrag nicht sehen",
        )
