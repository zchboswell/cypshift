#!/usr/bin/env python3
"""Verify exact synthetic parity for the frozen MapLight fixed features."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn, cast

import numpy as np
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_stage_a_contract.json"
FIXTURE_PATH = ROOT / "benchmarks/fixtures/maplight_fixed_parity_v1.csv"
SOURCE_ROOT = (
    ROOT / "data/external/maplight_tdc/c249378c63232354d17083c83fe94fe728960a27"
)
FEATURE_MODULE_PATH = ROOT / "research/maplight-fixed/maplight_fixed_features.py"
SUCCESS_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-parity-v1"
BLOCKER_PARENT = ROOT / "artifacts/blockers"

CONTRACT_SHA256 = "e20985ecabb1aa9ceaeddc3f81ad15dc60b194e250e28de934c12a6bfb10f710"
FIXTURE_SHA256 = "70ae570bbdbb5c8a225cfd20ab72f0d8f8b43dc1a3a6b2d3356bc52f4f4a513c"
SOURCE_CONTRACT_SHA256 = (
    "a2a608e327cd7adc5e54f24edbcb41007ef03313c26db582f37c9d85836b23a8"
)
PROJECT_SHA256 = "20addcbfa3d7dbfa5d3a9f24f3090c22f11b556166213b2649c6c55e58556234"
LOCK_SHA256 = "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
PYTHON_PIN_SHA256 = "3817f125779f46c574b17c4adbdd0975ef8c32ae92509fed295212797d314d6a"
PYTHON_EXECUTABLE_SHA256 = (
    "bdca214c1a74129f24da4e4b45fd00f2d650b0634c916643130a817b96069e33"
)
SOURCE_FILES = {
    "LICENSE": "281afcf01d4df616e2f8065ca100f0de6b8740c2f5865008a538368ea75e4334",
    "README.md": "eb0e2fb544353153095bf2253b4b76d1d18309aa6082e6237de4df91cbd17315",
    "maplight.py": "6dcb40fa43d39221259e03406f34be554fc138782c099894004549f7a8c24863",
    "maplight_gnn.py": "74fbd1c98d9afa7fa4bda1add21efd429e20dee0a4b0fb8fa7e9b3825c21fe13",
    "submission.ipynb": "26393242dcc7bd5509a8836f36a270106a1484af2abd0e90497aadad1a1e7754",
    "submission_gnn.ipynb": "95dc471338e8ca69a85a0c3c162cca3f5a1b220f3cd6a8d14f726adf5f7e1546",
}
WORKERS = ("upstream", "local_a", "local_b")
UPSTREAM_ARRAYS = (
    "morgan_count",
    "avalon_count",
    "erg",
    "rdkit_descriptors",
    "maplight_fixed",
)
LOCAL_ARRAYS = (
    "binary_morgan",
    "morgan_count",
    "avalon_count",
    "erg",
    "rdkit_descriptors",
    "maplight_fixed",
)
ARRAY_SPECIFICATIONS = {
    "binary_morgan": ((8, 2048), np.dtype(np.uint8)),
    "morgan_count": ((8, 1024), np.dtype(np.int8)),
    "avalon_count": ((8, 1024), np.dtype(np.int8)),
    "erg": ((8, 315), np.dtype("<f8")),
    "rdkit_descriptors": ((8, 200), np.dtype("<f8")),
    "maplight_fixed": ((8, 2563), np.dtype("<f8")),
}
SCIENTIFIC_ZEROS = {
    "real_feature_rows_parsed": 0,
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


class ParityError(RuntimeError):
    """A sanitized, receipt-safe parity failure."""

    def __init__(
        self,
        message: str,
        *,
        kind: str,
        stage: str,
        worker: str | None = None,
        block: str | None = None,
        row_index: int | None = None,
        expected: str | int | None = None,
        observed: str | int | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.stage = stage
        self.worker = worker
        self.block = block
        self.row_index = row_index
        self.expected = expected
        self.observed = observed


def _require(
    condition: bool,
    message: str,
    *,
    kind: str = "contract_mismatch",
    stage: str = "preflight",
    **detail: Any,
) -> None:
    if not condition:
        raise ParityError(message, kind=kind, stage=stage, **detail)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    _require(isinstance(value, dict), f"{path.name} is not an object")
    return cast(dict[str, Any], value)


def _import_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ParityError(
            "module import failed",
            kind="module_import_failed",
            stage="module_import",
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(arguments: Sequence[str]) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _clean_revision() -> str:
    _require(not _git(("status", "--porcelain", "--untracked-files=no")), "dirty tree")
    revision = _git(("rev-parse", "HEAD"))
    _require(len(revision) == 40, "source revision is not full length")
    signature = _git(
        (
            "show",
            "-s",
            "--format=%G?%x00%an%x00%ae%x00%cn%x00%ce",
            revision,
        )
    ).split("\0")
    _require(
        signature
        == [
            "G",
            "zchboswell",
            "261114960+zchboswell@users.noreply.github.com",
            "zchboswell",
            "261114960+zchboswell@users.noreply.github.com",
        ],
        "source revision signature or authorship differs",
    )
    return revision


def _signature_evidence(revision: str) -> dict[str, str]:
    status, fingerprint = _git(("show", "-s", "--format=%G?%x00%GF", revision)).split(
        "\0"
    )
    return {"status": status, "fingerprint": fingerprint}


def _normalized_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _verify_environment(contract: Mapping[str, Any]) -> dict[str, str]:
    compatible = contract["compatible_environment"]
    expected = {
        _normalized_distribution_name(key.rsplit("@", 1)[0]): key.rsplit("@", 1)[1]
        for key in compatible["resolved_package_licenses"]
    }
    observed: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        if name:
            observed[_normalized_distribution_name(name)] = distribution.version
    _require(
        observed == expected, "installed package set differs from frozen environment"
    )
    _require(platform.python_version() == "3.10.13", "Python version drift")
    _require(platform.system() == "Darwin", "operating system drift")
    _require(platform.machine() == "arm64", "architecture drift")
    _require(
        _sha256(Path(sys.executable).resolve()) == PYTHON_EXECUTABLE_SHA256,
        "Python hash drift",
    )
    return observed


def _verify_preflight() -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    _require(_sha256(CONTRACT_PATH) == CONTRACT_SHA256, "Stage A contract hash drift")
    contract = _load_json(CONTRACT_PATH)
    source_contract = (
        ROOT / contract["frozen_sources"]["maplight_source_contract"]["path"]
    )
    _require(
        _sha256(source_contract) == SOURCE_CONTRACT_SHA256, "source contract hash drift"
    )
    _require(_sha256(FIXTURE_PATH) == FIXTURE_SHA256, "fixture hash drift")
    _require(
        _sha256(ROOT / "research/maplight-fixed/pyproject.toml") == PROJECT_SHA256,
        "research project hash drift",
    )
    _require(
        _sha256(ROOT / "research/maplight-fixed/uv.lock") == LOCK_SHA256,
        "research lock hash drift",
    )
    _require(
        _sha256(ROOT / "research/maplight-fixed/.python-version") == PYTHON_PIN_SHA256,
        "Python pin hash drift",
    )
    _require(SOURCE_ROOT.is_dir(), "pinned source root is missing")
    _require(
        {path.name for path in SOURCE_ROOT.iterdir()} == set(SOURCE_FILES),
        "pinned source file set drift",
    )
    for name, expected_hash in SOURCE_FILES.items():
        path = SOURCE_ROOT / name
        _require(
            path.is_file() and not path.is_symlink(), "pinned source path is invalid"
        )
        _require(_sha256(path) == expected_hash, f"pinned source hash drift: {name}")
        _require(
            path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) == 0,
            f"pinned source is writable: {name}",
        )
    _verify_environment(contract)
    revision = _clean_revision()
    rows = _read_fixture()
    return contract, revision, rows


def _read_fixture() -> list[dict[str, str]]:
    with FIXTURE_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require(
            tuple(reader.fieldnames or ())
            == ("fixture_id", "pandas_index", "raw_smiles"),
            "fixture schema drift",
        )
        rows = [{key: str(value) for key, value in row.items()} for row in reader]
    _require(len(rows) == 8, "fixture row count drift")
    _require(
        [int(row["pandas_index"]) for row in rows] == [13, 2, 21, 5, 8, 3, 34, 1],
        "fixture order drift",
    )
    return rows


def _fixture_receipt(rows: Sequence[Mapping[str, str]]) -> list[dict[str, object]]:
    return [
        {
            "fixture_id": row["fixture_id"],
            "pandas_index": int(row["pandas_index"]),
            "raw_structure_sha256": hashlib.sha256(
                row["raw_smiles"].encode()
            ).hexdigest(),
        }
        for row in rows
    ]


def _write_npy(path: Path, array: NDArray[Any]) -> None:
    with path.open("xb") as handle:
        np.lib.format.write_array(handle, array, version=(1, 0), allow_pickle=False)


def _array_metadata(path: Path, name: str) -> dict[str, object]:
    array = np.load(path, allow_pickle=False)
    shape, dtype = ARRAY_SPECIFICATIONS[name]
    _require(
        array.shape == shape,
        "array shape mismatch",
        stage="array_validation",
        block=name,
    )
    _require(
        array.dtype == dtype,
        "array dtype mismatch",
        stage="array_validation",
        block=name,
    )
    _require(
        array.flags.c_contiguous,
        "array is not C-contiguous",
        stage="array_validation",
        block=name,
    )
    _require(
        bool(np.isfinite(array).all()),
        "array contains non-finite values",
        stage="array_validation",
        block=name,
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


def _worker_arrays(
    worker: str, rows: Sequence[Mapping[str, str]]
) -> tuple[dict[str, NDArray[Any]], tuple[str, ...]]:
    raw = tuple(row["raw_smiles"] for row in rows)
    raw_hashes = tuple(hashlib.sha256(value.encode()).hexdigest() for value in raw)
    if worker == "upstream":
        import pandas as pd  # type: ignore[import-untyped]
        from rdkit import Chem

        upstream = _import_path("pinned_maplight", SOURCE_ROOT / "maplight.py")
        series = pd.Series(
            raw, index=[int(row["pandas_index"]) for row in rows], dtype=object
        )
        molecules = series.apply(Chem.MolFromSmiles)

        def call(block: str, operation: Callable[[], Any]) -> NDArray[Any]:
            try:
                return cast(NDArray[Any], operation())
            except Exception as error:
                raise ParityError(
                    "upstream feature generation failed",
                    kind=type(error).__name__,
                    stage="worker_feature_generation",
                    worker=worker,
                    block=block,
                ) from error

        arrays = {
            "morgan_count": call(
                "morgan_count", lambda: upstream.get_morgan_fingerprints(molecules)
            ),
            "avalon_count": call(
                "avalon_count", lambda: upstream.get_avalon_fingerprints(molecules)
            ),
            "erg": call("erg", lambda: upstream.get_erg_fingerprints(molecules)),
            "rdkit_descriptors": call(
                "rdkit_descriptors", lambda: upstream.get_rdkit_features(molecules)
            ),
            "maplight_fixed": call(
                "maplight_fixed", lambda: upstream.get_fingerprints(series)
            ),
        }
        names = tuple(upstream.get_chosen_descriptors())
        return arrays, names

    features = _import_path(f"maplight_features_{worker}", FEATURE_MODULE_PATH)
    try:
        result = features.featurize_raw_structures(raw, raw_hashes)
    except Exception as error:
        raise ParityError(
            "local feature generation failed",
            kind=type(error).__name__,
            stage="worker_feature_generation",
            worker=worker,
            block=getattr(error, "block", None),
            row_index=getattr(error, "row_index", None),
        ) from error
    arrays = {name: getattr(result, name) for name in LOCAL_ARRAYS[:-1]}
    arrays["maplight_fixed"] = result.maplight_fixed()
    return arrays, tuple(features.descriptor_names())


def _worker_main(worker: str, output: Path, revision: str) -> int:
    output.mkdir(parents=False, exist_ok=False)
    try:
        _require(
            _clean_revision() == revision, "worker source revision drift", worker=worker
        )
        rows = _read_fixture()
        arrays, names = _worker_arrays(worker, rows)
        expected_names = UPSTREAM_ARRAYS if worker == "upstream" else LOCAL_ARRAYS
        _require(
            set(arrays) == set(expected_names), "worker array set drift", worker=worker
        )
        for name in expected_names:
            _write_npy(output / f"{name}.npy", arrays[name])
        receipt = {
            "schema_version": "cypshift.maplight_parity_worker.v1",
            "worker": worker,
            "source_revision": revision,
            "fixture": _fixture_receipt(rows),
            "descriptor_names": list(names),
            "arrays": list(expected_names),
            "original_arrays_writeable": {
                name: bool(arrays[name].flags.writeable) for name in expected_names
            },
        }
        (output / "worker_receipt.json").write_bytes(_json_bytes(receipt))
        return 0
    except Exception as error:
        if isinstance(error, ParityError):
            failure = _failure_fields(error)
        else:
            failure = {
                "kind": type(error).__name__,
                "stage": "worker_unhandled",
                "worker": worker,
            }
        (output / "worker_failure.json").write_bytes(_json_bytes(failure))
        return 1


def _failure_fields(error: ParityError) -> dict[str, object]:
    fields: dict[str, object] = {
        "kind": error.kind,
        "stage": error.stage,
    }
    for name in ("worker", "block", "row_index", "expected", "observed"):
        value = getattr(error, name)
        if value is not None:
            fields[name] = value
    return fields


def _worker_command(worker: str, output: Path, revision: str) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "--_worker",
        worker,
        "--_worker-output",
        str(output),
        "--_revision",
        revision,
    ]


def _run_worker(worker: str, root: Path, revision: str) -> Path:
    output = root / worker
    try:
        process = subprocess.run(
            _worker_command(worker, output, revision),
            cwd=ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=600,
        )
    except subprocess.TimeoutExpired as error:
        raise ParityError(
            "worker timed out",
            kind="worker_timeout",
            stage="worker_process",
            worker=worker,
        ) from error
    if process.returncode != 0:
        failure_path = output / "worker_failure.json"
        failure = _load_json(failure_path) if failure_path.is_file() else {}
        raise ParityError(
            "worker failed",
            kind=str(failure.get("kind", "worker_process_failure")),
            stage=str(failure.get("stage", "worker_process")),
            worker=worker,
            block=cast(str | None, failure.get("block")),
            row_index=cast(int | None, failure.get("row_index")),
        )
    return output


def _validate_fixture_receipt(
    observed: object, expected: Sequence[Mapping[str, object]], worker: str
) -> None:
    _require(
        observed == list(expected),
        "worker fixture identity drift",
        stage="worker_receipt",
        worker=worker,
    )


def _load_worker(
    root: Path,
    worker: str,
    revision: str,
    fixture: Sequence[Mapping[str, object]],
) -> tuple[dict[str, Path], dict[str, Any]]:
    receipt = _load_json(root / "worker_receipt.json")
    _require(
        receipt.get("worker") == worker,
        "worker identity drift",
        stage="worker_receipt",
        worker=worker,
    )
    _require(
        receipt.get("source_revision") == revision,
        "worker revision drift",
        stage="worker_receipt",
        worker=worker,
    )
    _validate_fixture_receipt(receipt.get("fixture"), fixture, worker)
    expected = UPSTREAM_ARRAYS if worker == "upstream" else LOCAL_ARRAYS
    _require(
        receipt.get("arrays") == list(expected),
        "worker array order drift",
        stage="worker_receipt",
        worker=worker,
    )
    paths = {name: root / f"{name}.npy" for name in expected}
    _require(
        all(path.is_file() for path in paths.values()),
        "worker array missing",
        stage="worker_receipt",
        worker=worker,
    )
    _require(
        {path.name for path in root.iterdir()}
        == {"worker_receipt.json", *(f"{name}.npy" for name in expected)},
        "worker output file set drift",
        stage="worker_receipt",
        worker=worker,
    )
    for name, path in paths.items():
        _array_metadata(path, name)
    if worker != "upstream":
        _require(
            receipt["original_arrays_writeable"]
            == {name: False for name in LOCAL_ARRAYS},
            "local arrays were mutable before serialization",
            stage="worker_receipt",
            worker=worker,
        )
    return paths, receipt


def _first_difference(
    expected: NDArray[Any], observed: NDArray[Any]
) -> tuple[int, int] | None:
    difference = np.argwhere(expected != observed)
    if difference.size == 0:
        return None
    return int(difference[0][0]), int(difference[0][1])


def _compare_arrays(
    expected_path: Path,
    observed_path: Path,
    name: str,
    comparison: str,
) -> dict[str, str]:
    expected = np.load(expected_path, allow_pickle=False)
    observed = np.load(observed_path, allow_pickle=False)
    _require(
        expected.shape == observed.shape,
        "comparison shape mismatch",
        stage=comparison,
        block=name,
    )
    _require(
        expected.dtype == observed.dtype,
        "comparison dtype mismatch",
        stage=comparison,
        block=name,
    )
    first = _first_difference(expected, observed)
    if first is not None:
        raise ParityError(
            "array values differ",
            kind="array_value_mismatch",
            stage=comparison,
            block=name,
            row_index=first[0],
            expected=str(expected[first]),
            observed=str(observed[first]),
        )
    _require(
        expected_path.read_bytes() == observed_path.read_bytes(),
        "NPY bytes differ",
        stage=comparison,
        block=name,
    )
    return {
        "element_sha256": hashlib.sha256(expected.tobytes(order="C")).hexdigest(),
        "npy_sha256": _sha256(expected_path),
    }


def _compare_slices(local: Mapping[str, Path]) -> dict[str, str]:
    complete = np.load(local["maplight_fixed"], allow_pickle=False)
    slices = {
        "morgan_count": (0, 1024),
        "avalon_count": (1024, 2048),
        "erg": (2048, 2363),
        "rdkit_descriptors": (2363, 2563),
    }
    evidence: dict[str, str] = {}
    for name, (start, stop) in slices.items():
        block = np.load(local[name], allow_pickle=False).astype("<f8", copy=False)
        _require(
            np.array_equal(complete[:, start:stop], block),
            "complete slice mismatch",
            stage="complete_slices",
            block=name,
        )
        evidence[name] = hashlib.sha256(block.tobytes(order="C")).hexdigest()
    return evidence


def _expect_error(identifier: str, operation: Callable[[], object]) -> dict[str, str]:
    try:
        operation()
    except Exception:
        return {"check_id": identifier, "status": "pass"}
    raise ParityError(
        "adversarial check did not fail",
        kind="adversarial_check_failure",
        stage="adversarial_checks",
        block=identifier,
    )


def _adversarial_checks(
    features: Any,
    local_paths: Mapping[str, Path],
    fixture: Sequence[Mapping[str, object]],
) -> list[dict[str, str]]:
    raw = ("CCO",)
    raw_hash = (hashlib.sha256(b"CCO").hexdigest(),)
    arrays = {
        name: np.load(path, allow_pickle=False)
        for name, path in local_paths.items()
        if name != "maplight_fixed"
    }
    checks = [
        _expect_error(
            "missing_input_rejected", lambda: features.featurize_raw_structures((), ())
        ),
        _expect_error(
            "empty_input_rejected",
            lambda: features.featurize_raw_structures(
                ("",), (hashlib.sha256(b"").hexdigest(),)
            ),
        ),
        _expect_error(
            "invalid_smiles_rejected",
            lambda: features.featurize_raw_structures(
                ("not-smiles",), (hashlib.sha256(b"not-smiles").hexdigest(),)
            ),
        ),
        _expect_error(
            "zero_atom_rejected",
            lambda: features.featurize_raw_structures(
                (" ",), (hashlib.sha256(b" ").hexdigest(),)
            ),
        ),
        _expect_error(
            "wrong_raw_hash_rejected",
            lambda: features.featurize_raw_structures(raw, ("0" * 64,)),
        ),
        _expect_error(
            "sparse_count_128_rejected",
            lambda: features._validate_sparse_counts({0: 128}, 1024),
        ),
        _expect_error(
            "negative_sparse_count_rejected",
            lambda: features._validate_sparse_counts({0: -1}, 1024),
        ),
        _expect_error(
            "boolean_sparse_count_rejected",
            lambda: features._validate_sparse_counts({0: True}, 1024),
        ),
        _expect_error(
            "noninteger_sparse_count_rejected",
            lambda: features._validate_sparse_counts({0: 1.5}, 1024),
        ),
    ]
    _require(
        features._validate_sparse_counts({0: 127}, 1024) == 127,
        "count 127 rejected",
        stage="adversarial_checks",
    )
    checks.append({"check_id": "sparse_count_127_accepted", "status": "pass"})

    for identifier, block, value in (
        ("nan_rejected", "erg", np.nan),
        ("positive_infinity_rejected", "rdkit_descriptors", np.inf),
        ("negative_infinity_rejected", "rdkit_descriptors", -np.inf),
    ):
        changed = {name: array.copy() for name, array in arrays.items()}
        changed[block][0, 0] = value

        def construct_changed(
            changed_arrays: Mapping[str, NDArray[Any]],
        ) -> Callable[[], Any]:
            return lambda: features.FixedFeatureArrays(
                raw_structure_sha256=tuple(
                    hashlib.sha256(f"row-{index}".encode()).hexdigest()
                    for index in range(8)
                ),
                **changed_arrays,
            )

        checks.append(
            _expect_error(
                identifier,
                construct_changed(changed),
            )
        )

    original_import = features.import_module

    def missing_import(name: str) -> Any:
        module = original_import(name)
        if name == "rdkit.Chem.Descriptors":

            class MissingProxy:
                def __getattr__(self, attribute: str) -> Any:
                    if attribute == features.DESCRIPTOR_NAMES[0]:
                        raise AttributeError(attribute)
                    return getattr(module, attribute)

            return MissingProxy()
        return module

    features.import_module = missing_import
    checks.append(
        _expect_error(
            "missing_descriptor_rejected",
            lambda: features.featurize_raw_structures(raw, raw_hash),
        )
    )
    features.import_module = original_import

    def raising_import(name: str) -> Any:
        if name == "rdkit.ML.Descriptors.MoleculeDescriptors":

            class RaisingCalculator:
                def __init__(self, names: Sequence[str]) -> None:
                    self.names = tuple(names)

                def GetDescriptorNames(self) -> tuple[str, ...]:
                    return self.names

                def CalcDescriptors(self, molecule: Any) -> NoReturn:
                    raise RuntimeError("synthetic descriptor failure")

            class RaisingModule:
                MolecularDescriptorCalculator = RaisingCalculator

            return RaisingModule()
        return original_import(name)

    features.import_module = raising_import
    checks.append(
        _expect_error(
            "raising_descriptor_rejected",
            lambda: features.featurize_raw_structures(raw, raw_hash),
        )
    )
    features.import_module = original_import

    reordered = list(fixture)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    checks.append(
        _expect_error(
            "raw_row_reorder_rejected",
            lambda: _validate_fixture_receipt(reordered, fixture, "synthetic"),
        )
    )
    checks.append(
        _expect_error(
            "duplicate_loss_rejected",
            lambda: _validate_fixture_receipt(list(fixture[:-1]), fixture, "synthetic"),
        )
    )
    checks.append(
        {
            "check_id": "standardized_hash_deduplication_deferred_to_real_feature_build",
            "status": "deferred",
        }
    )
    return checks


def _readonly(root: Path) -> None:
    for path in root.iterdir():
        os.chmod(path, 0o444)
    os.chmod(root, 0o555)


def _promote_success(
    staging: Path,
    local_paths: Mapping[str, Path],
    receipt: Mapping[str, object],
) -> None:
    retained: dict[str, dict[str, object]] = {}
    for name in LOCAL_ARRAYS:
        source = local_paths[name]
        target = staging / f"{name}.npy"
        shutil.copyfile(source, target)
        _require(
            source.read_bytes() == target.read_bytes(),
            "retained copy differs",
            stage="promotion",
            block=name,
        )
        retained[name] = _array_metadata(target, name)
    success = dict(receipt)
    success["retained_arrays"] = retained
    success["outputs"] = {name: data["npy_sha256"] for name, data in retained.items()}
    (staging / "parity_receipt.json").write_bytes(_json_bytes(success))
    _readonly(staging)
    staging.rename(SUCCESS_ROOT)


def _hash_if_file(path: Path) -> str | None:
    try:
        return _sha256(path) if path.is_file() else None
    except OSError:
        return None


def _write_failure(attempt: int, error: Exception, completed_workers: int) -> Path:
    root = BLOCKER_PARENT / f"maplight-fixed-stage-a-parity-v1-attempt-{attempt:03d}"
    _require(not root.exists(), "failure root already exists")
    BLOCKER_PARENT.mkdir(parents=True, exist_ok=True)
    root.mkdir()
    failure = (
        _failure_fields(error)
        if isinstance(error, ParityError)
        else {
            "kind": type(error).__name__,
            "stage": "supervisor_unhandled",
        }
    )
    receipt = {
        "schema_version": "cypshift.maplight_fixed_parity_failure.v1",
        "attempt": attempt,
        "expected_contract_sha256": CONTRACT_SHA256,
        "observed_inputs": {
            "contract_sha256": _hash_if_file(CONTRACT_PATH),
            "fixture_sha256": _hash_if_file(FIXTURE_PATH),
            "research_project_sha256": _hash_if_file(
                ROOT / "research/maplight-fixed/pyproject.toml"
            ),
            "research_lock_sha256": _hash_if_file(
                ROOT / "research/maplight-fixed/uv.lock"
            ),
            "python_pin_sha256": _hash_if_file(
                ROOT / "research/maplight-fixed/.python-version"
            ),
            "source_files": {
                name: _hash_if_file(SOURCE_ROOT / name) for name in SOURCE_FILES
            },
        },
        "implementation": {
            "source_revision": _git(("rev-parse", "HEAD")),
            "maplight_fixed_features_sha256": _hash_if_file(FEATURE_MODULE_PATH),
            "verify_parity_sha256": _hash_if_file(Path(__file__).resolve()),
        },
        "failure": failure,
        "completed_validated_workers": completed_workers,
        "retained_arrays": 0,
        "accounting": SCIENTIFIC_ZEROS,
    }
    (root / "failure_receipt.json").write_bytes(_json_bytes(receipt))
    _readonly(root)
    return root


def verify_synthetic_parity(attempt: int) -> Path:
    failure_root = (
        BLOCKER_PARENT / f"maplight-fixed-stage-a-parity-v1-attempt-{attempt:03d}"
    )
    _require(not SUCCESS_ROOT.exists(), "success root already exists")
    _require(not failure_root.exists(), "failure root already exists")
    completed_workers = 0
    work: Path | None = None
    staging: Path | None = None
    try:
        work = Path(
            tempfile.mkdtemp(prefix=".maplight-parity-", dir=ROOT / "artifacts")
        )
        staging = Path(
            tempfile.mkdtemp(
                prefix=".maplight-parity-success-", dir=ROOT / "artifacts/benchmarks"
            )
        )
        contract, revision, rows = _verify_preflight()
        fixture = _fixture_receipt(rows)
        workers: dict[str, tuple[dict[str, Path], dict[str, Any]]] = {}
        for worker in WORKERS:
            output = _run_worker(worker, work, revision)
            workers[worker] = _load_worker(output, worker, revision, fixture)
            completed_workers += 1

        upstream_paths, upstream_receipt = workers["upstream"]
        local_a_paths, local_a_receipt = workers["local_a"]
        local_b_paths, _ = workers["local_b"]
        descriptor_names = local_a_receipt["descriptor_names"]
        _require(
            descriptor_names == upstream_receipt["descriptor_names"],
            "descriptor order mismatch",
            stage="descriptor_parity",
        )
        descriptor_hash = hashlib.sha256(
            json.dumps(descriptor_names, separators=(",", ":")).encode()
        ).hexdigest()
        _require(
            descriptor_hash
            == contract["feature_contract"]["blocks"]["rdkit_descriptors"][
                "ordered_names_compact_json_sha256"
            ],
            "descriptor hash mismatch",
            stage="descriptor_parity",
        )

        local_repeat = {
            name: _compare_arrays(
                local_a_paths[name], local_b_paths[name], name, "local_repeat"
            )
            for name in LOCAL_ARRAYS
        }
        upstream_parity = {
            name: _compare_arrays(
                upstream_paths[name], local_a_paths[name], name, "upstream_parity"
            )
            for name in UPSTREAM_ARRAYS
        }
        slices = _compare_slices(local_a_paths)
        morgan_max = int(
            np.load(local_a_paths["morgan_count"], allow_pickle=False).max()
        )
        avalon_max = int(
            np.load(local_a_paths["avalon_count"], allow_pickle=False).max()
        )
        _require(
            max(morgan_max, avalon_max) > 1,
            "fixture does not distinguish count from binary",
            stage="count_coverage",
        )
        features = _import_path("maplight_features_supervisor", FEATURE_MODULE_PATH)
        adversarial = _adversarial_checks(features, local_a_paths, fixture)
        receipt = {
            "schema_version": "cypshift.maplight_fixed_parity.v1",
            "attempt": attempt,
            "source_revision": revision,
            "source_signature": _signature_evidence(revision),
            "contracts": {
                "maplight_fixed_stage_a_contract.json": CONTRACT_SHA256,
                "maplight_source_contract.json": SOURCE_CONTRACT_SHA256,
            },
            "implementation": {
                "maplight_fixed_features.py": _sha256(FEATURE_MODULE_PATH),
                "verify_parity.py": _sha256(Path(__file__).resolve()),
            },
            "fixture": {
                "sha256": FIXTURE_SHA256,
                "rows": fixture,
            },
            "environment": {
                "claim": "hash-locked compatible environment",
                "python": platform.python_version(),
                "platform": platform.platform(),
                "device_policy": "CPU only (declared)",
                "project_sha256": PROJECT_SHA256,
                "lock_sha256": LOCK_SHA256,
                "python_pin_sha256": PYTHON_PIN_SHA256,
                "installed_package_count": 23,
            },
            "worker_sequence": list(WORKERS),
            "descriptor_names_sha256": descriptor_hash,
            "count_maxima": {"morgan_count": morgan_max, "avalon_count": avalon_max},
            "parity": {
                "local_repeat": local_repeat,
                "upstream": upstream_parity,
                "complete_slices": slices,
            },
            "adversarial_checks": adversarial,
            "accounting": {
                "synthetic_top_level_arrays_generated": 17,
                "synthetic_fixture_row_loads": 24,
                "retained_arrays": 6,
                **SCIENTIFIC_ZEROS,
            },
            "claim_boundary": "Synthetic fixed-feature parity only; no real row or model result.",
        }
        _promote_success(staging, local_a_paths, receipt)
        return SUCCESS_ROOT
    except Exception as error:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
        blocker = _write_failure(attempt, error, completed_workers)
        raise ParityError(
            f"parity failed; blocker retained at {blocker.relative_to(ROOT)}",
            kind="parity_attempt_failed",
            stage="supervisor",
        ) from error
    finally:
        if work is not None and work.exists():
            shutil.rmtree(work)


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--_worker", choices=WORKERS, help=argparse.SUPPRESS)
    parser.add_argument("--_worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--_revision", help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if arguments._worker is None:
        _require(
            arguments.attempt is not None and arguments.attempt > 0,
            "--attempt must be positive",
        )
    return arguments


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    if arguments._worker is not None:
        _require(arguments._worker_output is not None, "worker output is required")
        _require(arguments._revision is not None, "worker revision is required")
        return _worker_main(
            arguments._worker, arguments._worker_output, arguments._revision
        )
    try:
        output = verify_synthetic_parity(arguments.attempt)
    except (OSError, ParityError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
