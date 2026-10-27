"""The rules of the text recognition, as plain functions: no Odoo, no files, no processes.

The scheduled action cuts the pages of a file that are scans into sections and runs ``ocrmypdf``
on one section at a time. What decides how it goes lives here, so each rule can be tried
with numbers alone:

- ``section_pages``, ``measured_seconds_per_page``, ``smoothed``, ``after_timeout``,
  ``fair_seconds``: how many pages the next section has, and what a section that ran out of time
  teaches;
- ``classify``: what to do after ``ocrmypdf`` ended (exit code and error text);
- ``page_ranges``, ``section_command``: the page list and the arguments for one section;
- ``estimate_dpi``: the resolution of an image that has none.

Times are seconds. The answers that are words ("done", "again" ...) are constants below.
"""

from typing import NamedTuple

# Time one section needs besides the pages (start of the programs, the PDF written): taken off
# the time left, and off a measured section before its time per page is worked out.
FIXED_SECONDS = 6
# Only this part of the time left is planned for the pages: the pages differ in cost.
SAFETY = 0.7
# The first section of a file has to measure the time per page: it is short.
FIRST_SECTION_PAGES = 10
MAX_SECTION_PAGES = 100
# Used while nothing is measured, to see if even the first page fits in the time left.
DEFAULT_SECONDS_PER_PAGE = 5.0
# Weight of the last section in the average of the time per page.
SMOOTHING = 0.5
# A section that is one page and had less time than this only lacked the time: no fault of the page.
MIN_COUNTING_SECONDS = 60
# In a short run the fair time is this part of the time the run gives the program.
FAIR_SHARE = 0.8
# The lowest time per page kept (zero would read as "not measured").
MIN_SECONDS_PER_PAGE = 0.1
A4_WIDTH_INCHES = 21 / 2.54
# Below this a resolution is a guess that the text may not survive; the caller warns.
LOW_DPI = 70

# The answers of ``classify``.
DONE = "done"
AGAIN = "again"  # the same section once more, perhaps with something added (``Outcome.add``)
FAIL = "fail"  # the file is given up for good
BLOCK = "block"  # the recognition as a whole stops: the setup is wrong
PAUSE = "pause"  # not now: the disk is full

# The exit code of a shell when the program is not found.
NOT_FOUND = 127

# What can be added to a section that failed, once each.
DPI, FORCE, DOWNSAMPLE = "dpi", "force", "downsample"


class Outcome(NamedTuple):
    action: str
    reason: str | None = None
    add: str | None = None
    attempts: int = 0


class Timeout(NamedTuple):
    pages: int
    seconds_per_page: float
    counts: bool


def section_pages(seconds_left, seconds_per_page, pages_left, fair=MIN_COUNTING_SECONDS):
    """Return how many pages the next section has: 0 if there is no time for even one.

    That is ``(time left - fixed time) * safety / time per page``, at least one page, at most
    ``MAX_SECTION_PAGES``, and never more than are left. For a file with nothing measured yet
    (``seconds_per_page`` 0) it is at most ``FIRST_SECTION_PAGES``, with a guessed time per
    page.

    If the time per page is so high that not even one page fits, but the time left is a fair
    time for a single page (``fair``, see ``after_timeout``), that page is tried all the same:
    otherwise a file whose time per page grew too large would never be tried again.
    """
    first = not seconds_per_page
    per_page = seconds_per_page or DEFAULT_SECONDS_PER_PAGE
    by_time = int((seconds_left - FIXED_SECONDS) * SAFETY / per_page)
    if by_time < 1:
        return 1 if pages_left >= 1 and seconds_left >= fair else 0
    return max(min(by_time, FIRST_SECTION_PAGES if first else MAX_SECTION_PAGES, pages_left), 0)


def fair_seconds(window):
    """Return the time a single page must have had to count against its file.

    That is ``MIN_COUNTING_SECONDS``, or in a run shorter than that most of the ``window`` (the
    time the run gives the program): the page must be able to have it, or a file whose page
    needs more than the run gives would never be tried again and never be given up.
    """
    return min(MIN_COUNTING_SECONDS, max(window, 0) * FAIR_SHARE)


def measured_seconds_per_page(pages, seconds):
    """Return the time per page of a section that took ``seconds`` for ``pages`` (without the fixed time).
    """
    return max((seconds - FIXED_SECONDS) / pages, MIN_SECONDS_PER_PAGE)


def smoothed(old, measured):
    """Return the new average time per page from the old one (0 if none) and the last section."""
    if not old:
        return measured
    return (1 - SMOOTHING) * old + SMOOTHING * measured


def after_timeout(pages, seconds_per_page, seconds, fair=MIN_COUNTING_SECONDS):
    """Return what to learn from a section of ``pages`` that was stopped by the time.

    The section ran for ``seconds``. ``fair`` is the time a single page must have had to count
    against the file (a run that is shorter than that lowers it, or the file could never be
    given up).

    :return: ``Timeout(pages, seconds_per_page, counts)``: the next section has half the pages
        (one at least), the time per page doubles, and ``counts`` says whether this is a try
        that counts against the file: only a single page that had a fair time and still did
        not finish.
    """
    return Timeout(
        max(pages // 2, 1),
        (seconds_per_page or DEFAULT_SECONDS_PER_PAGE) * 2,
        pages == 1 and seconds >= fair,
    )


def classify(
    exit_code,
    stderr="",
    *,
    tried=frozenset(),
    attempts=0,
    max_attempts=3,
    empty_result=False,
):
    """Decide what to do now that ``ocrmypdf`` has ended.

    :param exit_code: of the program; negative if a signal ended it
    :param stderr: what it wrote to stderr (text)
    :param tried: what was added to this section already (``DPI``, ``FORCE``, ``DOWNSAMPLE``)
    :param attempts: tries of this file that count, so far
    :param max_attempts: the tries after which the file is given up
    :param empty_result: the program said fine but wrote no PDF (or an empty one)
    :return: ``Outcome(action, reason, add, attempts)``; ``reason`` is a short code the caller
        turns into a message, ``add`` what the next try adds, ``attempts`` the new count
    """
    text = (stderr or "").lower()
    if "no space left" in text:
        return Outcome(PAUSE, "disk_full", None, attempts)
    if exit_code == 0:
        if not empty_result:
            return Outcome(DONE, None, None, attempts)
        return _once(FORCE, tried, attempts, "empty_result")
    if exit_code == 2:
        # The program refuses what it was told (an option it does not know): code 2 as well, and its
        # message names the options, ``--image-dpi`` among them. That is our fault, not the file's.
        if "usage: ocrmypdf" in text:
            return Outcome(BLOCK, "bad_setup", None, attempts)
        if "resolution (dpi)" in text:
            return _once(DPI, tried, attempts, "no_resolution")
        return Outcome(FAIL, "bad_file", None, attempts)
    if exit_code == 6:
        return _once(FORCE, tried, attempts, "already_text")
    if exit_code == 8:
        return Outcome(FAIL, "encrypted", None, attempts)
    if exit_code in (3, NOT_FOUND):
        return Outcome(BLOCK, "missing_dependency", None, attempts)
    if exit_code in (1, 9):
        return Outcome(BLOCK, "bad_setup", None, attempts)
    if exit_code == 7 and "image too large" in text:
        # A fault of the image: the same try would fail the same way.
        return _once(DOWNSAMPLE, tried, attempts, "image_too_large")
    # 7, 4, 5, 10, 15, a signal (killed for memory) ...: perhaps it was the moment, try again.
    attempts += 1
    if attempts >= max_attempts:
        return Outcome(FAIL, "gave_up", None, attempts)
    return Outcome(AGAIN, "failed", None, attempts)


def _once(add, tried, attempts, reason):
    if add in tried:
        return Outcome(FAIL, reason, None, attempts)
    return Outcome(AGAIN, reason, add, attempts)


def estimate_dpi(width_pixels):
    """Return the resolution of an image of unknown resolution, taking its width for an A4 page's.
    """
    return max(round(width_pixels / A4_WIDTH_INCHES), 1)


def page_ranges(numbers):
    """Return the pages as ``ocrmypdf --pages`` takes them: ``[3, 7, 12, 13, 14]`` is ``"3,7,12-14"``.
    """
    parts = []
    for number in sorted(set(numbers)):
        if parts and number == parts[-1][1] + 1:
            parts[-1][1] = number
        else:
            parts.append([number, number])
    return ",".join(str(first) if first == last else f"{first}-{last}" for first, last in parts)


def section_command(
    program,
    source,
    target,
    pages,
    *,
    languages,
    jobs,
    output_type,
    deskew_and_rotate=True,
    add=frozenset(),
    image_dpi=None,
):
    """Return the command line for one section: ``ocrmypdf`` on the page numbers in ``pages``.

    The other pages of the file are taken over as they are. Without ``FORCE`` pages that have
    text are left alone (``--skip-text``); with it every page is rasterized and read. Deskew
    and rotation are left out where the caller says so.

    :param add: what an earlier try of this section added, see ``classify``
    :param image_dpi: the resolution, for the try that has ``DPI`` in ``add``
    """
    command = [
        program,
        "--force-ocr" if FORCE in add else "--skip-text",
        "--pages",
        page_ranges(pages),
        "-l",
        languages,
        "-j",
        str(jobs),
        "--output-type",
        output_type,
        "--quiet",
    ]
    if deskew_and_rotate:
        command += ["--deskew", "--rotate-pages"]
    if DOWNSAMPLE in add:
        command.append("--tesseract-downsample-large-images")
    if DPI in add and image_dpi:
        command += ["--image-dpi", str(image_dpi)]
    return [*command, source, target]
