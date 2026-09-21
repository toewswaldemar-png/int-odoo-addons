import os
import shutil
import tempfile
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScanIdentity(TransactionCase):
    """Phase 1: SHA-256-basierte Identitätserkennung bei Umbenennung/Verschiebung,
    die stattfand, während Odoo nicht lief (Watcher tot -> _scan_and_reconcile
    muss den Unterschied zwischen 'echtes Rename' und 'Löschen+Neuanlegen' allein
    aus dem Dateisystem-Zustand rekonstruieren)."""

    def setUp(self):
        super().setUp()
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="int_filemanager_test_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.root_path", self.root)
        self.Model = self.env["int_filemanager.file"].sudo()
        # _scan_and_reconcile/_cron_compute_hashes committen absichtlich in
        # Batches (Produktivbetrieb: hunderttausende Zeilen) - TransactionCase
        # laesst pro Test aber keinen echten Commit zu (Savepoint-Rollback am
        # Testende wuerde sonst brechen). Fuer die Testdauer neutralisieren,
        # Standardmuster fuer Odoo-Tests gegen Cron-/Batch-Code.
        self.env.cr.commit = lambda: None

    def _write(self, rel_path, content=b"hello"):
        abs_path = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(content)
        return abs_path

    def _mkdir(self, rel_path):
        os.makedirs(os.path.join(self.root, rel_path), exist_ok=True)

    def _scan(self):
        self.Model._scan_and_reconcile()

    def _hash_pending(self):
        # Alle pending-Datensätze in einem Rutsch abarbeiten (Testkomfort -
        # der echte Cron arbeitet in Batches von HASH_CRON_BATCH_SIZE).
        while self.Model.search_count([("hash_state", "=", "pending"), ("is_dir", "=", False)]):
            self.Model._cron_compute_hashes()

    # ------------------------------------------------------------------
    # Kernszenario: bestätigter Hash vorhanden -> Merge, Identität bleibt
    # ------------------------------------------------------------------

    def test_offline_rename_with_confirmed_hash_merges(self):
        self._write("a.txt", b"content-1")
        self._scan()
        self._hash_pending()
        rec = self.Model.search([("path", "=", "a.txt")])
        self.assertEqual(rec.hash_state, "done")
        tag = self.env["int_filemanager.tag"].sudo().create({"name": "Wichtig"})
        rec.tag_ids = [(4, tag.id)]
        old_id = rec.id

        os.rename(os.path.join(self.root, "a.txt"), os.path.join(self.root, "b.txt"))
        self._scan()

        merged = self.Model.browse(old_id)
        self.assertTrue(merged.exists())
        self.assertEqual(merged.path, "b.txt")
        self.assertIn(tag, merged.tag_ids)
        self.assertEqual(self.Model.search_count([("path", "=", "a.txt")]), 0)
        self.assertEqual(
            self.env["int_filemanager.scan_log"].sudo().search_count([("event_type", "=", "merged")]), 1
        )

    def test_offline_rename_without_hash_does_not_merge(self):
        """Rename geschah, bevor der Hash je berechnet wurde -> kein Rateversuch,
        heutiges Verhalten (Löschen+Neuanlegen) bleibt bestehen - dokumentierte,
        akzeptierte Grenze, keine Verschlechterung ggü. heute."""
        self._write("a.txt", b"content-1")
        self._scan()
        rec = self.Model.search([("path", "=", "a.txt")])
        self.assertEqual(rec.hash_state, "pending")
        old_id = rec.id

        os.rename(os.path.join(self.root, "a.txt"), os.path.join(self.root, "b.txt"))
        self._scan()

        self.assertFalse(self.Model.browse(old_id).exists())
        new_rec = self.Model.search([("path", "=", "b.txt")])
        self.assertTrue(new_rec)
        self.assertNotEqual(new_rec.id, old_id)

    # ------------------------------------------------------------------
    # Negativfälle: kein falscher Merge
    # ------------------------------------------------------------------

    def test_delete_plus_new_same_size_different_content_no_merge(self):
        self._write("a.txt", b"AAAAA")
        self._scan()
        self._hash_pending()
        old_id = self.Model.search([("path", "=", "a.txt")]).id

        os.remove(os.path.join(self.root, "a.txt"))
        self._write("c.txt", b"CCCCC")  # gleiche Größe, anderer Inhalt
        self._scan()

        self.assertFalse(self.Model.browse(old_id).exists())
        self.assertTrue(self.Model.search([("path", "=", "c.txt")]))

    def test_swapped_same_size_files_no_merge(self):
        self._write("a.txt", b"AAAAA")
        self._write("b.txt", b"BBBBB")
        self._scan()
        self._hash_pending()
        a_id = self.Model.search([("path", "=", "a.txt")]).id
        b_id = self.Model.search([("path", "=", "b.txt")]).id

        os.remove(os.path.join(self.root, "a.txt"))
        os.remove(os.path.join(self.root, "b.txt"))
        self._write("c.txt", b"CCCCC")
        self._write("d.txt", b"DDDDD")
        self._scan()

        self.assertFalse(self.Model.browse(a_id).exists())
        self.assertFalse(self.Model.browse(b_id).exists())
        self.assertEqual(self.Model.search_count([("path", "in", ["c.txt", "d.txt"])]), 2)

    def test_identical_content_multiple_new_locations_no_false_merge(self):
        self._write("a.txt", b"SAME-CONTENT")
        self._scan()
        self._hash_pending()
        old_id = self.Model.search([("path", "=", "a.txt")]).id

        os.remove(os.path.join(self.root, "a.txt"))
        self._write("c1.txt", b"SAME-CONTENT")
        self._write("c2.txt", b"SAME-CONTENT")
        self._scan()

        self.assertFalse(self.Model.browse(old_id).exists())
        self.assertEqual(self.Model.search_count([("path", "in", ["c1.txt", "c2.txt"])]), 2)
        self.assertTrue(
            self.env["int_filemanager.scan_log"].sudo().search([("event_type", "=", "ambiguous")])
        )

    def test_rename_and_content_change_same_window_no_merge(self):
        self._write("a.txt", b"original-content")
        self._scan()
        self._hash_pending()
        old_id = self.Model.search([("path", "=", "a.txt")]).id

        os.rename(os.path.join(self.root, "a.txt"), os.path.join(self.root, "b.txt"))
        with open(os.path.join(self.root, "b.txt"), "wb") as f:
            f.write(b"changed-content-different-size-now")
        self._scan()

        self.assertFalse(self.Model.browse(old_id).exists())
        self.assertTrue(self.Model.search([("path", "=", "b.txt")]))

    def test_empty_folders_without_common_child_no_merge(self):
        self._mkdir("Empty1")
        self._scan()
        old_id = self.Model.search([("path", "=", "Empty1")]).id

        shutil.rmtree(os.path.join(self.root, "Empty1"))
        self._mkdir("Empty2")
        self._scan()

        self.assertFalse(self.Model.browse(old_id).exists())
        self.assertTrue(self.Model.search([("path", "=", "Empty2")]))

    # ------------------------------------------------------------------
    # Unterbaum-Move
    # ------------------------------------------------------------------

    def test_subtree_move_reassigns_children(self):
        self._write("Ordner/a.txt", b"content-a")
        self._write("Ordner/sub/b.txt", b"content-b")
        self._scan()
        self._hash_pending()
        folder_id = self.Model.search([("path", "=", "Ordner")]).id
        a_id = self.Model.search([("path", "=", "Ordner/a.txt")]).id
        sub_id = self.Model.search([("path", "=", "Ordner/sub")]).id
        b_id = self.Model.search([("path", "=", "Ordner/sub/b.txt")]).id

        shutil.move(os.path.join(self.root, "Ordner"), os.path.join(self.root, "Archiv"))
        self._scan()

        self.assertEqual(self.Model.browse(a_id).path, "Archiv/a.txt")
        self.assertEqual(self.Model.browse(b_id).path, "Archiv/sub/b.txt")
        self.assertEqual(self.Model.browse(sub_id).path, "Archiv/sub")
        self.assertEqual(self.Model.browse(folder_id).path, "Archiv")

    # ------------------------------------------------------------------
    # Hash-Race gegen parallele Änderungen
    # ------------------------------------------------------------------

    def test_hash_discarded_on_concurrent_modification(self):
        from ..hash_utils import compute_stable_hash

        abs_path = self._write("a.txt", b"x" * 10)
        real_stat = os.stat
        call_count = {"n": 0}

        class _FakeStat:
            def __init__(self, size, mtime_ns):
                self.st_size = size
                self.st_mtime_ns = mtime_ns

        def flaky_stat(path, *args, **kwargs):
            result = real_stat(path, *args, **kwargs)
            call_count["n"] += 1
            if call_count["n"] == 2:
                # Simuliert eine Änderung, die zwischen dem stat() vor und dem
                # stat() nach dem Lesen passiert ist.
                return _FakeStat(result.st_size + 1, result.st_mtime_ns)
            return result

        with patch("odoo.addons.int_filemanager.hash_utils.os.stat", side_effect=flaky_stat):
            digest = compute_stable_hash(abs_path)
        self.assertIsNone(digest)

    # ------------------------------------------------------------------
    # Hash-Budget pro Scan-Lauf
    # ------------------------------------------------------------------

    def test_hash_budget_exceeded_skips_merge_this_run(self):
        self._write("a.txt", b"x" * 1000)
        self._scan()
        self._hash_pending()
        old_id = self.Model.search([("path", "=", "a.txt")]).id

        os.rename(os.path.join(self.root, "a.txt"), os.path.join(self.root, "b.txt"))
        with patch(
            "odoo.addons.int_filemanager.models.filemanager_file.SCAN_HASH_BUDGET_BYTES", 10
        ):
            self._scan()

        # Budget zu klein für die 1000-Byte-Datei -> kein Merge in diesem Lauf,
        # konservativ heutiges Verhalten (Löschen+Neuanlegen).
        self.assertFalse(self.Model.browse(old_id).exists())
        self.assertTrue(self.Model.search([("path", "=", "b.txt")]))

    # ------------------------------------------------------------------
    # Asynchroner Hash-Cron: unbedingtes pending bei Watcher-Pfad
    # ------------------------------------------------------------------

    def test_index_upsert_marks_files_pending_not_folders(self):
        from ..index_utils import index_upsert

        file_path = self._write("watched.txt", b"content")
        self._mkdir("WatchedFolder")

        file_rec = index_upsert(self.env, file_path)
        folder_rec = index_upsert(self.env, os.path.join(self.root, "WatchedFolder"))

        self.assertEqual(file_rec.hash_state, "pending")
        self.assertTrue(folder_rec.is_dir)

    def test_scan_skips_stale_cleanup_for_missing_large_subtree(self):
        """Live 2026-09-17 als Beinahe-Vorfall gefunden: ein Wurzel-Unterordner (in der
        Produktion einer der drei CIFS-Mounts) kann beim Scan-Start voruebergehend leer/
        nicht erreichbar sein, waehrend der Rest des Baums normal vorhanden ist - der
        bestehende total_walked==0-Schutz greift dann NICHT (die Gesamtzahl ist nicht
        null). Ohne den hier getesteten Per-Unterbaum-Schutz wuerden alle bestehenden
        Eintraege unter dem nicht erreichbaren Unterbaum als stale geloescht - live fast
        mit ~1,38 Mio. Zeilen passiert, nur durch einen zufaelligen Absturz verhindert."""
        from ..models.filemanager_file import SCAN_STALE_TOPLEVEL_MIN_ROWS

        # "Remote" simuliert einen grossen CIFS-Mount, "Local" einen kleinen,
        # unabhaengigen Unterordner mit einer normalen, legitimen Loeschung.
        for i in range(SCAN_STALE_TOPLEVEL_MIN_ROWS + 5):
            self._write(f"Remote/file_{i}.txt")
        self._write("Local/only.txt")
        self._scan()

        remote_count_before = self.Model.search_count([("path", "=like", "Remote/%")])
        self.assertEqual(remote_count_before, SCAN_STALE_TOPLEVEL_MIN_ROWS + 5)

        # "Remote" verschwindet komplett (simuliert einen nicht gemounteten CIFS-Mount),
        # "Local/only.txt" wird dagegen echt geloescht.
        shutil.rmtree(os.path.join(self.root, "Remote"))
        os.remove(os.path.join(self.root, "Local", "only.txt"))
        self._scan()

        self.assertEqual(
            self.Model.search_count([("path", "=like", "Remote/%")]),
            remote_count_before,
            "Eintraege unter dem nicht erreichbaren Unterbaum duerfen nicht geloescht werden",
        )
        self.assertEqual(self.Model.search_count([("path", "=", "Local/only.txt")]), 0)
