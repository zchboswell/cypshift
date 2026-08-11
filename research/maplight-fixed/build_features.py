#!/usr/bin/env python3
"""Build one immutable, label-free MapLight Stage A feature root."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
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
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn, cast

import maplight_fixed_features as features
import numpy as np
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_stage_a_contract.json"
SHADOW_ROOT = ROOT / "artifacts/benchmarks/tdc-cyp-shadow-v1"
SHADOW_ROWS_PATH = SHADOW_ROOT / "shadow_rows.csv"
SHADOW_MANIFEST_PATH = SHADOW_ROOT / "shadow_manifest.json"
PARITY_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-parity-v1"
PARITY_RECEIPT_PATH = PARITY_ROOT / "parity_receipt.json"
SOURCE_ROOT = (
    ROOT / "data/external/maplight_tdc/c249378c63232354d17083c83fe94fe728960a27"
)
OUTPUT_PARENT = ROOT / "artifacts/benchmarks"
BLOCKER_PARENT = ROOT / "artifacts/blockers"

CONTRACT_SHA256 = "e20985ecabb1aa9ceaeddc3f81ad15dc60b194e250e28de934c12a6bfb10f710"
SHADOW_ROWS_SHA256 = "b633af0cbd5aa98a03ae77eb3e021eb32b441ae8133e24a2c9eb85394e41bc5f"
SHADOW_MANIFEST_SHA256 = (
    "3eb972713d88e08420134e7776755d4e62510a5250edf99edc2021272c112656"
)
PARITY_RECEIPT_SHA256 = (
    "68ee584ac87c53cdc896db6b593f3d84376e8b59573252bd6859192dfa0e94d4"
)
FEATURE_MODULE_SHA256 = (
    "16ba562d9ba99cbf3742bc0a89460ec3a5da89074b4a4a82afee68efb28f5ae6"
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
SHADOW_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure",
    "raw_structure_sha256",
    "standardized_structure",
    "standardized_structure_hash",
    "scaffold_group_hash",
    "community_group_hash",
    "scaffold_repeat_0_outer_fold",
    "scaffold_repeat_0_inner_fold",
    "scaffold_repeat_1_outer_fold",
    "scaffold_repeat_1_inner_fold",
    "scaffold_repeat_2_outer_fold",
    "scaffold_repeat_2_inner_fold",
    "community_repeat_0_outer_fold",
    "community_repeat_0_inner_fold",
    "community_repeat_1_outer_fold",
    "community_repeat_1_inner_fold",
    "community_repeat_2_outer_fold",
    "community_repeat_2_inner_fold",
)
FEATURE_ROW_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure_sha256",
    "standardized_structure_hash",
)
BLOCKS = (
    "binary_morgan",
    "morgan_count",
    "avalon_count",
    "erg",
    "rdkit_descriptors",
)
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


class FeatureBuildError(RuntimeError):
    """A compact, receipt-safe feature-build failure."""

    def __init__(
        self,
        message: str,
        *,
        kind: str = "contract_mismatch",
        stage: str = "preflight",
        block: str | None = None,
        row_index: int | None = None,
        raw_structure_sha256: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.stage = stage
        self.block = block
        self.row_index = row_index
        self.raw_structure_sha256 = raw_structure_sha256


def _require(condition: bool, message: str, **detail: Any) -> None:
    if not condition:
        raise FeatureBuildError(message, **detail)


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
    ).encode()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    _require(isinstance(value, dict), f"{path.name} is not a JSON object")
    return cast(dict[str, Any], value)


def _git(arguments: Sequence[str]) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _clean_revision() -> str:
    _require(not _git(("status", "--porcelain", "--untracked-files=no")), "dirty tree")
    revision = _git(("rev-parse", "HEAD"))
    signature = _git(
        ("show", "-s", "--format=%G?%x00%an%x00%ae%x00%cn%x00%ce", revision)
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
        "source signature or authorship differs",
    )
    return revision


def _normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _verify_environment(contract: Mapping[str, Any]) -> None:
    expected = {
        _normalized_name(key.rsplit("@", 1)[0]): key.rsplit("@", 1)[1]
        for key in contract["compatible_environment"]["resolved_package_licenses"]
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
        _sha256(Path(sys.executable).resolve()) == PYTHON_EXECUTABLE_SHA256,
        "Python executable differs",
    )


def _verify_inputs() -> tuple[dict[str, Any], str]:
    _require(_sha256(CONTRACT_PATH) == CONTRACT_SHA256, "contract hash differs")
    _require(_sha256(SHADOW_ROWS_PATH) == SHADOW_ROWS_SHA256, "shadow rows differ")
    _require(
        _sha256(SHADOW_MANIFEST_PATH) == SHADOW_MANIFEST_SHA256,
        "shadow manifest differs",
    )
    _require(
        _sha256(PARITY_RECEIPT_PATH) == PARITY_RECEIPT_SHA256,
        "parity receipt differs",
    )
    _require(
        _sha256(ROOT / "research/maplight-fixed/maplight_fixed_features.py")
        == FEATURE_MODULE_SHA256,
        "feature implementation differs from parity",
    )
    _require(
        _sha256(ROOT / "research/maplight-fixed/pyproject.toml") == PROJECT_SHA256,
        "research project differs",
    )
    _require(
        _sha256(ROOT / "research/maplight-fixed/uv.lock") == LOCK_SHA256,
        "research lock differs",
    )
    _require(
        _sha256(ROOT / "research/maplight-fixed/.python-version") == PYTHON_PIN_SHA256,
        "Python pin differs",
    )
    _require(
        SOURCE_ROOT.is_dir()
        and not SOURCE_ROOT.is_symlink()
        and SOURCE_ROOT.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        == 0,
        "pinned source root is invalid or writable",
    )
    _require(
        {path.name for path in SOURCE_ROOT.iterdir()} == set(SOURCE_FILES),
        "pinned source file set differs",
    )
    for name, expected_hash in SOURCE_FILES.items():
        path = SOURCE_ROOT / name
        _require(path.is_file() and not path.is_symlink(), "source path is invalid")
        _require(_sha256(path) == expected_hash, f"source hash differs: {name}")
        _require(
            path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) == 0,
            f"source file is writable: {name}",
        )
    contract = _load_json(CONTRACT_PATH)
    parity = _load_json(PARITY_RECEIPT_PATH)
    _require(parity.get("attempt") == 2, "unexpected parity attempt")
    _require(
        parity.get("accounting", {}).get("real_feature_rows_parsed") == 0,
        "parity accounting differs",
    )
    _require(
        set(parity.get("outputs", {})) == {*BLOCKS, "maplight_fixed"},
        "parity block set differs",
    )
    _verify_environment(contract)
    return contract, _clean_revision()


def _read_shadow_rows() -> list[dict[str, str]]:
    with SHADOW_ROWS_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require(
            tuple(reader.fieldnames or ()) == SHADOW_COLUMNS, "shadow schema differs"
        )
        rows = [{key: str(value) for key, value in row.items()} for row in reader]
    _require(len(rows) == 30038, "shadow row count differs")
    _require(
        len({row["molecule_id"] for row in rows}) == len(rows),
        "molecule IDs are not unique",
    )
    for row_index, row in enumerate(rows):
        raw_hash = hashlib.sha256(row["raw_structure"].encode()).hexdigest()
        _require(
            raw_hash == row["raw_structure_sha256"],
            "raw structure hash differs",
            stage="row_validation",
            row_index=row_index,
            raw_structure_sha256=raw_hash,
        )
        standardized_hash = hashlib.sha256(
            row["standardized_structure"].encode()
        ).hexdigest()
        _require(
            standardized_hash == row["standardized_structure_hash"],
            "standardized structure hash differs",
            stage="row_validation",
            row_index=row_index,
            raw_structure_sha256=raw_hash,
        )
    return rows


def _unique_raw_inputs(
    rows: Sequence[Mapping[str, str]],
) -> tuple[tuple[str, ...], tuple[str, ...], NDArray[np.int64]]:
    positions: dict[tuple[str, str], int] = {}
    raw_values: list[str] = []
    raw_hashes: list[str] = []
    inverse: NDArray[np.int64] = np.empty(len(rows), dtype=np.int64)
    for row_index, row in enumerate(rows):
        key = (row["raw_structure_sha256"], row["raw_structure"])
        position = positions.get(key)
        if position is None:
            position = len(raw_values)
            positions[key] = position
            raw_values.append(row["raw_structure"])
            raw_hashes.append(row["raw_structure_sha256"])
        inverse[row_index] = position
    _require(len(raw_values) == 15399, "unique raw input count differs")
    _require(
        len({row["standardized_structure_hash"] for row in rows}) == 15354,
        "standardized structure count differs",
    )
    multi_raw: dict[str, set[str]] = {}
    for row in rows:
        multi_raw.setdefault(row["standardized_structure_hash"], set()).add(
            row["raw_structure"]
        )
    multiplicities = [len(values) for values in multi_raw.values()]
    _require(
        sum(value > 1 for value in multiplicities) == 41, "multi-raw hash count differs"
    )
    _require(
        sum(value - 1 for value in multiplicities) == 45,
        "excess raw form count differs",
    )
    _require(max(multiplicities) == 4, "maximum raw-form multiplicity differs")
    return tuple(raw_values), tuple(raw_hashes), inverse


def _write_feature_rows(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=FEATURE_ROW_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row[name] for name in FEATURE_ROW_COLUMNS})


def _write_arrays(
    root: Path,
    unique_features: Any,
    inverse: NDArray[np.int64],
) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for name in BLOCKS:
        unique_array = cast(NDArray[Any], getattr(unique_features, name))
        array = np.ascontiguousarray(unique_array[inverse])
        _require(array.shape[0] == 30038, "expanded feature row count differs")
        path = root / f"{name}.npy"
        features.write_npy_v1(path, array)
        retained = np.load(path, allow_pickle=False)
        _require(np.array_equal(retained, array), "retained feature array differs")
        records[name] = {
            "path": path.name,
            "shape": list(retained.shape),
            "dtype": str(retained.dtype),
            "c_contiguous": bool(retained.flags.c_contiguous),
            "nonfinite_count": int((~np.isfinite(retained)).sum()),
            "element_sha256": hashlib.sha256(retained.tobytes(order="C")).hexdigest(),
            "npy_sha256": _sha256(path),
            "npy_size_bytes": path.stat().st_size,
        }
    return records


def _readonly(root: Path) -> None:
    for path in root.iterdir():
        os.chmod(path, 0o444)
    os.chmod(root, 0o555)


def _peak_rss_gib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**3)


def _timeout(_signum: int, _frame: object) -> NoReturn:
    raise FeatureBuildError(
        "feature build exceeded one hour", kind="runtime_limit", stage="resource_limit"
    )


def _failure_fields(error: Exception) -> dict[str, object]:
    fields: dict[str, object] = {
        "kind": getattr(error, "kind", type(error).__name__),
        "stage": getattr(error, "stage", "unhandled"),
    }
    for name in ("block", "row_index", "raw_structure_sha256"):
        value = getattr(error, name, None)
        if value is not None:
            fields[name] = value
    return fields


def _write_failure(build_id: int, error: Exception, elapsed: float) -> Path:
    root = (
        BLOCKER_PARENT / f"maplight-fixed-stage-a-features-v1-build-{build_id}-blocker"
    )
    _require(not root.exists(), "feature blocker root already exists")
    root.mkdir(parents=True)
    receipt = {
        "schema_version": "cypshift.maplight_fixed_feature_failure.v1",
        "build_id": build_id,
        "failure": _failure_fields(error),
        "elapsed_seconds": elapsed,
        "peak_rss_gib": _peak_rss_gib(),
        "inputs": {
            "contract_sha256": _sha256(CONTRACT_PATH),
            "shadow_rows_sha256": _sha256(SHADOW_ROWS_PATH),
            "shadow_manifest_sha256": _sha256(SHADOW_MANIFEST_PATH),
            "parity_receipt_sha256": _sha256(PARITY_RECEIPT_PATH),
        },
        "accounting": {"persisted_block_arrays": 0, **SCIENTIFIC_ZEROS},
    }
    (root / "failure_receipt.json").write_bytes(_json_bytes(receipt))
    _readonly(root)
    return root


def build_label_free_features(build_id: int) -> Path:
    output = OUTPUT_PARENT / f"maplight-fixed-stage-a-features-v1-build-{build_id}"
    blocker = (
        BLOCKER_PARENT / f"maplight-fixed-stage-a-features-v1-build-{build_id}-blocker"
    )
    _require(build_id in (1, 2), "build ID must be 1 or 2")
    _require(not output.exists(), "feature output already exists")
    _require(not blocker.exists(), "feature blocker already exists")
    start = time.perf_counter()
    staging: Path | None = None
    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(3600)
    try:
        contract, revision = _verify_inputs()
        rows = _read_shadow_rows()
        raw_values, raw_hashes, inverse = _unique_raw_inputs(rows)
        try:
            unique_features = features.featurize_raw_structures(raw_values, raw_hashes)
        except features.MapLightFeatureError as error:
            row_index = error.row_index
            raise FeatureBuildError(
                "feature generation failed",
                kind=type(error).__name__,
                stage="feature_generation",
                block=error.block,
                row_index=row_index,
                raw_structure_sha256=(
                    raw_hashes[row_index] if row_index is not None else None
                ),
            ) from error
        staging = Path(
            tempfile.mkdtemp(prefix=".maplight-features-", dir=OUTPUT_PARENT)
        )
        row_path = staging / "feature_rows.csv"
        _write_feature_rows(row_path, rows)
        arrays = _write_arrays(staging, unique_features, inverse)
        elapsed = time.perf_counter() - start
        peak = _peak_rss_gib()
        _require(
            elapsed <= 3600,
            "feature runtime exceeded",
            kind="runtime_limit",
            stage="resource_limit",
        )
        _require(
            peak <= 8,
            "feature memory exceeded",
            kind="memory_limit",
            stage="resource_limit",
        )
        _, final_revision = _verify_inputs()
        _require(
            final_revision == revision,
            "inputs changed during feature build",
            stage="final_rehash",
        )
        manifest = {
            "schema_version": "cypshift.maplight_fixed_features.v1",
            "build_id": build_id,
            "source_revision": revision,
            "inputs": {
                "contract_sha256": CONTRACT_SHA256,
                "shadow_rows_sha256": SHADOW_ROWS_SHA256,
                "shadow_manifest_sha256": SHADOW_MANIFEST_SHA256,
                "parity_receipt_sha256": PARITY_RECEIPT_SHA256,
                "feature_module_sha256": FEATURE_MODULE_SHA256,
                "research_project_sha256": PROJECT_SHA256,
                "research_lock_sha256": LOCK_SHA256,
                "python_pin_sha256": PYTHON_PIN_SHA256,
            },
            "rows": {
                "path": row_path.name,
                "sha256": _sha256(row_path),
                "rows": len(rows),
                "columns": list(FEATURE_ROW_COLUMNS),
            },
            "arrays": arrays,
            "population": {
                "source_rows": len(rows),
                "unique_raw_featurizations": len(raw_values),
                "unique_standardized_structures": 15354,
                "standardized_hashes_with_multiple_raw_forms": 41,
                "excess_raw_forms": 45,
                "maximum_raw_forms_per_standardized_hash": 4,
            },
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "device_policy": "CPU only (declared)",
            },
            "runtime_seconds": elapsed,
            "peak_rss_gib": peak,
            "accounting": {
                "feature_builds": 1,
                "persisted_block_arrays": 5,
                "source_rows_parsed": len(rows),
                "exact_raw_featurizations": len(raw_values),
                **SCIENTIFIC_ZEROS,
            },
            "claim_boundary": "Label-free fixed feature artifact; no model or score.",
        }
        (staging / "feature_manifest.json").write_bytes(_json_bytes(manifest))
        _readonly(staging)
        staging.rename(output)
        return output
    except Exception as error:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
        retained = _write_failure(build_id, error, time.perf_counter() - start)
        raise FeatureBuildError(
            f"feature build failed; blocker retained at {retained.relative_to(ROOT)}",
            kind="feature_build_failed",
            stage="supervisor",
        ) from error
    finally:
        signal.alarm(0)


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-id", required=True, type=int, choices=(1, 2))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    try:
        output = build_label_free_features(arguments.build_id)
    except (FeatureBuildError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
