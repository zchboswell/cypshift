#!/usr/bin/env python3
"""Run the sole receipt-bound official CYP3A4 TRACE oracle attempt."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import stat
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Any, Final, cast

SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5d_official_run_config.v1"
CONTRACT_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.oracle_official_execution_contract.v1"
)
CONTRACT_ID: Final = "R5D-CYP3A4-OFFICIAL-ATTEMPT-V1"
CONTRACT_SHA256: Final = (
    "f8aadef95be8e0d719a14d08bc2a1164a03d2cf5079e9ed2dec749ee048bd700"
)
CLAIM_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5d_official_attempt_claim.v1"
RECEIPT_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5d_official_attempt_receipt.v1"
RESOLVED_CONTRACT_SHA256: Final = (
    "9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50"
)
ROOT: Final = Path(__file__).resolve().parents[1]
CONTRACT_PATH: Final = (
    ROOT / "benchmarks/openadmet_cyp_2026/oracle_official_execution_contract_v1.json"
)
CONFIG_FIELDS: Final = {
    "schema_version",
    "r2b_root",
    "r3a_root",
    "r3c_root",
    "r4_root",
    "commit_oid",
    "expected_terminal_source_sha256",
    "expected_failure_source_sha256",
}
PARENT_NAMES: Final = ("r2b", "r3a", "r3c", "r4")
FORBIDDEN_COUNTERS: Final = {
    "blinded_test_files_opened",
    "tdi_files_opened",
    "official_metric_calls",
    "submissions_created",
    "transductive_relationships",
    "inferred_anchor_candidate_pools",
}
EXPECTED_RUNTIME: Final = {
    "platform": "Linux x86_64 CPU",
    "python_version": "3.12.3",
    "numpy_version": "2.5.2",
    "sklearn_version": "1.9.0",
    "rdkit_version": "2026.3.5",
    "uv_lock_sha256": (
        "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6"
    ),
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-wrapper-sha256", required=True)
    return parser


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


def _strict_object(data: bytes, label: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"{label} contains a duplicate key")
            result[key] = value
        return result

    value = json.loads(
        data,
        object_pairs_hook=pairs,
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"{label} contains {token}")
        ),
    )
    if not isinstance(value, dict):
        raise ValueError(f"{label} differs")
    return value


def _read_stable(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("bootstrap leaf differs")
        chunks: list[bytes] = []
        while block := os.read(fd, 1 << 20):
            chunks.append(block)
        data = b"".join(chunks)
        after = os.fstat(fd)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) or len(data) != before.st_size:
            raise ValueError("bootstrap leaf changed")
        return data
    finally:
        os.close(fd)


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


def _path(value: Any, label: str) -> Path:
    if not isinstance(value, str):
        raise ValueError(f"{label} differs")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} differs")
    return path


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


def _config(data: bytes) -> dict[str, Any]:
    value = _strict_object(data, "R5D run config")
    if data != _compact(value) or set(value) != CONFIG_FIELDS:
        raise ValueError("R5D run config differs")
    if value.get("schema_version") != SCHEMA:
        raise ValueError("R5D run config schema differs")
    return value


def _contract(data: bytes) -> dict[str, Any]:
    if sha256(data).hexdigest() != CONTRACT_SHA256:
        raise ValueError("official execution contract receipt differs")
    value = _strict_object(data, "R5D execution contract")
    if (
        value.get("schema_version") != CONTRACT_SCHEMA
        or value.get("contract_id") != CONTRACT_ID
        or value.get("resolved_oracle_contract_sha256") != RESOLVED_CONTRACT_SHA256
    ):
        raise ValueError("official execution contract identity differs")
    return value


def _parent_roots(config: Mapping[str, Any]) -> dict[str, Path]:
    return {
        name: _path(config[f"{name}_root"], f"{name} root") for name in PARENT_NAMES
    }


def _verify_parents_and_sources(
    contract: Mapping[str, Any], roots: Mapping[str, Path]
) -> tuple[dict[str, Path], dict[str, str], dict[str, str]]:
    from cypshift.openadmet_oracle_private_io import (
        open_directory_no_symlinks,
        read_stable_file,
    )
    from cypshift.openadmet_transformation_io import strict_json_object

    parent_rules = contract.get("parents")
    source_rules = contract.get("source_bundle")
    source_order = contract.get("source_order")
    if (
        not isinstance(parent_rules, Mapping)
        or set(parent_rules) != set(PARENT_NAMES)
        or not isinstance(source_rules, Mapping)
        or not isinstance(source_order, list)
        or not all(isinstance(name, str) for name in source_order)
        or len(source_order) != len(set(source_order))
        or set(source_order) != set(source_rules)
    ):
        raise ValueError("official contract ancestry differs")
    parent_receipts: dict[str, str] = {}
    parent_manifests: dict[str, Mapping[str, Any]] = {}
    for name in PARENT_NAMES:
        root = roots[name]
        root_fd = open_directory_no_symlinks(root)
        os.close(root_fd)
        rule = parent_rules[name]
        if not isinstance(rule, Mapping):
            raise ValueError("official parent rule differs")
        manifest_name = rule.get("manifest_name")
        if not isinstance(manifest_name, str) or "/" in manifest_name:
            raise ValueError("official parent manifest name differs")
        data = read_stable_file(root / manifest_name)
        receipt = sha256(data).hexdigest()
        if receipt != rule.get("manifest_sha256"):
            raise ValueError("official parent manifest receipt differs")
        manifest = strict_json_object(data, f"official {name} parent")
        if manifest.get("schema_version") != rule.get("manifest_schema"):
            raise ValueError("official parent manifest schema differs")
        required_status = rule.get("required_status")
        if required_status is not None and manifest.get("status") != required_status:
            raise ValueError("official parent status differs")
        parent_receipts[name] = receipt
        parent_manifests[name] = manifest
    revision = contract.get("official_source_revision")
    if parent_manifests["r2b"].get("source_revision") != revision:
        raise ValueError("official source revision differs")

    source_paths: dict[str, Path] = {}
    source_receipts: dict[str, str] = {}
    for name in source_order:
        rule = source_rules[name]
        if (
            not isinstance(name, str)
            or not isinstance(rule, Mapping)
            or set(rule) != {"parent", "relative_path", "sha256"}
        ):
            raise ValueError("official source rule differs")
        parent = rule.get("parent")
        relative = rule.get("relative_path")
        expected = rule.get("sha256")
        if (
            not isinstance(parent, str)
            or parent not in roots
            or relative != name
            or not isinstance(relative, str)
            or "/" in relative
        ):
            raise ValueError("official source binding differs")
        receipt = _digest(expected, f"official source receipt: {name}")
        path = roots[parent] / relative
        if sha256(read_stable_file(path)).hexdigest() != receipt:
            raise ValueError("official source leaf receipt differs")
        source_paths[name] = path
        source_receipts[name] = receipt
    return source_paths, source_receipts, parent_receipts


def _claim_attempt(
    attempt_root: Path,
    claim: bytes,
    *,
    open_directory_no_symlinks: Any,
    read_stable_file: Any,
) -> str:
    if attempt_root.exists() or attempt_root.is_symlink():
        raise ValueError("official attempt has already been consumed")
    parent_fd = open_directory_no_symlinks(attempt_root.parent)
    created = False
    try:
        os.mkdir(attempt_root.name, 0o700, dir_fd=parent_fd)
        created = True
        root_fd = os.open(
            attempt_root.name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        try:
            claim_fd = os.open(
                "attempt_claim.json",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=root_fd,
            )
            try:
                if os.write(claim_fd, claim) != len(claim):
                    raise ValueError("official attempt claim write differs")
                os.fsync(claim_fd)
                os.fchmod(claim_fd, 0o444)
            finally:
                os.close(claim_fd)
            os.fsync(root_fd)
        finally:
            os.close(root_fd)
        os.fsync(parent_fd)
    except Exception:
        if created:
            # The directory itself is the durable no-retry claim. Never erase it.
            pass
        raise
    finally:
        os.close(parent_fd)
    if read_stable_file(attempt_root / "attempt_claim.json") != claim:
        raise ValueError("official attempt claim bytes differ")
    return sha256(claim).hexdigest()


def _terminal_evidence(
    terminal_root: Path, status: str
) -> tuple[dict[str, str], dict[str, int], dict[str, Any]]:
    from cypshift.openadmet_oracle_private_io import read_exact_root
    from cypshift.openadmet_oracle_terminal import (
        STATUS_FILES,
        validate_terminal_payloads,
    )
    from cypshift.openadmet_transformation_io import strict_json_object

    if status not in STATUS_FILES:
        raise ValueError("official terminal status differs")
    payloads = read_exact_root(terminal_root, STATUS_FILES[status])
    validate_terminal_payloads(payloads, status)
    primary_name = "failure.json" if status == "R5_ORACLE_FAILED" else "manifest.json"
    primary = strict_json_object(payloads[primary_name], "official terminal record")
    accounting = primary.get("operation_accounting")
    authority = primary.get("authority")
    if (
        not isinstance(accounting, Mapping)
        or not isinstance(authority, Mapping)
        or any(type(value) is not int or value < 0 for value in accounting.values())
        or any(accounting.get(name) != 0 for name in FORBIDDEN_COUNTERS)
    ):
        raise ValueError("official terminal authority or accounting differs")
    return (
        {name: sha256(payloads[name]).hexdigest() for name in sorted(payloads)},
        cast(dict[str, int], dict(accounting)),
        dict(authority),
    )


def _validate_processes(
    processes: Sequence[Any], status: str, execution: Mapping[str, Any]
) -> list[dict[str, int | str]]:
    rows = [
        {
            "index": item.index,
            "verb": item.verb,
            "pid": item.pid,
            "returncode": item.returncode,
        }
        for item in processes
    ]
    if [row["index"] for row in rows] != list(range(len(rows))) or any(
        type(row["pid"]) is not int
        or row["pid"] <= 0
        or type(row["returncode"]) is not int
        or not isinstance(row["verb"], str)
        for row in rows
    ):
        raise ValueError("official process transcript differs")
    if status in {"R5_ORACLE_NO_SIGNAL", "R5_ORACLE_SIGNAL_PASS"}:
        topology = execution.get("supported_topology")
    elif status == "R5_ORACLE_UNDERPOWERED":
        topology = execution.get("underpowered_topology")
    else:
        topology = None
    if topology is not None:
        if not isinstance(topology, Mapping) or not isinstance(
            topology.get("verbs"), Mapping
        ):
            raise ValueError("official process topology differs")
        expected = dict(topology["verbs"])
        if (
            len(rows) != topology.get("total_child_processes")
            or Counter(cast(str, row["verb"]) for row in rows) != expected
            or any(row["returncode"] != 0 for row in rows)
        ):
            raise ValueError("official process topology differs")
    return rows


def _finish_attempt_root(attempt_root: Path) -> None:
    from cypshift.openadmet_oracle_private_io import open_directory_no_symlinks

    root_fd = open_directory_no_symlinks(attempt_root)
    try:
        if set(os.listdir(root_fd)) != {
            "attempt_claim.json",
            "receipt",
            "terminal",
        }:
            raise ValueError("official attempt final file set differs")
        os.fchmod(root_fd, 0o555)
        os.fsync(root_fd)
    finally:
        os.close(root_fd)
    parent_fd = open_directory_no_symlinks(attempt_root.parent)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def main() -> None:
    args = _parser().parse_args()
    wrapper_source = sha256(_read_stable(Path(__file__).resolve())).hexdigest()
    if _digest(args.expected_wrapper_sha256, "wrapper source") != wrapper_source:
        raise ValueError("wrapper source differs")

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

    config_data = _read_stable(args.config)
    config = _config(config_data)
    commit_oid = _commit_oid(config["commit_oid"])
    terminal_source = _digest(
        config["expected_terminal_source_sha256"], "terminal source"
    )
    failure_source = _digest(config["expected_failure_source_sha256"], "failure source")
    roots = _parent_roots(config)
    _runtime_gate()
    _checkout_gate(commit_oid)
    contract = _contract(_read_stable(CONTRACT_PATH))

    source_root = (ROOT / "src").resolve()
    sys.path.insert(0, str(source_root))
    os.environ["PYTHONPATH"] = str(source_root)
    modules = tuple(
        import_module(name)
        for name in (
            "cypshift.openadmet_oracle_private_io",
            "cypshift.openadmet_oracle_runner",
            "cypshift.openadmet_oracle_terminal",
            "cypshift.openadmet_oracle_terminal_io",
            "cypshift.openadmet_transformation_io",
        )
    )
    for module in modules:
        module_path = Path(cast(str, module.__file__)).resolve()
        if not module_path.is_relative_to(source_root):
            raise ValueError("repository module import root differs")

    from cypshift.openadmet_oracle_private_io import (
        open_directory_no_symlinks,
        publish_readonly_tree,
        read_exact_root,
        read_stable_file,
    )
    from cypshift.openadmet_oracle_runner import (
        OfficialRunInput,
        run_official_oracle,
    )
    from cypshift.openadmet_oracle_terminal_io import (
        failure_source_bundle_sha256,
        terminal_source_bundle_sha256,
    )

    if terminal_source_bundle_sha256() != terminal_source:
        raise ValueError("terminal source bundle differs")
    if failure_source_bundle_sha256() != failure_source:
        raise ValueError("failure source bundle differs")
    source_paths, source_receipts, parent_receipts = _verify_parents_and_sources(
        contract, roots
    )

    execution = contract.get("execution")
    envelope_rule = contract.get("attempt_envelope")
    if not isinstance(execution, Mapping) or not isinstance(envelope_rule, Mapping):
        raise ValueError("official execution rules differ")
    attempt_root = _path(execution.get("artifact_root"), "official artifact root")
    if execution.get("attempt_id") != "r5d-cyp3a4-official-attempt-1":
        raise ValueError("official attempt identity differs")
    claim_data = _compact(
        {
            "schema_version": CLAIM_SCHEMA,
            "contract_sha256": CONTRACT_SHA256,
            "attempt_id": execution["attempt_id"],
            "commit_oid": commit_oid,
            "config_sha256": sha256(config_data).hexdigest(),
            "wrapper_source_sha256": wrapper_source,
        }
    )
    claim_sha256 = _claim_attempt(
        attempt_root,
        claim_data,
        open_directory_no_symlinks=open_directory_no_symlinks,
        read_stable_file=read_stable_file,
    )
    private_root = attempt_root / "private"
    terminal_root = attempt_root / "terminal"
    receipt_root = attempt_root / "receipt"
    result = run_official_oracle(
        OfficialRunInput(
            source_paths,
            source_receipts,
            private_root,
            terminal_root,
            commit_oid,
            terminal_source,
            failure_source,
        )
    )
    terminal_receipts, accounting, authority = _terminal_evidence(
        terminal_root, result.status
    )
    processes = _validate_processes(result.processes, result.status, execution)
    envelope = {
        "schema_version": RECEIPT_SCHEMA,
        "contract_sha256": CONTRACT_SHA256,
        "resolved_oracle_contract_sha256": RESOLVED_CONTRACT_SHA256,
        "attempt_id": execution["attempt_id"],
        "status": result.status,
        "source_revision": contract["official_source_revision"],
        "commit_oid": commit_oid,
        "config_sha256": sha256(config_data).hexdigest(),
        "claim_sha256": claim_sha256,
        "wrapper_source_sha256": wrapper_source,
        "terminal_source_sha256": terminal_source,
        "failure_source_sha256": failure_source,
        "parent_receipts": dict(sorted(parent_receipts.items())),
        "source_receipts": dict(sorted(source_receipts.items())),
        "terminal_receipts": terminal_receipts,
        "processes": processes,
        "operation_accounting": accounting,
        "authority": authority,
    }
    if set(envelope) != set(cast(Sequence[str], envelope_rule.get("fields"))):
        raise ValueError("official attempt receipt fields differ")
    envelope_data = _compact(envelope)
    publish_readonly_tree(
        receipt_root, {"official_attempt_receipt.json": envelope_data}
    )
    if (
        read_exact_root(receipt_root, ("official_attempt_receipt.json",))[
            "official_attempt_receipt.json"
        ]
        != envelope_data
    ):
        raise ValueError("official attempt receipt bytes differ")
    if private_root.exists() or private_root.is_symlink():
        raise ValueError("official private residue remains")
    _finish_attempt_root(attempt_root)
    print(
        json.dumps(
            {
                "attempt_root": str(attempt_root),
                "process_count": len(processes),
                "receipt_sha256": sha256(envelope_data).hexdigest(),
                "status": result.status,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
