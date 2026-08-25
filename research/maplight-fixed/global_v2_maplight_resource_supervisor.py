#!/usr/bin/env python3
"""Fail-stop process-tree supervisor for the G2-7C MapLight attempt.

The supervisor owns the restricted root, creates the no-network/device-minimal
sandbox, observes itself and every descendant, acknowledges explicit stage/fit
checkpoints, and removes all mutable state before returning.  It deliberately
contains no model, metric, claim, or source logic.
"""

from __future__ import annotations

import ctypes
import json
import os
import selectors
import shutil
import signal
import socket
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

SCRIPT: Final = Path(__file__).resolve()
BWRAP: Final = Path("/usr/bin/bwrap")
POLL_INTERVAL_MAXIMUM: Final = 1.0
CHECKPOINT_ENV: Final = "CYPSHIFT_G2_7C_RESOURCE_SOCKET"
GPU_ENVIRONMENT_NAMES: Final = (
    "CUDA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "ROCR_VISIBLE_DEVICES",
    "NVIDIA_VISIBLE_DEVICES",
    "ONEAPI_DEVICE_SELECTOR",
)
PROXY_ENVIRONMENT_NAMES: Final = (
    "ALL_PROXY",
    "FTP_PROXY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "all_proxy",
    "ftp_proxy",
    "http_proxy",
    "https_proxy",
    "no_proxy",
)


class ResourceSupervisorError(RuntimeError):
    """The supervised process violated execution or accounting invariants."""


@dataclass(frozen=True)
class ResourceLimits:
    """Conjunctive limits for one complete supervised attempt."""

    wall_seconds: float
    cpu_seconds: float
    storage_bytes: int
    rss_bytes: int
    gpu_hours: float = 0.0


@dataclass(frozen=True)
class ResourceObservation:
    """Aggregate observations that contain no row-level scientific data."""

    wall_seconds: float
    cpu_seconds: float
    peak_storage_bytes: int
    peak_simultaneous_rss_bytes: int
    gpu_hours: float
    checkpoints_acknowledged: int
    descendant_processes_observed: int
    return_code: int | None
    cleanup_complete: bool
    network_namespace_isolated: bool
    gpu_environment_hidden: bool
    detached_children_observed: int
    warnings_observed: int


@dataclass(frozen=True)
class _ProcessStat:
    pid: int
    ppid: int
    pgrp: int
    session: int
    cpu_seconds_with_reaped_children: float
    rss_bytes: int
    start_ticks: int


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ResourceSupervisorError(message)


def _safe_exact_root(path: Path, label: str) -> Path:
    resolved = path.resolve(strict=False)
    _require(path.is_absolute(), f"{label} is not absolute")
    _require(".." not in path.parts, f"{label} contains parent traversal")
    _require(resolved not in {Path("/"), Path.home()}, f"{label} is too broad")
    _require(len(resolved.parts) >= 4, f"{label} is too broad")
    _require(
        not any(parent.is_symlink() for parent in path.parents),
        f"{label} has a symlinked parent",
    )
    return resolved


def _cleanup_exact_root(path: Path, label: str) -> None:
    root = _safe_exact_root(path, label)
    if not root.exists() and not root.is_symlink():
        return
    _require(root.is_dir() and not root.is_symlink(), f"{label} is not a directory")
    for child in sorted(
        root.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        _require(not child.is_symlink(), f"{label} contains a symlink")
        try:
            os.chmod(child, 0o755 if child.is_dir() else 0o600)
        except OSError:
            pass
    os.chmod(root, 0o700)
    shutil.rmtree(root)


def _allocated_bytes(root: Path) -> int:
    """Return allocated bytes and reject symlink/traversal ambiguity."""

    if not root.exists():
        return 0
    _require(root.is_dir() and not root.is_symlink(), "restricted root differs")
    total = root.stat(follow_symlinks=False).st_blocks * 512
    for path in root.rglob("*"):
        _require(not path.is_symlink(), "restricted root contains a symlink")
        total += path.stat(follow_symlinks=False).st_blocks * 512
    return total


def _process_stat(pid: int) -> _ProcessStat | None:
    try:
        raw = (Path("/proc") / str(pid) / "stat").read_text(encoding="ascii")
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return None
    close = raw.rfind(")")
    if close < 0:
        return None
    fields = raw[close + 2 :].split()
    if len(fields) < 22:
        return None
    ticks = os.sysconf("SC_CLK_TCK")
    page_size = os.sysconf("SC_PAGE_SIZE")
    cpu_ticks = sum(int(fields[index]) for index in (11, 12, 13, 14))
    return _ProcessStat(
        pid=pid,
        ppid=int(fields[1]),
        pgrp=int(fields[2]),
        session=int(fields[3]),
        cpu_seconds_with_reaped_children=cpu_ticks / ticks,
        rss_bytes=max(0, int(fields[21])) * page_size,
        start_ticks=int(fields[19]),
    )


def _all_process_stats() -> dict[int, _ProcessStat]:
    observed: dict[int, _ProcessStat] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        stat = _process_stat(int(entry.name))
        if stat is not None:
            observed[stat.pid] = stat
    return observed


def _descendants(root_pid: int) -> dict[int, _ProcessStat]:
    all_stats = _all_process_stats()
    children: dict[int, list[int]] = {}
    for stat in all_stats.values():
        children.setdefault(stat.ppid, []).append(stat.pid)
    pending = [root_pid]
    pids: set[int] = set()
    while pending:
        pid = pending.pop()
        if pid in pids:
            continue
        pids.add(pid)
        pending.extend(children.get(pid, ()))
    return {pid: all_stats[pid] for pid in pids if pid in all_stats}


def _set_subreaper() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    prctl = libc.prctl
    prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    prctl.restype = ctypes.c_int
    if prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        observed = ctypes.get_errno()
        raise ResourceSupervisorError(
            f"cannot become child subreaper: {os.strerror(observed)}"
        )


def _kill_process_tree(root_pid: int, tracked: set[int]) -> None:
    try:
        os.killpg(root_pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    for pid in sorted(tracked, reverse=True):
        if pid == os.getpid():
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline and _descendants(root_pid):
        time.sleep(0.01)
    try:
        os.killpg(root_pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    for pid in sorted(tracked, reverse=True):
        if pid == os.getpid():
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _checkpoint_listener(directory: int, name: str) -> socket.socket:
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    previous = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fchdir(directory)
        listener.bind(name)
        os.chmod(name, 0o600)
    finally:
        os.fchdir(previous)
        os.close(previous)
    listener.listen(64)
    listener.setblocking(False)
    return listener


def resource_checkpoint(label: str, *, timeout_seconds: float = 5.0) -> None:
    """Request an immediate supervisor sample before or after a stage/fit."""

    _require(
        label.startswith(("before:", "after:", "stage:")),
        "resource checkpoint label differs",
    )
    socket_path = os.environ.get(CHECKPOINT_ENV)
    _require(socket_path is not None, "resource supervisor checkpoint is unavailable")
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout_seconds)
    try:
        client.connect(socket_path)
        client.sendall((label + "\n").encode("utf-8"))
        reply = client.recv(256)
    except OSError as exc:
        raise ResourceSupervisorError("resource checkpoint failed") from exc
    finally:
        client.close()
    _require(reply == b"OK\n", "resource checkpoint rejected")


def _sandbox_command(
    command: Sequence[str],
    *,
    restricted_root: Path,
    control_alias: Path,
    writable_publication_parent: Path | None,
) -> list[str]:
    _require(BWRAP.is_file(), "bubblewrap is unavailable")
    wrapped = [
        str(BWRAP),
        "--die-with-parent",
        "--unshare-net",
        "--ro-bind",
        "/",
        "/",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--bind",
        str(restricted_root),
        str(restricted_root),
        "--bind",
        str(restricted_root),
        str(control_alias),
    ]
    if writable_publication_parent is not None:
        wrapped.extend(
            [
                "--bind",
                str(writable_publication_parent),
                str(writable_publication_parent),
            ]
        )
    for name in GPU_ENVIRONMENT_NAMES:
        wrapped.extend(("--setenv", name, ""))
    for name in PROXY_ENVIRONMENT_NAMES:
        wrapped.extend(("--unsetenv", name))
    wrapped.extend(("--", *command))
    return wrapped


def _observation(
    *,
    started: float,
    supervisor_cpu_started: float,
    live_cpu_seconds: float,
    reaped_cpu_seconds: float,
    peak_storage_bytes: int,
    peak_rss_bytes: int,
    checkpoints: int,
    tracked: set[int],
    return_code: int | None,
    cleanup_complete: bool,
    detached: int,
    warnings_observed: int,
) -> ResourceObservation:
    return ResourceObservation(
        wall_seconds=time.monotonic() - started,
        cpu_seconds=(time.process_time() - supervisor_cpu_started)
        + max(live_cpu_seconds, reaped_cpu_seconds),
        peak_storage_bytes=peak_storage_bytes,
        peak_simultaneous_rss_bytes=peak_rss_bytes,
        gpu_hours=0.0,
        checkpoints_acknowledged=checkpoints,
        descendant_processes_observed=len(tracked),
        return_code=return_code,
        cleanup_complete=cleanup_complete,
        network_namespace_isolated=True,
        gpu_environment_hidden=True,
        detached_children_observed=detached,
        warnings_observed=warnings_observed,
    )


def run_supervised(
    command: Sequence[str],
    *,
    restricted_root: Path,
    limits: ResourceLimits,
    poll_interval_seconds: float = 0.2,
    writable_publication_parent: Path | None = None,
    publication_root: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> ResourceObservation:
    """Run one command once and remove all mutable state before returning.

    A failure raises ``ResourceSupervisorError`` only after the complete fixed
    restricted root and any partial publication root are removed.
    """

    _require(bool(command) and all(command), "supervised command differs")
    _require(
        0 < poll_interval_seconds <= POLL_INTERVAL_MAXIMUM,
        "poll interval differs",
    )
    _require(
        limits.wall_seconds > 0
        and limits.cpu_seconds > 0
        and limits.storage_bytes > 0
        and limits.rss_bytes > 0
        and limits.gpu_hours == 0.0,
        "resource limits differ",
    )
    root = _safe_exact_root(restricted_root, "restricted root")
    _require(not root.exists() and not root.is_symlink(), "restricted root exists")
    publication_parent = None
    if writable_publication_parent is not None:
        publication_parent = _safe_exact_root(
            writable_publication_parent, "publication parent"
        )
        _require(
            publication_parent.is_dir() and not publication_parent.is_symlink(),
            "publication parent differs",
        )
    if publication_root is not None:
        publication_root = _safe_exact_root(publication_root, "publication root")
        _require(
            publication_parent is not None
            and publication_root.parent == publication_parent,
            "publication root is outside its fixed parent",
        )
        _require(
            not publication_root.exists() and not publication_root.is_symlink(),
            "publication root exists",
        )

    root.mkdir(parents=True, mode=0o700)
    started = time.monotonic()
    supervisor_cpu_started = time.process_time()
    socket_name = ".resource-supervisor.sock"
    socket_path = root / socket_name
    control_alias = Path(f"/tmp/cg2c-{os.getpid()}-{time.monotonic_ns()}")
    _require(not control_alias.exists(), "supervisor control alias exists")
    control_alias.mkdir(mode=0o700)
    stdout_path = root / ".stdout.log"
    stderr_path = root / ".stderr.log"
    socket_root_descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    listener = _checkpoint_listener(socket_root_descriptor, socket_name)
    selector = selectors.DefaultSelector()
    selector.register(listener, selectors.EVENT_READ)
    child_environment = dict(os.environ)
    if environment:
        child_environment.update(environment)
    child_environment[CHECKPOINT_ENV] = str(control_alias / socket_name)
    for name in GPU_ENVIRONMENT_NAMES:
        child_environment[name] = ""
    for name in PROXY_ENVIRONMENT_NAMES:
        child_environment.pop(name, None)

    _set_subreaper()
    peak_storage = _allocated_bytes(root)
    peak_rss = _process_stat(os.getpid()).rss_bytes if _process_stat(os.getpid()) else 0
    max_live_cpu = 0.0
    reaped_cpu = 0.0
    checkpoints = 0
    tracked: set[int] = set()
    detached = 0
    return_code: int | None = None
    failure: str | None = None
    process: subprocess.Popen[bytes] | None = None

    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                _sandbox_command(
                    command,
                    restricted_root=root,
                    control_alias=control_alias,
                    writable_publication_parent=publication_parent,
                ),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                env=child_environment,
                start_new_session=True,
            )
            root_session = os.getsid(process.pid)
            root_pgrp = os.getpgid(process.pid)
            while return_code is None and failure is None:
                live = _descendants(process.pid)
                tracked.update(live)
                if live:
                    escaped = [
                        stat
                        for stat in live.values()
                        if stat.session != root_session or stat.pgrp != root_pgrp
                    ]
                    if escaped:
                        detached += len(escaped)
                        failure = (
                            "descendant detached from the supervised process group"
                        )
                    live_cpu = sum(
                        stat.cpu_seconds_with_reaped_children for stat in live.values()
                    )
                    max_live_cpu = max(max_live_cpu, live_cpu)
                    supervisor = _process_stat(os.getpid())
                    live_rss = sum(stat.rss_bytes for stat in live.values())
                    if supervisor is not None:
                        live_rss += supervisor.rss_bytes
                    peak_rss = max(peak_rss, live_rss)
                try:
                    waited, status, usage = os.wait4(process.pid, os.WNOHANG)
                except ChildProcessError:
                    waited = process.pid
                    status = 0
                    usage = None
                if waited == process.pid:
                    return_code = os.waitstatus_to_exitcode(status)
                    process.returncode = return_code
                    if usage is not None:
                        reaped_cpu = usage.ru_utime + usage.ru_stime

                for _key, _mask in selector.select(timeout=poll_interval_seconds):
                    connection, _address = listener.accept()
                    with connection:
                        connection.settimeout(1.0)
                        request = connection.recv(4096)
                        valid = request.endswith(b"\n") and request.startswith(
                            (b"before:", b"after:", b"stage:")
                        )
                        if not valid:
                            failure = "resource checkpoint request differs"
                            connection.sendall(b"REJECT\n")
                        else:
                            checkpoints += 1
                            connection.sendall(b"OK\n")

                wall = time.monotonic() - started
                storage = _allocated_bytes(root)
                peak_storage = max(peak_storage, storage)
                cpu = (time.process_time() - supervisor_cpu_started) + max_live_cpu
                if wall > limits.wall_seconds:
                    failure = "wall limit exceeded"
                elif cpu > limits.cpu_seconds:
                    failure = "CPU limit exceeded"
                elif storage > limits.storage_bytes:
                    failure = "storage limit exceeded"
                elif peak_rss > limits.rss_bytes:
                    failure = "simultaneous RSS limit exceeded"

            if failure is not None and process is not None:
                _kill_process_tree(process.pid, tracked)
                try:
                    waited, status, usage = os.wait4(process.pid, 0)
                    if waited == process.pid:
                        return_code = os.waitstatus_to_exitcode(status)
                        process.returncode = return_code
                        reaped_cpu = max(reaped_cpu, usage.ru_utime + usage.ru_stime)
                except ChildProcessError:
                    pass
        warnings = 1 if stderr_path.read_bytes() else 0
        if failure is None and warnings:
            failure = "warning or stderr output observed"
        if failure is None and return_code != 0:
            failure = f"supervised process exited {return_code}"
        if failure is None and checkpoints == 0:
            failure = "no resource checkpoint was acknowledged"
    except BaseException as exc:
        if process is not None and return_code is None:
            _kill_process_tree(process.pid, tracked)
        failure = failure or f"supervisor failure: {type(exc).__name__}"
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
    finally:
        selector.close()
        listener.close()
        os.close(socket_root_descriptor)
        if socket_path.exists() and not socket_path.is_symlink():
            socket_path.unlink()
        _cleanup_exact_root(root, "restricted root")
        control_alias.rmdir()
        if (
            failure is not None
            and publication_root is not None
            and publication_root.exists()
        ):
            _cleanup_exact_root(publication_root, "partial publication root")

    observation = _observation(
        started=started,
        supervisor_cpu_started=supervisor_cpu_started,
        live_cpu_seconds=max_live_cpu,
        reaped_cpu_seconds=reaped_cpu,
        peak_storage_bytes=peak_storage,
        peak_rss_bytes=peak_rss,
        checkpoints=checkpoints,
        tracked=tracked,
        return_code=return_code,
        cleanup_complete=not root.exists(),
        detached=detached,
        warnings_observed=warnings if "warnings" in locals() else 0,
    )
    if failure is not None:
        detail = json.dumps(asdict(observation), sort_keys=True, allow_nan=False)
        raise ResourceSupervisorError(f"{failure}; observation={detail}")
    return observation
