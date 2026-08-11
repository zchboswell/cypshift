#!/usr/bin/env python3
"""Run the reviewed MapLight signed-int8 parity or one label-free feature build."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn, cast

import maplight_fixed_features as features
import numpy as np
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_int8_compat_contract.json"
PARENT_CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_stage_a_contract.json"
BLOCKER_RECORD_PATH = (
    ROOT / "benchmarks/receipts/maplight_fixed_stage_a_feature_blocker.json"
)
FIXTURE_PATH = ROOT / "benchmarks/fixtures/maplight_fixed_parity_v1.csv"
FEATURE_PATH = ROOT / "research/maplight-fixed/maplight_fixed_features.py"
BUILDER_PATH = Path(__file__).resolve()
SOURCE_ROOT = (
    ROOT / "data/external/maplight_tdc/c249378c63232354d17083c83fe94fe728960a27"
)
SAFE_PARITY_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-parity-v1"
SAFE_PARITY_PATH = SAFE_PARITY_ROOT / "parity_receipt.json"
SAFE_BLOCKER_PATH = (
    ROOT
    / "artifacts/blockers/maplight-fixed-stage-a-features-v1-build-1-blocker"
    / "failure_receipt.json"
)
SHADOW_ROOT = ROOT / "artifacts/benchmarks/tdc-cyp-shadow-v1"
SHADOW_ROWS_PATH = SHADOW_ROOT / "shadow_rows.csv"
SHADOW_MANIFEST_PATH = SHADOW_ROOT / "shadow_manifest.json"
PARITY_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-upstream-int8-parity-v1"
PARITY_BLOCKER_ROOT = (
    ROOT / "artifacts/blockers/maplight-fixed-upstream-int8-parity-v1-blocker"
)
OUTPUT_PARENT = ROOT / "artifacts/benchmarks"
BLOCKER_PARENT = ROOT / "artifacts/blockers"

CONTRACT_SHA256 = "ace395a195016854f81c96777921a2fad4c2f638927d2ad15c452b5ecd915ea8"
PARENT_CONTRACT_SHA256 = (
    "e20985ecabb1aa9ceaeddc3f81ad15dc60b194e250e28de934c12a6bfb10f710"
)
BLOCKER_RECORD_SHA256 = (
    "c69bd826dabb986cd7bcc084513f1782144f916b871cde2717e5c8f41cf601a7"
)
FIXTURE_SHA256 = "70ae570bbdbb5c8a225cfd20ab72f0d8f8b43dc1a3a6b2d3356bc52f4f4a513c"
SAFE_PARITY_SHA256 = "68ee584ac87c53cdc896db6b593f3d84376e8b59573252bd6859192dfa0e94d4"
SAFE_BLOCKER_SHA256 = "f52762005d152ea5d1bce241dca7428429368220648bf60af583325b45696009"
SHADOW_ROWS_SHA256 = "b633af0cbd5aa98a03ae77eb3e021eb32b441ae8133e24a2c9eb85394e41bc5f"
SHADOW_MANIFEST_SHA256 = (
    "3eb972713d88e08420134e7776755d4e62510a5250edf99edc2021272c112656"
)
WORKERS = ("upstream", "compatible_a", "compatible_b")
UPSTREAM_ARRAYS = (
    "morgan_count",
    "avalon_count",
    "erg",
    "rdkit_descriptors",
    "maplight_fixed",
)
LOCAL_ARRAYS = ("binary_morgan", *UPSTREAM_ARRAYS)
PERSISTED_BLOCKS = (
    "binary_morgan",
    "morgan_count",
    "avalon_count",
    "erg",
    "rdkit_descriptors",
)
OPERATION_FIELDS = (
    "attempted_feature_builds",
    "completed_feature_builds",
    "source_rows_parsed",
    "exact_raw_featurizations",
    "in_memory_block_arrays_completed",
    "persisted_block_arrays",
    "staging_roots_removed",
)
ARRAY_SPECS: dict[str, tuple[tuple[int, int], np.dtype[Any]]] = {
    "binary_morgan": ((8, 2048), np.dtype(np.uint8)),
    "morgan_count": ((8, 1024), np.dtype(np.int8)),
    "avalon_count": ((8, 1024), np.dtype(np.int8)),
    "erg": ((8, 315), np.dtype("<f8")),
    "rdkit_descriptors": ((8, 200), np.dtype("<f8")),
    "maplight_fixed": ((8, 2563), np.dtype("<f8")),
}
REAL_ARRAY_SPECS: dict[str, tuple[tuple[int, int], np.dtype[Any]]] = {
    name: ((30038, shape[1]), dtype)
    for name, (shape, dtype) in ARRAY_SPECS.items()
    if name in PERSISTED_BLOCKS
}
BOUNDARIES = {127: 127, 128: -128, 144: -112}
FIXED_SLICES = {
    "morgan_count": slice(0, 1024),
    "avalon_count": slice(1024, 2048),
    "erg": slice(2048, 2363),
    "rdkit_descriptors": slice(2363, 2563),
}
PARITY_CLAIM = "Synthetic exact-upstream compatibility only; no real row or model."
PARITY_FAILURE_CLAIM = "Synthetic compatibility parity failure; no real row or model."
FEATURE_CLAIM = "Label-free exact-upstream signed-int8 features; no model or score."
FEATURE_FAILURE_CLAIM = "Label-free compatibility feature failure; no model or score."
SCIENTIFIC_ZEROS = {
    "target_values_parsed": 0,
    "model_fits": 0,
    "predictions": 0,
    "metric_evaluations": 0,
    "public_test_rows_used": 0,
    "public_test_labels_parsed": 0,
    "public_test_family_task_slots_consumed": 0,
    "gin_weight_bytes_downloaded": 0,
    "challenge_assumptions_added": 0,
}
PARITY_ACCOUNTING_KEYS = (
    "upstream_fixture_processes_attempted",
    "upstream_fixture_processes_completed",
    "compatible_fixture_processes_attempted",
    "compatible_fixture_processes_completed",
    "boundary_conversions_attempted",
    "boundary_conversions_completed",
    "fixture_arrays_generated",
    "fixture_row_loads",
    "retained_arrays",
    "real_feature_rows_parsed",
    *SCIENTIFIC_ZEROS,
)
FEATURE_ROW_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure_sha256",
    "standardized_structure_hash",
)


class CompatError(RuntimeError):
    """A compact error safe for an immutable failure receipt."""

    def __init__(
        self,
        message: str,
        *,
        kind: str = "contract_mismatch",
        stage: str = "preflight",
        block: str | None = None,
        unique_raw_index: int | None = None,
        raw_structure_sha256: str | None = None,
        expected: str | int | None = None,
        observed: str | int | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.stage = stage
        self.block = block
        self.unique_raw_index = unique_raw_index
        self.raw_structure_sha256 = raw_structure_sha256
        self.expected = expected
        self.observed = observed


def _require(condition: bool, message: str, **detail: Any) -> None:
    if not condition:
        detail.setdefault("expected", "condition to pass")
        detail.setdefault("observed", "condition failed")
        raise CompatError(message, **detail)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_hash(path: Path, expected: str) -> None:
    observed = _sha256(path) if path.is_file() and not path.is_symlink() else "missing"
    _require(
        observed == expected,
        f"input differs: {path.name}",
        expected=expected,
        observed=observed,
    )


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    _require(isinstance(value, dict), f"{path.name} is not a JSON object")
    return cast(dict[str, Any], value)


def _exact_keys(value: Mapping[str, Any], keys: Sequence[str], name: str) -> None:
    _require(set(value) == set(keys), f"{name} fields differ")


def _operation_accounting(values: Sequence[int]) -> dict[str, int]:
    _require(len(values) == len(OPERATION_FIELDS), "operation accounting width differs")
    _require(
        all(type(value) is int and value >= 0 for value in values),
        "operation accounting value differs",
    )
    return dict(zip(OPERATION_FIELDS, values, strict=True))


def _add_operations(*records: Mapping[str, int]) -> dict[str, int]:
    return {key: sum(record[key] for record in records) for key in OPERATION_FIELDS}


def _zero_accounting(value: Mapping[str, Any]) -> None:
    _exact_keys(value, tuple(SCIENTIFIC_ZEROS), "scientific accounting")
    _require(
        all(type(item) is int and item == 0 for item in value.values()),
        "scientific accounting is not exactly zero",
    )


def _read_only_regular_file(path: Path) -> bool:
    return (
        path.is_file()
        and not path.is_symlink()
        and path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) == 0
    )


def _read_only_root(root: Path) -> bool:
    return (
        root.is_dir()
        and not root.is_symlink()
        and root.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) == 0
    )


def _path_absent(path: Path) -> bool:
    return not path.exists() and not path.is_symlink()


def _import_path(name: str, path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise CompatError("module specification is unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _git(arguments: Sequence[str]) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _clean_revision() -> str:
    _require(not _git(("status", "--porcelain", "--untracked-files=all")), "dirty tree")
    revision = _git(("rev-parse", "HEAD"))
    identity = _git(
        ("show", "-s", "--format=%G?%x00%an%x00%ae%x00%cn%x00%ce", revision)
    ).split("\0")
    _require(
        identity
        == [
            "G",
            "zchboswell",
            "261114960+zchboswell@users.noreply.github.com",
            "zchboswell",
            "261114960+zchboswell@users.noreply.github.com",
        ],
        "source signature or authorship differs",
    )
    for path in (FEATURE_PATH, BUILDER_PATH):
        relative = path.relative_to(ROOT).as_posix()
        blob = subprocess.run(
            ["git", "show", f"{revision}:{relative}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        _require(
            hashlib.sha256(blob).hexdigest() == _sha256(path),
            f"tracked implementation differs: {relative}",
        )
    return revision


def _normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _verify_environment(parent: Mapping[str, Any]) -> None:
    environment = parent["compatible_environment"]
    execution_platform = environment["execution_platform"]
    expected = {
        _normalized_name(key.rsplit("@", 1)[0]): key.rsplit("@", 1)[1]
        for key in environment["resolved_package_licenses"]
    }
    observed = {
        _normalized_name(distribution.metadata["Name"]): distribution.version
        for distribution in importlib.metadata.distributions()
        if distribution.metadata["Name"]
    }
    _require(observed == expected, "installed package set differs")
    _require(platform.python_version() == "3.10.13", "Python version differs")
    _require(platform.system() == "Darwin", "operating system differs")
    _require(platform.machine() == "arm64", "architecture differs")
    _require(
        platform.mac_ver()[0]
        == str(execution_platform["operating_system"]).removeprefix("macOS "),
        "macOS version differs",
    )
    _require(
        platform.release() == execution_platform["darwin_release"],
        "Darwin release differs",
    )
    cpu = subprocess.run(
        ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _require(cpu == execution_platform["cpu"], "CPU differs")
    _require(
        _sha256(Path(sys.executable).resolve())
        == environment["interpreter"]["installed_executable_sha256"],
        "Python executable differs",
    )


def _verify_common() -> tuple[dict[str, Any], str]:
    expected = {
        CONTRACT_PATH: CONTRACT_SHA256,
        PARENT_CONTRACT_PATH: PARENT_CONTRACT_SHA256,
        BLOCKER_RECORD_PATH: BLOCKER_RECORD_SHA256,
        FIXTURE_PATH: FIXTURE_SHA256,
        SAFE_PARITY_PATH: SAFE_PARITY_SHA256,
        SAFE_BLOCKER_PATH: SAFE_BLOCKER_SHA256,
    }
    for path, digest in expected.items():
        _require_hash(path, digest)
    parent = _load_json(PARENT_CONTRACT_PATH)
    environment = parent["compatible_environment"]
    for path_key, hash_key in (
        ("project_path", "project_sha256"),
        ("lock_path", "lock_sha256"),
        ("python_version_path", "python_version_sha256"),
    ):
        _require_hash(ROOT / environment[path_key], environment[hash_key])
    repository = parent["frozen_sources"]["maplight_repository"]
    _require(
        SOURCE_ROOT == ROOT / repository["stable_ignored_root"],
        "source root path differs",
    )
    source_files = repository["files"]
    _require(_read_only_root(SOURCE_ROOT), "source root is missing or writable")
    _require(
        {path.name for path in SOURCE_ROOT.iterdir()} == set(source_files),
        "source file set differs",
    )
    for name, digest in source_files.items():
        path = SOURCE_ROOT / name
        _require(_read_only_regular_file(path), f"source is invalid: {name}")
        _require_hash(path, digest)
    contract = _load_json(CONTRACT_PATH)
    _require(
        contract.get("schema_version")
        == "cypshift.maplight_fixed_int8_compat_contract.v1"
        and contract.get("status") == "pre_result_frozen",
        "compatibility contract identity differs",
    )
    _verify_environment(parent)
    return contract, _clean_revision()


def _read_fixture() -> list[dict[str, str]]:
    with FIXTURE_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require(
            tuple(reader.fieldnames or ())
            == ("fixture_id", "pandas_index", "raw_smiles"),
            "fixture schema differs",
        )
        rows = [{key: str(value) for key, value in row.items()} for row in reader]
    _require(
        len(rows) == 8
        and [int(row["pandas_index"]) for row in rows] == [13, 2, 21, 5, 8, 3, 34, 1],
        "fixture rows or order differ",
    )
    return rows


def _array_record(
    path: Path, shape: tuple[int, int], dtype: np.dtype[Any]
) -> dict[str, object]:
    with path.open("rb") as handle:
        npy_version = np.lib.format.read_magic(handle)
    _require(
        npy_version == (1, 0),
        "array NPY version differs",
        stage="array_validation",
        expected="1.0",
        observed=".".join(str(value) for value in npy_version),
    )
    array = np.load(path, allow_pickle=False)
    _require(array.shape == shape, "array shape differs", stage="array_validation")
    _require(array.dtype == dtype, "array dtype differs", stage="array_validation")
    _require(
        array.flags.c_contiguous, "array is not C-contiguous", stage="array_validation"
    )
    _require(
        bool(np.isfinite(array).all()), "array is non-finite", stage="array_validation"
    )
    return {
        "path": path.name,
        "shape": list(array.shape),
        "dtype": str(array.dtype),
        "c_contiguous": True,
        "nonfinite_count": 0,
        "element_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
        "npy_sha256": _sha256(path),
        "npy_size_bytes": path.stat().st_size,
    }


def _direct_boundary(count: int) -> int:
    data_structs = importlib.import_module("rdkit.DataStructs")
    fingerprint = data_structs.UIntSparseIntVect(4)
    fingerprint[1] = count
    array: NDArray[np.int8] = np.zeros((0,), dtype=np.int8)
    data_structs.ConvertToNumpyArray(fingerprint, array)
    return int(array[1])


def _worker_arrays(
    worker: str,
    rows: Sequence[Mapping[str, str]],
    accounting: dict[str, int],
) -> tuple[dict[str, NDArray[Any]], tuple[str, ...]]:
    raw = tuple(row["raw_smiles"] for row in rows)
    raw_hashes = tuple(hashlib.sha256(value.encode()).hexdigest() for value in raw)
    if worker == "upstream":
        import pandas as pd  # type: ignore[import-untyped]
        from rdkit import Chem

        upstream = _import_path("pinned_maplight_compat", SOURCE_ROOT / "maplight.py")
        series = pd.Series(
            raw, index=[int(row["pandas_index"]) for row in rows], dtype=object
        )
        molecules = series.apply(Chem.MolFromSmiles)

        def call(operation: Callable[[], Any]) -> NDArray[Any]:
            return cast(NDArray[Any], operation())

        operations = (
            ("morgan_count", lambda: upstream.get_morgan_fingerprints(molecules)),
            ("avalon_count", lambda: upstream.get_avalon_fingerprints(molecules)),
            ("erg", lambda: upstream.get_erg_fingerprints(molecules)),
            ("rdkit_descriptors", lambda: upstream.get_rdkit_features(molecules)),
            ("maplight_fixed", lambda: upstream.get_fingerprints(series)),
        )
        arrays: dict[str, NDArray[Any]] = {}
        for name, operation in operations:
            arrays[name] = call(operation)
            accounting["fixture_arrays_generated"] += 1
        return arrays, tuple(upstream.get_chosen_descriptors())

    def block_completed(_name: str) -> None:
        accounting["fixture_arrays_generated"] += 1

    result, _ = features.featurize_raw_structures_upstream_int8(
        raw, raw_hashes, block_completed=block_completed
    )
    arrays = {name: getattr(result, name) for name in PERSISTED_BLOCKS}
    arrays["maplight_fixed"] = result.maplight_fixed()
    accounting["fixture_arrays_generated"] += 1
    return arrays, tuple(features.descriptor_names())


def _worker_main(worker: str, output: Path, revision: str) -> int:
    output.mkdir(parents=False, exist_ok=False)
    accounting = {
        "fixture_arrays_generated": 0,
        "fixture_row_loads": 0,
        "boundary_conversions_attempted": 0,
        "boundary_conversions_completed": 0,
    }
    try:
        _require(_clean_revision() == revision, "worker revision differs")
        rows = _read_fixture()
        accounting["fixture_row_loads"] = len(rows)
        arrays, descriptor_names = _worker_arrays(worker, rows, accounting)
        boundaries: dict[int, int] = {}
        for count in BOUNDARIES:
            accounting["boundary_conversions_attempted"] += 1
            boundaries[count] = (
                _direct_boundary(count)
                if worker == "upstream"
                else features.signed_int8_count_witness(count)
            )
            accounting["boundary_conversions_completed"] += 1
        names = UPSTREAM_ARRAYS if worker == "upstream" else LOCAL_ARRAYS
        _require(set(arrays) == set(names), "worker array set differs")
        for name in names:
            features.write_npy_v1(output / f"{name}.npy", arrays[name])
        receipt = {
            "schema_version": "cypshift.maplight_int8_compat_worker.v1",
            "worker": worker,
            "source_revision": revision,
            "fixture_rows": 8,
            "descriptor_names": list(descriptor_names),
            "arrays": list(names),
            "boundaries": {str(key): value for key, value in boundaries.items()},
            "accounting": accounting,
        }
        (output / "worker_receipt.json").write_bytes(_json_bytes(receipt))
        return 0
    except Exception as error:
        (output / "worker_failure.json").write_bytes(
            _json_bytes(
                {
                    "worker": worker,
                    "exception_class": type(error).__name__,
                    "stage": getattr(error, "stage", "worker"),
                    "block": getattr(error, "block", None),
                    "accounting": accounting,
                }
            )
        )
        return 1


def _merge_worker_accounting(
    total: dict[str, int], observed: Mapping[str, Any]
) -> None:
    keys = (
        "fixture_arrays_generated",
        "fixture_row_loads",
        "boundary_conversions_attempted",
        "boundary_conversions_completed",
    )
    _exact_keys(observed, keys, "worker accounting")
    _require(
        all(type(value) is int and value >= 0 for value in observed.values()),
        "worker accounting value differs",
    )
    for key in keys:
        total[key] += observed[key]


def _run_worker(
    worker: str, root: Path, revision: str, accounting: dict[str, int]
) -> Path:
    output = root / worker
    process = subprocess.run(
        [
            sys.executable,
            str(BUILDER_PATH),
            "--_worker",
            worker,
            "--_worker-output",
            str(output),
            "--_worker-revision",
            revision,
        ],
        cwd=ROOT,
        check=False,
        timeout=600,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if process.returncode != 0:
        failure_path = output / "worker_failure.json"
        failure = _load_json(failure_path) if failure_path.is_file() else {}
        if isinstance(failure.get("accounting"), dict):
            _merge_worker_accounting(accounting, failure["accounting"])
        raise CompatError(
            "compatibility worker failed",
            kind="worker_failure",
            stage=str(failure.get("stage", "worker")),
            block=(
                str(failure["block"]) if failure.get("block") is not None else worker
            ),
        )
    return output


def _load_worker(
    root: Path, worker: str, revision: str, total: dict[str, int]
) -> tuple[dict[str, Path], dict[str, Any]]:
    receipt = _load_json(root / "worker_receipt.json")
    _exact_keys(
        receipt,
        (
            "schema_version",
            "worker",
            "source_revision",
            "fixture_rows",
            "descriptor_names",
            "arrays",
            "boundaries",
            "accounting",
        ),
        "worker receipt",
    )
    _require(
        receipt.get("schema_version") == "cypshift.maplight_int8_compat_worker.v1"
        and receipt.get("worker") == worker
        and receipt.get("source_revision") == revision
        and receipt.get("fixture_rows") == 8,
        "worker receipt differs",
    )
    names = UPSTREAM_ARRAYS if worker == "upstream" else LOCAL_ARRAYS
    _require(receipt.get("arrays") == list(names), "worker receipt arrays differ")
    _require(
        receipt.get("descriptor_names") == list(features.descriptor_names()),
        "worker descriptor order differs",
    )
    _require(
        receipt.get("boundaries")
        == {str(key): value for key, value in BOUNDARIES.items()},
        "worker boundary receipt differs",
    )
    _merge_worker_accounting(
        {key: 0 for key in receipt["accounting"]}, receipt["accounting"]
    )
    _require(
        receipt["accounting"]
        == {
            "fixture_arrays_generated": len(names),
            "fixture_row_loads": 8,
            "boundary_conversions_attempted": 3,
            "boundary_conversions_completed": 3,
        },
        "worker success accounting differs",
    )
    _merge_worker_accounting(total, receipt["accounting"])
    paths = {name: root / f"{name}.npy" for name in names}
    _require(
        {path.name for path in root.iterdir()}
        == {"worker_receipt.json", *(path.name for path in paths.values())},
        "worker file set differs",
    )
    for name, path in paths.items():
        _array_record(path, *ARRAY_SPECS[name])
    return paths, receipt


def _same_array(left: Path, right: Path, name: str) -> None:
    _require(left.read_bytes() == right.read_bytes(), f"{name} bytes differ")


def _readonly(root: Path) -> None:
    for path in root.iterdir():
        os.chmod(path, 0o444)
    os.chmod(root, 0o555)


def _remove_staging(root: Path) -> None:
    """Remove only one supervisor-created staging root, including after chmod."""

    if not root.exists():
        return
    os.chmod(root, 0o700)
    for path in root.iterdir():
        os.chmod(path, 0o600)
    shutil.rmtree(root)


def _promote_failure(root: Path, receipt: Mapping[str, Any]) -> Path:
    _require(_path_absent(root), "failure root already exists")
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}-", dir=root.parent))
    try:
        path = staging / "failure_receipt.json"
        path.write_bytes(_json_bytes(receipt))
        _require(_load_json(path) == receipt, "failure receipt differs")
        _readonly(staging)
        staging.rename(root)
        return root
    except Exception:
        _remove_staging(staging)
        raise


def _implementation(revision: str) -> dict[str, str]:
    return {
        "source_revision": revision,
        "feature_module_path": FEATURE_PATH.relative_to(ROOT).as_posix(),
        "feature_module_sha256": _sha256(FEATURE_PATH),
        "builder_path": BUILDER_PATH.relative_to(ROOT).as_posix(),
        "builder_sha256": _sha256(BUILDER_PATH),
    }


def _contracts() -> dict[str, str]:
    return {"compatibility": CONTRACT_SHA256, "parent": PARENT_CONTRACT_SHA256}


def _parity_inputs() -> dict[str, str]:
    return {
        "fixture": FIXTURE_SHA256,
        "safe_parity": SAFE_PARITY_SHA256,
        "safe_blocker": SAFE_BLOCKER_SHA256,
    }


def _feature_inputs() -> dict[str, str]:
    return {
        "shadow_rows": SHADOW_ROWS_SHA256,
        "shadow_manifest": SHADOW_MANIFEST_SHA256,
        "safe_parity": SAFE_PARITY_SHA256,
        "safe_blocker": SAFE_BLOCKER_SHA256,
    }


def _population() -> dict[str, int]:
    return {
        "source_rows": 30038,
        "unique_exact_raw_inputs": 15399,
        "unique_standardized_structures": 15354,
        "standardized_hashes_with_multiple_raw_forms": 41,
        "excess_raw_forms": 45,
        "maximum_raw_forms_per_standardized_hash": 4,
    }


def _environment() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "rdkit": importlib.metadata.version("rdkit"),
        "numpy": np.__version__,
        "platform": platform.platform(),
    }


def _parity_identity(revision: str) -> dict[str, object]:
    return {
        "schema_version": "cypshift.maplight_int8_compat_parity.v1",
        "source_revision": revision,
        "contracts": _contracts(),
        "inputs": _parity_inputs(),
        "implementation": _implementation(revision),
        "fixture": {
            "rows": 8,
            "descriptor_names_sha256": features.DESCRIPTOR_NAMES_SHA256,
        },
        "claim_boundary": PARITY_CLAIM,
    }


def _feature_identity(
    build_id: int, revision: str, parity_sha256: str
) -> dict[str, object]:
    return {
        "schema_version": "cypshift.maplight_int8_compat_features.v1",
        "experiment": "maplight_fixed_upstream_int8_v1",
        "build_id": build_id,
        "source_revision": revision,
        "contracts": _contracts(),
        "inputs": _feature_inputs(),
        "implementation": _implementation(revision),
        "compatibility_parity": {
            "receipt_sha256": parity_sha256,
            "source_revision": revision,
        },
        "population": _population(),
        "environment": _environment(),
        "claim_boundary": FEATURE_CLAIM,
    }


def _failure_fields(error: Exception) -> dict[str, object]:
    result: dict[str, object] = {
        "kind": getattr(error, "kind", type(error).__name__),
        "stage": getattr(error, "stage", "unhandled"),
        "exception_class": type(error).__name__,
    }
    for key in (
        "block",
        "unique_raw_index",
        "raw_structure_sha256",
        "expected",
        "observed",
    ):
        result[key] = getattr(error, key, None)
    return result


def _write_parity_failure(
    error: Exception, revision: str | None, accounting: Mapping[str, int]
) -> Path:
    _exact_keys(accounting, PARITY_ACCOUNTING_KEYS, "parity failure accounting")
    _require(
        all(type(value) is int and value >= 0 for value in accounting.values()),
        "parity failure accounting value differs",
    )
    receipt = {
        "schema_version": "cypshift.maplight_int8_compat_parity_failure.v1",
        "source_revision": revision,
        "contracts": _contracts(),
        "inputs": _parity_inputs(),
        "implementation": (_implementation(revision) if revision is not None else None),
        "failure": _failure_fields(error),
        "completed_operations": {
            key: value for key, value in accounting.items() if value > 0
        },
        "accounting": dict(accounting),
        "claim_boundary": PARITY_FAILURE_CLAIM,
    }
    return _promote_failure(PARITY_BLOCKER_ROOT, receipt)


def run_compatibility_parity() -> Path:
    _require(_path_absent(PARITY_ROOT), "compatibility parity already exists")
    _require(_path_absent(PARITY_BLOCKER_ROOT), "compatibility parity blocker exists")
    work: Path | None = None
    staging: Path | None = None
    revision: str | None = None
    accounting = {key: 0 for key in PARITY_ACCOUNTING_KEYS}
    try:
        contract, revision = _verify_common()
        work = Path(tempfile.mkdtemp(prefix=".int8-parity-", dir=PARITY_ROOT.parent))
        results: dict[str, tuple[dict[str, Path], dict[str, Any]]] = {}
        for worker in WORKERS:
            attempted_key = (
                "upstream_fixture_processes_attempted"
                if worker == "upstream"
                else "compatible_fixture_processes_attempted"
            )
            completed_key = attempted_key.replace("attempted", "completed")
            accounting[attempted_key] += 1
            results[worker] = _load_worker(
                _run_worker(worker, work, revision, accounting),
                worker,
                revision,
                accounting,
            )
            accounting[completed_key] += 1
        upstream_paths, upstream_receipt = results["upstream"]
        local_a, receipt_a = results["compatible_a"]
        local_b, receipt_b = results["compatible_b"]
        for name in UPSTREAM_ARRAYS:
            _same_array(upstream_paths[name], local_a[name], name)
        for name in LOCAL_ARRAYS:
            _same_array(local_a[name], local_b[name], name)
        complete = np.load(local_a["maplight_fixed"], allow_pickle=False)
        for name, block_slice in FIXED_SLICES.items():
            block = np.load(local_a[name], allow_pickle=False).astype("<f8")
            _require(
                np.array_equal(complete[:, block_slice], block),
                f"complete matrix slice differs: {name}",
                stage="slice_parity",
                block=name,
            )
        safe = _load_json(SAFE_PARITY_PATH)
        _require(
            _sha256(local_a["binary_morgan"]) == safe["outputs"]["binary_morgan"],
            "binary Morgan differs from safe parity",
        )
        boundary_records = []
        for count, expected in BOUNDARIES.items():
            upstream = int(upstream_receipt["boundaries"][str(count)])
            first = int(receipt_a["boundaries"][str(count)])
            second = int(receipt_b["boundaries"][str(count)])
            _require(
                (upstream, first, second) == (expected, expected, expected),
                "signed-int8 boundary differs",
                stage="boundary",
                expected=expected,
                observed=first,
            )
            boundary_records.append(
                {
                    "preconversion_count": count,
                    "dtype": "numpy.int8",
                    "upstream_value": upstream,
                    "compatible_process_1_value": first,
                    "compatible_process_2_value": second,
                }
            )
        staging = Path(
            tempfile.mkdtemp(prefix=".int8-parity-result-", dir=PARITY_ROOT.parent)
        )
        arrays: dict[str, dict[str, object]] = {}
        for name in LOCAL_ARRAYS:
            target = staging / f"{name}.npy"
            target.write_bytes(local_a[name].read_bytes())
            arrays[name] = _array_record(target, *ARRAY_SPECS[name])
        _, final_revision = _verify_common()
        _require(
            final_revision == revision, "parity inputs changed", stage="final_rehash"
        )
        success_accounting = accounting.copy()
        success_accounting["retained_arrays"] = len(arrays)
        _require(
            success_accounting
            == contract["compatibility_parity"]["success_accounting"],
            "parity accounting differs",
        )
        receipt = {
            **_parity_identity(revision),
            "count_boundaries": boundary_records,
            "arrays": arrays,
            "accounting": success_accounting,
        }
        receipt_path = staging / "compatibility_parity_receipt.json"
        receipt_path.write_bytes(_json_bytes(receipt))
        _require(_load_json(receipt_path) == receipt, "parity receipt differs")
        shutil.rmtree(work)
        work = None
        _readonly(staging)
        staging.rename(PARITY_ROOT)
        staging = None
        return PARITY_ROOT
    except Exception as error:
        if work is not None and work.exists():
            shutil.rmtree(work)
        if staging is not None and staging.exists():
            _remove_staging(staging)
        blocker = _write_parity_failure(error, revision, accounting)
        raise CompatError(f"parity failed; blocker retained at {blocker}") from error


def _read_shadow_rows() -> list[dict[str, str]]:
    with SHADOW_ROWS_PATH.open(encoding="utf-8", newline="") as handle:
        rows = [
            {key: str(value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    _require(len(rows) == 30038, "shadow row count differs")
    return rows


def _unique_raw_inputs(
    rows: Sequence[Mapping[str, str]],
) -> tuple[tuple[str, ...], tuple[str, ...], NDArray[np.int64]]:
    positions: dict[tuple[str, str], int] = {}
    raw: list[str] = []
    hashes: list[str] = []
    inverse: NDArray[np.int64] = np.empty(len(rows), dtype=np.int64)
    for index, row in enumerate(rows):
        key = (row["raw_structure_sha256"], row["raw_structure"])
        position = positions.get(key)
        if position is None:
            position = len(raw)
            positions[key] = position
            raw.append(row["raw_structure"])
            hashes.append(row["raw_structure_sha256"])
        inverse[index] = position
    _require(len(raw) == 15399, "unique raw count differs")
    return tuple(raw), tuple(hashes), inverse


def _write_feature_rows(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=FEATURE_ROW_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in FEATURE_ROW_COLUMNS})


def _feature_output(build_id: int) -> Path:
    return OUTPUT_PARENT / f"maplight-fixed-upstream-int8-features-v1-build-{build_id}"


def _feature_blocker(build_id: int) -> Path:
    return BLOCKER_PARENT / (
        f"maplight-fixed-upstream-int8-features-v1-build-{build_id}-blocker"
    )


def _verify_parity_root(revision: str) -> dict[str, Any]:
    _require(_path_absent(PARITY_BLOCKER_ROOT), "compatibility parity blocker exists")
    _require(_read_only_root(PARITY_ROOT), "compatibility parity root is invalid")
    receipt_path = PARITY_ROOT / "compatibility_parity_receipt.json"
    expected_files = {
        "compatibility_parity_receipt.json",
        *(f"{name}.npy" for name in LOCAL_ARRAYS),
    }
    _require(
        {path.name for path in PARITY_ROOT.iterdir()} == expected_files,
        "compatibility parity file set differs",
    )
    _require(
        all(_read_only_regular_file(path) for path in PARITY_ROOT.iterdir()),
        "compatibility parity file mode differs",
    )
    receipt = _load_json(receipt_path)
    contract = _load_json(CONTRACT_PATH)
    _exact_keys(
        receipt,
        contract["compatibility_parity"]["receipt_required_fields"]["top_level"],
        "compatibility parity receipt",
    )
    for key, expected in _parity_identity(revision).items():
        _require(receipt[key] == expected, f"compatibility parity {key} differs")
    expected_boundaries = [
        {
            "preconversion_count": count,
            "dtype": "numpy.int8",
            "upstream_value": value,
            "compatible_process_1_value": value,
            "compatible_process_2_value": value,
        }
        for count, value in BOUNDARIES.items()
    ]
    _require(
        receipt["count_boundaries"] == expected_boundaries,
        "compatibility parity boundaries differ",
    )
    _require(set(receipt["arrays"]) == set(LOCAL_ARRAYS), "parity arrays differ")
    for name, record in receipt["arrays"].items():
        _require(record["path"] == f"{name}.npy", f"parity path differs: {name}")
        _require(
            record == _array_record(PARITY_ROOT / record["path"], *ARRAY_SPECS[name]),
            f"compatibility parity array receipt differs: {name}",
        )
    expected_accounting = contract["compatibility_parity"]["success_accounting"]
    _require(receipt["accounting"] == expected_accounting, "parity accounting differs")
    return receipt


def _validate_build_root(
    root: Path,
    expected_id: int,
    revision: str,
    parity_sha256: str,
    *,
    require_read_only: bool = True,
) -> dict[str, Any]:
    _require(root.is_dir() and not root.is_symlink(), "prior build root is invalid")
    expected_files = {
        "feature_manifest.json",
        "feature_rows.csv",
        *(f"{name}.npy" for name in PERSISTED_BLOCKS),
    }
    _require(
        {path.name for path in root.iterdir()} == expected_files,
        "prior build file set differs",
    )
    if require_read_only:
        _require(_read_only_root(root), "prior build root is writable")
        _require(
            all(_read_only_regular_file(path) for path in root.iterdir()),
            "prior build file mode differs",
        )
    manifest = _load_json(root / "feature_manifest.json")
    contract = _load_json(CONTRACT_PATH)
    _exact_keys(
        manifest,
        contract["artifact_schemas"]["success_manifest"]["top_level_fields"],
        "feature manifest",
    )
    for key, expected in _feature_identity(
        expected_id, revision, parity_sha256
    ).items():
        _require(manifest[key] == expected, f"prior build {key} differs")
    if expected_id == 1:
        _require(manifest["prior_build"] is None, "prior build linkage differs")
    else:
        _require(
            manifest["prior_build"]
            == {
                "manifest_sha256": _sha256(
                    _feature_output(1) / "feature_manifest.json"
                ),
                "validated_before_row_resolution": True,
            },
            "prior build linkage differs",
        )
    row_record = manifest["rows"]
    _exact_keys(row_record, ("path", "sha256", "rows", "columns"), "row record")
    _require(
        row_record["path"] == "feature_rows.csv"
        and row_record["rows"] == 30038
        and row_record["columns"] == list(FEATURE_ROW_COLUMNS)
        and _sha256(root / "feature_rows.csv") == row_record["sha256"],
        "prior build rows differ",
    )
    _require(set(manifest["arrays"]) == set(PERSISTED_BLOCKS), "prior arrays differ")
    for name, record in manifest["arrays"].items():
        _require(record["path"] == f"{name}.npy", f"prior path differs: {name}")
        _require(
            record == _array_record(root / record["path"], *REAL_ARRAY_SPECS[name]),
            f"prior array differs: {name}",
        )
    _require(
        set(manifest["overflow"]) == {"morgan_count", "avalon_count"},
        "prior overflow blocks differ",
    )
    for record in manifest["overflow"].values():
        _exact_keys(
            record, tuple(features.CountOverflowStats.__annotations__), "overflow"
        )
        _require(
            all(type(value) is int for value in record.values()),
            "prior overflow value differs",
        )
        _require(
            record["maximum_preconversion_count"] >= 0
            and 0 <= record["unique_raw_rows_with_counts_above_127"] <= 15399
            and record["bins_above_127"] >= 0
            and -128 <= record["minimum_converted_int8_value"] <= 127
            and -128 <= record["maximum_converted_int8_value"] <= 127,
            "prior overflow bounds differ",
        )
    accounting = manifest["accounting"]
    _exact_keys(
        accounting, ("current_attempt", "cumulative", "scientific_zeros"), "accounting"
    )
    expected_current = _operation_accounting([1, 1, 30038, 15399, 5, 5, 0])
    expected_cumulative = _operation_accounting(
        [1, 1, 30038, 15399, 5, 5, 0]
        if expected_id == 1
        else [2, 2, 60076, 30798, 10, 10, 0]
    )
    _require(
        accounting["current_attempt"] == expected_current
        and accounting["cumulative"] == expected_cumulative,
        "prior operation accounting differs",
    )
    _zero_accounting(accounting["scientific_zeros"])
    _require(
        type(manifest["runtime_seconds"]) in (int, float)
        and 0 <= manifest["runtime_seconds"] <= 3600
        and type(manifest["peak_rss_gib"]) in (int, float)
        and 0 <= manifest["peak_rss_gib"] <= 8,
        "prior resource receipt differs",
    )
    return manifest


def _peak_rss_gib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**3)


def _timeout(_signum: int, _frame: object) -> NoReturn:
    raise CompatError("feature build timed out", kind="runtime_limit", stage="resource")


def _write_build_failure(
    build_id: int,
    error: Exception,
    revision: str | None,
    parity_sha256: str | None,
    elapsed: float,
    current: Mapping[str, int],
    cumulative: Mapping[str, int],
) -> Path:
    root = _feature_blocker(build_id)
    receipt = {
        "schema_version": "cypshift.maplight_int8_compat_feature_failure.v1",
        "experiment": "maplight_fixed_upstream_int8_v1",
        "build_id": build_id,
        "source_revision": revision,
        "contracts": _contracts(),
        "inputs": _feature_inputs(),
        "implementation": _implementation(revision) if revision else None,
        "compatibility_parity": parity_sha256,
        "failure": _failure_fields(error),
        "completed_operations": {
            key: value for key, value in current.items() if value > 0
        },
        "runtime_seconds": elapsed,
        "peak_rss_gib": _peak_rss_gib(),
        "accounting": {
            "current_attempt": dict(current),
            "cumulative": dict(cumulative),
            "scientific_zeros": SCIENTIFIC_ZEROS,
        },
        "claim_boundary": FEATURE_FAILURE_CLAIM,
    }
    return _promote_failure(root, receipt)


def build_compatibility_features(build_id: int) -> Path:
    _require(build_id in (1, 2), "build ID differs")
    output = _feature_output(build_id)
    blocker = _feature_blocker(build_id)
    _require(
        _path_absent(output) and _path_absent(blocker),
        "build output already exists",
    )
    revision: str | None = None
    parity_sha256: str | None = None
    staging: Path | None = None
    start = time.perf_counter()
    current = _operation_accounting([1, 0, 0, 0, 0, 0, 0])
    prior_counts = _operation_accounting(
        [1, 1, 30038, 15399, 5, 5, 0] if build_id == 2 else [0, 0, 0, 0, 0, 0, 0]
    )
    cumulative = _add_operations(prior_counts, current)
    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(3600)
    try:
        _, revision = _verify_common()
        _verify_parity_root(revision)
        parity_path = PARITY_ROOT / "compatibility_parity_receipt.json"
        parity_sha256 = _sha256(parity_path)
        prior: dict[str, Any] | None = None
        if build_id == 2:
            _require(_path_absent(_feature_blocker(1)), "build 1 blocker exists")
            prior = _validate_build_root(_feature_output(1), 1, revision, parity_sha256)
        _require(_read_only_root(SHADOW_ROOT), "shadow root is invalid")
        _require(
            _read_only_regular_file(SHADOW_ROWS_PATH)
            and _read_only_regular_file(SHADOW_MANIFEST_PATH),
            "shadow input mode differs",
        )
        _require_hash(SHADOW_ROWS_PATH, SHADOW_ROWS_SHA256)
        _require_hash(SHADOW_MANIFEST_PATH, SHADOW_MANIFEST_SHA256)
        rows = _read_shadow_rows()
        current["source_rows_parsed"] = len(rows)
        raw, hashes, inverse = _unique_raw_inputs(rows)

        def block_completed(_name: str) -> None:
            current["in_memory_block_arrays_completed"] += 1

        try:
            unique_features, overflow = features.featurize_raw_structures_upstream_int8(
                raw, hashes, block_completed=block_completed
            )
        except features.MapLightFeatureError as error:
            index = error.row_index
            raise CompatError(
                "feature generation failed",
                kind=type(error).__name__,
                stage="feature_generation",
                block=error.block,
                unique_raw_index=index,
                raw_structure_sha256=hashes[index] if index is not None else None,
            ) from error
        current["exact_raw_featurizations"] = len(raw)
        staging = Path(tempfile.mkdtemp(prefix=".int8-features-", dir=OUTPUT_PARENT))
        row_path = staging / "feature_rows.csv"
        _write_feature_rows(row_path, rows)
        arrays: dict[str, dict[str, object]] = {}
        for name in PERSISTED_BLOCKS:
            array = np.ascontiguousarray(getattr(unique_features, name)[inverse])
            target = staging / f"{name}.npy"
            features.write_npy_v1(target, array)
            arrays[name] = _array_record(target, *REAL_ARRAY_SPECS[name])
            current["persisted_block_arrays"] += 1
        if build_id == 2:
            prior_root = _feature_output(1)
            _require(
                row_path.read_bytes() == (prior_root / "feature_rows.csv").read_bytes(),
                "repeat rows differ",
            )
            for name in PERSISTED_BLOCKS:
                _require(
                    (staging / f"{name}.npy").read_bytes()
                    == (prior_root / f"{name}.npy").read_bytes(),
                    f"repeat array differs: {name}",
                )
        success_current = current.copy()
        success_current["completed_feature_builds"] = 1
        success_cumulative = (
            success_current.copy()
            if build_id == 1
            else _add_operations(prior_counts, success_current)
        )
        elapsed = time.perf_counter() - start
        peak = _peak_rss_gib()
        _require(
            elapsed <= 3600 and peak <= 8,
            "feature resource cap exceeded",
            stage="resource",
        )
        _, final_revision = _verify_common()
        _require_hash(SHADOW_ROWS_PATH, SHADOW_ROWS_SHA256)
        _require_hash(SHADOW_MANIFEST_PATH, SHADOW_MANIFEST_SHA256)
        _require(
            final_revision == revision,
            "feature inputs changed during build",
            stage="final_rehash",
        )
        _verify_parity_root(revision)
        manifest: dict[str, Any] = {
            **_feature_identity(build_id, revision, parity_sha256),
            "prior_build": (
                None
                if prior is None
                else {
                    "manifest_sha256": _sha256(
                        _feature_output(1) / "feature_manifest.json"
                    ),
                    "validated_before_row_resolution": True,
                }
            ),
            "rows": {
                "path": row_path.name,
                "sha256": _sha256(row_path),
                "rows": 30038,
                "columns": list(FEATURE_ROW_COLUMNS),
            },
            "arrays": arrays,
            "overflow": {name: asdict(record) for name, record in overflow.items()},
            "runtime_seconds": elapsed,
            "peak_rss_gib": peak,
            "accounting": {
                "current_attempt": success_current,
                "cumulative": success_cumulative,
                "scientific_zeros": SCIENTIFIC_ZEROS,
            },
        }
        if prior is not None:
            for key in (
                "contracts",
                "inputs",
                "implementation",
                "compatibility_parity",
                "overflow",
                "population",
                "environment",
            ):
                _require(
                    manifest[key] == prior[key],
                    f"repeat manifest field differs: {key}",
                    stage="repeat_gate",
                )
            _require(
                manifest["accounting"]["scientific_zeros"]
                == prior["accounting"]["scientific_zeros"],
                "repeat scientific accounting differs",
                stage="repeat_gate",
            )
        (staging / "feature_manifest.json").write_bytes(_json_bytes(manifest))
        _validate_build_root(
            staging,
            build_id,
            revision,
            parity_sha256,
            require_read_only=False,
        )
        signal.alarm(0)
        _readonly(staging)
        _require(
            _read_only_root(staging)
            and all(_read_only_regular_file(path) for path in staging.iterdir()),
            "successful feature root mode differs",
            stage="promotion",
        )
        staging.rename(output)
        return output
    except Exception as error:
        if staging is not None and staging.exists():
            _remove_staging(staging)
            current["staging_roots_removed"] += 1
        cumulative = _add_operations(prior_counts, current)
        blocker_root = _write_build_failure(
            build_id,
            error,
            revision,
            parity_sha256,
            time.perf_counter() - start,
            current,
            cumulative,
        )
        raise CompatError(
            f"feature build failed; blocker retained at {blocker_root}"
        ) from error
    finally:
        signal.alarm(0)


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--parity", action="store_true")
    modes.add_argument("--build-id", type=int, choices=(1, 2))
    modes.add_argument("--_worker", choices=WORKERS, help=argparse.SUPPRESS)
    parser.add_argument("--_worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--_worker-revision", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    if arguments._worker is not None:
        _require(
            arguments._worker_output is not None
            and arguments._worker_revision is not None,
            "worker arguments are incomplete",
        )
        return _worker_main(
            arguments._worker,
            arguments._worker_output,
            arguments._worker_revision,
        )
    try:
        result = (
            run_compatibility_parity()
            if arguments.parity
            else build_compatibility_features(arguments.build_id)
        )
    except (CompatError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(result.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
