"""Thin deterministic state-machine coordinator for the synthetic R5C run."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

from cypshift.openadmet_oracle_inner_io import EXPECTED_RUNTIME
from cypshift.openadmet_oracle_private_io import (
    open_directory_no_symlinks,
    publish_readonly_tree,
    read_exact_root,
    remove_private_root,
)
from cypshift.openadmet_oracle_runner_commands import (
    G0_LOCKED_PYTHON,
    PAIR_PYTHON,
)
from cypshift.openadmet_oracle_terminal_io import (
    failure_source_bundle_sha256,
    terminal_source_bundle_sha256,
)
from cypshift.openadmet_oracle_worker import (
    RESULT_SCHEMA,
    VERBS,
    worker_source_sha256,
)
from cypshift.openadmet_oracle_worker import (
    SCHEMA as WORKER_SCHEMA,
)
from cypshift.openadmet_transformation_io import strict_json_object

ROOT: Final = Path(__file__).resolve().parents[2]
RUNNER_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_synthetic_runner.v1"


def _zero_accounting() -> dict[str, int]:
    from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS

    return dict.fromkeys(ACCOUNTING_FIELDS, 0)


class OracleRunnerError(RuntimeError):
    """The deterministic state machine could not reach one terminal."""


class OracleProcessFailure(OracleRunnerError):
    """One fresh child returned a nonzero process status."""

    def __init__(self, verb: str, returncode: int) -> None:
        super().__init__(f"{verb} returned {returncode}")
        self.verb = verb
        self.returncode = returncode


@dataclass(frozen=True, slots=True)
class SyntheticRunInput:
    source_paths: Mapping[str, Path]
    expected_source_receipts: Mapping[str, str]
    private_root: Path
    terminal_root: Path
    commit_oid: str
    expected_terminal_source_sha256: str
    expected_failure_source_sha256: str


@dataclass(frozen=True, slots=True)
class ProcessRecord:
    index: int
    verb: str
    pid: int
    returncode: int


@dataclass(frozen=True, slots=True)
class SyntheticRunResult:
    terminal_root: Path
    status: str
    processes: tuple[ProcessRecord, ...]


@dataclass(slots=True)
class _Coordinator:
    private_root: Path
    meta_root: Path
    processes: list[ProcessRecord] = field(default_factory=list)
    stage: str = "projection"
    verified_receipts: dict[str, str] = field(default_factory=dict)
    verified_accounting: dict[str, int] = field(default_factory=_zero_accounting)

    def worker(self, verb: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if verb not in VERBS:
            raise OracleRunnerError("worker verb differs")
        index = len(self.processes)
        control_root = self.meta_root / f"control-{index:05d}"
        result_root = self.meta_root / f"result-{index:05d}"
        control_data = _compact(
            {
                "schema_version": WORKER_SCHEMA,
                "verb": verb,
                "worker_sha256": worker_source_sha256(),
                "result_root": str(result_root),
                "payload": dict(payload),
            }
        )
        publish_readonly_tree(control_root, {"control.json": control_data})
        command = (
            sys.executable,
            "-m",
            "cypshift.openadmet_oracle_worker",
            verb,
            str(control_root),
        )
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=_model_subprocess_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        self.processes.append(
            ProcessRecord(index, verb, process.pid, process.returncode)
        )
        try:
            if process.returncode != 0:
                del stdout, stderr
                raise OracleProcessFailure(verb, process.returncode)
            data = read_exact_root(result_root, ("result.json",))["result.json"]
            record = strict_json_object(data, "worker result")
            if data != _compact(record) or set(record) != {
                "schema_version",
                "verb",
                "worker_sha256",
                "result",
            }:
                raise OracleRunnerError("worker result differs")
            if (
                record["schema_version"] != RESULT_SCHEMA
                or record["verb"] != verb
                or record["worker_sha256"] != worker_source_sha256()
                or not isinstance(record["result"], Mapping)
            ):
                raise OracleRunnerError("worker result binding differs")
            return cast(Mapping[str, Any], record["result"])
        finally:
            if result_root.exists():
                remove_private_root(result_root)
            if control_root.exists():
                remove_private_root(control_root)

    def command(self, verb: str, command: tuple[str, ...]) -> None:
        """Run one accepted locked CLI once and retain only process status."""

        index = len(self.processes)
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=_model_subprocess_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        self.processes.append(
            ProcessRecord(index, verb, process.pid, process.returncode)
        )
        if process.returncode != 0:
            del stdout, stderr
            raise OracleProcessFailure(verb, process.returncode)

    def register_manifest(self, label: str, root: Path) -> dict[str, Any]:
        """Accumulate one complete independently verified child delta once."""

        from cypshift.openadmet_oracle_private_io import read_stable_file

        if (
            not label
            or label in self.verified_receipts
            or any(not (char.isalnum() or char in "_.-") for char in label)
        ):
            raise OracleRunnerError("verified child label differs")
        data = read_stable_file(root / "manifest.json")
        manifest = strict_json_object(data, "completed child manifest")
        accounting = manifest.get("operation_accounting")
        if not isinstance(accounting, Mapping):
            raise OracleRunnerError("completed child accounting differs")
        vector = dict(accounting)
        if set(vector) != set(self.verified_accounting) or any(
            type(value) is not int or value < 0 for value in vector.values()
        ):
            raise OracleRunnerError("completed child accounting differs")
        receipt = sha256(data).hexdigest()
        self.verified_receipts[label] = receipt
        for name, value in vector.items():
            self.verified_accounting[name] += cast(int, value)
        return {
            "root": str(root),
            "manifest_sha256": receipt,
            "operation_accounting": vector,
        }


def runner_source_sha256() -> str:
    from cypshift.openadmet_oracle_private_io import read_stable_file

    return sha256(read_stable_file(Path(__file__).resolve())).hexdigest()


def run_synthetic_oracle(config: SyntheticRunInput) -> SyntheticRunResult:
    """Run one fresh synthetic state machine without retry or resume."""

    try:
        _pre_gate(config)
    except Exception:
        _destination_gate(config, allow_stale_control=True)
        return _publish_pregate_failure(config)
    private_root = config.private_root
    meta_root = _meta_root(config)
    private_root.mkdir(mode=0o700)
    meta_root.mkdir(mode=0o700)
    coordinator = _Coordinator(private_root, meta_root)
    stage = "projection"
    fits_started = False
    try:
        source = coordinator.worker(
            "source",
            {
                "source_paths": {
                    name: str(path)
                    for name, path in sorted(config.source_paths.items())
                },
                "expected_receipts": dict(
                    sorted(config.expected_source_receipts.items())
                ),
                "output_root": str(private_root / "source"),
            },
        )
        source_root = _path_result(source, "root")
        source_receipts = _string_mapping(source, "receipts")
        projection = coordinator.worker(
            "project",
            {
                "source_root": str(source_root),
                "expected_receipts": source_receipts,
                "output_root": str(private_root / "projection"),
            },
        )
        projection_root = _path_result(projection, "root")
        stage = "preflight"
        support = coordinator.worker(
            "support",
            {
                "source_root": str(source_root),
                "expected_receipts": source_receipts,
                "evidence_root": str(private_root / "support-evidence"),
                "support_root": str(private_root / "support"),
            },
        )
        if support.get("support_status") == "UNDERPOWERED":
            _remove_known((projection_root, source_root))
            cleanup = coordinator.worker(
                "cleanup",
                {
                    "output_root": str(private_root / "cleanup"),
                    "capabilities": [
                        {
                            "label": "prefit-support",
                            "root": str(_path_result(support, "root")),
                            "relative_path": "support.json",
                            "sha256": _digest_result(support, "sha256"),
                        }
                    ],
                },
            )
            coordinator.worker(
                "underpowered",
                {
                    "support": {
                        "root": str(_path_result(support, "root")),
                        "sha256": _digest_result(support, "sha256"),
                    },
                    "cleanup": {
                        "root": str(_path_result(cleanup, "root")),
                        "sha256": _digest_result(cleanup, "sha256"),
                        "capabilities": [
                            {
                                "label": "prefit-support",
                                "root": str(_path_result(support, "root")),
                                "relative_path": "support.json",
                                "sha256": _digest_result(support, "sha256"),
                            }
                        ],
                    },
                    "output_root": str(config.terminal_root),
                    "source_sha256": config.expected_terminal_source_sha256,
                },
            )
            _require_empty(private_root)
            return SyntheticRunResult(
                config.terminal_root,
                "R5_ORACLE_UNDERPOWERED",
                tuple(coordinator.processes),
            )
        if support.get("support_status") != "SUPPORTED":
            raise OracleRunnerError("support status differs")
        projection_manifests = _string_mapping(projection, "manifests")
        from cypshift.openadmet_oracle_runner_full import run_supported

        fits_started = True
        status = run_supported(
            coordinator=coordinator,
            private_root=private_root,
            terminal_root=config.terminal_root,
            source_root=source_root,
            source_receipts=source_receipts,
            projection_root=projection_root,
            projection_manifests=projection_manifests,
            support_root=_path_result(support, "root"),
            support_sha256=_digest_result(support, "sha256"),
            terminal_source_sha256=config.expected_terminal_source_sha256,
        )
        _require_empty(private_root)
        return SyntheticRunResult(
            config.terminal_root, status, tuple(coordinator.processes)
        )
    except Exception as exc:
        if config.terminal_root.exists():
            raise
        if fits_started:
            return _publish_late_failure(config, coordinator, exc)
        witness = coordinator.worker(
            "purge",
            {
                "private_root": str(private_root),
                "witness_root": str(private_root / "failure-witness"),
            },
        )
        capability = {
            "label": "prefit-cleanup-witness",
            "root": str(_path_result(witness, "root")),
            "relative_path": "manifest.json",
            "sha256": _digest_result(witness, "sha256"),
        }
        cleanup = coordinator.worker(
            "cleanup",
            {
                "output_root": str(private_root / "cleanup"),
                "capabilities": [capability],
            },
        )
        coordinator.worker(
            "failed",
            {
                "record": {
                    "stage": stage,
                    "failure_code": "PROCESS",
                    "reason": "synthetic prefit stage failed",
                    "verified_receipts": {capability["label"]: capability["sha256"]},
                    "operation_accounting": _zero_accounting(),
                },
                "cleanup": {
                    "root": str(_path_result(cleanup, "root")),
                    "sha256": _digest_result(cleanup, "sha256"),
                    "capabilities": [capability],
                },
                "output_root": str(config.terminal_root),
                "source_sha256": config.expected_failure_source_sha256,
            },
        )
        _require_empty(private_root)
        return SyntheticRunResult(
            config.terminal_root,
            "R5_ORACLE_FAILED",
            tuple(coordinator.processes),
        )
    finally:
        if meta_root.exists() and not any(meta_root.iterdir()):
            meta_root.rmdir()
        if private_root.exists() and not any(private_root.iterdir()):
            private_root.rmdir()


def _pre_gate(config: SyntheticRunInput) -> None:
    _destination_gate(config)
    _validate_checkout(config.commit_oid)
    _validate_runtime()
    _validate_model_executables()
    observed_failure_source = failure_source_bundle_sha256()
    if (
        not _is_digest(config.expected_failure_source_sha256)
        or observed_failure_source != config.expected_failure_source_sha256
    ):
        raise OracleRunnerError("failure publisher source bundle differs")
    observed_source = terminal_source_bundle_sha256()
    if (
        not _is_digest(config.expected_terminal_source_sha256)
        or observed_source != config.expected_terminal_source_sha256
    ):
        raise OracleRunnerError("terminal source bundle differs")
    worker_source_sha256()
    runner_source_sha256()


def _validate_checkout(commit_oid: str) -> None:
    if not _is_commit_oid(commit_oid):
        raise OracleRunnerError("git commit OID differs")
    environment = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"}
    observed = subprocess.run(
        ("git", "rev-parse", "--verify", "HEAD"),
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not _is_commit_oid(observed) or observed != commit_oid:
        raise OracleRunnerError("git commit differs")
    dirty = subprocess.run(
        ("git", "status", "--porcelain=v1"),
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if dirty:
        raise OracleRunnerError("git worktree is not clean")


def _destination_gate(
    config: SyntheticRunInput, *, allow_stale_control: bool = False
) -> None:
    if config.private_root.exists() or config.private_root.is_symlink():
        raise OracleRunnerError("private run root already exists")
    if config.terminal_root.exists() or config.terminal_root.is_symlink():
        raise OracleRunnerError("terminal root already exists")
    for path in (config.private_root, config.terminal_root):
        if (
            not path.is_absolute()
            or path != path.absolute()
            or not path.parent.is_dir()
            or path.parent.is_symlink()
        ):
            raise OracleRunnerError("run output path differs")
        parent_fd = open_directory_no_symlinks(path.parent)
        os.close(parent_fd)
    if (
        config.private_root == config.terminal_root
        or config.private_root in config.terminal_root.parents
        or config.terminal_root in config.private_root.parents
    ):
        raise OracleRunnerError("private and terminal roots overlap")
    meta_root = _meta_root(config)
    failure_meta_root = _failure_meta_root(config)
    if failure_meta_root.exists() or failure_meta_root.is_symlink():
        raise OracleRunnerError("failure control root already exists")
    if not allow_stale_control and (meta_root.exists() or meta_root.is_symlink()):
        raise OracleRunnerError("private control root already exists")


def _publish_pregate_failure(config: SyntheticRunInput) -> SyntheticRunResult:
    private_root = config.private_root
    stale_meta_root = _meta_root(config)
    meta_root = _failure_meta_root(config)
    private_root.mkdir(mode=0o700)
    meta_root.mkdir(mode=0o700)
    coordinator = _Coordinator(private_root, meta_root)
    try:
        capabilities: list[dict[str, str]] = []
        if stale_meta_root.exists() or stale_meta_root.is_symlink():
            witness = coordinator.worker(
                "purge",
                {
                    "private_root": str(stale_meta_root),
                    "witness_root": str(stale_meta_root / "failure-witness"),
                },
            )
            capabilities.append(
                {
                    "label": "stale-control-cleanup-witness",
                    "root": str(_path_result(witness, "root")),
                    "relative_path": "manifest.json",
                    "sha256": _digest_result(witness, "sha256"),
                }
            )
        cleanup = coordinator.worker(
            "cleanup",
            {
                "output_root": str(private_root / "cleanup"),
                "capabilities": capabilities,
            },
        )
        coordinator.worker(
            "failed",
            {
                "record": {
                    "stage": "pre_gate",
                    "failure_code": "RUNTIME",
                    "reason": "synthetic runner pre gate failed",
                    "verified_receipts": {
                        item["label"]: item["sha256"] for item in capabilities
                    },
                    "operation_accounting": _zero_accounting(),
                },
                "cleanup": {
                    "root": str(_path_result(cleanup, "root")),
                    "sha256": _digest_result(cleanup, "sha256"),
                    "capabilities": capabilities,
                },
                "output_root": str(config.terminal_root),
                "source_sha256": config.expected_failure_source_sha256,
            },
        )
        _require_empty(private_root)
        return SyntheticRunResult(
            config.terminal_root,
            "R5_ORACLE_FAILED",
            tuple(coordinator.processes),
        )
    finally:
        if stale_meta_root.exists() and not any(stale_meta_root.iterdir()):
            stale_meta_root.rmdir()
        if meta_root.exists() and not any(meta_root.iterdir()):
            meta_root.rmdir()
        if private_root.exists() and not any(private_root.iterdir()):
            private_root.rmdir()


def _meta_root(config: SyntheticRunInput) -> Path:
    return config.private_root.parent / f".{config.private_root.name}-control"


def _failure_meta_root(config: SyntheticRunInput) -> Path:
    return config.terminal_root.parent / f".{config.terminal_root.name}-failure-control"


def _is_commit_oid(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdef" for char in value)


def _is_digest(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _validate_runtime() -> None:
    from cypshift.openadmet_oracle_private_io import read_stable_file

    runtime = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "sklearn_version": importlib.metadata.version("scikit-learn"),
        "rdkit_version": importlib.metadata.version("rdkit"),
        "uv_lock_sha256": sha256(read_stable_file(ROOT / "uv.lock")).hexdigest(),
    }
    if runtime != EXPECTED_RUNTIME:
        raise OracleRunnerError("root runtime differs")


def _validate_model_executables() -> None:
    if (
        not G0_LOCKED_PYTHON.is_file()
        or not PAIR_PYTHON.is_file()
        or Path(sys.executable).resolve() != PAIR_PYTHON.resolve()
    ):
        raise OracleRunnerError("model executable differs")


def _model_subprocess_environment() -> dict[str, str]:
    return {
        "PATH": os.defpath,
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }


def _publish_late_failure(
    config: SyntheticRunInput,
    coordinator: _Coordinator,
    failure: Exception,
) -> SyntheticRunResult:
    private_root = config.private_root
    witness = coordinator.worker(
        "purge",
        {
            "private_root": str(private_root),
            "witness_root": str(private_root / "failure-witness"),
        },
    )
    capability = {
        "label": "failed-run-cleanup-witness",
        "root": str(_path_result(witness, "root")),
        "relative_path": "manifest.json",
        "sha256": _digest_result(witness, "sha256"),
    }
    cleanup = coordinator.worker(
        "cleanup",
        {
            "output_root": str(private_root / "cleanup"),
            "capabilities": [capability],
        },
    )
    if isinstance(failure, OracleProcessFailure):
        child, returncode = failure.verb, failure.returncode
    else:
        child, returncode = "coordinator", 0
    reason = f"{coordinator.stage} {child} returncode {returncode}"
    receipts = {
        **dict(sorted(coordinator.verified_receipts.items())),
        capability["label"]: capability["sha256"],
    }
    coordinator.worker(
        "failed",
        {
            "record": {
                "stage": coordinator.stage,
                "failure_code": "PROCESS",
                "reason": reason,
                "verified_receipts": receipts,
                "operation_accounting": dict(coordinator.verified_accounting),
            },
            "cleanup": {
                "root": str(_path_result(cleanup, "root")),
                "sha256": _digest_result(cleanup, "sha256"),
                "capabilities": [capability],
            },
            "output_root": str(config.terminal_root),
            "source_sha256": config.expected_failure_source_sha256,
        },
    )
    _require_empty(private_root)
    return SyntheticRunResult(
        config.terminal_root,
        "R5_ORACLE_FAILED",
        tuple(coordinator.processes),
    )


def _remove_known(roots: tuple[Path, ...]) -> None:
    for root in roots:
        remove_private_root(root)


def _require_empty(root: Path) -> None:
    if any(root.iterdir()):
        raise OracleRunnerError("private run cleanup differs")


def _path_result(value: Mapping[str, Any], name: str) -> Path:
    item = value.get(name)
    if not isinstance(item, str):
        raise OracleRunnerError(f"worker {name} path differs")
    path = Path(item)
    if not path.is_absolute() or ".." in path.parts:
        raise OracleRunnerError(f"worker {name} path differs")
    return path


def _digest_result(value: Mapping[str, Any], name: str) -> str:
    item = value.get(name)
    if (
        not isinstance(item, str)
        or len(item) != 64
        or any(char not in "0123456789abcdef" for char in item)
    ):
        raise OracleRunnerError(f"worker {name} receipt differs")
    return item


def _string_mapping(value: Mapping[str, Any], name: str) -> dict[str, str]:
    item = value.get(name)
    if not isinstance(item, Mapping):
        raise OracleRunnerError(f"worker {name} mapping differs")
    result = dict(item)
    if any(
        not isinstance(key, str) or not isinstance(data, str)
        for key, data in result.items()
    ):
        raise OracleRunnerError(f"worker {name} mapping differs")
    return cast(dict[str, str], result)


def _process_reason(value: str) -> str:
    text = " ".join(value.split())
    return text[-160:] if text else "subprocess failed"


def _compact(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


__all__ = [
    "OracleRunnerError",
    "ProcessRecord",
    "RUNNER_SCHEMA",
    "SyntheticRunInput",
    "SyntheticRunResult",
    "run_synthetic_oracle",
    "runner_source_sha256",
]
