"""What the design of int_blob takes from the core, shown on a real database.

Each test names the claim of the README that it backs.
"""

import base64
import hashlib
import os

import psycopg2.errors

from odoo import models
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged
from odoo.tools import SQL

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


@tagged("post_install", "-at_install")
class TestCoreAssumptions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env["ir.attachment"]
        cls.partner = cls.env["res.partner"].create({"name": "Blob owner"})

    def place_blob(self, data, mark=True):
        """Put ``data`` where the filestore keeps it, the way the planned method will."""
        checksum = hashlib.sha1(data).hexdigest()
        fname = f"{checksum[:2]}/{checksum}"
        path = self.Attachment._full_path(fname)
        if mark:
            self.Attachment._mark_for_gc(fname)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as out:
            out.write(data)
        self.addCleanup(remove, path)
        return checksum, fname, path

    def make_attachment(self, data, fname, checksum, **values):
        """The row of a blob that lies in the store: made empty, then pointed at the file.

        ``create`` and ``write`` of the core drop ``store_fname``, ``checksum`` and ``file_size``
        (they are computed from the content); the core sets them with the ``write`` of the
        base model, like ``_set_attachment_data``.
        """
        attachment = self.Attachment.sudo().create(
            {"name": "blob.bin", "mimetype": "application/octet-stream", **values}
        )
        models.Model.write(
            attachment, {"store_fname": fname, "checksum": checksum, "file_size": len(data)}
        )
        attachment.flush_recordset(["store_fname", "checksum", "file_size"])
        return attachment

    # The way the row is made.
    def test_create_and_write_drop_the_computed_fields(self):
        """``create`` and ``write`` of the core ignore ``store_fname``, ``checksum`` and ``file_size``."""
        checksum, fname, _path = self.place_blob(b"dropped")
        values = {"store_fname": fname, "checksum": checksum, "file_size": 7}
        attachment = self.Attachment.sudo().create({"name": "dropped", **values})
        self.assertFalse(attachment.store_fname)
        attachment.write(dict(values))  # the core removes the fields from the dict it is given
        self.assertFalse(attachment.store_fname)
        models.Model.write(attachment, values)
        self.assertEqual(
            (attachment.store_fname, attachment.checksum, attachment.file_size), (fname, checksum, 7)
        )

    # Open point 1: the size over 2 GB.
    def test_file_size_is_a_32_bit_column(self):
        """``file_size`` is ``int4``: a file of 2 GiB or more cannot be recorded, so the method refuses it.

        The column is not widened: a module that changes the type of a column of the core makes
        the core convert it back as soon as the module is not loaded (uninstall, update), and
        that fails for a stored size over 2 GiB, so the registry of the database does not load.
        """
        field = self.Attachment._fields["file_size"]
        self.assertEqual(field.column_type[0], "int4")
        self.env.cr.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'ir_attachment' AND column_name = 'file_size'"
        )
        self.assertEqual(self.env.cr.fetchone()[0], "integer")
        attachment = self.Attachment.create({"name": "size", "raw": b"x"})
        for size, fits in ((2**31 - 1, True), (2**31, False)):
            if fits:
                models.Model.write(attachment.sudo(), {"file_size": size})
                attachment.flush_recordset(["file_size"])
                continue
            with self.assertRaises(psycopg2.errors.NumericValueOutOfRange), self.env.cr.savepoint():
                self.env.cr.execute(
                    SQL("UPDATE ir_attachment SET file_size = %s WHERE id = %s", size, attachment.id)
                )

    # Open point 2: only the filestore.
    def test_location_db_keeps_the_data_in_the_database(self):
        """With ``ir_attachment.location = db`` the core writes no file and the cleaner does nothing."""
        self.env["ir.config_parameter"].sudo().set_param("ir_attachment.location", "db")
        self.assertEqual(self.Attachment._storage(), "db")
        attachment = self.Attachment.create({"name": "in db", "raw": b"x" * 100})
        self.assertFalse(attachment.store_fname)
        self.assertEqual(bytes(attachment.db_datas), b"x" * 100)
        self.assertIsNone(self.Attachment._gc_file_store())

    # Open point 3: the Binary field finds an attachment that was made by hand.
    def test_binary_field_reads_an_attachment_made_by_hand(self):
        """A row with ``res_model``, ``res_id`` and ``res_field`` and a file in the store is the value of the field."""
        field = self.partner._fields["image_1920"]
        self.assertTrue(field.attachment)
        checksum, fname, _path = self.place_blob(PNG)
        self.make_attachment(
            PNG,
            fname,
            checksum,
            res_model="res.partner",
            res_id=self.partner.id,
            res_field="image_1920",
            mimetype="image/png",
        )
        self.partner.invalidate_recordset(["image_1920"])
        self.assertEqual(base64.b64decode(self.partner.image_1920), PNG)

    def test_field_attachment_is_hidden_from_the_plain_search(self):
        """An attachment with ``res_field`` stays out of the usual lists of attachments."""
        data = b"hidden"
        checksum, fname, _path = self.place_blob(data)
        attachment = self.make_attachment(
            data, fname, checksum, res_model="res.partner", res_id=self.partner.id, res_field="image_1920"
        )
        domain = [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
        self.assertNotIn(attachment, self.Attachment.search(domain))
        self.assertIn(attachment, self.Attachment.with_context(skip_res_field_check=True).search(domain))

    # The owner and the rights.
    def test_access_follows_the_owner(self):
        """Who may read the owner may read the file; an attachment without an owner is for its creator."""
        user = new_test_user(self.env, login="blob_internal", groups="base.group_user")
        checksum, fname, _path = self.place_blob(b"owned")
        owned = self.make_attachment(b"owned", fname, checksum, res_model="res.partner", res_id=self.partner.id)
        orphan = self.make_attachment(b"owned", fname, checksum)
        param = self.env["ir.config_parameter"].sudo().search([], limit=1)
        forbidden_owner = self.make_attachment(
            b"owned", fname, checksum, res_model="ir.config_parameter", res_id=param.id
        )
        as_user = self.Attachment.with_user(user)
        self.assertEqual(as_user.browse(owned.id).name, "blob.bin")
        with self.assertRaises(AccessError):
            as_user.browse(orphan.id).name  # noqa: B018
        with self.assertRaises(AccessError):
            as_user.browse(forbidden_owner.id).name  # noqa: B018

    # The steps of the planned method.
    def test_checklist_removes_a_blob_without_a_row_and_keeps_one_with_a_row(self):
        """The core cleaner deletes a marked file that no row names, and spares one that a row names."""
        _checksum, _fname, lonely = self.place_blob(os.urandom(16))
        data = os.urandom(16)
        checksum, fname, kept = self.place_blob(data)
        self.make_attachment(data, fname, checksum)
        self.Attachment._gc_file_store_unsafe()
        self.assertFalse(os.path.exists(lonely))
        self.assertTrue(os.path.exists(kept))

    def test_check_contents_takes_the_head_of_a_file(self):
        """The type is found from the name and the head, the whole file is not needed."""
        for name, head, expected in (
            ("song.mp3", b"ID3" + bytes(200), "audio/mpeg"),
            ("pic.png", PNG, "image/png"),
        ):
            values = self.Attachment.with_context(
                image_no_postprocess=True, attachments_mime_plainxml=True
            )._check_contents({"name": name, "mimetype": None, "raw": head})
            self.assertEqual(values["mimetype"], expected, name)

    def test_name_is_the_sha1_and_a_taken_place_is_checked(self):
        """The core names a file by its SHA-1; a different file at the same place is refused."""
        data = os.urandom(24)
        self.assertEqual(self.Attachment._compute_checksum(data), hashlib.sha1(data).hexdigest())
        checksum, fname, path = self.place_blob(data, mark=False)
        self.assertEqual(self.Attachment._get_path(data, checksum), (fname, path))
        with open(path, "wb") as out:
            out.write(b"other content")
        with self.assertRaises(UserError):
            self.Attachment._get_path(data, checksum)
