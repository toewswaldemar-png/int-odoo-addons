"""Start the text recognition (``ocrmypdf``) as a child process of the scheduled action.

    python start_ocr.py <nice> <job folder> <program> [arguments ...]

It does not import Odoo (standard library only). What it sets up for the program, and why:

- The limit on the address space (``RLIMIT_AS``) is raised to its hard value. Odoo lowers the
  soft value in the server process (in both modes) and the child inherits it; Tesseract and
  Ghostscript need more.
- The priority (``nice``) is set to the given absolute value. ``os.nice`` is relative and a
  prefork cron worker starts with 10 already.
- ``OMP_THREAD_LIMIT=1``: one thread per Tesseract process (``ocrmypdf`` sets it itself in
  recent versions; the line keeps it from depending on that).
- ``TMPDIR`` (``TEMP`` and ``TMP`` on Windows) is the job folder, so the temporary files of the
  recognition lie next to the result and are removed with it.

On POSIX it then replaces itself with the program (``execvp``), so the parent kills and
measures the program itself. Windows has no ``execvp`` that replaces the process, no
``resource`` and no ``nice``: there it starts the program and gives back its exit code.
The exit code is that of the program; 127 if it was not found.
"""

import os
import subprocess
import sys

NOT_FOUND = 127


def prepare(nice, folder):
    """Set the limits and the environment of this process, which the program then inherits."""
    os.environ["OMP_THREAD_LIMIT"] = "1"
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = folder
    try:
        import resource  # noqa: PLC0415 (does not exist on Windows)
    except ImportError:
        return
    _soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (hard, hard))
    try:
        # A lower number than the one we have needs a right we do not have: keep what we have.
        os.nice(nice - os.nice(0))
    except OSError:
        pass


def main(argv):
    if len(argv) < 4:
        sys.stderr.write(__doc__)
        return 2
    nice, folder, command = int(argv[1]), argv[2], argv[3:]
    prepare(nice, folder)
    try:
        if os.name == "nt":
            return subprocess.call(command)  # noqa: S603 (the parent names the program)
        os.execvp(command[0], command)  # noqa: S606
    except FileNotFoundError:
        sys.stderr.write(f"{command[0]}: not found\n")
        return NOT_FOUND
    return 0  # not reached on POSIX: execvp does not return


if __name__ == "__main__":
    sys.exit(main(sys.argv))
