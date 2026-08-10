from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import cypshift.shadow_watchdog as watchdog
from cypshift.shadow import ShadowResourceLimitError
from cypshift.shadow_watchdog import (
    ResourceMonitorError,
    WatchdogResult,
    supervise_assignment,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_assignment_script() -> ModuleType:
    name = "_cypshift_assign_tdc_shadow_test"
    spec = spec_from_file_location(name, ROOT / "scripts" / "assign_tdc_shadow.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load shadow assignment script")
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


assignment_script = _load_assignment_script()


@dataclass
class _Process:
    polls: list[int | None]
    pid: int = 321
    terminated: bool = False
    killed: bool = False

    def poll(self) -> int | None:
        if len(self.polls) == 1:
            return self.polls[0]
        return self.polls.pop(0)

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float) -> int:
        del timeout
        return -15


def _popen(monkeypatch: pytest.MonkeyPatch, process: _Process) -> None:
    monkeypatch.setattr(
        watchdog,
        "_spawn",
        lambda command: process,
    )


def test_supervisor_returns_completed_child_and_uses_fixed_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _Process([None, 0])
    _popen(monkeypatch, process)
    ticks = iter((10.0, 10.1, 10.2))
    monkeypatch.setattr(watchdog, "_now", lambda: next(ticks))
    monkeypatch.setattr(watchdog, "_rss_gib", lambda pid: 0.25)
    sleeps: list[float] = []
    monkeypatch.setattr(watchdog, "_sleep", sleeps.append)

    result = supervise_assignment(("python", "assignment.py"))

    assert result.returncode == 0
    assert result.failure_kind is None
    assert result.peak_rss_gib == 0.25
    assert sleeps == [1.0]
    assert not process.terminated


def test_supervisor_stops_runtime_overrun(monkeypatch: pytest.MonkeyPatch) -> None:
    process = _Process([None])
    _popen(monkeypatch, process)
    ticks = iter((0.0, watchdog.MAX_RUNTIME_SECONDS + 0.001))
    monkeypatch.setattr(watchdog, "_now", lambda: next(ticks))
    monkeypatch.setattr(
        watchdog,
        "_rss_gib",
        lambda pid: pytest.fail("RSS must not be sampled after the runtime cap"),
    )

    result = supervise_assignment(("assignment",))

    assert result.failure_kind == "runtime_limit_exceeded"
    assert result.peak_rss_gib is None
    assert process.terminated


def test_supervisor_rejects_child_that_completed_after_runtime_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _Process([0])
    _popen(monkeypatch, process)
    ticks = iter((0.0, watchdog.MAX_RUNTIME_SECONDS + 0.001))
    monkeypatch.setattr(watchdog, "_now", lambda: next(ticks))

    result = supervise_assignment(("assignment",))

    assert result.returncode == 0
    assert result.failure_kind == "runtime_limit_exceeded"
    assert not process.terminated


def test_supervisor_stops_rss_overrun(monkeypatch: pytest.MonkeyPatch) -> None:
    process = _Process([None])
    _popen(monkeypatch, process)
    ticks = iter((0.0, 0.1))
    monkeypatch.setattr(watchdog, "_now", lambda: next(ticks))
    monkeypatch.setattr(watchdog, "_rss_gib", lambda pid: 12.0001)

    result = supervise_assignment(("assignment",))

    assert result.failure_kind == "peak_rss_limit_exceeded"
    assert result.peak_rss_gib == 12.0001
    assert process.terminated


def test_supervisor_fails_closed_when_rss_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _Process([None, None, None])
    _popen(monkeypatch, process)
    ticks = iter((0.0, 0.1, 0.2))
    monkeypatch.setattr(watchdog, "_now", lambda: next(ticks))
    samples = iter((0.25, None))

    def unavailable(pid: int) -> float:
        sample = next(samples)
        if sample is None:
            raise ResourceMonitorError(str(pid))
        return sample

    monkeypatch.setattr(watchdog, "_rss_gib", unavailable)
    monkeypatch.setattr(watchdog, "_sleep", lambda seconds: None)

    result = supervise_assignment(("assignment",))

    assert result.failure_kind == "rss_monitor_unavailable"
    assert result.peak_rss_gib is None
    assert process.terminated


def test_missing_rss_after_child_exit_is_not_a_monitor_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _Process([None, 0])
    _popen(monkeypatch, process)
    ticks = iter((0.0, 0.1))
    monkeypatch.setattr(watchdog, "_now", lambda: next(ticks))

    def unavailable(pid: int) -> float:
        raise ResourceMonitorError(str(pid))

    monkeypatch.setattr(watchdog, "_rss_gib", unavailable)

    result = supervise_assignment(("assignment",))

    assert result.returncode == 0
    assert result.failure_kind is None
    assert not process.terminated


def test_rss_uses_macos_ps_kib(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(watchdog.platform, "system", lambda: "Darwin")
    observed: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        observed.append(command)
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": 1.0,
        }
        return subprocess.CompletedProcess(command, 0, "12582912\n", "")

    monkeypatch.setattr(subprocess, "run", run)

    assert watchdog._rss_gib(321) == 12.0
    assert observed == [["/bin/ps", "-o", "rss=", "-p", "321"]]


def test_rss_rejects_unpinned_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(watchdog.platform, "system", lambda: "Linux")
    with pytest.raises(ResourceMonitorError, match="pinned macOS"):
        watchdog._rss_gib(321)


def test_rss_timeout_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(watchdog.platform, "system", lambda: "Darwin")

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        raise subprocess.TimeoutExpired(command, 1.0)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ResourceMonitorError, match="cannot execute"):
        watchdog._rss_gib(321)


def _script_paths(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    return (
        tmp_path / "contract",
        tmp_path / "implementation",
        tmp_path / "rows",
        tmp_path / "manifest",
        tmp_path / "lock",
    )


def _command_path(command: list[str], option: str) -> Path:
    return Path(command[command.index(option) + 1])


def test_staged_success_is_promoted_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = "a" * 40
    output = tmp_path / "final"
    monkeypatch.setattr(
        assignment_script, "clean_source_revision", lambda repository: revision
    )

    def supervise(command: list[str]) -> WatchdogResult:
        staged = _command_path(command, "--out")
        staged.mkdir()
        (staged / "shadow_rows.csv").write_text("rows\n", encoding="utf-8")
        (staged / "shadow_assignment_receipt.json").write_text("{}\n", encoding="utf-8")
        return WatchdogResult(0, None, 1.0, 0.25)

    monkeypatch.setattr(assignment_script, "supervise_assignment", supervise)

    assignment_script._run_supervised(*_script_paths(tmp_path), output)

    assert (output / "shadow_rows.csv").read_text(encoding="utf-8") == "rows\n"
    assert not list(tmp_path.glob(".final.shadow-assignment-*"))


def test_resource_kill_discards_partial_stage_before_failure_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = "a" * 40
    output = tmp_path / "final"
    monkeypatch.setattr(
        assignment_script, "clean_source_revision", lambda repository: revision
    )

    def supervise(command: list[str]) -> WatchdogResult:
        staged = _command_path(command, "--out")
        staged.mkdir()
        (staged / "partial").write_text("incomplete", encoding="utf-8")
        return WatchdogResult(-15, "peak_rss_limit_exceeded", 2.0, 12.5)

    def write_receipt(*args: object, **kwargs: object) -> Path:
        assert not output.exists()
        assert not list(tmp_path.glob(".final.shadow-assignment-*"))
        assert kwargs["failure_kind"] == "peak_rss_limit_exceeded"
        output.mkdir()
        receipt = output / "shadow_assignment_failure.json"
        receipt.write_text("{}\n", encoding="utf-8")
        return receipt

    monkeypatch.setattr(assignment_script, "supervise_assignment", supervise)
    monkeypatch.setattr(
        assignment_script, "write_assignment_failure_receipt", write_receipt
    )

    with pytest.raises(SystemExit) as stopped:
        assignment_script._run_supervised(*_script_paths(tmp_path), output)

    assert stopped.value.code == 1
    assert (output / "shadow_assignment_failure.json").is_file()
    assert not (output / "partial").exists()


def test_worker_resource_status_preserves_internal_peak(tmp_path: Path) -> None:
    status = tmp_path / "resource_failure.json"
    error = ShadowResourceLimitError("peak_rss_limit_exceeded", 12.0, 12.25)

    assignment_script._write_worker_failure(status, error)
    failure = assignment_script._read_worker_failure(status)

    assert failure.failure_kind == "peak_rss_limit_exceeded"
    assert failure.elapsed_seconds == 12.0
    assert failure.peak_rss_gib == 12.25


def test_internal_resource_cap_becomes_final_failure_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = "a" * 40
    output = tmp_path / "final"
    monkeypatch.setattr(
        assignment_script, "clean_source_revision", lambda repository: revision
    )

    def supervise(command: list[str]) -> WatchdogResult:
        status = _command_path(command, "--worker-resource-status")
        assignment_script._write_worker_failure(
            status,
            ShadowResourceLimitError("peak_rss_limit_exceeded", 3.0, 12.25),
        )
        return WatchdogResult(75, None, 3.1, 0.5)

    def write_receipt(*args: object, **kwargs: object) -> Path:
        assert not list(tmp_path.glob(".final.shadow-assignment-*"))
        assert kwargs["peak_rss_gib"] == 12.25
        output.mkdir()
        receipt = output / "shadow_assignment_failure.json"
        receipt.write_text("{}\n", encoding="utf-8")
        return receipt

    monkeypatch.setattr(assignment_script, "supervise_assignment", supervise)
    monkeypatch.setattr(
        assignment_script, "write_assignment_failure_receipt", write_receipt
    )

    with pytest.raises(SystemExit) as stopped:
        assignment_script._run_supervised(*_script_paths(tmp_path), output)

    assert stopped.value.code == 1
    assert (output / "shadow_assignment_failure.json").is_file()
