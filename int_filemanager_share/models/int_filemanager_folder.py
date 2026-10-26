from odoo import models

# The context key that the reading for the guests of a share sets (never the browser): the id of
# the folder that the share gives. Its parent is not shown, see ``_read_format``.
SHARE_ROOT_KEY = "int_filemanager_share_root"


class IntFilemanagerFolder(models.Model):
    _name = "int.filemanager.folder"
    _inherit = ["int.filemanager.folder", "int.filemanager.shareable"]
    _share_target = "folder_id"

    def _read_format(self, fnames, load="_classic_read"):
        """The shared folder has no parent for the guests of its share.

        Its parent lies outside what they may reach, and its name must not be given away. The
        search panel of the guests needs it as well: it keeps a folder only if the chain of its
        parents lies in the result completely (``_search_panel_sanitized_parent_hierarchy``),
        so a root with a parent outside would leave the panel empty. Here, where every reading
        passes (``read``, ``search_read``, ``web_read``), the root has none.
        """
        result = super()._read_format(fnames, load)
        root_id = self.env.context.get(SHARE_ROOT_KEY)
        if root_id:
            for values in result:
                if values["id"] == root_id and "parent_id" in values:
                    values["parent_id"] = False
        return result
