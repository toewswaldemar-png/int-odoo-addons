"""Draw the first page of a PDF as a small picture. Runs as a child process of the scheduled action.

    python pdf_thumbnail.py <path> <size> <memory MiB>

It does not import Odoo (``pypdfium2`` and Pillow only), so the parent can bound it in time and
memory and kill it: a broken file can make the PDF library crash, and in the Odoo process that
would take every user's session with it.

The picture is a JPEG that fits in a square of ``size`` pixels, written to stdout. A file that
cannot be drawn (broken, needs a password, no page) writes the reason to stderr and exits with 1.
"""

import sys

import pypdfium2

JPEG_QUALITY = 80


def limit_memory(budget_mib):
    """Keep the process from growing by more than ``budget_mib`` (the address space)."""
    try:
        import resource  # noqa: PLC0415
    except ImportError:
        return
    try:
        with open("/proc/self/statm", encoding="ascii") as statm:
            current = int(statm.read().split()[0]) * resource.getpagesize()
    except (OSError, ValueError):
        current = 512 * 1024 * 1024
    _soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    wanted = current + budget_mib * 1024 * 1024
    if hard != resource.RLIM_INFINITY:
        wanted = min(wanted, hard)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (wanted, hard))
    except (ValueError, OSError):
        pass


def main(argv):
    path, size, memory_mib = argv[1], int(argv[2]), int(argv[3])
    limit_memory(memory_mib)
    try:
        document = pypdfium2.PdfDocument(path)
        try:
            page = document[0]
            width, height = page.get_size()
            image = page.render(scale=size / max(width, height)).to_pil().convert("RGB")
        finally:
            document.close()
        image.save(sys.stdout.buffer, "JPEG", quality=JPEG_QUALITY)
    except MemoryError:
        sys.stderr.write("memory: the page needs more memory than the budget.\n")
        return 1
    except Exception as error:  # noqa: BLE001 (whatever a broken file makes the library raise)
        sys.stderr.write(f"{type(error).__name__}: {error}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
