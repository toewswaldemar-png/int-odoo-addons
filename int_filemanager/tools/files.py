"""Removing what a failed or stopped step left on the disk."""

import contextlib
import os
import shutil


def remove_file(path):
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)


def remove_path(path):
    """Remove a file or a folder with all in it (what a stopped program left)."""
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, ignore_errors=True)
    else:
        remove_file(path)
