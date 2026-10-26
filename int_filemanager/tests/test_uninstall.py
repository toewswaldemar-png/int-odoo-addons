import os
import tempfile
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from .. import hooks
from ..models.int_filemanager_document import BLOB_FOLDER


@tagged("post_install", "-at_install")
class TestUninstall(TransactionCase):
    """The files of the documents do not stay in the filestore when the module goes."""

    def _uninstall(self, store):
        with patch.object(hooks, "filestore", return_value=store):
            hooks.uninstall_hook(self.env)

    def test_the_files_go_after_the_commit_and_nothing_else_does(self):
        with tempfile.TemporaryDirectory() as store:
            blobs = os.path.join(store, BLOB_FOLDER)
            os.makedirs(os.path.join(blobs, "ab"))
            attachments = os.path.join(store, "cd")
            os.makedirs(attachments)
            self._uninstall(store)
            # Not yet: if the uninstallation is rolled back, the documents need their files.
            self.assertTrue(os.path.isdir(blobs))
            self.env.cr.postcommit.run()
            self.assertFalse(os.path.exists(blobs))
            # What belongs to the core (the attachments) is not touched.
            self.assertTrue(os.path.isdir(attachments))

    def test_a_rolled_back_uninstallation_removes_nothing(self):
        with tempfile.TemporaryDirectory() as store:
            blobs = os.path.join(store, BLOB_FOLDER)
            os.makedirs(blobs)
            self._uninstall(store)
            self.env.cr.postcommit.clear()
            self.assertTrue(os.path.isdir(blobs))
