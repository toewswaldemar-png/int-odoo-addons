from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import new_test_user, tagged

from odoo.addons.int_filemanager.tests import text_files
from odoo.addons.int_filemanager_ocr.models import int_filemanager_text_page as page_module
from odoo.addons.int_filemanager_ocr.models.int_filemanager_document import (
    CONTENT_BLOCK,
    CONTENT_WORD_LENGTH,
    CONTENT_WORDS_MAX,
)
from odoo.addons.int_filemanager_ocr.models.int_filemanager_text_page import (
    HITS_PER_FILE,
    SNIPPET_RADIUS,
    _snippet,
)

from .test_text_search import TextCase

USER_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_user"
WORDS_KEY = "int_filemanager_words"


def matched(hit):
    """The words of the excerpt that are marked."""
    return [string for string, is_match in hit["parts"] if is_match]


def excerpt(hit):
    return "".join(string for string, _is_match in hit["parts"])


@tagged("post_install", "-at_install")
class TestTextHits(TextCase):
    """Where the words of a search are: pages, excerpts, the words as they are written."""

    def _hits(self, document, *words, limit=HITS_PER_FILE):
        self._read_all()
        found = self.Page._content_hits([document.checksum], list(words), 0, limit)
        return found.get(document.checksum)

    def test_the_pages_with_a_hit_are_named(self):
        document = self._document(
            "a.pdf", text_files.pdf(["The invoice of the plumber", "Second page", "The plumber again"])
        )
        found = self._hits(document, "plumber", limit=10)
        self.assertEqual([hit["page"] for hit in found["hits"]], [1, 3])
        self.assertEqual(found["total"], 2)

    def test_a_file_without_a_hit_is_not_named(self):
        document = self._document("a.txt", b"nothing to see")
        self._read_all()
        self.assertEqual(self.Page._content_hits([document.checksum], ["plumber"]), {})

    def test_no_words_no_work(self):
        document = self._document("a.txt", b"some text")
        self._read_all()
        for words in ([], [""], ["  "]):
            with self.subTest(words=words):
                self.assertEqual(self.Page._content_hits([document.checksum], words), {})
        self.assertEqual(self.Page._content_hits([], ["text"]), {})

    def test_the_first_pages_are_given_and_the_rest_is_counted(self):
        pages = [f"The plumber on page {number}" for number in range(1, HITS_PER_FILE + 3)]
        document = self._document("a.pdf", text_files.pdf(pages))
        found = self._hits(document, "plumber")
        self.assertEqual([hit["page"] for hit in found["hits"]], list(range(1, HITS_PER_FILE + 1)))
        self.assertEqual(found["total"], HITS_PER_FILE + 2)

    def test_a_block_of_pages_starts_after_the_offset(self):
        document = self._document("a.pdf", text_files.pdf([f"The plumber on page {n}" for n in range(1, 6)]))
        self._read_all()
        pages = lambda offset, limit: [  # noqa: E731
            hit["page"]
            for hit in self.Page._content_hits([document.checksum], ["plumber"], offset, limit)[
                document.checksum
            ]["hits"]
        ]
        self.assertEqual(pages(0, 2), [1, 2])
        self.assertEqual(pages(2, 2), [3, 4])
        self.assertEqual(pages(4, 2), [5])
        self.assertEqual(self.Page._content_hits([document.checksum], ["plumber"], 5, 2), {})

    def test_the_excerpt_keeps_the_umlauts_and_the_case_of_the_file(self):
        document = self._document("a.docx", text_files.docx(["Herr Müller wohnt in der Straße"]))
        for words in ("Mueller", "Müller", "MÜLLER"):
            with self.subTest(words=words):
                [hit] = self._hits(document, words)["hits"]
                self.assertEqual(matched(hit), ["Müller"])
                self.assertEqual(excerpt(hit), "Herr Müller wohnt in der Straße")
                self.assertEqual(hit["terms"], ["Müller"])

    def test_every_form_of_the_word_is_marked_and_named_once(self):
        document = self._document("a.txt", b"Die Rechnung und die Rechnungen, die Rechnung.")
        [hit] = self._hits(document, "Rechnung")["hits"]
        self.assertEqual(matched(hit), ["Rechnung", "Rechnungen", "Rechnung"])
        self.assertEqual(hit["terms"], ["Rechnung", "Rechnungen"])

    def test_a_phrase_and_several_words_are_marked(self):
        document = self._document("a.txt", b"red apples and green pears and red cherries")
        [hit] = self._hits(document, '"green pears"')["hits"]
        self.assertEqual(matched(hit), ["green", "pears"])
        [hit] = self._hits(document, "apples", "cherries")["hits"]
        self.assertEqual(matched(hit), ["apples", "cherries"])

    def test_the_excerpt_is_cut_at_words_with_dots_where_the_text_goes_on(self):
        words = [f"word{number}" for number in range(300)]
        text = " ".join(words[:150] + ["needle"] + words[150:])
        document = self._document("a.txt", text.encode())
        [hit] = self._hits(document, "needle")["hits"]
        shown = excerpt(hit)
        self.assertTrue(shown.startswith("… word"))
        self.assertTrue(shown.endswith(" …"))
        self.assertLessEqual(len(shown), 2 * SNIPPET_RADIUS + len("needle") + 4)
        for word in shown.strip("… ").split():
            self.assertTrue(word == "needle" or word in words, word)
        self.assertEqual(matched(hit), ["needle"])

    def test_a_text_with_the_marks_in_it_gets_no_excerpt_but_a_page(self):
        document = self._document("a.txt", b"before \x02 plumber \x03 after")
        [hit] = self._hits(document, "plumber")["hits"]
        self.assertEqual((hit["page"], hit["parts"], hit["terms"]), (1, [], []))

    def test_a_folding_that_does_not_fit_gives_the_folded_text(self):
        document = self._document("a.docx", text_files.docx(["Herr Müller wohnt hier"]))
        self._read_all()
        with patch.object(page_module, "_folded_length", return_value=9):
            found = self.Page._content_hits([document.checksum], ["Müller"])
        self.assertEqual(matched(found[document.checksum]["hits"][0]), ["mueller"])

    def test_the_snippet_of_nothing_is_nothing(self):
        self.assertEqual(_snippet("text", []), [])

    # --- the field of the documents ----------------------------------------------

    def _with_words(self, documents, *words):
        return documents.with_context(**{WORDS_KEY: list(words)})

    def test_the_field_is_empty_without_words(self):
        document = self._document("a.txt", b"plumber")
        self._read_all()
        self.assertFalse(document.content_hits)
        self.assertFalse(self._with_words(document).content_hits)
        self.assertFalse(self._with_words(document, "nothing").content_hits)

    def test_the_field_gives_the_hits_for_the_words_in_the_context(self):
        document = self._document("a.pdf", text_files.pdf(["a", "the plumber"]))
        twin = self._document("b.pdf", text_files.pdf(["a", "the plumber"]))
        other = self._document("c.txt", b"something else")
        self._read_all()
        documents = self._with_words(document + twin + other, "plumber")
        self.assertEqual([hit["page"] for hit in documents[0].content_hits["hits"]], [2])
        self.assertEqual(documents[0].content_hits, documents[1].content_hits)
        self.assertFalse(documents[2].content_hits)

    def test_the_words_are_taken_as_a_text_too_and_limited(self):
        document = self._document("a.txt", b"plumber")
        self._read_all()
        self.assertTrue(self._with_words(document, "plumber").content_hits)
        self.assertTrue(document.with_context(**{WORDS_KEY: "plumber"}).content_hits)
        self.assertFalse(document.with_context(**{WORDS_KEY: 5}).content_hits)
        many = [f"nothing{number}" for number in range(30)]
        # Only the first ten are looked at.
        self.assertFalse(self._with_words(document, *many, "plumber").content_hits)

    def test_a_user_gets_hits_for_the_documents_that_he_reads_only(self):
        alice = new_test_user(self.env, login="hits_alice", groups=USER_GROUPS)
        secret = self.env["int.filemanager.folder"].create({"name": "Secret", "access_mode": "restricted"})
        shared = self.env["int.filemanager.folder"].create({"name": "Shared", "access_mode": "open"})
        hidden = self._document("secret.txt", b"the confidential plan", secret)
        twin = self._document("twin.txt", b"the confidential plan", shared)
        self._read_all()
        found = self.Document.with_user(alice).search([("content_search", "ilike", "confidential")])
        self.assertEqual(found, twin)
        hits = self._with_words(found, "confidential").content_hits
        self.assertEqual(matched(hits["hits"][0]), ["confidential"])
        # The hidden one stays hidden, whatever the context says.
        self.assertFalse(self.Document.with_user(alice).search([("id", "=", hidden.id)]))

    # --- the count and the other hits of a file -----------------------------------

    def test_the_count_is_the_pages_with_a_hit_and_the_words_go_with_the_hits(self):
        document = self._document("a.pdf", text_files.pdf([f"The plumber on page {n}" for n in range(1, 5)]))
        self._read_all()
        self.assertEqual(document.content_hit_count, 0)
        found = self._with_words(document, "plumber")
        self.assertEqual(found.content_hit_count, 4)
        self.assertEqual(found.content_hits["total"], 4)
        self.assertEqual(found.content_hits["words"], ["plumber"])
        self.assertEqual(len(found.content_hits["hits"]), HITS_PER_FILE)
        self.assertEqual(self._with_words(document, "nothing").content_hit_count, 0)

    def test_the_other_hits_come_in_blocks(self):
        document = self._document("a.pdf", text_files.pdf([f"The plumber on page {n}" for n in range(1, 6)]))
        self._read_all()
        first = document.get_content_hits(["plumber"], 0, 2)
        self.assertEqual(([hit["page"] for hit in first["hits"]], first["total"]), ([1, 2], 5))
        rest = document.get_content_hits(["plumber"], 2, 10)
        self.assertEqual([hit["page"] for hit in rest["hits"]], [3, 4, 5])
        self.assertEqual(document.get_content_hits(["plumber"], 9, 2), {"hits": [], "total": 0})
        self.assertEqual(document.get_content_hits(["nothing"]), {"hits": [], "total": 0})

    def test_a_wrong_offset_or_limit_falls_back(self):
        pages = [f"The plumber on page {n}" for n in range(1, CONTENT_BLOCK + 4)]
        document = self._document("a.pdf", text_files.pdf(pages))
        self._read_all()
        for offset, limit in ((-3, -1), ("x", None), (1.5, 0.5)):
            with self.subTest(offset=offset, limit=limit):
                found = document.get_content_hits(["plumber"], offset, limit)
                self.assertEqual(len(found["hits"]), CONTENT_BLOCK)
                self.assertEqual(found["hits"][0]["page"], 1)

    def test_the_words_are_cut_in_number_and_length(self):
        words = self.Document._content_words([f"w{n}" for n in range(30)] + [5, "  "])
        self.assertEqual(len(words), CONTENT_WORDS_MAX)
        self.assertEqual(self.Document._content_words("x" * 500), ["x" * CONTENT_WORD_LENGTH])
        self.assertEqual(self.Document._content_words(5), [])

    def test_a_user_asks_for_the_hits_of_the_documents_that_he_reads_only(self):
        bob = new_test_user(self.env, login="hits_bob", groups=USER_GROUPS)
        secret = self.env["int.filemanager.folder"].create({"name": "Secret", "access_mode": "restricted"})
        shared = self.env["int.filemanager.folder"].create({"name": "Shared", "access_mode": "open"})
        hidden = self._document("secret.txt", b"the confidential plan", secret)
        open_one = self._document("open.txt", b"the confidential plan", shared)
        self._read_all()
        found = open_one.with_user(bob).get_content_hits(["confidential"])
        self.assertEqual(found["total"], 1)
        with self.assertRaises(AccessError):
            hidden.with_user(bob).get_content_hits(["confidential"])
