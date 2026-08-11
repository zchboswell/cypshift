"""Build the one frozen MapLight signed-int8 plus charge-NaN feature overlay.

This direct research script reuses the reviewed signed-int8 runner's receipt,
environment, row, and serialization helpers.  It adds no feature registry or
model surface.  Its only scientific change is the exact D-027 NaN policy.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import signal
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, NoReturn

import maplight_fixed_features as features
import numpy as np
import run_int8_compat as base
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[2]
BUILDER_PATH = Path(__file__).resolve()
CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_nan_compat_contract.json"
DIAGNOSIS_PATH = ROOT / "benchmarks/receipts/maplight_fixed_nan_diagnosis.json"
PRIOR_BLOCKER_PATH = (
    ROOT
    / "artifacts/blockers/maplight-fixed-upstream-int8-features-v1-build-1-blocker"
    / "failure_receipt.json"
)
PARITY_RECEIPT_PATH = base.PARITY_ROOT / "compatibility_parity_receipt.json"

CONTRACT_SHA256 = "52f01f93470cfe461e7ee9fed0ff3a06d7362aceaef343da0c5840d2a74bea09"
DIAGNOSIS_SHA256 = "9832efb282ff965b8234a178ea9f79db3df6e6b9e6499268afaac46fb4905230"
PRIOR_BLOCKER_SHA256 = (
    "b337f9653c95c0f7a7b6881e4e77378f877020d9766d04c73250d15091f4ba73"
)
PARITY_RECEIPT_SHA256 = (
    "a5d1c0004efdc9f35b15ebadf87b77c3ccfbf09454efe7aede58b6355c257ecb"
)

ALLOWED_INDICES = features.ALLOWED_GASTEIGER_NAN_DESCRIPTOR_INDICES
ALLOWED_NAMES = features.ALLOWED_GASTEIGER_NAN_DESCRIPTOR_NAMES
PERSISTED_BLOCKS = base.PERSISTED_BLOCKS
SCIENTIFIC_ZEROS = {
    "target_values_parsed": 0,
    "scientific_model_fits": 0,
    "scientific_predictions": 0,
    "metric_evaluations": 0,
    "public_test_rows_used": 0,
    "public_test_labels_parsed": 0,
    "public_test_family_task_slots_consumed": 0,
    "gin_weight_bytes_downloaded": 0,
    "challenge_assumptions_added": 0,
}
FEATURE_CLAIM = (
    "Label-free exact-upstream signed-int8 features preserving only the four "
    "diagnosed Gasteiger charge NaNs; no scientific model or score."
)
FAILURE_CLAIM = (
    "Label-free NaN-compatibility feature failure; no scientific model or score."
)
MANIFEST_FIELDS = (
    "schema_version",
    "experiment",
    "build_id",
    "prior_build",
    "source_revision",
    "contracts",
    "inputs",
    "implementation",
    "compatibility_parity",
    "rows",
    "arrays",
    "overflow",
    "nonfinite",
    "consumer_probe",
    "population",
    "environment",
    "runtime_seconds",
    "peak_rss_gib",
    "accounting",
    "claim_boundary",
)


class NanCompatError(base.CompatError):
    """Compact D-027 error carrying no raw structure text."""

    def __init__(
        self,
        message: str,
        *,
        kind: str = "contract_mismatch",
        stage: str = "preflight",
        block: str | None = None,
        unique_raw_index: int | None = None,
        raw_structure_sha256: str | None = None,
        descriptor_index: int | None = None,
        descriptor_name: str | None = None,
        expected: str | int | None = None,
        observed: str | int | None = None,
    ) -> None:
        super().__init__(
            message,
            kind=kind,
            stage=stage,
            block=block,
            unique_raw_index=unique_raw_index,
            raw_structure_sha256=raw_structure_sha256,
            expected=expected,
            observed=observed,
        )
        self.descriptor_index = descriptor_index
        self.descriptor_name = descriptor_name


def _output(build_id: int) -> Path:
    return base.OUTPUT_PARENT / (
        f"maplight-fixed-upstream-int8-nan-features-v1-build-{build_id}"
    )


def _blocker(build_id: int) -> Path:
    return base.BLOCKER_PARENT / (
        f"maplight-fixed-upstream-int8-nan-features-v1-build-{build_id}-blocker"
    )


def _implementation(revision: str) -> dict[str, str]:
    return {
        "source_revision": revision,
        "feature_module_path": base.FEATURE_PATH.relative_to(ROOT).as_posix(),
        "feature_module_sha256": base._sha256(base.FEATURE_PATH),
        "signed_int8_runner_path": base.BUILDER_PATH.relative_to(ROOT).as_posix(),
        "signed_int8_runner_sha256": base._sha256(base.BUILDER_PATH),
        "nan_runner_path": BUILDER_PATH.relative_to(ROOT).as_posix(),
        "nan_runner_sha256": base._sha256(BUILDER_PATH),
    }


def _contracts() -> dict[str, str]:
    return {
        "nan_compatibility": CONTRACT_SHA256,
        "signed_int8_compatibility": base.CONTRACT_SHA256,
        "stage_a_parent": base.PARENT_CONTRACT_SHA256,
    }


def _inputs() -> dict[str, str]:
    return {
        "shadow_rows": base.SHADOW_ROWS_SHA256,
        "shadow_manifest": base.SHADOW_MANIFEST_SHA256,
        "signed_int8_parity": PARITY_RECEIPT_SHA256,
        "signed_int8_feature_blocker": PRIOR_BLOCKER_SHA256,
        "nan_diagnosis": DIAGNOSIS_SHA256,
    }


def _verify_common() -> tuple[dict[str, Any], str]:
    parent, revision = base._verify_common()
    for path, expected in (
        (CONTRACT_PATH, CONTRACT_SHA256),
        (DIAGNOSIS_PATH, DIAGNOSIS_SHA256),
        (PRIOR_BLOCKER_PATH, PRIOR_BLOCKER_SHA256),
        (PARITY_RECEIPT_PATH, PARITY_RECEIPT_SHA256),
    ):
        base._require_hash(path, expected)
    base._require(
        base._read_only_regular_file(PRIOR_BLOCKER_PATH),
        "signed-int8 blocker mode differs",
    )
    relative_builder = BUILDER_PATH.relative_to(ROOT).as_posix()
    base._require(
        base._git(("ls-files", "--error-unmatch", relative_builder))
        == relative_builder,
        "NaN runner is not tracked",
    )
    contract = base._load_json(CONTRACT_PATH)
    diagnosis = base._load_json(DIAGNOSIS_PATH)
    base._require(
        contract["sole_scientific_change"]["allowed_columns"]
        == [
            {"index": index, "name": name}
            for index, name in zip(ALLOWED_INDICES, ALLOWED_NAMES, strict=True)
        ],
        "allowed NaN columns differ",
    )
    expected = contract["sole_scientific_change"]["expected_label_free_diagnostic"]
    evidence = diagnosis["nonfinite_descriptor_policy_evidence"]
    base._require(
        evidence["descriptor_indices"] == list(ALLOWED_INDICES)
        and evidence["descriptor_names"] == list(ALLOWED_NAMES)
        and evidence["unique_exact_raw_structures_affected"]
        == expected["unique_exact_raw_structures_with_allowed_nan"],
        "tracked NaN diagnosis differs",
    )
    return parent, revision


def _verify_frozen_parity() -> dict[str, Any]:
    base._require(
        base._path_absent(base.PARITY_BLOCKER_ROOT),
        "signed-int8 parity blocker exists",
    )
    base._require(base._read_only_root(base.PARITY_ROOT), "parity root is invalid")
    expected_files = {
        "compatibility_parity_receipt.json",
        *(f"{name}.npy" for name in base.LOCAL_ARRAYS),
    }
    base._require(
        {path.name for path in base.PARITY_ROOT.iterdir()} == expected_files
        and all(
            base._read_only_regular_file(path) for path in base.PARITY_ROOT.iterdir()
        ),
        "parity file set or mode differs",
    )
    base._require_hash(PARITY_RECEIPT_PATH, PARITY_RECEIPT_SHA256)
    receipt = base._load_json(PARITY_RECEIPT_PATH)
    base._require(
        set(receipt["arrays"]) == set(base.LOCAL_ARRAYS), "parity arrays differ"
    )
    for name, record in receipt["arrays"].items():
        base._require(record["path"] == f"{name}.npy", "parity path differs")
        base._require(
            record
            == base._array_record(
                base.PARITY_ROOT / record["path"], *base.ARRAY_SPECS[name]
            ),
            f"parity array differs: {name}",
        )
    base._require(
        receipt["accounting"]["real_feature_rows_parsed"] == 0,
        "parity scientific boundary differs",
    )
    return receipt


def _array_record(
    path: Path,
    shape: tuple[int, int],
    dtype: np.dtype[Any],
    *,
    allowed_nan_columns: tuple[int, ...] = (),
) -> dict[str, object]:
    with path.open("rb") as handle:
        version = np.lib.format.read_magic(handle)
    base._require(version == (1, 0), "array NPY version differs")
    array = np.load(path, allow_pickle=False)
    base._require(array.shape == shape, "array shape differs")
    base._require(array.dtype == dtype, "array dtype differs")
    base._require(array.flags.c_contiguous, "array is not C-contiguous")
    base._require(not bool(np.isinf(array).any()), "array contains infinity")
    nan = np.isnan(array)
    if bool(nan.any()):
        allowed = np.zeros(array.shape[1], dtype=np.bool_)
        allowed[list(allowed_nan_columns)] = True
        base._require(
            not bool(np.logical_and(nan, ~allowed[np.newaxis, :]).any()),
            "array contains NaN outside allowed columns",
        )
    return {
        "path": path.name,
        "shape": list(array.shape),
        "dtype": str(array.dtype),
        "c_contiguous": True,
        "nonfinite_count": int(nan.sum()),
        "element_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
        "npy_sha256": base._sha256(path),
        "npy_size_bytes": path.stat().st_size,
    }


def _nonfinite_record(
    unique_descriptors: NDArray[np.float64],
    expanded_descriptors: NDArray[np.float64],
    raw_hashes: tuple[str, ...],
) -> dict[str, object]:
    unique_nan = np.isnan(unique_descriptors)
    expanded_nan = np.isnan(expanded_descriptors)
    allowed = np.zeros(unique_descriptors.shape[1], dtype=np.bool_)
    allowed[list(ALLOWED_INDICES)] = True
    base._require(
        not bool(np.isinf(unique_descriptors).any())
        and not bool(np.isinf(expanded_descriptors).any()),
        "descriptor infinity detected",
    )
    base._require(
        not bool(np.logical_and(unique_nan, ~allowed[np.newaxis, :]).any())
        and not bool(np.logical_and(expanded_nan, ~allowed[np.newaxis, :]).any()),
        "descriptor NaN mask differs",
    )
    affected = np.flatnonzero(unique_nan.any(axis=1))
    base._require(len(affected) > 0, "diagnosed NaN population is absent")
    record = {
        "allowed_kind": "NaN",
        "allowed_descriptor_indices": list(ALLOWED_INDICES),
        "allowed_descriptor_names": list(ALLOWED_NAMES),
        "unique_exact_raw_structures_with_nan": int(unique_nan.any(axis=1).sum()),
        "expanded_rows_with_nan": int(expanded_nan.any(axis=1).sum()),
        "unique_nan_cells": int(unique_nan.sum()),
        "expanded_nan_cells": int(expanded_nan.sum()),
        "positive_infinity_cells": int(np.isposinf(expanded_descriptors).sum()),
        "negative_infinity_cells": int(np.isneginf(expanded_descriptors).sum()),
        "nan_cells_outside_allowed_columns": int(
            np.logical_and(expanded_nan, ~allowed[np.newaxis, :]).sum()
        ),
        "first_unique_exact_raw_index": int(affected[0]),
        "first_raw_structure_sha256": raw_hashes[int(affected[0])],
    }
    expected = base._load_json(CONTRACT_PATH)["sole_scientific_change"][
        "expected_label_free_diagnostic"
    ]
    translated = {
        "unique_exact_raw_structures_with_nan": expected[
            "unique_exact_raw_structures_with_allowed_nan"
        ],
        "expanded_rows_with_nan": expected["expanded_rows_with_allowed_nan"],
        "unique_nan_cells": expected["unique_nan_cells"],
        "expanded_nan_cells": expected["expanded_nan_cells"],
        "first_unique_exact_raw_index": expected["first_unique_exact_raw_index"],
        "first_raw_structure_sha256": expected["first_raw_structure_sha256"],
    }
    base._require(
        all(record[key] == value for key, value in translated.items())
        and record["positive_infinity_cells"] == 0
        and record["negative_infinity_cells"] == 0
        and record["nan_cells_outside_allowed_columns"] == 0,
        "NaN diagnosis does not reproduce",
    )
    return record


def _expected_nonfinite_record() -> dict[str, object]:
    expected = base._load_json(CONTRACT_PATH)["sole_scientific_change"][
        "expected_label_free_diagnostic"
    ]
    return {
        "allowed_kind": "NaN",
        "allowed_descriptor_indices": list(ALLOWED_INDICES),
        "allowed_descriptor_names": list(ALLOWED_NAMES),
        "unique_exact_raw_structures_with_nan": expected[
            "unique_exact_raw_structures_with_allowed_nan"
        ],
        "expanded_rows_with_nan": expected["expanded_rows_with_allowed_nan"],
        "unique_nan_cells": expected["unique_nan_cells"],
        "expanded_nan_cells": expected["expanded_nan_cells"],
        "positive_infinity_cells": 0,
        "negative_infinity_cells": 0,
        "nan_cells_outside_allowed_columns": 0,
        "first_unique_exact_raw_index": expected["first_unique_exact_raw_index"],
        "first_raw_structure_sha256": expected["first_raw_structure_sha256"],
    }


def _catboost_probe() -> dict[str, object]:
    catboost = __import__("catboost")
    matrix = np.array(
        [[0.0, np.nan], [1.0, 0.0], [0.0, 1.0], [1.0, np.nan]] * 2,
        dtype=np.float64,
    )
    target = np.array([0, 1, 0, 1] * 2, dtype=np.int8)
    model = catboost.CatBoostClassifier(
        loss_function="Logloss",
        random_strength=2,
        random_seed=1,
        verbose=0,
        allow_writing_files=False,
        thread_count=1,
    )
    model.fit(matrix, target)
    probability = model.predict_proba(matrix)[:, 1]
    resolved = model.get_all_params()["nan_mode"]
    base._require(bool(np.isfinite(probability).all()), "probe prediction is nonfinite")
    base._require(resolved == "Min", "CatBoost resolved nan_mode differs")
    return {
        "library": "CatBoostClassifier",
        "version": importlib.metadata.version("catboost"),
        "rows": 8,
        "synthetic_fits_attempted": 1,
        "synthetic_fits_completed": 1,
        "finite_probabilities": True,
        "resolved_nan_mode": resolved,
    }


def _validate_build(
    root: Path,
    build_id: int,
    revision: str,
    *,
    read_only: bool = True,
) -> dict[str, Any]:
    expected_files = {
        "feature_manifest.json",
        "feature_rows.csv",
        *(f"{name}.npy" for name in PERSISTED_BLOCKS),
    }
    base._require(root.is_dir() and not root.is_symlink(), "build root is invalid")
    base._require(
        {path.name for path in root.iterdir()} == expected_files,
        "build file set differs",
    )
    if read_only:
        base._require(
            base._read_only_root(root)
            and all(base._read_only_regular_file(path) for path in root.iterdir()),
            "build mode differs",
        )
    manifest = base._load_json(root / "feature_manifest.json")
    base._exact_keys(manifest, MANIFEST_FIELDS, "feature manifest")
    base._require(
        manifest["schema_version"] == "cypshift.maplight_nan_compat_features.v1"
        and manifest["experiment"] == "maplight_fixed_upstream_int8_nan_v1"
        and manifest["build_id"] == build_id,
        "build identity differs",
    )
    base._require(manifest["source_revision"] == revision, "revision differs")
    base._require(manifest["contracts"] == _contracts(), "contracts differ")
    base._require(manifest["inputs"] == _inputs(), "inputs differ")
    base._require(
        manifest["implementation"] == _implementation(revision),
        "implementation differs",
    )
    parity = base._load_json(PARITY_RECEIPT_PATH)
    base._require(
        manifest["compatibility_parity"]
        == {
            "receipt_sha256": PARITY_RECEIPT_SHA256,
            "historical_source_revision": parity["source_revision"],
        },
        "parity binding differs",
    )
    if build_id == 1:
        base._require(manifest["prior_build"] is None, "prior build differs")
    else:
        base._require(
            manifest["prior_build"]
            == {
                "manifest_sha256": base._sha256(_output(1) / "feature_manifest.json"),
                "validated_before_row_resolution": True,
            },
            "prior build differs",
        )
    base._require(
        manifest["rows"]
        == {
            "path": "feature_rows.csv",
            "sha256": base._sha256(root / "feature_rows.csv"),
            "rows": 30038,
            "columns": list(base.FEATURE_ROW_COLUMNS),
        },
        "feature rows differ",
    )
    base._require(set(manifest["arrays"]) == set(PERSISTED_BLOCKS), "arrays differ")
    for name, record in manifest["arrays"].items():
        base._require(record["path"] == f"{name}.npy", "array path differs")
        allowed = ALLOWED_INDICES if name == "rdkit_descriptors" else ()
        base._require(
            record
            == _array_record(
                root / record["path"],
                *base.REAL_ARRAY_SPECS[name],
                allowed_nan_columns=allowed,
            ),
            f"array receipt differs: {name}",
        )
    base._require(
        manifest["nonfinite"] == _expected_nonfinite_record()
        and manifest["arrays"]["rdkit_descriptors"]["nonfinite_count"] == 328
        and all(
            manifest["arrays"][name]["nonfinite_count"] == 0
            for name in PERSISTED_BLOCKS
            if name != "rdkit_descriptors"
        ),
        "nonfinite receipt differs",
    )
    base._require(
        set(manifest["overflow"]) == {"morgan_count", "avalon_count"},
        "overflow blocks differ",
    )
    for record in manifest["overflow"].values():
        base._exact_keys(
            record, tuple(features.CountOverflowStats.__annotations__), "overflow"
        )
        base._require(
            all(type(value) is int for value in record.values())
            and record["maximum_preconversion_count"] >= 0
            and 0 <= record["unique_raw_rows_with_counts_above_127"] <= 15399
            and record["bins_above_127"] >= 0
            and -128 <= record["minimum_converted_int8_value"] <= 127
            and -128 <= record["maximum_converted_int8_value"] <= 127,
            "overflow receipt differs",
        )
    base._require(
        manifest["consumer_probe"]
        == {
            "library": "CatBoostClassifier",
            "version": "1.2.1",
            "rows": 8,
            "synthetic_fits_attempted": 1,
            "synthetic_fits_completed": 1,
            "finite_probabilities": True,
            "resolved_nan_mode": "Min",
        },
        "consumer probe differs",
    )
    base._require(manifest["population"] == base._population(), "population differs")
    base._require(manifest["environment"] == base._environment(), "environment differs")
    accounting = manifest["accounting"]
    base._exact_keys(
        accounting, ("current_attempt", "cumulative", "scientific_zeros"), "accounting"
    )
    expected_current = base._operation_accounting([1, 1, 30038, 15399, 5, 5, 0])
    expected_cumulative = base._operation_accounting(
        [1, 1, 30038, 15399, 5, 5, 0]
        if build_id == 1
        else [2, 2, 60076, 30798, 10, 10, 0]
    )
    base._require(
        accounting["current_attempt"] == expected_current
        and accounting["cumulative"] == expected_cumulative
        and accounting["scientific_zeros"] == SCIENTIFIC_ZEROS,
        "scientific accounting differs",
    )
    base._require(
        type(manifest["runtime_seconds"]) in (int, float)
        and 0 <= manifest["runtime_seconds"] <= 3600
        and type(manifest["peak_rss_gib"]) in (int, float)
        and 0 <= manifest["peak_rss_gib"] <= 8,
        "resource receipt differs",
    )
    base._require(manifest["claim_boundary"] == FEATURE_CLAIM, "claim differs")
    return manifest


def _failure_fields(error: Exception) -> dict[str, object]:
    result = base._failure_fields(error)
    result["descriptor_index"] = getattr(error, "descriptor_index", None)
    result["descriptor_name"] = getattr(error, "descriptor_name", None)
    return result


def _write_failure(
    build_id: int,
    error: Exception,
    revision: str | None,
    elapsed: float,
    current: Mapping[str, int],
    cumulative: Mapping[str, int],
) -> Path:
    receipt = {
        "schema_version": "cypshift.maplight_nan_compat_feature_failure.v1",
        "experiment": "maplight_fixed_upstream_int8_nan_v1",
        "build_id": build_id,
        "source_revision": revision,
        "contracts": _contracts(),
        "inputs": _inputs(),
        "implementation": _implementation(revision) if revision else None,
        "failure": _failure_fields(error),
        "runtime_seconds": elapsed,
        "peak_rss_gib": base._peak_rss_gib(),
        "accounting": {
            "current_attempt": dict(current),
            "cumulative": dict(cumulative),
            "scientific_zeros": SCIENTIFIC_ZEROS,
        },
        "claim_boundary": FAILURE_CLAIM,
    }
    return base._promote_failure(_blocker(build_id), receipt)


def _timeout(_signum: int, _frame: object) -> NoReturn:
    raise NanCompatError(
        "feature build timed out", kind="runtime_limit", stage="resource"
    )


def build_nan_compat_features(build_id: int) -> Path:
    base._require(build_id in (1, 2), "build ID differs")
    output = _output(build_id)
    blocker = _blocker(build_id)
    base._require(
        base._path_absent(output) and base._path_absent(blocker),
        "build output already exists",
    )
    revision: str | None = None
    staging: Path | None = None
    start = time.perf_counter()
    current = base._operation_accounting([1, 0, 0, 0, 0, 0, 0])
    prior_counts = base._operation_accounting([0, 0, 0, 0, 0, 0, 0])
    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(3600)
    try:
        _, revision = _verify_common()
        _verify_frozen_parity()
        prior: dict[str, Any] | None = None
        if build_id == 2:
            base._require(base._path_absent(_blocker(1)), "build 1 blocker exists")
            prior = _validate_build(_output(1), 1, revision)
            prior_counts = base._operation_accounting([1, 1, 30038, 15399, 5, 5, 0])
        base._require(base._read_only_root(base.SHADOW_ROOT), "shadow root is invalid")
        base._require_hash(base.SHADOW_ROWS_PATH, base.SHADOW_ROWS_SHA256)
        base._require_hash(base.SHADOW_MANIFEST_PATH, base.SHADOW_MANIFEST_SHA256)
        rows = base._read_shadow_rows()
        current["source_rows_parsed"] = len(rows)
        raw, hashes, inverse = base._unique_raw_inputs(rows)

        def block_completed(_name: str) -> None:
            current["in_memory_block_arrays_completed"] += 1

        try:
            unique_features, overflow = features.featurize_raw_structures_upstream_int8(
                raw,
                hashes,
                block_completed=block_completed,
                nonfinite_policy="allow_gasteiger_charge_nan",
            )
        except features.MapLightFeatureError as error:
            index = error.row_index
            column = error.column_index
            raise NanCompatError(
                "feature generation failed",
                kind=type(error).__name__,
                stage="feature_generation",
                block=error.block,
                unique_raw_index=index,
                raw_structure_sha256=hashes[index] if index is not None else None,
                descriptor_index=column if error.block == "rdkit_descriptors" else None,
                descriptor_name=(
                    features.DESCRIPTOR_NAMES[column]
                    if error.block == "rdkit_descriptors" and column is not None
                    else None
                ),
            ) from error
        current["exact_raw_featurizations"] = len(raw)
        expanded_descriptors = np.ascontiguousarray(
            unique_features.rdkit_descriptors[inverse]
        )
        nonfinite = _nonfinite_record(
            unique_features.rdkit_descriptors, expanded_descriptors, hashes
        )
        probe = _catboost_probe()
        staging = Path(
            tempfile.mkdtemp(prefix=".nan-features-", dir=base.OUTPUT_PARENT)
        )
        row_path = staging / "feature_rows.csv"
        base._write_feature_rows(row_path, rows)
        arrays: dict[str, dict[str, object]] = {}
        for name in PERSISTED_BLOCKS:
            array = np.ascontiguousarray(getattr(unique_features, name)[inverse])
            target = staging / f"{name}.npy"
            features.write_npy_v1(target, array)
            arrays[name] = _array_record(
                target,
                *base.REAL_ARRAY_SPECS[name],
                allowed_nan_columns=(
                    ALLOWED_INDICES if name == "rdkit_descriptors" else ()
                ),
            )
            current["persisted_block_arrays"] += 1
        if build_id == 2:
            prior_root = _output(1)
            base._require(
                row_path.read_bytes() == (prior_root / "feature_rows.csv").read_bytes(),
                "repeat rows differ",
            )
            for name in PERSISTED_BLOCKS:
                base._require(
                    (staging / f"{name}.npy").read_bytes()
                    == (prior_root / f"{name}.npy").read_bytes(),
                    f"repeat array differs: {name}",
                )
        success_current = dict(current)
        success_current["completed_feature_builds"] = 1
        success_cumulative = (
            success_current
            if build_id == 1
            else base._add_operations(prior_counts, success_current)
        )
        elapsed = time.perf_counter() - start
        peak = base._peak_rss_gib()
        base._require(elapsed <= 3600 and peak <= 8, "resource cap exceeded")
        _, final_revision = _verify_common()
        _verify_frozen_parity()
        base._require(final_revision == revision, "inputs changed during build")
        manifest: dict[str, Any] = {
            "schema_version": "cypshift.maplight_nan_compat_features.v1",
            "experiment": "maplight_fixed_upstream_int8_nan_v1",
            "build_id": build_id,
            "prior_build": (
                None
                if prior is None
                else {
                    "manifest_sha256": base._sha256(
                        _output(1) / "feature_manifest.json"
                    ),
                    "validated_before_row_resolution": True,
                }
            ),
            "source_revision": revision,
            "contracts": _contracts(),
            "inputs": _inputs(),
            "implementation": _implementation(revision),
            "compatibility_parity": {
                "receipt_sha256": PARITY_RECEIPT_SHA256,
                "historical_source_revision": base._load_json(PARITY_RECEIPT_PATH)[
                    "source_revision"
                ],
            },
            "rows": {
                "path": row_path.name,
                "sha256": base._sha256(row_path),
                "rows": 30038,
                "columns": list(base.FEATURE_ROW_COLUMNS),
            },
            "arrays": arrays,
            "overflow": {name: asdict(record) for name, record in overflow.items()},
            "nonfinite": nonfinite,
            "consumer_probe": probe,
            "population": base._population(),
            "environment": base._environment(),
            "runtime_seconds": elapsed,
            "peak_rss_gib": peak,
            "accounting": {
                "current_attempt": success_current,
                "cumulative": success_cumulative,
                "scientific_zeros": SCIENTIFIC_ZEROS,
            },
            "claim_boundary": FEATURE_CLAIM,
        }
        if prior is not None:
            for key in (
                "contracts",
                "inputs",
                "implementation",
                "compatibility_parity",
                "overflow",
                "nonfinite",
                "consumer_probe",
                "population",
                "environment",
                "claim_boundary",
            ):
                base._require(manifest[key] == prior[key], f"repeat {key} differs")
        (staging / "feature_manifest.json").write_bytes(base._json_bytes(manifest))
        _validate_build(staging, build_id, revision, read_only=False)
        signal.alarm(0)
        base._readonly(staging)
        staging.rename(output)
        return output
    except Exception as error:
        if staging is not None and staging.exists():
            base._remove_staging(staging)
            current["staging_roots_removed"] += 1
        cumulative = base._add_operations(prior_counts, current)
        failure = _write_failure(
            build_id,
            error,
            revision,
            time.perf_counter() - start,
            current,
            cumulative,
        )
        raise NanCompatError(
            f"feature build failed; blocker retained at {failure}"
        ) from error
    finally:
        signal.alarm(0)


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-id", type=int, choices=(1, 2), required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    try:
        output = build_nan_compat_features(arguments.build_id)
    except (base.CompatError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
