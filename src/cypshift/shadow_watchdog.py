"""Active resource guard for the one-shot shadow assignment."""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

POLL_SECONDS = 1.0
MAX_RUNTIME_SECONDS = 240.0 * 60.0
MAX_RSS_GIB = 12.0
_KIB_PER_GIB = 1024.0 * 1024.0
_STOP_WAIT_SECONDS = 5.0
_PS_TIMEOUT_SECONDS = 1.0

FailureKind = Literal[
    "runtime_limit_exceeded",
    "peak_rss_limit_exceeded",
    "rss_monitor_unavailable",
]


class ResourceMonitorError(RuntimeError):
    """Raised when the pinned host cannot provide a trustworthy RSS sample."""


@dataclass(frozen=True, slots=True)
class WatchdogResult:
    """Outcome of one supervised assignment process."""

    returncode: int
    failure_kind: FailureKind | None
    elapsed_seconds: float
    peak_rss_gib: float | None


def supervise_assignment(command: Sequence[str]) -> WatchdogResult:
    """Run one assignment and stop it when either frozen resource cap is exceeded."""

    if not command:
        raise ValueError("assignment command must not be empty")
    started = _now()
    process = _spawn(command)
    peak_rss_gib: float | None = None

    while True:
        returncode = process.poll()
        elapsed = _now() - started
        if elapsed > MAX_RUNTIME_SECONDS:
            return WatchdogResult(
                returncode if returncode is not None else _stop(process),
                "runtime_limit_exceeded",
                elapsed,
                peak_rss_gib,
            )
        if returncode is not None:
            return WatchdogResult(returncode, None, elapsed, peak_rss_gib)

        try:
            rss_gib = _rss_gib(process.pid)
        except ResourceMonitorError:
            # A short-lived child can exit between poll and ps. That is completion,
            # not a monitoring failure.
            returncode = process.poll()
            if returncode is not None:
                return WatchdogResult(returncode, None, elapsed, peak_rss_gib)
            return WatchdogResult(
                _stop(process),
                "rss_monitor_unavailable",
                elapsed,
                None,
            )

        peak_rss_gib = rss_gib if peak_rss_gib is None else max(peak_rss_gib, rss_gib)
        if peak_rss_gib > MAX_RSS_GIB:
            return WatchdogResult(
                _stop(process),
                "peak_rss_limit_exceeded",
                elapsed,
                peak_rss_gib,
            )
        _sleep(POLL_SECONDS)


def _rss_gib(pid: int) -> float:
    if sys.platform != "darwin":
        raise ResourceMonitorError("RSS monitoring requires the pinned macOS host")
    try:
        completed = subprocess.run(
            ["/bin/ps", "-o", "rss=", "-p", str(pid)],
            check=False,
            capture_output=True,
            text=True,
            timeout=_PS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ResourceMonitorError("cannot execute /bin/ps") from exc
    fields = completed.stdout.split()
    if completed.returncode != 0 or len(fields) != 1:
        raise ResourceMonitorError("/bin/ps did not return one RSS value")
    try:
        rss_kib = int(fields[0])
    except ValueError as exc:
        raise ResourceMonitorError("/bin/ps returned a non-integer RSS value") from exc
    if rss_kib <= 0:
        raise ResourceMonitorError("/bin/ps returned a non-positive RSS value")
    return rss_kib / _KIB_PER_GIB


def _stop(process: subprocess.Popen[bytes]) -> int:
    process.terminate()
    try:
        return process.wait(timeout=_STOP_WAIT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.wait(timeout=_STOP_WAIT_SECONDS)


def _spawn(command: Sequence[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(list(command))


def _now() -> float:
    return time.monotonic()


def _sleep(seconds: float) -> None:
    time.sleep(seconds)
