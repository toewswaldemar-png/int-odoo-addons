"""The programs that the filemanager starts: a question, a child process, a command with a limit."""

import os
import subprocess

PROBE_SECONDS = 10


def probe(command):
    """What a program writes when asked for its version or languages (empty if it fails)."""
    try:
        done = subprocess.run(  # noqa: S603 (a program found on the path, fixed arguments)
            command, capture_output=True, check=False, timeout=PROBE_SECONDS, text=True, errors="replace"
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout + done.stderr


def last_line(text):
    """The last line of a text that has something in it, short (for a message)."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1][:200] if lines else ""


def limited(command, seconds, nice, kill_after):
    """``command`` behind ``nice`` and ``timeout``: the lowest priority, and a time it may take.

    ``timeout`` stops everything the program started once ``seconds`` are up, and kills what is
    still there ``kill_after`` seconds later. ``nice`` is the absolute priority; a lower number
    than the one of this process needs a right we do not have, so the priority stays as it is then.
    """
    return [
        "nice",
        "-n",
        str(max(nice - os.nice(0), 0)),
        "timeout",
        f"--kill-after={kill_after}",
        f"{seconds:.3f}",
        *command,
    ]
