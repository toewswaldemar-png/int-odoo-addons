"""Fault injection for tests of the write paths.

The write paths call fault_point() at named stages. A test can make a stage
raise, kill the process, wait for a second process (barrier) or hold for a
while, to force a real overlap of two requests instead of hoping for one.

Inactive unless INT_FILEMANAGER_FAULT_FILE is set; then costs one lookup.
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
    """The barrier was not reached by enough processes in time."""


def fault_point(stage):
    """Trigger the fault a test configured for ``stage``, if any.

    The fault file contains one of:

    - ``<stage>``: raise FaultInjected
    - ``<stage>:exit``: os._exit(137)
    - ``<stage>:barrier:<n>``: wait until ``n`` processes reached this stage
    - ``<stage>:hold:<seconds>``: the first process to arrive sleeps that long
      (or until ``<fault file>.release.<stage>`` exists); later ones pass
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
    # elif: a test that mocks os._exit() must not fall through to "unknown mode".
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
    """Register at ``barrier_dir``, wait for ``participant_count`` registrations."""
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
