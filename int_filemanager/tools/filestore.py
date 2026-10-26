"""The parts of ``ir.attachment`` that the storage of the filemanager relies on.

The files of the documents lie in the filestore of the database, next to the attachments, but are
not attachments (see ``IntFilemanagerDocument``). ``ir.attachment`` makes the path of the filestore
and the types of the files; these methods are private to the core and not promised to stay. This
is the one place that calls them, and ``tests/test_core_contract.py`` fails if an Odoo update
changes them.
"""


def filestore(env):
    """The directory of the filestore of this database."""
    return env["ir.attachment"]._filestore()


def full_path(env, relative):
    """The absolute path of a file in the filestore (``relative`` as ``ab/abcdef``)."""
    return env["ir.attachment"]._full_path(relative)


def check_contents(env, name, mimetype, head):
    """The values of a file as the core ``ir.attachment`` makes them: its type from the type the
    client gave, the file name and the head of the file; html, svg and xml become ``text/plain``
    (office formats excepted), for every user.

    :param head: the first bytes of the file (the type is guessed from no more than that)
    :return: ``{"name", "mimetype", ...}``
    """
    return (
        env["ir.attachment"]
        .with_context(image_no_postprocess=True, attachments_mime_plainxml=True)
        ._check_contents({"name": name, "mimetype": mimetype, "raw": head})
    )
