import io
import os
import sys
import time
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.sql_db import db_connect
from odoo.tests.common import TransactionCase, new_test_user, tagged
from odoo.tools import SQL

from odoo.addons.int_filemanager_ocr.models.int_filemanager_text import ENGINE_VERSION, SETTINGS
from odoo.addons.int_filemanager_ocr.models.int_filemanager_text_page import folded

from odoo.addons.int_filemanager.tests import text_files

MODULE = "odoo.addons.int_filemanager_ocr.models.int_filemanager_text"
USER_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_user"


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


class TextCase(TransactionCase):
    """Documents with files, and the reading of their text without the scheduled action."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env["int.filemanager.document"]
        cls.Text = cls.env["int.filemanager.text"]
        cls.Page = cls.env["int.filemanager.text.page"]
        cls.folder = cls.env["int.filemanager.folder"].create({"name": "Texts"})

    def setUp(self):
        super().setUp()
        # The steps of the action commit; a test is not allowed to.
        commit = patch.object(self.env.cr, "commit")
        commit.start()
        self.addCleanup(commit.stop)

    def _document(self, name, content, folder=None):
        document = self.Document._create_from_stream(io.BytesIO(content), name, folder or self.folder)
        self.addCleanup(remove, self.Document._blob_path(document.checksum))
        return document

    def _read_all(self):
        """Make the rows and read every file that waits, as the scheduled action does."""
        self.Text._create_rows(1000)
        for row in self.Text.search([("state", "=", "pending")]):
            row._read_text(time.monotonic() + 120)
        self.Text.flush_model()

    def _text_of(self, document):
        return self.Text.search([("checksum", "=", document.checksum)])

    def _found(self, words, user=None, operator="ilike"):
        Document = self.Document.with_user(user) if user else self.Document
        return Document.search([("content_search", operator, words)])


@tagged("post_install", "-at_install")
class TestTextSearch(TextCase):
    """The search in the text of the files."""

    def test_the_text_of_a_pdf_is_found_by_its_words(self):
        document = self._document("a.pdf", text_files.pdf(["The invoice of the plumber", "Second page"]))
        self._read_all()
        self.assertEqual(self._found("plumber"), document)
        self.assertEqual(self._found("second invoice"), self.Document.browse())
        self.assertEqual(self._found("plumber second"), self.Document.browse())

    def test_umlauts_are_folded_in_both_directions(self):
        document = self._document("a.docx", text_files.docx(["Herr Müller wohnt in der Straße"]))
        self._read_all()
        for words in ("Müller", "Mueller", "MÜLLER", "strasse", "Straße"):
            with self.subTest(words=words):
                self.assertEqual(self._found(words), document)

    def test_word_forms_are_found_by_their_stem(self):
        document = self._document("a.txt", b"Die Rechnungen sind bezahlt")
        self._read_all()
        self.assertEqual(self._found("Rechnung"), document)
        self.assertEqual(self._found("Rechnu"), self.Document.browse())

    def test_the_search_syntax_of_the_web_works(self):
        document = self._document("a.txt", b"red apples and green pears")
        self._document("b.txt", b"red cherries")
        self._read_all()
        self.assertEqual(self._found('"green pears"'), document)
        self.assertEqual(self._found("red -cherries"), document)
        self.assertEqual(len(self._found("apples or cherries")), 2)

    def test_the_equal_sign_and_a_blank_search_are_taken(self):
        document = self._document("a.txt", b"unique token")
        self._read_all()
        self.assertEqual(self._found("token", operator="="), document)
        self.assertEqual(self._found("   "), self.Document.search([]))

    def test_other_operators_are_refused(self):
        self._document("a.txt", b"text")
        self._read_all()
        for operator in ("like", ">"):
            with self.subTest(operator=operator), self.assertRaises(UserError):
                self._found("text", operator=operator)

    def test_not_containing_is_the_rest(self):
        found, other = self._document("a.txt", b"alpha"), self._document("b.txt", b"beta")
        self._read_all()
        for operator in ("not ilike", "!="):
            with self.subTest(operator=operator):
                self.assertEqual(self._found("alpha", operator=operator) & (found + other), other)

    def test_archived_documents_are_not_found(self):
        document = self._document("a.txt", b"findable")
        self._read_all()
        document.active = False
        self.assertEqual(self._found("findable"), self.Document.browse())

    def test_files_with_the_same_content_share_one_text(self):
        first = self._document("a.txt", b"same words")
        second = self._document("b.txt", b"same words")
        self._read_all()
        self.assertEqual(len(self._text_of(first)), 1)
        self.assertEqual(self._found("words"), first + second)

    def test_the_folding_does_not_depend_on_the_locale_of_the_database(self):
        # ``lower`` follows the collation: with "C" a capital umlaut stays as it is.
        for word, expected in (("ÜBUNG", "uebung"), ("Übung", "uebung"), ("Ärger", "aerger")):
            with self.subTest(word=word):
                self.env.cr.execute(
                    SQL('SELECT %s', SQL(folded("%s::text COLLATE \"C\""), word))
                )
                self.assertEqual(self.env.cr.fetchone()[0], expected)

    # --- who may see a hit -------------------------------------------------------

    def test_a_hit_is_shown_only_for_documents_in_folders_the_user_may_see(self):
        alice = new_test_user(self.env, login="text_alice", groups=USER_GROUPS)
        secret = self.env["int.filemanager.folder"].create({"name": "Secret", "access_mode": "restricted"})
        shared = self.env["int.filemanager.folder"].create({"name": "Shared", "access_mode": "open"})
        hidden = self._document("secret.txt", b"the confidential plan", secret)
        twin = self._document("twin.txt", b"the confidential plan", shared)
        only = self._document("only.txt", b"the confidential memo", secret)
        self._read_all()
        self.assertEqual(self._found("confidential", alice), twin)
        self.assertEqual(self._found("memo", alice), self.Document.browse())
        self.assertEqual(self._found("confidential"), hidden + twin + only)

    def test_the_users_cannot_read_the_text_models(self):
        alice = new_test_user(self.env, login="text_bob", groups=USER_GROUPS)
        self._document("a.txt", b"anything")
        self._read_all()
        for model in (self.Text, self.Page):
            with self.subTest(model=model._name), self.assertRaises(AccessError):
                model.with_user(alice).search([])

    def test_the_administrator_can_read_the_texts(self):
        boss = new_test_user(
            self.env, login="text_boss", groups="base.group_user,int_filemanager.int_filemanager_group_admin"
        )
        self._document("a.txt", b"anything")
        self._read_all()
        self.assertTrue(self.Text.with_user(boss).search([]))
        self.assertTrue(self.Page.with_user(boss).search([]))

    # --- the label and the memory ------------------------------------------------

    def test_the_field_has_a_label_of_its_own(self):
        fields_ = self.Document._fields
        labels = [field.string for name, field in fields_.items() if name != "content_search"]
        self.assertNotIn(fields_["content_search"].string, labels)

    def test_the_memory_for_the_search_is_set_for_the_transaction_only(self):
        self._document("a.txt", b"word")
        self._read_all()
        self.env["ir.config_parameter"].set_param("int_filemanager.work_mem_mib", "33")
        self.env.cr.execute("SHOW work_mem")
        usual = self.env.cr.fetchone()[0]
        self._found("word")
        self.env.cr.execute("SHOW work_mem")
        self.assertEqual(self.env.cr.fetchone()[0], "33MB")
        self.env.cr.execute("SHOW max_parallel_workers_per_gather")
        self.assertEqual(self.env.cr.fetchone()[0], "0")
        # On a connection of its own: after the transaction the usual value is back.
        with db_connect(self.env.cr.dbname).cursor() as cr:
            cr.execute("SHOW work_mem")
            self.assertEqual(cr.fetchone()[0], usual)
            cr.execute("SELECT set_config('work_mem', '33MB', true)")
            cr.commit()
            cr.execute("SHOW work_mem")
            self.assertEqual(cr.fetchone()[0], usual)


@tagged("post_install", "-at_install")
class TestTextRows(TextCase):
    """Which files get a row, how it is filled, and what the cleaner removes."""

    def test_rows_are_made_for_the_types_that_have_text_and_for_nothing_else(self):
        wanted = [
            self._document("a.pdf", text_files.pdf(["x"])),
            self._document("a.docx", text_files.docx(["x"])),
            self._document("a.xlsx", text_files.xlsx([["x"]])),
            self._document("a.pptx", text_files.pptx([["x"]])),
            self._document("a.odt", text_files.odt(["x"])),
            self._document("a.txt", b"x"),
            self._document("a.csv", b"x;y"),
        ]
        unwanted = [
            self._document("a.png", b"\x89PNG\r\n\x1a\n" + b"\0" * 20),
            self._document("a.mp3", b"ID3" + b"\0" * 20),
        ]
        before = self.Text.search([])
        self.assertEqual(self.Text._create_rows(1000) >= len(wanted), True)
        made = self.Text.search([]) - before
        self.assertEqual(set(made.mapped("checksum")) & {d.checksum for d in unwanted}, set())
        self.assertLessEqual({d.checksum for d in wanted}, set(made.mapped("checksum")))
        # Nothing left to make: those without text are not "documents without a row".
        self.assertEqual(self.Text._create_rows(1000), 0)

    def test_archived_documents_get_no_row_until_they_come_back(self):
        document = self._document("a.txt", b"archived text")
        document.active = False
        self.Text._create_rows(1000)
        self.assertFalse(self._text_of(document))
        document.active = True
        self.Text._create_rows(1000)
        self.assertTrue(self._text_of(document))

    def test_the_text_of_a_file_without_text_is_empty(self):
        document = self._document("a.pdf", text_files.pdf([""], pictures=[0]))
        self._read_all()
        row = self._text_of(document)
        self.assertEqual((row.state, row.page_count), ("empty", 1))

    def test_a_file_that_is_missing_fails(self):
        document = self._document("a.txt", b"gone")
        self.Text._create_rows(1000)
        os.unlink(self.Document._blob_path(document.checksum))
        row = self._text_of(document)
        row._read_text(time.monotonic() + 60)
        self.assertEqual(row.state, "failed")
        self.assertIn("missing", row.message)

    def test_a_broken_file_fails_with_the_reason(self):
        document = self._document("a.docx", b"PK\x03\x04 broken")
        self._read_all()
        row = self._text_of(document)
        self.assertEqual(row.state, "failed")
        self.assertTrue(row.message)

    def test_a_page_that_cannot_be_indexed_is_cut_and_the_others_stay(self):
        # A text of 55,000 different words (Cyrillic) is above what one entry of the search may
        # hold; the size in bytes is no help. The batch must not break.
        digits = "абвгдежзик"
        words = " ".join(
            "".join(digits[int(char)] for char in f"{number:07d}") for number in range(60000)
        )
        document = self._document("a.txt", words.encode())
        other = self._document("b.txt", b"harmless")
        with patch.dict(SETTINGS, {"text_block_kib": (2000, 1)}):
            self._read_all()
        row = self._text_of(document)
        self.assertEqual(row.state, "done")
        self.assertIn("different words", row.message)
        self.assertEqual(self._text_of(other).state, "done")
        self.assertTrue(self.Page.search([("text_id", "=", row.id)]))

    def test_a_large_text_is_kept_in_blocks_and_all_of_it_is_found(self):
        lines = [f"entry{number} common" for number in range(30000)]
        document = self._document("big.txt", "\n".join(lines).encode())
        self._read_all()
        row = self._text_of(document)
        self.assertGreater(self.Page.search_count([("text_id", "=", row.id)]), 5)
        self.assertEqual(self.Document.search([("content_search", "ilike", "entry29999")]), document)
        self.assertEqual(self.Document.search([("content_search", "ilike", "entry0")]), document)

    # --- tries, versions, limits -------------------------------------------------

    def test_a_row_that_is_still_running_counts_as_a_failed_try_and_gives_up(self):
        document = self._document("a.txt", b"x")
        self.Text._create_rows(1000)
        row = self._text_of(document)
        row.state = "running"
        self.Text._requeue_stale()
        self.assertEqual((row.state, row.attempts), ("pending", 1))
        row.state = "running"
        row.attempts = 2
        self.Text._requeue_stale()
        self.assertEqual(row.state, "failed")

    def test_a_new_engine_version_reads_the_text_again(self):
        document = self._document("a.txt", b"first words")
        self._read_all()
        row = self._text_of(document)
        self.assertEqual((row.state, row.engine_version), ("done", ENGINE_VERSION))
        row.engine_version = ENGINE_VERSION - 1
        self.assertEqual(self.Text._requeue(100), 1)
        self.assertEqual((row.state, row.next_page), ("pending", 1))
        self.assertFalse(self.Page.search([("text_id", "=", row.id)]))
        self._read_all()
        self.assertEqual(row.state, "done")

    def test_a_file_skipped_for_memory_is_read_again_when_the_budget_grows(self):
        document = self._document("a.txt", b"x")
        self.Text._create_rows(1000)
        row = self._text_of(document)
        row.write({"state": "skipped", "memory_limit_mib": 1024})
        self.assertEqual(self.Text._requeue(100), 0)
        self.env["ir.config_parameter"].set_param("int_filemanager.memory_mib", "2048")
        self.assertEqual(self.Text._requeue(100), 1)
        self.assertEqual(row.state, "pending")

    def test_the_settings_work_at_once_and_a_wrong_value_falls_back(self):
        Params = self.env["ir.config_parameter"]
        self.assertEqual(self.Text._setting("memory_mib"), 1024)
        Params.set_param("int_filemanager.memory_mib", "300")
        self.assertEqual(self.Text._setting("memory_mib"), 300)
        Params.set_param("int_filemanager.memory_mib", "1")
        self.assertEqual(self.Text._setting("memory_mib"), 64)
        Params.set_param("int_filemanager.memory_mib", "lots")
        self.assertEqual(self.Text._setting("memory_mib"), 1024)

    # --- the reader that is stopped ----------------------------------------------

    def _fake_reader(self, script):
        """A reader that runs ``script`` (Python) instead of the real one."""
        return patch.object(
            type(self.Text), "_reader_command", lambda *_args: [sys.executable, "-c", script]
        )

    def test_a_reader_that_runs_out_of_time_keeps_the_pages_it_finished(self):
        document = self._document("a.txt", b"x")
        self.Text._create_rows(1000)
        row = self._text_of(document)
        script = (
            "import json,sys,time\n"
            "print(json.dumps({'pages': 9}), flush=True)\n"
            "print(json.dumps({'page': 1, 'text': 'first page'}), flush=True)\n"
            "print(json.dumps({'page': 2, 'text': 'second page'}), flush=True)\n"
            "time.sleep(60)\n"
        )
        started = time.monotonic()
        with self._fake_reader(script):
            row._read_text(time.monotonic() + 3)
        self.assertLess(time.monotonic() - started, 20)
        self.assertEqual((row.state, row.next_page, row.page_count, row.attempts), ("pending", 3, 9, 0))
        self.assertEqual(self.Page.search([("text_id", "=", row.id)]).mapped("page"), [1, 2])

    def test_a_page_that_never_ends_fails_after_the_tries(self):
        document = self._document("a.txt", b"x")
        self.Text._create_rows(1000)
        row = self._text_of(document)
        with self._fake_reader("import time\ntime.sleep(60)\n"), patch(f"{MODULE}.MIN_ATTEMPT_SECONDS", 1):
            for expected in ("pending", "pending", "failed"):
                row._read_text(time.monotonic() + 2)
                self.assertEqual(row.state, expected)
        self.assertEqual(row.attempts, 3)
        self.assertIn("longer", row.message)

    def test_a_short_time_left_is_no_try(self):
        document = self._document("a.txt", b"x")
        self.Text._create_rows(1000)
        row = self._text_of(document)
        with self._fake_reader("import time\ntime.sleep(60)\n"), patch(f"{MODULE}.MIN_ATTEMPT_SECONDS", 5):
            row._read_text(time.monotonic() + 2)
        self.assertEqual((row.state, row.attempts), ("pending", 0))

    def test_a_reader_that_dies_counts_as_a_failed_try(self):
        document = self._document("a.txt", b"x")
        self.Text._create_rows(1000)
        row = self._text_of(document)
        with self._fake_reader("import sys\nsys.exit(139)\n"):
            row._read_text(time.monotonic() + 30)
        self.assertEqual((row.state, row.attempts), ("pending", 1))

    def test_a_reader_that_runs_out_of_memory_skips_the_file(self):
        document = self._document("a.txt", b"x")
        self.Text._create_rows(1000)
        row = self._text_of(document)
        script = "import json\nprint(json.dumps({'error': 'memory', 'message': 'no'}))\n"
        with self._fake_reader(script):
            row._read_text(time.monotonic() + 30)
        self.assertEqual((row.state, row.memory_limit_mib), ("skipped", 1024))

    def test_a_cut_line_of_a_killed_reader_is_ignored(self):
        document = self._document("a.txt", b"x")
        self.Text._create_rows(1000)
        row = self._text_of(document)
        script = (
            "import sys,time\n"
            "sys.stdout.write('{\"page\": 1, \"text\": \"whole\"}\\n{\"page\": 2, \"te')\n"
            "sys.stdout.flush()\n"
            "time.sleep(60)\n"
        )
        with self._fake_reader(script):
            row._read_text(time.monotonic() + 3)
        self.assertEqual(self.Page.search([("text_id", "=", row.id)]).mapped("page"), [1])

    # --- the cleaner -------------------------------------------------------------

    def test_the_text_goes_with_the_last_document(self):
        first = self._document("a.txt", b"shared")
        second = self._document("b.txt", b"shared")
        self._read_all()
        row = self._text_of(first)
        pages = self.Page.search([("text_id", "=", row.id)])
        self.assertTrue(pages)
        first.unlink()
        self.assertEqual(self.Text._gc_texts()[0], 0)
        self.assertTrue(row.exists())
        second.active = False
        self.assertEqual(self.Text._gc_texts()[0], 0)  # an archived document keeps it
        second.unlink()
        self.assertEqual(self.Text._gc_texts(), (1, 0))
        self.assertFalse(row.exists())
        self.assertFalse(pages.exists())

    def test_the_cleaner_works_in_batches_and_says_what_is_left(self):
        for number in range(5):
            self.Text.create({"checksum": f"{number}" * 64})
        with patch(f"{MODULE}.GC_BATCH", 2):
            self.assertEqual([self.Text._gc_texts() for _ in range(3)], [(2, 1), (2, 1), (1, 0)])


@tagged("post_install", "-at_install")
class TestTextCron(TextCase):
    """The scheduled action: its time budget and its steps."""

    def _cron(self):
        return self.env.ref("int_filemanager_ocr.int_filemanager_text_cron")

    def _run(self):
        """Run the scheduled action as Odoo does, without the commit a test must not make."""
        self.Text.with_context(cron_id=self._cron().id)._cron_ocr()
        self.env.invalidate_all()

    def test_the_action_makes_rows_and_reads_every_file(self):
        first = self._document("a.pdf", text_files.pdf(["alpha text"]))
        second = self._document("b.txt", b"beta text")
        self._run()
        self.assertEqual(self._text_of(first).state, "done")
        self.assertEqual(self._text_of(second).state, "done")
        self.assertEqual(self._found("beta"), second)
        # Nothing to do the second time.
        self._run()

    def test_a_run_without_time_reports_the_waiting_files_and_does_nothing(self):
        self._document("a.txt", b"waiting")
        self.Text._create_rows(1000)
        reported = []
        cron_model = type(self.env["ir.cron"])
        with patch.object(cron_model, "_commit_progress", lambda _self, *args, **kw: reported.append((args, kw)) or 0), patch.object(
            type(self.Text), "_pass_deadline", lambda *_args: time.monotonic() - 1
        ):
            self.Text.with_context(cron_id=self._cron().id)._cron_ocr()
        self.assertEqual(reported, [((0,), {"remaining": self.Text.search_count([("state", "=", "pending")])})])
        self.assertEqual(self.Text.search_count([("state", "=", "running")]), 0)

    def test_the_action_is_for_the_scheduler_only(self):
        with self.assertRaises(AssertionError):
            self.Text._cron_ocr()
