"""Fault injection and cross-process barrier for the v2 write-path tests
(Konzept 16, code review findings A3/A4: "Tests mit erzwungener Ueberlappung
[...], nicht durch gleichzeitiges Starten").

Generalises the pattern already proven in publish_service.fault_point()
(1.15.0 durchstich): a stage name written to the file INT_FILEMANAGER_FAULT_FILE
points at triggers either a raised exception or a hard os._exit() the next
time the write path calls fault_point() with a matching stage name. This
module adds a barrier mode so two REAL processes can be forced to interleave
at a precise point (e.g. "both past the uniqueness check, neither has
inserted yet") instead of relying on them merely being started at the same
time, which the review found unreliable (A3: "der Test hat den Wettlauf
offenbar zeitlich nicht getroffen").

Inert in production: nothing here is imported or set unless a test sets
INT_FILEMANAGER_FAULT_FILE, so fault_point() costs one environment lookup.
"""

import os
import time

FAULT_FILE_ENV = "INT_FILEMANAGER_FAULT_FILE"
DEFAULT_BARRIER_TIMEOUT_S = 30.0
DEFAULT_BARRIER_POLL_S = 0.05

# stage -> callable(), for in-process tests (TransactionCase) that want to
# intervene between two stages without a fault file and a second process.
_test_hooks = {}


class FaultInjected(RuntimeError):
    """Raised by fault_point() when a test asked for an exception at this stage."""


class FaultBarrierTimeout(RuntimeError):
    """A barrier did not reach its expected participant count in time - the
    two processes did not overlap the way the test intended."""


def fault_point(stage):
    """Call at a defined hook point in a write path (e.g. "before_insert",
    "after_commit"). A no-op unless a test registered an in-process hook for
    *stage* or pointed INT_FILEMANAGER_FAULT_FILE at a file containing:

    - "<stage>"                    -> raises FaultInjected
    - "<stage>:exit"                -> os._exit(137) (real process, no cleanup)
    - "<stage>:barrier:<n>"         -> blocks until *n* processes (including
                                       this one) have called fault_point() for
                                       this stage, then returns normally
    - "<stage>:hold:<seconds>"      -> the FIRST process to arrive claims the
                                       spec (deletes the file) and sleeps that
                                       long; every later arrival, including a
                                       retry of the same request, passes
                                       untouched. Lets a test keep a row lock
                                       held past lock_timeout without the
                                       holder's own retry holding it again.
                                       Ends early once the file
                                       "<fault file>.release.<stage>" exists.
    """
    hook = _test_hooks.get(stage)
    if hook is not None:
        hook()
    path = os.environ.get(FAULT_FILE_ENV)
    if not path:
        return
    try:
        with open(path, encoding="utf-8") as f:
            spec = f.read().strip()
    except OSError:
        return
    name, _sep, mode = spec.partition(":")
    if name != stage:
        return
    # elif, not a sequence of ifs: os._exit() never returns in production, but a test
    # mocking it to verify the call must still stop here instead of falling through to
    # "unknown mode" below.
    if mode == "exit":
        os._exit(137)
    elif mode.startswith("barrier:"):
        count = int(mode.split(":", 2)[1])
        wait_at_barrier(f"{path}.barrier.{stage}", count)
    elif mode.startswith("hold:"):
        seconds = float(mode.split(":", 2)[1])
        try:
            # unlink is the atomic claim: exactly one racer gets past it.
            os.unlink(path)
        except OSError:
            return
        release = f"{path}.release.{stage}"
        deadline = time.monotonic() + seconds
        # A test that knows when the other side is done can end the hold early by
        # creating <fault file>.release.<stage>; otherwise it simply runs out.
        while time.monotonic() < deadline and not os.path.exists(release):
            time.sleep(DEFAULT_BARRIER_POLL_S)
    elif mode:
        raise FaultInjected(f"fault_point: unknown mode {mode!r} for stage {stage!r}")
    else:
        raise FaultInjected(f"fault_point: fault injected at stage {stage!r}")


def wait_at_barrier(
    barrier_dir,
    participant_count,
    timeout=DEFAULT_BARRIER_TIMEOUT_S,
    poll=DEFAULT_BARRIER_POLL_S,
):
    """Register this process (by pid + a monotonic tie-breaker, so two calls
    from the same pid still count twice) at *barrier_dir* and block until
    *participant_count* registrations are visible there. Forces the precise
    overlap A3 needs, instead of hoping two independently started requests
    happen to race."""
    os.makedirs(barrier_dir, exist_ok=True)
    marker = os.path.join(barrier_dir, f"{os.getpid()}.{time.monotonic_ns()}")
    with open(marker, "w", encoding="utf-8"):
        pass
    deadline = time.monotonic() + timeout
    while True:
        if len(os.listdir(barrier_dir)) >= participant_count:
            return
        if time.monotonic() >= deadline:
            raise FaultBarrierTimeout(
                f"barrier {barrier_dir!r} did not reach {participant_count} "
                f"participant(s) within {timeout}s"
            )
        time.sleep(poll)
