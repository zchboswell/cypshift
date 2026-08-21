#!/usr/bin/env python3
"""Run one fresh synthetic R5C oracle state machine from a path-only config."""

from __future__ import annotations

import argparse
import ctypes
import importlib.metadata
import json
import os
import platform
import secrets
import stat
import subprocess
import sys
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Any, cast

SCHEMA = "cypshift.openadmet_cyp_2026.r5c_synthetic_run_config.v1"
ROOT = Path(__file__).resolve().parents[1]
FAILURE_SCHEMA = "cypshift.openadmet_cyp_2026.r5c_oracle_failure.v1"
RESOLVED_CONTRACT_SHA256 = (
    "9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50"
)
ACCOUNTING_FIELDS = tuple(
    "direct_target_values_parsed anchor_labels_exposed_to_models "
    "query_truth_values_opened_by_scorers maplight_model_fits ridge_model_fits "
    "hierarchy_fits predictions_frozen internal_absolute_error_evaluations "
    "blinded_test_files_opened tdi_files_opened official_metric_calls "
    "submissions_created transductive_relationships inferred_anchor_candidate_pools".split()
)
SOURCE_FILES = tuple(
    "direct_observations.csv group_folds.csv campaign_episodes_public.csv "
    "campaign_episodes_truth.csv episode_label_masks.csv feature_manifest.json "
    "feature_rows.csv maplight_morgan_count.npy maplight_avalon_count.npy "
    "maplight_erg.npy maplight_rdkit_descriptors.npy morgan_binary.npy "
    "global_oof_predictions.csv global_inner_oof_predictions.csv "
    "transformation_pairs.csv episode_transformations.csv transformation_coverage.json".split()
)
FAILURE_SOURCE_FILES = tuple(
    "scripts/run_openadmet_r5c.py src/cypshift/openadmet_oracle_pair_cell_io.py "
    "src/cypshift/openadmet_oracle_private_io.py src/cypshift/openadmet_oracle_projection.py "
    "src/cypshift/openadmet_oracle_runner.py src/cypshift/openadmet_oracle_runner_cleanup.py "
    "src/cypshift/openadmet_oracle_sealed.py src/cypshift/openadmet_oracle_terminal.py "
    "src/cypshift/openadmet_oracle_terminal_cleanup.py "
    "src/cypshift/openadmet_oracle_terminal_io.py src/cypshift/openadmet_oracle_worker.py "
    "src/cypshift/openadmet_transformation_io.py".split()
)
EXPECTED_RUNTIME = {
    "platform": "Linux x86_64 CPU",
    "python_version": "3.12.3",
    "numpy_version": "2.5.2",
    "sklearn_version": "1.9.0",
    "rdkit_version": "2026.3.5",
    "uv_lock_sha256": "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6",
}
CONFIG_FIELDS = set(
    "schema_version source_paths source_receipts private_root terminal_root commit_oid "
    "expected_terminal_source_sha256 expected_failure_source_sha256".split()
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-runner-sha256", required=True)
    return parser


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{label} differs")
    return value


def _commit_oid(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError("commit OID differs")
    return value


def _read_stable(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("run config file differs")
        data = bytearray()
        while block := os.read(fd, 1 << 20):
            data.extend(block)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise ValueError("run config changed while reading")
        return bytes(data)
    finally:
        os.close(fd)


def _path(value: Any, label: str) -> Path:
    if not isinstance(value, str):
        raise ValueError(f"{label} differs")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} differs")
    return path


def _strict_object(data: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("run config differs")
            result[key] = value
        return result

    value = json.loads(
        data,
        object_pairs_hook=pairs,
        parse_constant=lambda _value: (_ for _ in ()).throw(
            ValueError("run config differs")
        ),
    )
    if not isinstance(value, dict):
        raise ValueError("run config differs")
    return value


def _failure_bundle_sha256() -> str:
    material = bytearray()
    for name in sorted(FAILURE_SOURCE_FILES):
        material.extend(name.encode())
        material.extend(b"|")
        material.extend(sha256(_read_stable(ROOT / name)).hexdigest().encode())
        material.extend(b"\n")
    return sha256(material).hexdigest()


def _runtime_gate() -> None:
    observed = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "sklearn_version": importlib.metadata.version("scikit-learn"),
        "rdkit_version": importlib.metadata.version("rdkit"),
        "uv_lock_sha256": sha256(_read_stable(ROOT / "uv.lock")).hexdigest(),
    }
    if observed != EXPECTED_RUNTIME:
        raise ValueError("root runtime differs")


def _checkout_gate(commit_oid: str) -> None:
    environment = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"}
    observed = subprocess.run(
        ("git", "rev-parse", "--verify", "HEAD"),
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if observed != commit_oid:
        raise ValueError("git commit differs")
    dirty = subprocess.run(
        ("git", "status", "--porcelain=v1"),
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if dirty:
        raise ValueError("git worktree is not clean")


def _failure_bytes(script_sha256: str, source_sha256: str) -> bytes:
    authority = dict.fromkeys(
        (
            "oracle_evidence",
            "inferred_anchor_contract",
            "model_fits",
            "predictions",
            "internal_metrics",
            "official_st_rae",
            "test_access",
            "tdi",
            "submission",
            "transduction",
        ),
        False,
    )
    record = {
        "schema_version": FAILURE_SCHEMA,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "stage": "pre_gate",
        "failure_code": "RUNTIME",
        "reason": "synthetic runner pre gate failed",
        "verified_receipts": {
            "bootstrap_source_sha256": script_sha256,
            "failure_source_sha256": source_sha256,
        },
        "operation_accounting": dict.fromkeys(ACCOUNTING_FIELDS, 0),
        "authority": authority,
    }
    return (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _publish_bootstrap_failure(
    output_root: Path, script_sha256: str, source_sha256: str
) -> None:
    parent = output_root.parent
    if (
        not output_root.is_absolute()
        or ".." in output_root.parts
        or not parent.is_dir()
        or parent.is_symlink()
        or output_root.exists()
        or output_root.is_symlink()
    ):
        raise ValueError("terminal root differs")
    stage = parent / f".r5c-bootstrap-{secrets.token_hex(12)}"
    stage.mkdir(mode=0o700)
    failure = stage / "failure.json"
    try:
        payload = _failure_bytes(script_sha256, source_sha256)
        file_fd = os.open(
            failure,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        try:
            os.write(file_fd, payload)
            os.fsync(file_fd)
            os.fchmod(file_fd, 0o444)
        finally:
            os.close(file_fd)
        if _read_stable(failure) != payload:
            raise ValueError("bootstrap failure bytes differ")
        stage.chmod(0o555)
        stage_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(stage_fd)
        finally:
            os.close(stage_fd)
        rename = ctypes.CDLL(None, use_errno=True).renameat2
        if rename(-100, os.fsencode(stage), -100, os.fsencode(output_root), 1) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
    finally:
        if stage.exists():
            stage.chmod(0o700)
            if failure.exists():
                failure.unlink()
            stage.rmdir()


def main() -> None:
    args = _parser().parse_args()
    observed = sha256(_read_stable(Path(__file__).resolve())).hexdigest()
    if _digest(args.expected_runner_sha256, "runner source") != observed:
        raise ValueError("runner source differs")
    hostile = {
        str(Path(item).resolve())
        for item in os.environ.get("PYTHONPATH", "").split(os.pathsep)
        if item
    }
    sys.path[:] = [
        item
        for item in sys.path
        if not item or str(Path(item).resolve()) not in hostile
    ]
    os.environ.pop("PYTHONPATH", None)
    os.environ["PYTHONNOUSERSITE"] = "1"
    data = _read_stable(args.config)
    config = _strict_object(data)
    terminal_root = _path(config.get("terminal_root"), "terminal root")
    try:
        canonical = (
            json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode()
        if (
            data != canonical
            or set(config) != CONFIG_FIELDS
            or config.get("schema_version") != SCHEMA
        ):
            raise ValueError("run config differs")
        paths = config.get("source_paths")
        receipts = config.get("source_receipts")
        if (
            not isinstance(paths, dict)
            or not isinstance(receipts, dict)
            or set(paths) != set(SOURCE_FILES)
            or set(receipts) != set(SOURCE_FILES)
        ):
            raise ValueError("run config source mappings differ")
        source_paths = {
            name: _path(paths[name], f"source path: {name}") for name in SOURCE_FILES
        }
        source_receipts = {
            name: _digest(receipts[name], f"source receipt: {name}")
            for name in SOURCE_FILES
        }
        private_root = _path(config["private_root"], "private root")
        commit_oid = _commit_oid(config["commit_oid"])
        terminal_source = _digest(
            config["expected_terminal_source_sha256"], "terminal source"
        )
        failure_source = _digest(
            config["expected_failure_source_sha256"], "failure source"
        )
        _runtime_gate()
        observed_failure_source = _failure_bundle_sha256()
        if observed_failure_source != failure_source:
            raise ValueError("failure publisher source bundle differs")
        _checkout_gate(commit_oid)
    except Exception:
        observed_failure_source = _failure_bundle_sha256()
        _publish_bootstrap_failure(terminal_root, observed, observed_failure_source)
        print(
            json.dumps(
                {
                    "status": "R5_ORACLE_FAILED",
                    "terminal_root": str(terminal_root),
                    "processes": [],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return

    source_root = (ROOT / "src").resolve()
    sys.path.insert(0, str(source_root))
    os.environ["PYTHONPATH"] = str(source_root)
    runner = import_module("cypshift.openadmet_oracle_runner")
    transformation_io = import_module("cypshift.openadmet_transformation_io")
    for module in (runner, transformation_io):
        module_path = Path(cast(str, module.__file__)).resolve()
        if not module_path.is_relative_to(source_root):
            raise ValueError("repository module import root differs")

    if transformation_io.strict_json_object(data, "R5C run config") != config:
        raise ValueError("run config differs")
    result = runner.run_synthetic_oracle(
        runner.SyntheticRunInput(
            source_paths,
            source_receipts,
            private_root,
            terminal_root,
            commit_oid,
            terminal_source,
            failure_source,
        )
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "terminal_root": str(result.terminal_root),
                "processes": [
                    {
                        "index": item.index,
                        "verb": item.verb,
                        "pid": item.pid,
                        "returncode": item.returncode,
                    }
                    for item in result.processes
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
