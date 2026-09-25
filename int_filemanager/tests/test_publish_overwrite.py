import base64
import os
import shutil
import tempfile

from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, tagged

from odoo.addons.int_filemanager import publish_service
from odoo.addons.int_filemanager.publish_service import FaultInjected


@tagged("post_install", "-at_install")
class TestPublishOverwrite(HttpCase):
    """Durchstich "Upload ueberschreiben" im Ablauf "Datenbank hat Vorrang"
    (docs/int_filemanager_konzept_db_vorrang_2026-09-24.md, 4.1 und Pflichttests in 10).

    Odoos TestCursor ignoriert postcommit-Hooks - publish_pending() ist deshalb einzeln aufrufbar und
    wird hier direkt angestossen. Die Phasen committen ueber eigene Cursor; im Testmodus sind das
    Savepoints auf derselben Verbindung: ein Fehler rollt nur die laufende Phase zurueck, bereits
    "committete" Phasen bleiben erhalten - dasselbe Verhalten wie echte Commits. Echte Prozessabbrueche
    (os._exit) werden auf der Testinstanz geprueft, nicht hier."""

    def setUp(self):
        super().setUp()
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="int_filemanager_pub_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.root_path", self.root)
        self.env.cr.commit = lambda: None
        self.addCleanup(self._reset_faults)

        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.env["res.users"].sudo().create(
            {"name": "PublishTester", "login": "pub_test_user", "group_ids": [(6, 0, [base_group.id])]}
        )
        self.dbname = self.env.cr.dbname

    def _reset_faults(self):
        publish_service._fault_stage = None
        publish_service._test_hooks.clear()

    # -- Hilfen -------------------------------------------------------------------------

    def _make_file(self, name, content=b"old"):
        with open(os.path.join(self.root, name), "wb") as f:
            f.write(content)
        self.env["int_filemanager.file"].sudo()._scan_and_reconcile()
        self.env.cr.clear()
        return self.env["int_filemanager.file"].sudo().search([("path", "=", name)])

    def _upload(self, name, content):
        self.authenticate("pub_test_user", "irrelevant")
        resp = self.url_open("/int_filemanager/upload", data={"path": ""}, files={"ufile": (name, content)})
        self.env.cr.clear()
        return resp

    def _disk(self, name):
        with open(os.path.join(self.root, name), "rb") as f:
            return f.read()

    def _versions(self, rec):
        return self.env["int_filemanager.version"].sudo().search([("file_id", "=", rec.id)], order="version_no")

    def _pending_blobs(self, rec):
        return self.env["ir.attachment"].sudo().search_count(
            [("res_model", "=", "int_filemanager.file"), ("res_field", "=", "pending_content"), ("res_id", "=", rec.id)]
        )

    def _temp_files(self):
        return [n for n in os.listdir(self.root) if n.startswith(".int_filemanager_tmp_")]

    def _publish_expecting_fault(self, rec_id):
        """Bewusst KEIN assertRaises: Odoos assertRaises umgibt den Block mit einem Savepoint auf dem
        Test-Cursor und rollt bei der Ausnahme alles darin zurueck - auch die "committeten" Phasen
        unserer eigenen Cursor (im Testmodus Savepoints derselben Verbindung). Das wuerde genau die
        Dauerhaftigkeit verdecken, die hier geprueft wird; in Produktion sind es echte Commits."""
        try:
            publish_service.publish_pending(self.dbname, rec_id)
        except FaultInjected:
            return
        self.fail("Fehlerinjektion hat nicht ausgeloest")

    def _refresh(self, rec):
        self.env.cr.clear()
        return rec.sudo().browse(rec.id)

    # -- Request-Teil -----------------------------------------------------------------------

    def test_upload_stages_only_in_db(self):
        rec = self._make_file("doc.txt", b"old")
        self.assertEqual(rec.share_state, "synced")
        self.assertEqual(rec.revision, 0)

        resp = self._upload("doc.txt", b"new")
        self.assertEqual(resp.status_code, 200)

        rec = self._refresh(rec)
        self.assertEqual(rec.share_state, "pending")
        self.assertEqual(rec.revision, 1)
        self.assertEqual(base64.b64decode(rec.pending_content), b"new")
        self.assertEqual(self._pending_blobs(rec), 1)
        # Der Request fasst den Share nicht an: Platte unveraendert, noch keine Version.
        self.assertEqual(self._disk("doc.txt"), b"old")
        self.assertEqual(len(self._versions(rec)), 0)

    def test_publish_completes_state_machine(self):
        rec = self._make_file("doc.txt", b"old")
        self._upload("doc.txt", b"new-content")

        self.assertEqual(publish_service.publish_pending(self.dbname, rec.id), "published")
        rec = self._refresh(rec)
        self.assertEqual(self._disk("doc.txt"), b"new-content")
        self.assertEqual(rec.share_state, "synced")
        self.assertFalse(rec.pending_content)
        self.assertFalse(rec.pending_sha256)
        self.assertFalse(rec.pending_version_id)
        self.assertEqual(self._pending_blobs(rec), 0)
        self.assertEqual(rec.size, len(b"new-content"))
        versions = self._versions(rec)
        self.assertEqual(len(versions), 1)
        self.assertEqual(base64.b64decode(versions.content), b"old")
        self.assertEqual(versions.origin, "app")
        self.assertEqual(self._temp_files(), [])
        # Zweiter Aufruf (z.B. Cron nach erfolgreichem Hook): nichts mehr zu tun.
        self.assertEqual(publish_service.publish_pending(self.dbname, rec.id), "noop")
        self.assertEqual(len(self._versions(rec)), 1)

    def test_identical_content_creates_no_pending_and_no_version(self):
        rec = self._make_file("doc.txt", b"same")
        resp = self._upload("doc.txt", b"same")
        self.assertEqual(resp.status_code, 200)
        rec = self._refresh(rec)
        self.assertEqual(rec.share_state, "synced")
        self.assertEqual(rec.revision, 0)
        self.assertEqual(self._pending_blobs(rec), 0)
        self.assertEqual(len(self._versions(rec)), 0)

    def test_stage_fault_rolls_everything_back(self):
        rec = self._make_file("doc.txt", b"old")
        publish_service._fault_stage = "stage_before_commit"
        self._upload("doc.txt", b"new")
        publish_service._fault_stage = None

        rec = self._refresh(rec)
        self.assertEqual(rec.share_state, "synced")
        self.assertEqual(rec.revision, 0)
        self.assertEqual(self._pending_blobs(rec), 0)
        self.assertEqual(self._disk("doc.txt"), b"old")

    def test_second_upload_while_pending_is_rejected_without_data_loss(self):
        rec = self._make_file("doc.txt", b"old")
        self._upload("doc.txt", b"first")
        resp = self._upload("doc.txt", b"second")
        self.assertNotEqual(resp.status_code, 200)

        rec = self._refresh(rec)
        self.assertEqual(rec.revision, 1)
        self.assertEqual(base64.b64decode(rec.pending_content), b"first")
        self.assertEqual(publish_service.publish_pending(self.dbname, rec.id), "published")
        self.assertEqual(self._disk("doc.txt"), b"first")

    def test_size_limit_rejected_before_staging(self):
        rec = self._make_file("doc.txt", b"old")
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.version_max_size_mb", "1")
        with self.assertRaises(UserError):
            publish_service.stage_overwrite(self.env, rec, b"x" * (2 * 1024 * 1024))
        self.assertEqual(rec.share_state, "synced")

    # -- Fehlerinjektion nach jeder Stufe ----------------------------------------------------

    def test_fault_after_every_hook_stage_is_recoverable(self):
        stages = {
            # stufe: ist die Datei zum Zeitpunkt des Fehlers schon ersetzt?
            "hook_before_snapshot": False,
            "hook_after_snapshot_commit": False,
            "hook_after_temp_written": False,
            "hook_after_replace": True,
            "hook_before_finalize_commit": True,
        }
        for i, (stage, replaced) in enumerate(stages.items()):
            with self.subTest(stage=stage):
                name = f"stage_{i}.txt"
                rec = self._make_file(name, b"old-" + name.encode())
                self._upload(name, b"new-" + name.encode())

                publish_service._fault_stage = stage
                self._publish_expecting_fault(rec.id)
                publish_service._fault_stage = None

                rec = self._refresh(rec)
                self.assertEqual(rec.share_state, "pending", "Zustand darf nach einem Abbruch nicht 'synced' sein")
                self.assertEqual(self._disk(name), (b"new-" if replaced else b"old-") + name.encode())
                self.assertEqual(self._temp_files(), [], "Temp-Datei muss aufgeraeumt sein")
                # Phase A ist dauerhaft: die Sicherung des alten Stands ueberlebt jeden spaeteren Abbruch.
                expected_versions = 0 if stage == "hook_before_snapshot" else 1
                self.assertEqual(
                    len(self._versions(rec)), expected_versions, "Sicherung aus Phase A muss den Abbruch ueberleben"
                )
                self.assertEqual(bool(rec.pending_version_id), expected_versions == 1)

                # Wiederholung (Cron): gleiches Ergebnis, keine Doppelversion, kein Datenverlust.
                self.assertEqual(publish_service.publish_pending(self.dbname, rec.id), "published")
                rec = self._refresh(rec)
                self.assertEqual(self._disk(name), b"new-" + name.encode())
                self.assertEqual(rec.share_state, "synced")
                self.assertEqual(self._pending_blobs(rec), 0)
                versions = self._versions(rec)
                self.assertEqual(len(versions), 1, "genau eine Version des alten Stands")
                self.assertEqual(base64.b64decode(versions.content), b"old-" + name.encode())
                self.assertEqual(self._temp_files(), [])

    def test_repeated_faults_then_success_still_single_version(self):
        rec = self._make_file("doc.txt", b"old")
        self._upload("doc.txt", b"new")
        for stage in ("hook_after_snapshot_commit", "hook_after_temp_written", "hook_after_snapshot_commit"):
            publish_service._fault_stage = stage
            self._publish_expecting_fault(rec.id)
        publish_service._fault_stage = None
        self.assertEqual(publish_service.publish_pending(self.dbname, rec.id), "published")
        rec = self._refresh(rec)
        self.assertEqual(len(self._versions(rec)), 1)
        self.assertEqual(self._disk("doc.txt"), b"new")

    def test_orphan_temp_file_of_crashed_attempt_is_removed_on_retry(self):
        rec = self._make_file("doc.txt", b"old")
        self._upload("doc.txt", b"new")
        # Reste eines harten Abbruchs zwischen Schreiben und os.replace (auch ein ganz junger).
        orphan_old = os.path.join(self.root, f".int_filemanager_tmp_{rec.id}_dead")
        orphan_new = os.path.join(self.root, f".int_filemanager_tmp_{rec.id}_live")
        foreign = os.path.join(self.root, f".int_filemanager_tmp_{rec.id + 999}_dead")
        other_name = os.path.join(self.root, "doc.txt.bak")
        for path in (orphan_old, orphan_new, foreign, other_name):
            with open(path, "wb") as f:
                f.write(b"partial")
        old = os.stat(orphan_old).st_mtime - 3600
        os.utime(orphan_old, (old, old))

        # Erstlauf scannt den Ordner nicht ...
        publish_service._fault_stage = "hook_after_snapshot_commit"
        self._publish_expecting_fault(rec.id)
        publish_service._fault_stage = None
        self.assertTrue(os.path.exists(orphan_old) and os.path.exists(orphan_new))
        # ... der Wiederholungslauf raeumt alle Reste DIESES Vorgangs ab (der Sperrhalter ist der einzige
        # Schreiber), aber nichts Fremdes.
        self.assertEqual(publish_service.publish_pending(self.dbname, rec.id), "published")
        self.assertFalse(os.path.exists(orphan_old))
        self.assertFalse(os.path.exists(orphan_new))
        self.assertTrue(os.path.exists(foreign), "Temp-Datei einer anderen Datei nie anfassen")
        self.assertTrue(os.path.exists(other_name), "gewoehnliche Dateien nie anfassen")

    def test_cron_retry_also_cleans_orphans_without_prior_snapshot(self):
        """Datei extern entfernt (kein Snapshot, pending_version_id leer), Abbruch nach dem Schreiben der
        Temp-Datei: der Cron-Lauf (is_retry) muss den Rest trotzdem finden."""
        rec = self._make_file("doc.txt", b"old")
        self._upload("doc.txt", b"new")
        os.remove(os.path.join(self.root, "doc.txt"))
        orphan = os.path.join(self.root, f".int_filemanager_tmp_{rec.id}_dead")
        with open(orphan, "wb") as f:
            f.write(b"partial")
        self.assertEqual(publish_service.publish_pending(self.dbname, rec.id, is_retry=True), "published")
        self.assertFalse(os.path.exists(orphan))
        self.assertEqual(self._disk("doc.txt"), b"new")

    # -- Externe Aenderung waehrend des Veroeffentlichens -------------------------------------

    def test_external_change_between_snapshot_and_replace_is_kept_as_version(self):
        rec = self._make_file("doc.txt", b"old")
        self._upload("doc.txt", b"new")
        fired = []

        def external_write():
            if not fired:
                fired.append(True)
                with open(os.path.join(self.root, "doc.txt"), "wb") as f:
                    f.write(b"changed-in-explorer")

        publish_service._test_hooks["hook_after_snapshot_commit"] = external_write
        self.assertEqual(publish_service.publish_pending(self.dbname, rec.id), "published")

        rec = self._refresh(rec)
        self.assertEqual(self._disk("doc.txt"), b"new")
        versions = self._versions(rec)
        self.assertEqual([base64.b64decode(v.content) for v in versions], [b"old", b"changed-in-explorer"])
        self.assertEqual(versions[0].origin, "app")
        self.assertEqual(versions[1].origin, "extern")

    def test_external_change_before_publish_is_marked_extern(self):
        rec = self._make_file("doc.txt", b"old")
        self._upload("doc.txt", b"new")
        # Explorer schreibt, bevor der Hook laeuft (z.B. Hook ausgefallen, Cron spaeter).
        with open(os.path.join(self.root, "doc.txt"), "wb") as f:
            f.write(b"explorer-was-here")
        self.assertEqual(publish_service.publish_pending(self.dbname, rec.id), "published")
        rec = self._refresh(rec)
        versions = self._versions(rec)
        self.assertEqual(len(versions), 1)
        self.assertEqual(base64.b64decode(versions.content), b"explorer-was-here")
        self.assertEqual(versions.origin, "extern")
        self.assertEqual(self._disk("doc.txt"), b"new")

    def test_file_removed_externally_is_recreated_from_db(self):
        rec = self._make_file("doc.txt", b"old")
        self._upload("doc.txt", b"new")
        os.remove(os.path.join(self.root, "doc.txt"))
        self.assertEqual(publish_service.publish_pending(self.dbname, rec.id), "published")
        rec = self._refresh(rec)
        self.assertEqual(self._disk("doc.txt"), b"new")
        self.assertEqual(len(self._versions(rec)), 0, "es gab keinen alten Stand zu sichern")

    # -- Cron ----------------------------------------------------------------------------------

    def test_cron_publishes_only_aged_pending_rows(self):
        rec = self._make_file("doc.txt", b"old")
        self._upload("doc.txt", b"new")
        # Frischer Vorgang: laeuft evtl. gerade im Hook -> nicht anfassen.
        self.assertEqual(publish_service.publish_all_pending(self.env), {})
        self.assertEqual(self._disk("doc.txt"), b"old")
        self.env.cr.execute(
            "UPDATE int_filemanager_file SET write_date = write_date - interval '1 hour' WHERE id = %s", (rec.id,)
        )
        self.env.cr.clear()
        self.assertEqual(publish_service.publish_all_pending(self.env), {rec.id: "published"})
        self.assertEqual(self._disk("doc.txt"), b"new")

    def test_cron_model_method_runs(self):
        rec = self._make_file("doc.txt", b"old")
        self._upload("doc.txt", b"new")
        self.env.cr.execute(
            "UPDATE int_filemanager_file SET write_date = write_date - interval '1 hour' WHERE id = %s", (rec.id,)
        )
        self.env.cr.clear()
        self.env["int_filemanager.file"]._cron_publish_pending()
        self.assertEqual(self._disk("doc.txt"), b"new")

    # -- Unstimmiger Zustand -------------------------------------------------------------------

    def test_blob_hash_mismatch_sets_conflict_and_writes_nothing(self):
        rec = self._make_file("doc.txt", b"old")
        self._upload("doc.txt", b"new")
        rec = self._refresh(rec)
        rec.pending_sha256 = "0" * 64
        self.env.flush_all()
        self.assertEqual(publish_service.publish_pending(self.dbname, rec.id), "conflict")
        rec = self._refresh(rec)
        self.assertEqual(rec.share_state, "conflict")
        self.assertEqual(self._disk("doc.txt"), b"old")
