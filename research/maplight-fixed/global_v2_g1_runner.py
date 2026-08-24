#!/usr/bin/env python3
"""Synthetic-only nested EXP-G1 runner for OpenADMET Global-v2.

This module implements the G2-3B control plane.  It deliberately separates a
deterministic full-topology model double from the small real-CatBoost runtime
probe.  Neither path has authority to open official inputs or to make a
scientific model claim.
"""

from __future__ import annotations

import csv
import importlib.metadata
import io
import json
import math
import platform
import random
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_runner as base
import numpy as np

ROOT: Final = Path(__file__).resolve().parents[2]
SCRIPT: Final = Path(__file__).resolve()
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from cypshift.openadmet_global_v2_metric import (  # noqa: E402
    PredictionRow,
    TruthRow,
    tutorial_endpoint_st_rae,
)

CONTRACT: Final = (
    ROOT / "benchmarks/openadmet_cyp_2026/global_v2_g1_synthetic_contract.json"
)
CONTRACT_SHA256: Final = (
    "c8c706a815c3fa44933021e1f44b33cb3372a9334c9bc34f01dd5c851bdba866"
)
PARENT: Final = ROOT / "benchmarks/openadmet_cyp_2026/global_v2_g1_screen_contract.json"
PARENT_SHA256: Final = (
    "ce39721f403686dbac67cf72ea3b5996212bb571b08cd1bb7f571d0c2e5d97c3"
)
METRIC_SOURCE: Final = ROOT / "src/cypshift/openadmet_global_v2_metric.py"
METRIC_SOURCE_SHA256: Final = (
    "e63f12af8e911da5f2f9ffde802f14039b7d8fb38293be85fec754793fc43269"
)
LOCK: Final = SCRIPT.with_name("uv.lock")
LOCK_SHA256: Final = "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
ACCEPTED_MAPLIGHT_RUNNER_SHA256: Final = (
    "154f8d231c490da7d2af419bfb533ec18a17c2d4ec3938c0373995a3a9acb93f"
)

SOURCE_SCHEMA: Final = "cypshift.openadmet_cyp_2026.global_v2_g1_synthetic_source.v1"
MODEL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_model_capability.v1"
)
SELECTOR_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_selector_capability.v1"
)
SCORER_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_scorer_capability.v1"
)
INNER_RAW_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_inner_raw_predictions.v1"
)
INNER_FROZEN_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_inner_frozen_predictions.v1"
)
SELECTION_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_selections.v1"
)
OUTER_RAW_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_outer_raw_predictions.v1"
)
OUTER_FROZEN_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_outer_frozen_predictions.v1"
)
SCORED_SCHEMA: Final = "cypshift.openadmet_cyp_2026.global_v2_g1_scored.v1"
FUTURE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_future_configurations.v1"
)
PROBE_SCHEMA: Final = "cypshift.openadmet_cyp_2026.global_v2_g1_runtime_probes.v1"
TERMINAL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_synthetic_terminal.v1"
)

ENDPOINTS: Final = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
REPEATS: Final = tuple(range(3))
OUTER_FOLDS: Final = tuple(range(5))
INNER_FOLDS: Final = tuple(range(4))
CONFIGURATION_IDS: Final = tuple(f"G1-C{index:02d}" for index in range(12))
MODEL_SEEDS: Final = (20260824, 20260825, 20260826)
FEATURE_WIDTHS: Final = (
    ("maplight_morgan_count.npy", 1024),
    ("maplight_avalon_count.npy", 1024),
    ("maplight_erg.npy", 315),
    ("maplight_rdkit_descriptors.npy", 200),
)
FEATURE_WIDTH: Final = 2563

FEATURE_COLUMNS: Final = ("molecule_id", "similarity_component_hash")
FOLD_COLUMNS: Final = (
    "molecule_id",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "outer_validation_fold",
    "inner_fold",
)
TRUTH_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "availability",
    "point",
    "low",
    "high",
)
TARGET_COLUMNS: Final = ("molecule_id", "point")
INNER_TRUTH_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "inner_fold",
    "availability",
    "point",
    "low",
    "high",
)
OUTER_TRUTH_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "availability",
    "point",
    "low",
    "high",
)
BASELINE_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "prediction",
)
INNER_RAW_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "inner_fold",
    "configuration_id",
    "model_seed",
    "prediction",
    "contract_sha256",
    "canonical_source_sha256",
    "feature_rows_sha256",
    "folds_sha256",
    "target_receipt_sha256",
    "model_id",
    "split_id",
)
INNER_FROZEN_COLUMNS: Final = tuple(
    name for name in INNER_RAW_COLUMNS if name != "model_seed"
)
SELECTION_METRIC_COLUMNS: Final = (
    "endpoint",
    "repeat",
    "outer_fold",
    "configuration_id",
    "tutorial_st_rae",
    "component_macro_mae",
    "eligible_rows",
    "components",
)
SELECTION_COLUMNS: Final = (
    "endpoint",
    "repeat",
    "outer_fold",
    "configuration_id",
    "tutorial_st_rae",
    "component_macro_mae",
    "selection_token_sha256",
)
PROJECTION_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "configuration_id",
    "prediction",
)
OUTER_RAW_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "configuration_id",
    "model_seed",
    "prediction",
    "selection_token_sha256",
    "contract_sha256",
    "canonical_source_sha256",
    "feature_rows_sha256",
    "folds_sha256",
    "target_receipt_sha256",
    "model_id",
    "split_id",
)
OUTER_FROZEN_COLUMNS: Final = tuple(
    name for name in OUTER_RAW_COLUMNS if name != "model_seed"
)
OUTER_CELL_METRIC_COLUMNS: Final = (
    "repeat",
    "outer_fold",
    "candidate_component_macro_mae",
    "baseline_component_macro_mae",
    "difference",
    "favorable",
)
ENDPOINT_METRIC_COLUMNS: Final = (
    "endpoint",
    "candidate_tutorial_st_rae",
    "baseline_tutorial_st_rae",
    "candidate_component_macro_mae",
    "baseline_component_macro_mae",
    "component_mae_difference",
)
FUTURE_METRIC_COLUMNS: Final = (
    "endpoint",
    "configuration_id",
    "tutorial_st_rae",
    "component_macro_mae",
)
FUTURE_TOKEN_COLUMNS: Final = (
    "endpoint",
    "configuration_id",
    "tutorial_st_rae",
    "component_macro_mae",
    "future_configuration_token_sha256",
)
SELECTION_SUMMARY_COLUMNS: Final = (
    "scope",
    "endpoint",
    "repeat",
    "outer_fold",
    "configuration_id",
    "tutorial_st_rae",
    "component_macro_mae",
    "token_sha256",
)

OFFICIAL_ZERO_FIELDS: Final = (
    "official_target_values_opened",
    "official_features_opened",
    "official_model_fits",
    "official_predictions_generated",
    "development_metric_evaluations",
    "official_metric_evaluations",
    "confirmatory_truth_values_opened",
    "historical_r3c_row_level_artifacts_opened",
    "blinded_test_files_opened",
    "tdi_files_opened",
    "external_records_acquired",
    "submissions_created",
    "leaderboard_observations",
    "live_uploads",
)
DENIED_AUTHORITY: Final = {
    "official_target_access": False,
    "official_feature_access": False,
    "official_model_fitting": False,
    "official_prediction_generation": False,
    "development_metric_evaluation": False,
    "official_metric_evaluation": False,
    "confirmatory_truth_access": False,
    "historical_r3c_row_level_access": False,
    "blinded_test_access": False,
    "tdi_access": False,
    "external_record_acquisition": False,
    "submission_generation": False,
    "leaderboard_observation": False,
    "live_upload": False,
}


class G1SyntheticError(RuntimeError):
    """A G2-3B receipt, family, capability, or determinism invariant failed."""


ProbeRunner = Callable[[Path, Path], Path]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise G1SyntheticError(message)


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _sha_text(*values: object) -> str:
    return base.sha256_bytes("|".join(map(str, values)).encode("utf-8"))


def _float(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise G1SyntheticError(f"{label} is not numeric") from exc
    _require(
        math.isfinite(result) and value == format(result, ".17g"),
        f"{label} is nonfinite or noncanonical",
    )
    return result


def _json(path: Path) -> dict[str, Any]:
    value, _raw = base._load_json(path)
    return value


def _rows(path: Path, columns: Sequence[str]) -> list[dict[str, str]]:
    return base._read_csv(path, columns)


def _static_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(base.sha256_path(CONTRACT) == CONTRACT_SHA256, "G2-3B contract differs")
    _require(base.sha256_path(PARENT) == PARENT_SHA256, "G2-3A parent differs")
    _require(base.sha256_path(LOCK) == LOCK_SHA256, "research lock differs")
    _require(
        base.sha256_path(METRIC_SOURCE) == METRIC_SOURCE_SHA256,
        "tutorial metric source differs",
    )
    _require(
        base.sha256_path(base.SCRIPT) == ACCEPTED_MAPLIGHT_RUNNER_SHA256,
        "accepted MapLight runner differs",
    )
    contract = _json(CONTRACT)
    parent = _json(PARENT)
    _require(contract["parent"]["sha256"] == PARENT_SHA256, "parent binding differs")
    screen = parent["screen"]
    _require(
        tuple(item["configuration_id"] for item in screen["configurations"])
        == CONFIGURATION_IDS
        and tuple(screen["model_seeds"]) == MODEL_SEEDS,
        "screen identity differs",
    )
    return contract, parent


def _source_files(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    base._readonly_root(root, "G2-3B synthetic source")
    manifest = _json(root / "manifest.json")
    expected = {
        "feature_rows.csv",
        "folds.csv",
        "truth.csv",
        *(name for name, _width in FEATURE_WIDTHS),
    }
    receipts = manifest.get("source_receipts")
    _require(
        manifest.get("schema_version") == SOURCE_SCHEMA
        and manifest.get("synthetic") is True
        and manifest.get("semantic_source_id") == "g2-3b-exp-g1-synthetic-v1"
        and manifest.get("feature_order")
        == [f"{name}:{width}" for name, width in FEATURE_WIDTHS]
        and isinstance(receipts, Mapping),
        "synthetic source identity differs",
    )
    assert isinstance(receipts, Mapping)
    _require(set(receipts) == expected, "synthetic source receipt set differs")
    observed = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    _require(observed == {*expected, "manifest.json"}, "synthetic source files differ")
    loaded: dict[str, bytes] = {}
    for name in sorted(expected):
        data = base._regular(root / name, f"source {name}").read_bytes()
        _require(base.sha256_bytes(data) == receipts[name], f"source receipt differs: {name}")
        loaded[name] = data
    return manifest, loaded


def _parse_csv_bytes(
    value: bytes, columns: Sequence[str], label: str
) -> list[dict[str, str]]:
    try:
        reader = csv.DictReader(io.StringIO(value.decode("utf-8"), newline=""))
    except UnicodeError as exc:
        raise G1SyntheticError(f"{label} is not UTF-8") from exc
    _require(reader.fieldnames == list(columns), f"{label} columns differ")
    rows = list(reader)
    _require(all(None not in row for row in rows), f"{label} row width differs")
    return rows


def _load_npy(value: bytes, label: str) -> np.ndarray[Any, Any]:
    try:
        array = np.load(io.BytesIO(value), allow_pickle=False)
    except (ValueError, OSError) as exc:
        raise G1SyntheticError(f"{label} is not a safe NumPy array") from exc
    return cast(np.ndarray[Any, Any], array)


def _validate_label_free(
    feature_rows: Sequence[Mapping[str, str]],
    fold_rows: Sequence[Mapping[str, str]],
) -> tuple[list[str], dict[str, str], dict[tuple[str, int, int], Mapping[str, str]]]:
    _require(len(feature_rows) == 80, "feature row count differs")
    molecules = [row["molecule_id"] for row in feature_rows]
    _require(len(set(molecules)) == 80 and all(molecules), "molecule identities differ")
    components = {
        row["molecule_id"]: row["similarity_component_hash"] for row in feature_rows
    }
    _require(
        len(set(components.values())) == 40
        and all(_is_sha(value) for value in components.values()),
        "component identities differ",
    )
    counts: dict[str, int] = defaultdict(int)
    for value in components.values():
        counts[value] += 1
    _require(set(counts.values()) == {2}, "components are not two-molecule families")
    _require(len(fold_rows) == 80 * 3 * 5, "fold row count differs")
    indexed: dict[tuple[str, int, int], Mapping[str, str]] = {}
    for row in fold_rows:
        molecule = row["molecule_id"]
        _require(components.get(molecule) == row["similarity_component_hash"], "fold component differs")
        try:
            repeat = int(row["repeat"])
            assigned_outer = int(row["outer_fold"])
            context = int(row["outer_validation_fold"])
        except ValueError as exc:
            raise G1SyntheticError("fold integer differs") from exc
        _require(
            repeat in REPEATS and assigned_outer in OUTER_FOLDS and context in OUTER_FOLDS,
            "fold context differs",
        )
        key = molecule, repeat, context
        _require(key not in indexed, "duplicate fold scope")
        indexed[key] = row
        if assigned_outer == context:
            _require(row["inner_fold"] == "", "outer validation has inner assignment")
        else:
            try:
                inner = int(row["inner_fold"])
            except ValueError as exc:
                raise G1SyntheticError("inner fold differs") from exc
            _require(inner in INNER_FOLDS, "inner fold differs")
    for repeat in REPEATS:
        outer_by_component: dict[str, set[int]] = defaultdict(set)
        for molecule in molecules:
            row = indexed[molecule, repeat, 0]
            outer_by_component[components[molecule]].add(int(row["outer_fold"]))
        _require(
            all(len(values) == 1 for values in outer_by_component.values()),
            "component crosses an outer boundary",
        )
        for outer in OUTER_FOLDS:
            inner_by_component: dict[str, set[int]] = defaultdict(set)
            for molecule in molecules:
                row = indexed[molecule, repeat, outer]
                if int(row["outer_fold"]) != outer:
                    inner_by_component[components[molecule]].add(int(row["inner_fold"]))
            _require(
                len(inner_by_component) == 32
                and all(len(values) == 1 for values in inner_by_component.values()),
                "component crosses a scoped inner boundary",
            )
            _require(
                set().union(*inner_by_component.values()) == set(INNER_FOLDS),
                "inner fold support differs",
            )
    return molecules, components, indexed


def _validate_truth(
    truth_rows: Sequence[Mapping[str, str]], components: Mapping[str, str]
) -> dict[tuple[str, str], Mapping[str, str]]:
    _require(len(truth_rows) == 80 * 4, "truth row count differs")
    result: dict[tuple[str, str], Mapping[str, str]] = {}
    for row in truth_rows:
        molecule = row["molecule_id"]
        endpoint = row["endpoint"]
        _require(
            components.get(molecule) == row["similarity_component_hash"]
            and endpoint in ENDPOINTS,
            "truth identity differs",
        )
        key = molecule, endpoint
        _require(key not in result, "truth key is duplicated")
        availability = row["availability"]
        if availability == "complete":
            point = _float(row["point"], "truth point")
            low = _float(row["low"], "truth low")
            high = _float(row["high"], "truth high")
            _require(low <= point <= high, "truth bounds differ")
        elif availability == "missing":
            _require(
                row["point"] == row["low"] == row["high"] == "",
                "missing truth contains a value",
            )
        else:
            raise G1SyntheticError("truth availability differs")
        result[key] = row
    _require(
        any(row["availability"] == "missing" for row in truth_rows),
        "missing truth case is absent",
    )
    return result


def _canonical_source_receipt(
    feature_csv: bytes,
    folds_csv: bytes,
    truth_csv: bytes,
    arrays: Mapping[str, bytes],
) -> str:
    leaves = {
        "feature_rows.csv": base.sha256_bytes(feature_csv),
        "folds.csv": base.sha256_bytes(folds_csv),
        "truth.csv": base.sha256_bytes(truth_csv),
        **{name: base.sha256_bytes(value) for name, value in arrays.items()},
    }
    return base.sha256_bytes(
        "".join(f"{name}|{value}\n" for name, value in sorted(leaves.items())).encode(
            "utf-8"
        )
    )


def _stage_authority(stage: str) -> dict[str, bool]:
    value = dict(DENIED_AUTHORITY)
    value.update(
        {
            "synthetic_source_generation": stage == "source",
            "synthetic_model_double_execution": stage == "model",
            "synthetic_catboost_fitting": stage == "model",
            "synthetic_inner_selection": stage == "selector",
            "synthetic_outer_scoring": stage == "scorer",
        }
    )
    return value


def _target_path(
    root: Path,
    *,
    stage: str,
    endpoint: str,
    repeat: int,
    outer: int,
    inner: int | None,
) -> Path:
    base_path = root / "targets" / stage / endpoint / f"repeat-{repeat}" / f"outer-{outer}"
    return base_path / ("targets.csv" if inner is None else f"inner-{inner}.csv")


def _cell_ids(
    molecules: Sequence[str],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    *,
    repeat: int,
    outer: int,
    inner: int | None,
) -> tuple[list[str], list[str]]:
    if inner is None:
        training = sorted(
            molecule
            for molecule in molecules
            if int(folds[molecule, repeat, outer]["outer_fold"]) != outer
        )
        prediction = sorted(
            molecule
            for molecule in molecules
            if int(folds[molecule, repeat, outer]["outer_fold"]) == outer
        )
    else:
        training = sorted(
            molecule
            for molecule in molecules
            if int(folds[molecule, repeat, outer]["outer_fold"]) != outer
            and int(folds[molecule, repeat, outer]["inner_fold"]) != inner
        )
        prediction = sorted(
            molecule
            for molecule in molecules
            if int(folds[molecule, repeat, outer]["outer_fold"]) != outer
            and int(folds[molecule, repeat, outer]["inner_fold"]) == inner
        )
    _require(bool(training) and bool(prediction), "cell support is empty")
    return training, prediction


def compile_capabilities(
    *, source_root: Path, output_root: Path, expected_runner_sha256: str
) -> tuple[Path, Path, Path]:
    """Authenticate one fixture and publish disjoint immutable stage capabilities."""

    _static_contract()
    _require(base.sha256_path(SCRIPT) == expected_runner_sha256, "G2-3B runner source differs")
    _require(not output_root.exists(), "capability output exists")
    source_manifest, loaded = _source_files(source_root)

    # The label-free boundary is parsed and proven before truth bytes are parsed.
    raw_features = _parse_csv_bytes(loaded["feature_rows.csv"], FEATURE_COLUMNS, "feature rows")
    raw_folds = _parse_csv_bytes(loaded["folds.csv"], FOLD_COLUMNS, "fold rows")
    molecules_physical, components, folds_index = _validate_label_free(raw_features, raw_folds)
    physical_index = {molecule: index for index, molecule in enumerate(molecules_physical)}
    molecules = sorted(molecules_physical)
    features = [
        {"molecule_id": molecule, "similarity_component_hash": components[molecule]}
        for molecule in molecules
    ]
    folds = sorted(
        (dict(row) for row in raw_folds),
        key=lambda row: (
            row["molecule_id"],
            int(row["repeat"]),
            int(row["outer_validation_fold"]),
        ),
    )
    canonical_arrays: dict[str, np.ndarray[Any, Any]] = {}
    array_bytes: dict[str, bytes] = {}
    order = [physical_index[molecule] for molecule in molecules]
    for name, width in FEATURE_WIDTHS:
        array = _load_npy(loaded[name], name)
        _require(
            array.shape == (80, width)
            and array.dtype == np.dtype("<f4")
            and np.isfinite(array).all(),
            f"{name} shape, dtype, or finite policy differs",
        )
        canonical = np.ascontiguousarray(array[order], dtype="<f4")
        canonical_arrays[name] = canonical
        stream = io.BytesIO()
        np.lib.format.write_array(stream, canonical, version=(1, 0), allow_pickle=False)
        array_bytes[name] = stream.getvalue()
    _require(
        np.all((canonical_arrays["maplight_morgan_count.npy"][:, 0] >= 4.0)
        & (canonical_arrays["maplight_morgan_count.npy"][:, 0] < 6.0))
        and np.all(canonical_arrays["maplight_avalon_count.npy"][:, 0] >= 0.0)
        and np.all(canonical_arrays["maplight_avalon_count.npy"][:, 0] <= 6.0)
        and np.all(canonical_arrays["maplight_erg.npy"][:, 0] >= -0.5)
        and np.all(canonical_arrays["maplight_erg.npy"][:, 0] <= 0.5)
        and np.all(canonical_arrays["maplight_rdkit_descriptors.npy"][:, 0] >= 0.0)
        and np.all(canonical_arrays["maplight_rdkit_descriptors.npy"][:, 0] <= 1.25),
        "synthetic feature-order sentinels differ",
    )

    raw_truth = _parse_csv_bytes(loaded["truth.csv"], TRUTH_COLUMNS, "truth rows")
    truth = _validate_truth(raw_truth, components)
    canonical_truth = sorted(
        (dict(row) for row in raw_truth),
        key=lambda row: (row["molecule_id"], ENDPOINTS.index(row["endpoint"])),
    )
    feature_csv = base.csv_bytes(FEATURE_COLUMNS, features)
    folds_csv = base.csv_bytes(FOLD_COLUMNS, folds)
    truth_csv = base.csv_bytes(TRUTH_COLUMNS, canonical_truth)
    source_sha = _canonical_source_receipt(feature_csv, folds_csv, truth_csv, array_bytes)
    root_instance_sha = base.sha256_path(source_root / "manifest.json")

    target_files: dict[str, bytes] = {}
    inner_truth: list[dict[str, object]] = []
    outer_truth: list[dict[str, object]] = []
    baseline_rows: list[dict[str, object]] = []
    for endpoint in ENDPOINTS:
        for repeat in REPEATS:
            for outer in OUTER_FOLDS:
                outer_train, outer_prediction = _cell_ids(
                    molecules, folds_index, repeat=repeat, outer=outer, inner=None
                )
                outer_targets = [
                    {
                        "molecule_id": molecule,
                        "point": truth[molecule, endpoint]["point"],
                    }
                    for molecule in outer_train
                    if truth[molecule, endpoint]["availability"] == "complete"
                ]
                path = _target_path(
                    Path("."),
                    stage="outer",
                    endpoint=endpoint,
                    repeat=repeat,
                    outer=outer,
                    inner=None,
                ).as_posix().removeprefix("./")
                target_files[path] = base.csv_bytes(TARGET_COLUMNS, outer_targets)
                for molecule in outer_prediction:
                    row = truth[molecule, endpoint]
                    outer_truth.append(
                        {
                            "molecule_id": molecule,
                            "endpoint": endpoint,
                            "similarity_component_hash": components[molecule],
                            "repeat": repeat,
                            "outer_fold": outer,
                            "availability": row["availability"],
                            "point": row["point"],
                            "low": row["low"],
                            "high": row["high"],
                        }
                    )
                    latent = float(canonical_arrays["maplight_morgan_count.npy"][molecules.index(molecule), 0])
                    baseline_rows.append(
                        {
                            "molecule_id": molecule,
                            "endpoint": endpoint,
                            "similarity_component_hash": components[molecule],
                            "repeat": repeat,
                            "outer_fold": outer,
                            "prediction": format(latent + ENDPOINTS.index(endpoint) * 0.5 + 0.375, ".17g"),
                        }
                    )
                for inner in INNER_FOLDS:
                    inner_train, inner_prediction = _cell_ids(
                        molecules,
                        folds_index,
                        repeat=repeat,
                        outer=outer,
                        inner=inner,
                    )
                    inner_targets = [
                        {
                            "molecule_id": molecule,
                            "point": truth[molecule, endpoint]["point"],
                        }
                        for molecule in inner_train
                        if truth[molecule, endpoint]["availability"] == "complete"
                    ]
                    path = _target_path(
                        Path("."),
                        stage="inner",
                        endpoint=endpoint,
                        repeat=repeat,
                        outer=outer,
                        inner=inner,
                    ).as_posix().removeprefix("./")
                    target_files[path] = base.csv_bytes(TARGET_COLUMNS, inner_targets)
                    for molecule in inner_prediction:
                        row = truth[molecule, endpoint]
                        inner_truth.append(
                            {
                                "molecule_id": molecule,
                                "endpoint": endpoint,
                                "similarity_component_hash": components[molecule],
                                "repeat": repeat,
                                "outer_fold": outer,
                                "inner_fold": inner,
                                "availability": row["availability"],
                                "point": row["point"],
                                "low": row["low"],
                                "high": row["high"],
                            }
                        )
    _require(len(target_files) == 300, "target capability count differs")
    _require(len(inner_truth) == 80 * 4 * 3 * 4, "inner truth topology differs")
    _require(len(outer_truth) == 80 * 4 * 3, "outer truth topology differs")

    feature_receipt = base.sha256_bytes(feature_csv)
    fold_receipt = base.sha256_bytes(folds_csv)
    target_tree = base.sha256_bytes(
        "".join(
            f"{name}|{base.sha256_bytes(value)}\n"
            for name, value in sorted(target_files.items())
        ).encode("utf-8")
    )
    model_files: dict[str, bytes] = {
        "feature_rows.csv": feature_csv,
        "folds.csv": folds_csv,
        **array_bytes,
        **target_files,
    }
    model_manifest = {
        "schema_version": MODEL_SCHEMA,
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "parent_sha256": PARENT_SHA256,
        "runner_source_sha256": expected_runner_sha256,
        "canonical_source_sha256": source_sha,
        "root_instance_sha256": root_instance_sha,
        "semantic_source_id": source_manifest["semantic_source_id"],
        "feature_rows_sha256": feature_receipt,
        "folds_sha256": fold_receipt,
        "arrays": {
            name: {"sha256": base.sha256_bytes(value), "width": width, "dtype": "float32"}
            for (name, width), value in zip(FEATURE_WIDTHS, array_bytes.values(), strict=True)
        },
        "target_tree_sha256": target_tree,
        "counts": {"molecules": 80, "components": 40, "target_files": 300},
        "truth_files": 0,
        "authority": _stage_authority("model"),
    }
    model = base.publish_files(
        output_root / "model-capability",
        {**model_files, "manifest.json": base.json_bytes(model_manifest)},
    )
    model_manifest_sha = base.sha256_path(model / "manifest.json")

    inner_truth_csv = base.csv_bytes(INNER_TRUTH_COLUMNS, inner_truth)
    selector_manifest = {
        "schema_version": SELECTOR_SCHEMA,
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "canonical_source_sha256": source_sha,
        "root_instance_sha256": root_instance_sha,
        "model_capability_manifest_sha256": model_manifest_sha,
        "inner_truth_sha256": base.sha256_bytes(inner_truth_csv),
        "counts": {"inner_truth_rows": len(inner_truth)},
        "feature_arrays": 0,
        "training_target_files": 0,
        "outer_truth_files": 0,
        "authority": _stage_authority("selector"),
    }
    selector = base.publish_files(
        output_root / "selector-capability",
        {
            "inner_validation_truth.csv": inner_truth_csv,
            "manifest.json": base.json_bytes(selector_manifest),
        },
    )

    outer_truth_csv = base.csv_bytes(OUTER_TRUTH_COLUMNS, outer_truth)
    baseline_csv = base.csv_bytes(BASELINE_COLUMNS, baseline_rows)
    scorer_manifest = {
        "schema_version": SCORER_SCHEMA,
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "canonical_source_sha256": source_sha,
        "root_instance_sha256": root_instance_sha,
        "model_capability_manifest_sha256": model_manifest_sha,
        "outer_truth_sha256": base.sha256_bytes(outer_truth_csv),
        "baseline_predictions_sha256": base.sha256_bytes(baseline_csv),
        "counts": {"outer_truth_rows": len(outer_truth), "baseline_prediction_rows": len(baseline_rows)},
        "feature_arrays": 0,
        "training_target_files": 0,
        "inner_truth_files": 0,
        "authority": _stage_authority("scorer"),
    }
    scorer = base.publish_files(
        output_root / "scorer-capability",
        {
            "outer_truth.csv": outer_truth_csv,
            "baseline_predictions.csv": baseline_csv,
            "manifest.json": base.json_bytes(scorer_manifest),
        },
    )
    return model, selector, scorer


def _load_model_capability(
    root: Path,
) -> tuple[
    dict[str, Any],
    list[str],
    dict[str, str],
    dict[tuple[str, int, int], Mapping[str, str]],
    dict[str, np.ndarray[Any, Any]],
]:
    base._readonly_root(root, "G2-3B model capability")
    manifest = _json(root / "manifest.json")
    _require(
        manifest.get("schema_version") == MODEL_SCHEMA
        and manifest.get("synthetic") is True
        and manifest.get("contract_sha256") == CONTRACT_SHA256
        and manifest.get("parent_sha256") == PARENT_SHA256
        and manifest.get("runner_source_sha256") == base.sha256_path(SCRIPT)
        and manifest.get("truth_files") == 0
        and manifest.get("authority") == _stage_authority("model"),
        "model capability identity differs",
    )
    features = _rows(root / "feature_rows.csv", FEATURE_COLUMNS)
    folds = _rows(root / "folds.csv", FOLD_COLUMNS)
    _require(
        base.sha256_path(root / "feature_rows.csv")
        == manifest.get("feature_rows_sha256")
        and base.sha256_path(root / "folds.csv") == manifest.get("folds_sha256"),
        "model feature or fold receipt differs",
    )
    molecules, components, indexed = _validate_label_free(features, folds)
    _require(molecules == sorted(molecules), "model capability is not canonical")
    arrays: dict[str, np.ndarray[Any, Any]] = {}
    receipts = manifest.get("arrays")
    _require(isinstance(receipts, Mapping), "model array receipts differ")
    assert isinstance(receipts, Mapping)
    for name, width in FEATURE_WIDTHS:
        _require(
            base.sha256_path(root / name) == receipts[name]["sha256"],
            f"model array receipt differs: {name}",
        )
        array = np.load(root / name, allow_pickle=False)
        _require(
            array.shape == (80, width)
            and array.dtype == np.dtype("<f4")
            and array.flags.c_contiguous
            and np.isfinite(array).all(),
            f"model array layout differs: {name}",
        )
        arrays[name] = cast(np.ndarray[Any, Any], array)
    targets = sorted((root / "targets").rglob("*.csv"))
    _require(len(targets) == 300, "model target capability count differs")
    expected_files = {
        "manifest.json",
        "feature_rows.csv",
        "folds.csv",
        *(name for name, _width in FEATURE_WIDTHS),
        *(path.relative_to(root).as_posix() for path in targets),
    }
    observed_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    _require(observed_files == expected_files, "model capability file set differs")
    tree = base.sha256_bytes(
        "".join(
            f"{path.relative_to(root).as_posix()}|{base.sha256_path(path)}\n"
            for path in targets
        ).encode("utf-8")
    )
    _require(tree == manifest.get("target_tree_sha256"), "model target tree differs")
    return manifest, molecules, components, indexed, arrays


def _matrix(
    arrays: Mapping[str, np.ndarray[Any, Any]], indices: Sequence[int]
) -> np.ndarray[Any, Any]:
    return cast(
        np.ndarray[Any, Any],
        np.ascontiguousarray(
            np.concatenate([arrays[name][list(indices)] for name, _ in FEATURE_WIDTHS], axis=1),
            dtype=np.float32,
        ),
    )


def _model_double_bias(
    *, endpoint: str, repeat: int, outer: int, configuration_id: str
) -> float:
    configuration = CONFIGURATION_IDS.index(configuration_id)
    endpoint_index = ENDPOINTS.index(endpoint)
    if endpoint == "CYP1A2" and repeat == 0 and outer == 0:
        if configuration == 0:
            return 0.125
        if configuration == 1:
            return -0.125
    desired = (endpoint_index + repeat + outer) % 3
    if configuration == desired:
        return 0.0
    return 0.125 + 0.0625 * abs(configuration - desired)


def expected_outer_configuration(endpoint: str, repeat: int, outer: int) -> str:
    """Return the predeclared mechanics oracle for one outer endpoint cell."""

    _require(endpoint in ENDPOINTS and repeat in REPEATS and outer in OUTER_FOLDS, "oracle cell differs")
    if endpoint == "CYP1A2" and repeat == 0 and outer == 0:
        return "G1-C00"
    return f"G1-C{(ENDPOINTS.index(endpoint) + repeat + outer) % 3:02d}"


def _model_double_predictions(
    *,
    prediction_features: np.ndarray[Any, Any],
    endpoint: str,
    repeat: int,
    outer: int,
    configuration_id: str,
    model_seed: int,
) -> np.ndarray[Any, Any]:
    _require(
        prediction_features.ndim == 2
        and prediction_features.shape[1] == FEATURE_WIDTH
        and np.isfinite(prediction_features).all(),
        "model-double prediction features differ",
    )
    _require(configuration_id in CONFIGURATION_IDS, "model-double configuration differs")
    _require(model_seed in MODEL_SEEDS, "model-double seed differs")
    seed_offset = (MODEL_SEEDS.index(model_seed) - 1) * 0.015625
    values = (
        prediction_features[:, 0].astype(np.float64)
        + ENDPOINTS.index(endpoint) * 0.5
        + _model_double_bias(
            endpoint=endpoint,
            repeat=repeat,
            outer=outer,
            configuration_id=configuration_id,
        )
        + seed_offset
    )
    _require(np.isfinite(values).all(), "model-double prediction is nonfinite")
    return cast(np.ndarray[Any, Any], values)


def _iteration(values: Sequence[Any], reverse: bool) -> Sequence[Any]:
    return tuple(reversed(values)) if reverse else values


def run_inner_models(
    *, model_capability_root: Path, output_root: Path, reverse_execution_order: bool = False
) -> Path:
    """Run all 8,640 synthetic inner model-stage identities without selector truth."""

    manifest, molecules, components, folds, arrays = _load_model_capability(model_capability_root)
    index = {molecule: position for position, molecule in enumerate(molecules)}
    rows: list[dict[str, object]] = []
    invocations = 0
    training_values_opened = 0
    for endpoint in _iteration(ENDPOINTS, reverse_execution_order):
        for repeat in _iteration(REPEATS, reverse_execution_order):
            for outer in _iteration(OUTER_FOLDS, reverse_execution_order):
                for inner in _iteration(INNER_FOLDS, reverse_execution_order):
                    training_ids, prediction_ids = _cell_ids(
                        molecules,
                        folds,
                        repeat=repeat,
                        outer=outer,
                        inner=inner,
                    )
                    target_path = _target_path(
                        model_capability_root,
                        stage="inner",
                        endpoint=endpoint,
                        repeat=repeat,
                        outer=outer,
                        inner=inner,
                    )
                    targets = _rows(target_path, TARGET_COLUMNS)
                    target_ids = [row["molecule_id"] for row in targets]
                    _require(target_ids == sorted(target_ids), "inner target identity order differs")
                    _require(set(target_ids).issubset(training_ids), "inner target crosses training boundary")
                    _require(
                        all(math.isfinite(_float(row["point"], "inner training point")) for row in targets),
                        "inner target differs",
                    )
                    prediction_matrix = _matrix(arrays, [index[value] for value in prediction_ids])
                    for configuration_id in _iteration(CONFIGURATION_IDS, reverse_execution_order):
                        for model_seed in _iteration(MODEL_SEEDS, reverse_execution_order):
                            invocations += 1
                            training_values_opened += len(targets)
                            predicted = _model_double_predictions(
                                prediction_features=prediction_matrix,
                                endpoint=endpoint,
                                repeat=repeat,
                                outer=outer,
                                configuration_id=configuration_id,
                                model_seed=model_seed,
                            )
                            model_id = _sha_text(
                                CONTRACT_SHA256,
                                manifest["canonical_source_sha256"],
                                "inner",
                                endpoint,
                                repeat,
                                outer,
                                inner,
                                configuration_id,
                                model_seed,
                                base.sha256_path(target_path),
                            )
                            target_receipt = base.sha256_path(target_path)
                            split_id = _sha_text(manifest["folds_sha256"], repeat, outer, inner)
                            for molecule, prediction in zip(prediction_ids, predicted, strict=True):
                                rows.append(
                                    {
                                        "molecule_id": molecule,
                                        "endpoint": endpoint,
                                        "similarity_component_hash": components[molecule],
                                        "repeat": repeat,
                                        "outer_fold": outer,
                                        "inner_fold": inner,
                                        "configuration_id": configuration_id,
                                        "model_seed": model_seed,
                                        "prediction": format(float(prediction), ".17g"),
                                        "contract_sha256": CONTRACT_SHA256,
                                        "canonical_source_sha256": manifest["canonical_source_sha256"],
                                        "feature_rows_sha256": manifest["feature_rows_sha256"],
                                        "folds_sha256": manifest["folds_sha256"],
                                        "target_receipt_sha256": target_receipt,
                                        "model_id": model_id,
                                        "split_id": split_id,
                                    }
                                )
    rows.sort(key=lambda row: tuple(row[name] for name in INNER_RAW_COLUMNS[:8]))
    expected_rows = 80 * 4 * 3 * 4 * 12 * 3
    _require(invocations == 8640, "inner model-stage invocation count differs")
    _require(
        len(rows) == expected_rows == 138240,
        f"inner raw prediction count differs: {len(rows)}",
    )
    raw = base.csv_bytes(INNER_RAW_COLUMNS, rows)
    result = {
        "schema_version": INNER_RAW_SCHEMA,
        "status": "G2_3B_INNER_MODEL_DOUBLE_COMPLETE",
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "model_capability_manifest_sha256": base.sha256_path(model_capability_root / "manifest.json"),
        "canonical_source_sha256": manifest["canonical_source_sha256"],
        "root_instance_sha256": manifest["root_instance_sha256"],
        "feature_rows_sha256": manifest["feature_rows_sha256"],
        "folds_sha256": manifest["folds_sha256"],
        "counts": {
            "model_double_invocations": invocations,
            "raw_prediction_rows": len(rows),
            "training_target_values_opened": training_values_opened,
            "selector_truth_values_opened": 0,
            "outer_truth_values_opened": 0,
        },
        "output_receipts": {"inner_raw_predictions.csv": base.sha256_bytes(raw)},
        "authority": _stage_authority("model"),
    }
    return base.publish_files(
        output_root,
        {"inner_raw_predictions.csv": raw, "manifest.json": base.json_bytes(result)},
    )


def _load_prediction_root(
    root: Path, *, schema: str, filename: str, columns: Sequence[str]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    base._readonly_root(root, filename)
    manifest = _json(root / "manifest.json")
    _require(
        manifest.get("schema_version") == schema
        and manifest.get("synthetic") is True
        and manifest.get("contract_sha256") == CONTRACT_SHA256,
        f"{filename} manifest differs",
    )
    rows = _rows(root / filename, columns)
    _require(
        base.sha256_path(root / filename) == manifest["output_receipts"][filename],
        f"{filename} receipt differs",
    )
    return manifest, rows


def _validated_seed_mean(
    rows: Sequence[Mapping[str, str]], *, stage: str
) -> tuple[float, list[Mapping[str, str]]]:
    _require(stage in {"inner", "outer"}, "seed reduction stage differs")
    _require(len(rows) == 3, f"{stage} seed set cardinality differs")
    ordered = sorted(rows, key=lambda row: int(row["model_seed"]))
    _require(
        [int(row["model_seed"]) for row in ordered] == list(MODEL_SEEDS),
        f"{stage} seed set differs",
    )
    _require(
        len({row["model_id"] for row in ordered}) == 3,
        f"{stage} model identity set differs",
    )
    for row in ordered:
        _require(row["configuration_id"] in CONFIGURATION_IDS, f"{stage} configuration differs")
        _require(_is_sha(row["target_receipt_sha256"]), f"{stage} target receipt differs")
        if stage == "inner":
            expected_model = _sha_text(
                CONTRACT_SHA256,
                row["canonical_source_sha256"],
                "inner",
                row["endpoint"],
                row["repeat"],
                row["outer_fold"],
                row["inner_fold"],
                row["configuration_id"],
                row["model_seed"],
                row["target_receipt_sha256"],
            )
            expected_split = _sha_text(
                row["folds_sha256"], row["repeat"], row["outer_fold"], row["inner_fold"]
            )
        else:
            expected_model = _sha_text(
                CONTRACT_SHA256,
                row["canonical_source_sha256"],
                "outer",
                row["endpoint"],
                row["repeat"],
                row["outer_fold"],
                row["configuration_id"],
                row["model_seed"],
                row["selection_token_sha256"],
                row["target_receipt_sha256"],
            )
            expected_split = _sha_text(
                row["folds_sha256"], row["repeat"], row["outer_fold"], "outer"
            )
        _require(
            row["model_id"] == expected_model and row["split_id"] == expected_split,
            f"{stage} prediction identity is forged",
        )
    prediction = math.fsum(_float(row["prediction"], f"{stage} prediction") for row in ordered) / 3.0
    _require(math.isfinite(prediction), f"{stage} seed mean is nonfinite")
    return prediction, ordered


def freeze_inner_predictions(*, raw_root: Path, output_root: Path) -> Path:
    """Verify each exact three-seed inner set and freeze its canonical mean."""

    manifest, rows = _load_prediction_root(
        raw_root,
        schema=INNER_RAW_SCHEMA,
        filename="inner_raw_predictions.csv",
        columns=INNER_RAW_COLUMNS,
    )
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        _require(row["contract_sha256"] == CONTRACT_SHA256, "inner prediction contract differs")
        _require(row["canonical_source_sha256"] == manifest["canonical_source_sha256"], "inner prediction source differs")
        _float(row["prediction"], "inner prediction")
        key = tuple(row[name] for name in INNER_RAW_COLUMNS if name not in {"model_seed", "prediction", "model_id"})
        groups[key].append(row)
    frozen: list[dict[str, object]] = []
    for grouped in groups.values():
        prediction, ordered = _validated_seed_mean(grouped, stage="inner")
        first = ordered[0]
        output = {name: first[name] for name in INNER_FROZEN_COLUMNS}
        output["prediction"] = format(prediction, ".17g")
        output["model_id"] = _sha_text(*(row["model_id"] for row in ordered))
        frozen.append(output)
    frozen.sort(key=lambda row: tuple(row[name] for name in INNER_FROZEN_COLUMNS[:7]))
    _require(len(frozen) == 46080, "inner frozen prediction count differs")
    value = base.csv_bytes(INNER_FROZEN_COLUMNS, frozen)
    result = {
        "schema_version": INNER_FROZEN_SCHEMA,
        "status": "G2_3B_INNER_PREDICTIONS_FROZEN",
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "inner_raw_manifest_sha256": base.sha256_path(raw_root / "manifest.json"),
        "canonical_source_sha256": manifest["canonical_source_sha256"],
        "root_instance_sha256": manifest["root_instance_sha256"],
        "counts": {"seed_sets": len(frozen), "seeds_per_set": 3, "truth_values_opened": 0},
        "output_receipts": {"inner_frozen_predictions.csv": base.sha256_bytes(value)},
        "authority": _stage_authority("model"),
    }
    return base.publish_files(
        output_root,
        {"inner_frozen_predictions.csv": value, "manifest.json": base.json_bytes(result)},
    )


def _component_macro_mae(
    truth: Sequence[Mapping[str, str]], predictions: Mapping[str, float]
) -> tuple[float, int, int]:
    residuals: dict[str, list[float]] = defaultdict(list)
    eligible = 0
    for row in sorted(truth, key=lambda item: item["molecule_id"]):
        if row["availability"] != "complete":
            continue
        molecule = row["molecule_id"]
        _require(molecule in predictions, "component metric prediction is missing")
        residuals[row["similarity_component_hash"]].append(
            abs(predictions[molecule] - _float(row["point"], "component truth point"))
        )
        eligible += 1
    _require(bool(residuals), "component metric population is empty")
    component_values = [
        math.fsum(values) / len(values)
        for _component, values in sorted(residuals.items())
    ]
    result = math.fsum(component_values) / len(component_values)
    _require(math.isfinite(result), "component metric is nonfinite")
    return result, eligible, len(component_values)


def _tutorial_score(
    truth: Sequence[Mapping[str, str]], predictions: Mapping[str, float], endpoint: str
) -> tuple[float, int]:
    truth_rows = [
        TruthRow(
            molecule_id=row["molecule_id"],
            endpoint=endpoint,
            point=_float(row["point"], "tutorial truth point"),
            low=_float(row["low"], "tutorial truth low"),
            high=_float(row["high"], "tutorial truth high"),
        )
        for row in sorted(truth, key=lambda item: item["molecule_id"])
        if row["availability"] == "complete"
    ]
    prediction_rows = [
        PredictionRow(molecule_id=molecule, endpoint=endpoint, prediction=value)
        for molecule, value in sorted(predictions.items())
    ]
    score = tutorial_endpoint_st_rae(truth_rows, prediction_rows, endpoint)
    return score.value, score.eligible_rows


def _load_selector_capability(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    base._readonly_root(root, "G2-3B selector capability")
    manifest = _json(root / "manifest.json")
    _require(
        manifest.get("schema_version") == SELECTOR_SCHEMA
        and manifest.get("synthetic") is True
        and manifest.get("contract_sha256") == CONTRACT_SHA256
        and manifest.get("authority") == _stage_authority("selector")
        and manifest.get("feature_arrays") == 0
        and manifest.get("training_target_files") == 0
        and manifest.get("outer_truth_files") == 0,
        "selector capability identity differs",
    )
    observed = {path.name for path in root.iterdir()}
    _require(observed == {"inner_validation_truth.csv", "manifest.json"}, "selector capability files differ")
    rows = _rows(root / "inner_validation_truth.csv", INNER_TRUTH_COLUMNS)
    _require(
        base.sha256_path(root / "inner_validation_truth.csv") == manifest["inner_truth_sha256"]
        and len(rows) == 3840,
        "selector truth receipt or count differs",
    )
    return manifest, rows


def select_inner_configurations(
    *, frozen_root: Path, selector_capability_root: Path, output_root: Path
) -> Path:
    """Open inner truth only after all frozen predictions and select 60 tokens."""

    frozen_manifest, frozen = _load_prediction_root(
        frozen_root,
        schema=INNER_FROZEN_SCHEMA,
        filename="inner_frozen_predictions.csv",
        columns=INNER_FROZEN_COLUMNS,
    )
    selector_manifest, truth_rows = _load_selector_capability(selector_capability_root)
    _require(
        selector_manifest["canonical_source_sha256"] == frozen_manifest["canonical_source_sha256"],
        "selector and frozen source lineage differs",
    )
    _require(
        selector_manifest["root_instance_sha256"] == frozen_manifest["root_instance_sha256"],
        "selector and frozen root instance differs",
    )
    truth_by_cell: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    for row in truth_rows:
        truth_by_cell[row["endpoint"], int(row["repeat"]), int(row["outer_fold"])].append(row)
    prediction_by_cell: dict[
        tuple[str, int, int, str], dict[str, float]
    ] = defaultdict(dict)
    for row in frozen:
        key = (
            row["endpoint"],
            int(row["repeat"]),
            int(row["outer_fold"]),
            row["configuration_id"],
        )
        molecule = row["molecule_id"]
        _require(molecule not in prediction_by_cell[key], "inner frozen prediction is duplicated")
        prediction_by_cell[key][molecule] = _float(row["prediction"], "inner frozen prediction")
    metric_rows: list[dict[str, object]] = []
    selections: list[dict[str, object]] = []
    metric_calls = 0
    for endpoint in ENDPOINTS:
        for repeat in REPEATS:
            for outer in OUTER_FOLDS:
                truth = truth_by_cell[endpoint, repeat, outer]
                _require(len(truth) == 64, "selector truth cell count differs")
                candidates: list[tuple[float, float, str, int, int]] = []
                for configuration_id in CONFIGURATION_IDS:
                    predictions = prediction_by_cell[
                        endpoint, repeat, outer, configuration_id
                    ]
                    _require(len(predictions) == 64, "selector prediction cell count differs")
                    tutorial, eligible = _tutorial_score(truth, predictions, endpoint)
                    component_mae, component_eligible, components = _component_macro_mae(
                        truth, predictions
                    )
                    _require(eligible == component_eligible, "selector masks differ")
                    metric_calls += 1
                    metric_rows.append(
                        {
                            "endpoint": endpoint,
                            "repeat": repeat,
                            "outer_fold": outer,
                            "configuration_id": configuration_id,
                            "tutorial_st_rae": format(tutorial, ".17g"),
                            "component_macro_mae": format(component_mae, ".17g"),
                            "eligible_rows": eligible,
                            "components": components,
                        }
                    )
                    candidates.append((tutorial, component_mae, configuration_id, eligible, components))
                selected = min(candidates, key=lambda value: value[:3])
                _require(
                    selected[2] == expected_outer_configuration(endpoint, repeat, outer),
                    "predeclared inner selection oracle differs",
                )
                token = _sha_text(
                    CONTRACT_SHA256,
                    frozen_manifest["canonical_source_sha256"],
                    selector_manifest["inner_truth_sha256"],
                    endpoint,
                    repeat,
                    outer,
                    selected[2],
                    format(selected[0], ".17g"),
                    format(selected[1], ".17g"),
                )
                selections.append(
                    {
                        "endpoint": endpoint,
                        "repeat": repeat,
                        "outer_fold": outer,
                        "configuration_id": selected[2],
                        "tutorial_st_rae": format(selected[0], ".17g"),
                        "component_macro_mae": format(selected[1], ".17g"),
                        "selection_token_sha256": token,
                    }
                )
    metric_rows.sort(key=lambda row: tuple(row[name] for name in SELECTION_METRIC_COLUMNS[:4]))
    selections.sort(key=lambda row: tuple(row[name] for name in SELECTION_COLUMNS[:3]))
    _require(metric_calls == 720 and len(selections) == 60, "selector topology differs")
    _require(len({row["configuration_id"] for row in selections}) >= 3, "selection diversity oracle differs")

    projection_groups: dict[tuple[str, str, str, int, str], list[tuple[int, float]]] = defaultdict(list)
    for row in frozen:
        key = (
            row["molecule_id"],
            row["endpoint"],
            row["similarity_component_hash"],
            int(row["repeat"]),
            row["configuration_id"],
        )
        projection_groups[key].append((int(row["outer_fold"]), _float(row["prediction"], "projection prediction")))
    projection: list[dict[str, object]] = []
    for key, values in projection_groups.items():
        ordered = sorted(values)
        _require(len(ordered) == 4 and len({outer for outer, _ in ordered}) == 4, "projection outer-context set differs")
        projection.append(
            {
                "molecule_id": key[0],
                "endpoint": key[1],
                "similarity_component_hash": key[2],
                "repeat": key[3],
                "configuration_id": key[4],
                "prediction": format(math.fsum(value for _outer, value in ordered) / 4.0, ".17g"),
            }
        )
    projection.sort(key=lambda row: tuple(row[name] for name in PROJECTION_COLUMNS[:5]))
    _require(len(projection) == 11520, "complete selection projection count differs")
    metric_csv = base.csv_bytes(SELECTION_METRIC_COLUMNS, metric_rows)
    selection_csv = base.csv_bytes(SELECTION_COLUMNS, selections)
    projection_csv = base.csv_bytes(PROJECTION_COLUMNS, projection)
    result = {
        "schema_version": SELECTION_SCHEMA,
        "status": "G2_3B_INNER_SELECTIONS_FROZEN",
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "inner_frozen_manifest_sha256": base.sha256_path(frozen_root / "manifest.json"),
        "selector_capability_manifest_sha256": base.sha256_path(selector_capability_root / "manifest.json"),
        "canonical_source_sha256": frozen_manifest["canonical_source_sha256"],
        "root_instance_sha256": frozen_manifest["root_instance_sha256"],
        "counts": {
            "configuration_metrics": len(metric_rows),
            "selection_tokens": len(selections),
            "complete_projection_rows": len(projection),
            "tutorial_metric_calls": metric_calls,
            "outer_truth_values_opened": 0,
        },
        "output_receipts": {
            "inner_selection_metrics.csv": base.sha256_bytes(metric_csv),
            "selection_tokens.csv": base.sha256_bytes(selection_csv),
            "complete_selection_projection.csv": base.sha256_bytes(projection_csv),
        },
        "authority": _stage_authority("selector"),
    }
    return base.publish_files(
        output_root,
        {
            "inner_selection_metrics.csv": metric_csv,
            "selection_tokens.csv": selection_csv,
            "complete_selection_projection.csv": projection_csv,
            "manifest.json": base.json_bytes(result),
        },
    )


def _load_selections(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    base._readonly_root(root, "G2-3B selection root")
    manifest = _json(root / "manifest.json")
    _require(
        manifest.get("schema_version") == SELECTION_SCHEMA
        and manifest.get("synthetic") is True
        and manifest.get("contract_sha256") == CONTRACT_SHA256,
        "selection root identity differs",
    )
    rows = _rows(root / "selection_tokens.csv", SELECTION_COLUMNS)
    _require(
        len(rows) == 60
        and base.sha256_path(root / "selection_tokens.csv")
        == manifest["output_receipts"]["selection_tokens.csv"],
        "selection token receipt differs",
    )
    seen: set[tuple[str, int, int]] = set()
    for row in rows:
        key = row["endpoint"], int(row["repeat"]), int(row["outer_fold"])
        _require(key not in seen and row["configuration_id"] in CONFIGURATION_IDS, "selection token identity differs")
        _require(_is_sha(row["selection_token_sha256"]), "selection token hash differs")
        seen.add(key)
    return manifest, rows


def run_outer_models(
    *,
    model_capability_root: Path,
    selection_root: Path,
    output_root: Path,
    reverse_execution_order: bool = False,
) -> Path:
    """Run exactly three model-double seeds for each selected outer cell."""

    model_manifest, molecules, components, folds, arrays = _load_model_capability(model_capability_root)
    selection_manifest, selection_rows = _load_selections(selection_root)
    _require(
        selection_manifest["canonical_source_sha256"] == model_manifest["canonical_source_sha256"],
        "outer model selection lineage differs",
    )
    _require(
        selection_manifest["root_instance_sha256"] == model_manifest["root_instance_sha256"],
        "outer model root instance differs",
    )
    selections = {
        (row["endpoint"], int(row["repeat"]), int(row["outer_fold"])): row
        for row in selection_rows
    }
    index = {molecule: position for position, molecule in enumerate(molecules)}
    rows: list[dict[str, object]] = []
    invocations = 0
    training_values_opened = 0
    for endpoint in _iteration(ENDPOINTS, reverse_execution_order):
        for repeat in _iteration(REPEATS, reverse_execution_order):
            for outer in _iteration(OUTER_FOLDS, reverse_execution_order):
                selection = selections[endpoint, repeat, outer]
                configuration_id = selection["configuration_id"]
                training_ids, prediction_ids = _cell_ids(
                    molecules, folds, repeat=repeat, outer=outer, inner=None
                )
                target_path = _target_path(
                    model_capability_root,
                    stage="outer",
                    endpoint=endpoint,
                    repeat=repeat,
                    outer=outer,
                    inner=None,
                )
                targets = _rows(target_path, TARGET_COLUMNS)
                _require(
                    [row["molecule_id"] for row in targets]
                    == sorted(row["molecule_id"] for row in targets)
                    and set(row["molecule_id"] for row in targets).issubset(training_ids),
                    "outer target crosses training boundary",
                )
                prediction_matrix = _matrix(arrays, [index[value] for value in prediction_ids])
                for model_seed in _iteration(MODEL_SEEDS, reverse_execution_order):
                    invocations += 1
                    training_values_opened += len(targets)
                    predicted = _model_double_predictions(
                        prediction_features=prediction_matrix,
                        endpoint=endpoint,
                        repeat=repeat,
                        outer=outer,
                        configuration_id=configuration_id,
                        model_seed=model_seed,
                    )
                    model_id = _sha_text(
                        CONTRACT_SHA256,
                        model_manifest["canonical_source_sha256"],
                        "outer",
                        endpoint,
                        repeat,
                        outer,
                        configuration_id,
                        model_seed,
                        selection["selection_token_sha256"],
                        base.sha256_path(target_path),
                    )
                    target_receipt = base.sha256_path(target_path)
                    split_id = _sha_text(model_manifest["folds_sha256"], repeat, outer, "outer")
                    for molecule, prediction in zip(prediction_ids, predicted, strict=True):
                        rows.append(
                            {
                                "molecule_id": molecule,
                                "endpoint": endpoint,
                                "similarity_component_hash": components[molecule],
                                "repeat": repeat,
                                "outer_fold": outer,
                                "configuration_id": configuration_id,
                                "model_seed": model_seed,
                                "prediction": format(float(prediction), ".17g"),
                                "selection_token_sha256": selection["selection_token_sha256"],
                                "contract_sha256": CONTRACT_SHA256,
                                "canonical_source_sha256": model_manifest["canonical_source_sha256"],
                                "feature_rows_sha256": model_manifest["feature_rows_sha256"],
                                "folds_sha256": model_manifest["folds_sha256"],
                                "target_receipt_sha256": target_receipt,
                                "model_id": model_id,
                                "split_id": split_id,
                            }
                        )
    rows.sort(key=lambda row: tuple(row[name] for name in OUTER_RAW_COLUMNS[:7]))
    _require(invocations == 180 and len(rows) == 2880, "outer model topology differs")
    value = base.csv_bytes(OUTER_RAW_COLUMNS, rows)
    result = {
        "schema_version": OUTER_RAW_SCHEMA,
        "status": "G2_3B_OUTER_MODEL_DOUBLE_COMPLETE",
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "model_capability_manifest_sha256": base.sha256_path(model_capability_root / "manifest.json"),
        "selection_manifest_sha256": base.sha256_path(selection_root / "manifest.json"),
        "canonical_source_sha256": model_manifest["canonical_source_sha256"],
        "root_instance_sha256": model_manifest["root_instance_sha256"],
        "counts": {
            "model_double_invocations": invocations,
            "raw_prediction_rows": len(rows),
            "training_target_values_opened": training_values_opened,
            "outer_truth_values_opened": 0,
        },
        "output_receipts": {"outer_raw_predictions.csv": base.sha256_bytes(value)},
        "authority": _stage_authority("model"),
    }
    return base.publish_files(
        output_root,
        {"outer_raw_predictions.csv": value, "manifest.json": base.json_bytes(result)},
    )


def freeze_outer_predictions(*, raw_root: Path, selection_root: Path, output_root: Path) -> Path:
    """Freeze selected outer predictions before the scorer can open outer truth."""

    manifest, rows = _load_prediction_root(
        raw_root,
        schema=OUTER_RAW_SCHEMA,
        filename="outer_raw_predictions.csv",
        columns=OUTER_RAW_COLUMNS,
    )
    _selection_manifest, selection_rows = _load_selections(selection_root)
    _require(
        _selection_manifest["root_instance_sha256"] == manifest["root_instance_sha256"],
        "outer freezer root instance differs",
    )
    tokens = {
        (row["endpoint"], row["repeat"], row["outer_fold"]): row
        for row in selection_rows
    }
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        token = tokens[row["endpoint"], row["repeat"], row["outer_fold"]]
        _require(
            row["configuration_id"] == token["configuration_id"]
            and row["selection_token_sha256"] == token["selection_token_sha256"]
            and row["canonical_source_sha256"] == manifest["canonical_source_sha256"],
            "outer selection lineage differs",
        )
        _float(row["prediction"], "outer prediction")
        key = tuple(row[name] for name in OUTER_RAW_COLUMNS if name not in {"model_seed", "prediction", "model_id"})
        groups[key].append(row)
    frozen: list[dict[str, object]] = []
    for grouped in groups.values():
        prediction, ordered = _validated_seed_mean(grouped, stage="outer")
        first = ordered[0]
        output = {name: first[name] for name in OUTER_FROZEN_COLUMNS}
        output["prediction"] = format(prediction, ".17g")
        output["model_id"] = _sha_text(*(row["model_id"] for row in ordered))
        frozen.append(output)
    frozen.sort(key=lambda row: tuple(row[name] for name in OUTER_FROZEN_COLUMNS[:6]))
    _require(len(frozen) == 960, "outer frozen prediction count differs")
    value = base.csv_bytes(OUTER_FROZEN_COLUMNS, frozen)
    result = {
        "schema_version": OUTER_FROZEN_SCHEMA,
        "status": "G2_3B_OUTER_PREDICTIONS_FROZEN",
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "outer_raw_manifest_sha256": base.sha256_path(raw_root / "manifest.json"),
        "selection_manifest_sha256": base.sha256_path(selection_root / "manifest.json"),
        "canonical_source_sha256": manifest["canonical_source_sha256"],
        "root_instance_sha256": manifest["root_instance_sha256"],
        "counts": {"seed_sets": len(frozen), "seeds_per_set": 3, "outer_truth_values_opened": 0},
        "output_receipts": {"outer_frozen_predictions.csv": base.sha256_bytes(value)},
        "authority": _stage_authority("model"),
    }
    return base.publish_files(
        output_root,
        {"outer_frozen_predictions.csv": value, "manifest.json": base.json_bytes(result)},
    )


def _load_scorer_capability(root: Path) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    base._readonly_root(root, "G2-3B scorer capability")
    manifest = _json(root / "manifest.json")
    _require(
        manifest.get("schema_version") == SCORER_SCHEMA
        and manifest.get("synthetic") is True
        and manifest.get("contract_sha256") == CONTRACT_SHA256
        and manifest.get("authority") == _stage_authority("scorer")
        and manifest.get("feature_arrays") == 0
        and manifest.get("training_target_files") == 0
        and manifest.get("inner_truth_files") == 0,
        "scorer capability identity differs",
    )
    _require(
        {path.name for path in root.iterdir()}
        == {"outer_truth.csv", "baseline_predictions.csv", "manifest.json"},
        "scorer capability files differ",
    )
    truth = _rows(root / "outer_truth.csv", OUTER_TRUTH_COLUMNS)
    baseline = _rows(root / "baseline_predictions.csv", BASELINE_COLUMNS)
    _require(
        len(truth) == len(baseline) == 960
        and base.sha256_path(root / "outer_truth.csv") == manifest["outer_truth_sha256"]
        and base.sha256_path(root / "baseline_predictions.csv")
        == manifest["baseline_predictions_sha256"],
        "scorer receipt or count differs",
    )
    return manifest, truth, baseline


def _mean(values: Iterable[float], denominator: int, label: str) -> float:
    material = list(values)
    _require(len(material) == denominator and denominator > 0, f"{label} cardinality differs")
    result = math.fsum(material) / denominator
    _require(math.isfinite(result), f"{label} is nonfinite")
    return result


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    _require(
        bool(ordered)
        and all(math.isfinite(value) for value in ordered)
        and 0.0 <= probability <= 1.0,
        "bootstrap quantile input differs",
    )
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _paired_component_bootstrap(
    *,
    truth_rows: Sequence[Mapping[str, str]],
    candidate: Mapping[tuple[str, str, int], float],
    baseline: Mapping[tuple[str, str, int], float],
) -> dict[str, object]:
    residuals: dict[tuple[str, str, int, str], list[tuple[float, float]]] = defaultdict(list)
    for row in truth_rows:
        if row["availability"] != "complete":
            continue
        key = row["molecule_id"], row["endpoint"], int(row["repeat"])
        _require(key in candidate and key in baseline, "bootstrap paired identity differs")
        point = _float(row["point"], "bootstrap truth point")
        residuals[
            row["similarity_component_hash"], row["endpoint"], int(row["repeat"]), row["molecule_id"]
        ].append((abs(candidate[key] - point), abs(baseline[key] - point)))
    component_cells: dict[tuple[str, str, int], tuple[float, float]] = {}
    component_names = sorted({key[0] for key in residuals})
    for component in component_names:
        for endpoint in ENDPOINTS:
            for repeat in REPEATS:
                molecule_values = [
                    pair
                    for (observed_component, observed_endpoint, observed_repeat, _molecule), pairs in residuals.items()
                    if observed_component == component
                    and observed_endpoint == endpoint
                    and observed_repeat == repeat
                    for pair in pairs
                ]
                _require(bool(molecule_values), "bootstrap component lacks an endpoint row")
                component_cells[component, endpoint, repeat] = (
                    _mean((value[0] for value in molecule_values), len(molecule_values), "candidate component residual"),
                    _mean((value[1] for value in molecule_values), len(molecule_values), "baseline component residual"),
                )
    _require(len(component_names) == 40, "bootstrap component count differs")
    generator = random.Random(20260827)
    differences: list[float] = []
    attempts = 0
    while len(differences) < 2000 and attempts < 20000:
        attempts += 1
        draw = [component_names[generator.randrange(len(component_names))] for _ in component_names]
        candidate_cells: list[float] = []
        baseline_cells: list[float] = []
        for endpoint in ENDPOINTS:
            for repeat in REPEATS:
                candidate_cells.append(
                    _mean(
                        (component_cells[name, endpoint, repeat][0] for name in draw),
                        len(draw),
                        "bootstrap candidate cell",
                    )
                )
                baseline_cells.append(
                    _mean(
                        (component_cells[name, endpoint, repeat][1] for name in draw),
                        len(draw),
                        "bootstrap baseline cell",
                    )
                )
        candidate_value = _mean(candidate_cells, 12, "bootstrap candidate macro")
        baseline_value = _mean(baseline_cells, 12, "bootstrap baseline macro")
        difference = candidate_value - baseline_value
        if math.isfinite(difference):
            differences.append(difference)
    _require(len(differences) == 2000, "bootstrap accepted replicate count differs")
    return {
        "unit": "synthetic_similarity_component_hash",
        "seed": 20260827,
        "accepted_replicates": len(differences),
        "attempts": attempts,
        "maximum_attempts": 20000,
        "difference": "candidate_component_macro_mae_minus_baseline",
        "lower_95": _quantile(differences, 0.025),
        "upper_95": _quantile(differences, 0.975),
    }


def score_outer_predictions(
    *, outer_frozen_root: Path, scorer_capability_root: Path, output_root: Path
) -> Path:
    """Open outer truth only after all 60 selected outer freezers are immutable."""

    frozen_manifest, frozen_rows = _load_prediction_root(
        outer_frozen_root,
        schema=OUTER_FROZEN_SCHEMA,
        filename="outer_frozen_predictions.csv",
        columns=OUTER_FROZEN_COLUMNS,
    )
    scorer_manifest, truth_rows, baseline_rows = _load_scorer_capability(scorer_capability_root)
    _require(
        scorer_manifest["canonical_source_sha256"] == frozen_manifest["canonical_source_sha256"],
        "outer scorer lineage differs",
    )
    _require(
        scorer_manifest["root_instance_sha256"] == frozen_manifest["root_instance_sha256"],
        "outer scorer root instance differs",
    )
    candidate: dict[tuple[str, str, int], float] = {}
    candidate_cell: dict[tuple[str, str, int, int], float] = {}
    component_by_molecule: dict[str, str] = {}
    for row in frozen_rows:
        key = row["molecule_id"], row["endpoint"], int(row["repeat"])
        cell_key = (*key, int(row["outer_fold"]))
        _require(key not in candidate and cell_key not in candidate_cell, "outer candidate identity is duplicated")
        value = _float(row["prediction"], "outer frozen prediction")
        candidate[key] = value
        candidate_cell[cell_key] = value
        component_by_molecule[row["molecule_id"]] = row["similarity_component_hash"]
    baseline: dict[tuple[str, str, int], float] = {}
    for row in baseline_rows:
        key = row["molecule_id"], row["endpoint"], int(row["repeat"])
        _require(key not in baseline, "baseline identity is duplicated")
        baseline[key] = _float(row["prediction"], "baseline prediction")
    _require(set(candidate) == set(baseline), "candidate and baseline identities differ")

    truth_by_endpoint_repeat: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    truth_by_cell: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    for row in truth_rows:
        truth_by_endpoint_repeat[row["endpoint"], int(row["repeat"])].append(row)
        truth_by_cell[row["endpoint"], int(row["repeat"]), int(row["outer_fold"])].append(row)
    endpoint_repeat_values: dict[tuple[str, int], tuple[float, float, float, float]] = {}
    tutorial_calls = 0
    for endpoint in ENDPOINTS:
        for repeat in REPEATS:
            truth = truth_by_endpoint_repeat[endpoint, repeat]
            candidate_predictions = {
                row["molecule_id"]: candidate[row["molecule_id"], endpoint, repeat]
                for row in truth
            }
            baseline_predictions = {
                row["molecule_id"]: baseline[row["molecule_id"], endpoint, repeat]
                for row in truth
            }
            candidate_tutorial, _eligible = _tutorial_score(truth, candidate_predictions, endpoint)
            baseline_tutorial, _eligible = _tutorial_score(truth, baseline_predictions, endpoint)
            candidate_component, _eligible, _components = _component_macro_mae(truth, candidate_predictions)
            baseline_component, _eligible, _components = _component_macro_mae(truth, baseline_predictions)
            tutorial_calls += 2
            endpoint_repeat_values[endpoint, repeat] = (
                candidate_tutorial,
                baseline_tutorial,
                candidate_component,
                baseline_component,
            )
    endpoint_metrics: list[dict[str, object]] = []
    for endpoint in ENDPOINTS:
        candidate_tutorial = _mean((endpoint_repeat_values[endpoint, repeat][0] for repeat in REPEATS), 3, "endpoint candidate tutorial")
        baseline_tutorial = _mean((endpoint_repeat_values[endpoint, repeat][1] for repeat in REPEATS), 3, "endpoint baseline tutorial")
        candidate_component = _mean((endpoint_repeat_values[endpoint, repeat][2] for repeat in REPEATS), 3, "endpoint candidate component")
        baseline_component = _mean((endpoint_repeat_values[endpoint, repeat][3] for repeat in REPEATS), 3, "endpoint baseline component")
        endpoint_metrics.append(
            {
                "endpoint": endpoint,
                "candidate_tutorial_st_rae": format(candidate_tutorial, ".17g"),
                "baseline_tutorial_st_rae": format(baseline_tutorial, ".17g"),
                "candidate_component_macro_mae": format(candidate_component, ".17g"),
                "baseline_component_macro_mae": format(baseline_component, ".17g"),
                "component_mae_difference": format(candidate_component - baseline_component, ".17g"),
            }
        )
    outer_cells: list[dict[str, object]] = []
    favorable = 0
    for repeat in REPEATS:
        for outer in OUTER_FOLDS:
            candidate_endpoint: list[float] = []
            baseline_endpoint: list[float] = []
            for endpoint in ENDPOINTS:
                truth = truth_by_cell[endpoint, repeat, outer]
                candidate_predictions = {
                    row["molecule_id"]: candidate_cell[
                        row["molecule_id"], endpoint, repeat, outer
                    ]
                    for row in truth
                }
                baseline_predictions = {
                    row["molecule_id"]: baseline[row["molecule_id"], endpoint, repeat]
                    for row in truth
                }
                candidate_endpoint.append(_component_macro_mae(truth, candidate_predictions)[0])
                baseline_endpoint.append(_component_macro_mae(truth, baseline_predictions)[0])
            candidate_value = _mean(candidate_endpoint, 4, "outer candidate macro")
            baseline_value = _mean(baseline_endpoint, 4, "outer baseline macro")
            is_favorable = candidate_value < baseline_value
            favorable += int(is_favorable)
            outer_cells.append(
                {
                    "repeat": repeat,
                    "outer_fold": outer,
                    "candidate_component_macro_mae": format(candidate_value, ".17g"),
                    "baseline_component_macro_mae": format(baseline_value, ".17g"),
                    "difference": format(candidate_value - baseline_value, ".17g"),
                    "favorable": "true" if is_favorable else "false",
                }
            )
    candidate_primary = _mean(
        (
            _mean((endpoint_repeat_values[endpoint, repeat][0] for endpoint in ENDPOINTS), 4, "candidate repeat tutorial")
            for repeat in REPEATS
        ),
        3,
        "candidate primary",
    )
    baseline_primary = _mean(
        (
            _mean((endpoint_repeat_values[endpoint, repeat][1] for endpoint in ENDPOINTS), 4, "baseline repeat tutorial")
            for repeat in REPEATS
        ),
        3,
        "baseline primary",
    )
    candidate_component = _mean(
        (endpoint_repeat_values[endpoint, repeat][2] for endpoint in ENDPOINTS for repeat in REPEATS),
        12,
        "candidate component macro",
    )
    baseline_component = _mean(
        (endpoint_repeat_values[endpoint, repeat][3] for endpoint in ENDPOINTS for repeat in REPEATS),
        12,
        "baseline component macro",
    )
    bootstrap = _paired_component_bootstrap(
        truth_rows=truth_rows, candidate=candidate, baseline=baseline
    )
    result = {
        "status": "G2_3B_SYNTHETIC_OUTER_EVIDENCE_FROZEN",
        "scientific_interpretation": "Synthetic mechanics only; these values cannot select or rank a model.",
        "candidate_primary_tutorial_st_rae": candidate_primary,
        "baseline_primary_tutorial_st_rae": baseline_primary,
        "relative_primary_improvement": (baseline_primary - candidate_primary) / baseline_primary,
        "candidate_component_macro_mae": candidate_component,
        "baseline_component_macro_mae": baseline_component,
        "absolute_component_mae_improvement": baseline_component - candidate_component,
        "favorable_outer_cells": favorable,
        "maximum_endpoint_mae_degradation": max(
            _float(row["component_mae_difference"], "endpoint difference")
            for row in endpoint_metrics
        ),
        "paired_component_upper_95": bootstrap["upper_95"],
    }
    outer_csv = base.csv_bytes(OUTER_CELL_METRIC_COLUMNS, outer_cells)
    endpoint_csv = base.csv_bytes(ENDPOINT_METRIC_COLUMNS, endpoint_metrics)
    bootstrap_json = base.json_bytes(bootstrap)
    result_json = base.json_bytes(result)
    scored_manifest = {
        "schema_version": SCORED_SCHEMA,
        "status": "G2_3B_SYNTHETIC_OUTER_EVIDENCE_FROZEN",
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "outer_frozen_manifest_sha256": base.sha256_path(outer_frozen_root / "manifest.json"),
        "scorer_capability_manifest_sha256": base.sha256_path(scorer_capability_root / "manifest.json"),
        "canonical_source_sha256": frozen_manifest["canonical_source_sha256"],
        "root_instance_sha256": frozen_manifest["root_instance_sha256"],
        "counts": {
            "outer_prediction_rows": len(frozen_rows),
            "outer_truth_rows": len(truth_rows),
            "tutorial_metric_calls": tutorial_calls,
            "bootstrap_accepted_replicates": bootstrap["accepted_replicates"],
        },
        "output_receipts": {
            "g1_synthetic_outer_cell_metrics.csv": base.sha256_bytes(outer_csv),
            "g1_synthetic_endpoint_metrics.csv": base.sha256_bytes(endpoint_csv),
            "g1_synthetic_bootstrap_summary.json": base.sha256_bytes(bootstrap_json),
            "g1_synthetic_result.json": base.sha256_bytes(result_json),
        },
        "authority": _stage_authority("scorer"),
    }
    return base.publish_files(
        output_root,
        {
            "g1_synthetic_outer_cell_metrics.csv": outer_csv,
            "g1_synthetic_endpoint_metrics.csv": endpoint_csv,
            "g1_synthetic_bootstrap_summary.json": bootstrap_json,
            "g1_synthetic_result.json": result_json,
            "manifest.json": base.json_bytes(scored_manifest),
        },
    )


def freeze_future_configurations(
    *,
    selection_root: Path,
    selector_capability_root: Path,
    scored_root: Path,
    output_root: Path,
) -> Path:
    """Freeze future endpoint tokens after immutable outer evidence exists."""

    selection_manifest, _selection_rows = _load_selections(selection_root)
    selector_manifest, inner_truth = _load_selector_capability(selector_capability_root)
    base._readonly_root(scored_root, "G2-3B scored root")
    scored_manifest = _json(scored_root / "manifest.json")
    _require(
        scored_manifest.get("schema_version") == SCORED_SCHEMA
        and scored_manifest.get("status") == "G2_3B_SYNTHETIC_OUTER_EVIDENCE_FROZEN"
        and scored_manifest.get("canonical_source_sha256")
        == selection_manifest["canonical_source_sha256"]
        == selector_manifest["canonical_source_sha256"],
        "future freezer lineage differs",
    )
    _require(
        scored_manifest.get("root_instance_sha256")
        == selection_manifest["root_instance_sha256"]
        == selector_manifest["root_instance_sha256"],
        "future freezer root instance differs",
    )
    projection = _rows(selection_root / "complete_selection_projection.csv", PROJECTION_COLUMNS)
    _require(
        len(projection) == 11520
        and base.sha256_path(selection_root / "complete_selection_projection.csv")
        == selection_manifest["output_receipts"]["complete_selection_projection.csv"],
        "future projection receipt differs",
    )
    truth_unique: dict[tuple[str, str], dict[str, str]] = {}
    for row in inner_truth:
        key = row["molecule_id"], row["endpoint"]
        normalized = {
            "molecule_id": row["molecule_id"],
            "endpoint": row["endpoint"],
            "similarity_component_hash": row["similarity_component_hash"],
            "availability": row["availability"],
            "point": row["point"],
            "low": row["low"],
            "high": row["high"],
        }
        if key in truth_unique:
            _require(truth_unique[key] == normalized, "future truth copies differ")
        else:
            truth_unique[key] = normalized
    _require(len(truth_unique) == 320, "future truth identity count differs")
    predictions: dict[tuple[str, int, str], dict[str, float]] = defaultdict(dict)
    for row in projection:
        key = row["endpoint"], int(row["repeat"]), row["configuration_id"]
        molecule = row["molecule_id"]
        _require(molecule not in predictions[key], "future projection identity is duplicated")
        predictions[key][molecule] = _float(row["prediction"], "future projection prediction")
    metric_calls = 0
    metrics: list[dict[str, object]] = []
    tokens: list[dict[str, object]] = []
    for endpoint in ENDPOINTS:
        truth = [truth_unique[molecule, endpoint] for molecule in sorted({key[0] for key in truth_unique if key[1] == endpoint})]
        candidates: list[tuple[float, float, str]] = []
        for configuration_id in CONFIGURATION_IDS:
            repeat_tutorial: list[float] = []
            repeat_component: list[float] = []
            for repeat in REPEATS:
                values = predictions[endpoint, repeat, configuration_id]
                _require(len(values) == 80, "future projection cell count differs")
                repeat_tutorial.append(_tutorial_score(truth, values, endpoint)[0])
                repeat_component.append(_component_macro_mae(truth, values)[0])
                metric_calls += 1
            tutorial = _mean(repeat_tutorial, 3, "future tutorial")
            component = _mean(repeat_component, 3, "future component")
            metrics.append(
                {
                    "endpoint": endpoint,
                    "configuration_id": configuration_id,
                    "tutorial_st_rae": format(tutorial, ".17g"),
                    "component_macro_mae": format(component, ".17g"),
                }
            )
            candidates.append((tutorial, component, configuration_id))
        selected = min(candidates)
        _require(selected[2] == "G1-C01", "future configuration oracle differs")
        token = _sha_text(
            CONTRACT_SHA256,
            selection_manifest["canonical_source_sha256"],
            scored_manifest["output_receipts"]["g1_synthetic_result.json"],
            endpoint,
            selected[2],
            format(selected[0], ".17g"),
            format(selected[1], ".17g"),
        )
        tokens.append(
            {
                "endpoint": endpoint,
                "configuration_id": selected[2],
                "tutorial_st_rae": format(selected[0], ".17g"),
                "component_macro_mae": format(selected[1], ".17g"),
                "future_configuration_token_sha256": token,
            }
        )
    metrics.sort(key=lambda row: tuple(row[name] for name in FUTURE_METRIC_COLUMNS[:2]))
    tokens.sort(key=lambda row: row["endpoint"])
    _require(metric_calls == 144 and len(metrics) == 48 and len(tokens) == 4, "future freezer topology differs")
    metric_csv = base.csv_bytes(FUTURE_METRIC_COLUMNS, metrics)
    token_csv = base.csv_bytes(FUTURE_TOKEN_COLUMNS, tokens)
    result = {
        "schema_version": FUTURE_SCHEMA,
        "status": "G2_3B_FUTURE_CONFIGURATIONS_FROZEN",
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "selection_manifest_sha256": base.sha256_path(selection_root / "manifest.json"),
        "selector_capability_manifest_sha256": base.sha256_path(selector_capability_root / "manifest.json"),
        "scored_manifest_sha256": base.sha256_path(scored_root / "manifest.json"),
        "canonical_source_sha256": selection_manifest["canonical_source_sha256"],
        "root_instance_sha256": selection_manifest["root_instance_sha256"],
        "counts": {"configuration_metrics": 48, "future_tokens": 4, "tutorial_metric_calls": metric_calls},
        "output_receipts": {
            "future_configuration_metrics.csv": base.sha256_bytes(metric_csv),
            "future_configuration_tokens.csv": base.sha256_bytes(token_csv),
        },
        "authority": _stage_authority("selector"),
    }
    return base.publish_files(
        output_root,
        {
            "future_configuration_metrics.csv": metric_csv,
            "future_configuration_tokens.csv": token_csv,
            "manifest.json": base.json_bytes(result),
        },
    )


def _runtime_identity() -> dict[str, str]:
    observed = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python": platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
        "catboost": importlib.metadata.version("catboost"),
    }
    _require(
        observed
        == {
            "platform": "Linux x86_64 CPU",
            "python": "3.10.13",
            "numpy": "1.25.2",
            "catboost": "1.2.1",
        },
        f"locked G2-3B runtime differs: {observed}",
    )
    return observed


def _probe_identities() -> list[tuple[str, int]]:
    return [
        *((configuration_id, MODEL_SEEDS[0]) for configuration_id in CONFIGURATION_IDS),
        (CONFIGURATION_IDS[0], MODEL_SEEDS[1]),
        (CONFIGURATION_IDS[0], MODEL_SEEDS[2]),
    ]


def run_runtime_probes(*, model_capability_root: Path, output_root: Path) -> Path:
    """Fit the exact fourteen real locked-runtime constructor probes for one root."""

    _contract, parent = _static_contract()
    runtime = _runtime_identity()
    manifest, molecules, _components, folds, arrays = _load_model_capability(model_capability_root)
    index = {molecule: position for position, molecule in enumerate(molecules)}
    training_ids, prediction_ids = _cell_ids(
        molecules, folds, repeat=0, outer=0, inner=None
    )
    targets = _rows(
        _target_path(
            model_capability_root,
            stage="outer",
            endpoint="CYP1A2",
            repeat=0,
            outer=0,
            inner=None,
        ),
        TARGET_COLUMNS,
    )
    target_map = {row["molecule_id"]: _float(row["point"], "probe target") for row in targets}
    fitted_ids = [molecule for molecule in training_ids if molecule in target_map]
    _require(len(fitted_ids) >= 48 and len(prediction_ids) == 16, "runtime probe support differs")
    training = _matrix(arrays, [index[molecule] for molecule in fitted_ids])
    y = np.asarray([target_map[molecule] for molecule in fitted_ids], dtype=np.float64)
    prediction = _matrix(arrays, [index[molecule] for molecule in prediction_ids])
    try:
        from catboost import (  # type: ignore[import-not-found]  # noqa: PLC0415
            CatBoostRegressor,
        )
    except ImportError as exc:
        raise G1SyntheticError("CatBoost 1.2.1 is unavailable") from exc
    configurations = {
        item["configuration_id"]: {
            name: value for name, value in item.items() if name != "configuration_id"
        }
        for item in parent["screen"]["configurations"]
    }
    common = dict(parent["screen"]["common_arguments"])
    probes: list[dict[str, object]] = []
    for configuration_id, seed in _probe_identities():
        constructor = {**configurations[configuration_id], **common, "random_seed": seed}
        model = CatBoostRegressor(**constructor)
        _require(model.get_params() == constructor, "CatBoost constructor arguments differ")
        model.fit(training, y)
        resolved = cast(dict[str, Any], model.get_all_params())
        _require(resolved.get("random_seed") == seed, "resolved CatBoost seed differs")
        predicted = np.asarray(model.predict(prediction), dtype=np.float64)
        _require(predicted.shape == (16,) and np.isfinite(predicted).all(), "runtime probe prediction differs")
        constructor_sha = base.sha256_bytes(base.json_bytes(constructor))
        resolved_sha = base.sha256_bytes(base.json_bytes(resolved))
        prediction_sha = base.sha256_bytes(
            base.json_bytes([format(float(value), ".17g") for value in predicted])
        )
        probes.append(
            {
                "configuration_id": configuration_id,
                "model_seed": seed,
                "constructor_sha256": constructor_sha,
                "resolved_parameter_sha256": resolved_sha,
                "prediction_sha256": prediction_sha,
                "training_rows": len(fitted_ids),
                "prediction_rows": len(prediction_ids),
                "finite_predictions": True,
            }
        )
    _require(len(probes) == 14, "runtime probe fit count differs")
    _require({row["configuration_id"] for row in probes} == set(CONFIGURATION_IDS), "runtime configuration coverage differs")
    _require(
        {row["model_seed"] for row in probes if row["configuration_id"] == "G1-C00"}
        == set(MODEL_SEEDS),
        "runtime seed coverage differs",
    )
    value = base.json_bytes(probes)
    result = {
        "schema_version": PROBE_SCHEMA,
        "status": "G2_3B_LOCKED_RUNTIME_PROBES_COMPLETE",
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "model_capability_manifest_sha256": base.sha256_path(model_capability_root / "manifest.json"),
        "canonical_source_sha256": manifest["canonical_source_sha256"],
        "root_instance_sha256": manifest["root_instance_sha256"],
        "runtime": runtime,
        "counts": {"real_catboost_fits": len(probes), "configuration_forms": 12, "model_seeds": 3},
        "output_receipts": {"g1_synthetic_runtime_probes.json": base.sha256_bytes(value)},
        "authority": _stage_authority("model"),
    }
    return base.publish_files(
        output_root,
        {"g1_synthetic_runtime_probes.json": value, "manifest.json": base.json_bytes(result)},
    )


def publish_fake_runtime_probes(*, model_capability_root: Path, output_root: Path) -> Path:
    """Publish deterministic probe-shaped unit-test evidence without a real fit."""

    manifest, _molecules, _components, _folds, _arrays = _load_model_capability(model_capability_root)
    probes = [
        {
            "configuration_id": configuration_id,
            "model_seed": seed,
            "constructor_sha256": _sha_text("fake-constructor", configuration_id, seed),
            "resolved_parameter_sha256": _sha_text("fake-resolved", configuration_id, seed),
            "prediction_sha256": _sha_text("fake-prediction", configuration_id, seed),
            "training_rows": 60,
            "prediction_rows": 16,
            "finite_predictions": True,
        }
        for configuration_id, seed in _probe_identities()
    ]
    value = base.json_bytes(probes)
    result = {
        "schema_version": PROBE_SCHEMA,
        "status": "G2_3B_LOCKED_RUNTIME_PROBES_COMPLETE",
        "synthetic": True,
        "test_double": True,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "model_capability_manifest_sha256": base.sha256_path(model_capability_root / "manifest.json"),
        "canonical_source_sha256": manifest["canonical_source_sha256"],
        "root_instance_sha256": manifest["root_instance_sha256"],
        "runtime": {"synthetic_test": "fake"},
        "counts": {"real_catboost_fits": 14, "configuration_forms": 12, "model_seeds": 3},
        "output_receipts": {"g1_synthetic_runtime_probes.json": base.sha256_bytes(value)},
        "authority": _stage_authority("model"),
    }
    return base.publish_files(
        output_root,
        {"g1_synthetic_runtime_probes.json": value, "manifest.json": base.json_bytes(result)},
    )


def _validate_probe_rows(value: bytes) -> list[Mapping[str, object]]:
    try:
        parsed = json.loads(value)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise G1SyntheticError("runtime probe rows are not JSON") from exc
    _require(isinstance(parsed, list), "runtime probe rows are not a list")
    rows = cast(list[Mapping[str, object]], parsed)
    _require(len(rows) == 14, "runtime probe row count differs")
    identities = [(row.get("configuration_id"), row.get("model_seed")) for row in rows]
    _require(identities == _probe_identities(), "runtime probe identity coverage differs")
    for row in rows:
        _require(
            all(
                _is_sha(row.get(name))
                for name in (
                    "constructor_sha256",
                    "resolved_parameter_sha256",
                    "prediction_sha256",
                )
            )
            and isinstance(row.get("training_rows"), int)
            and cast(int, row["training_rows"]) >= 48
            and row.get("prediction_rows") == 16
            and row.get("finite_predictions") is True,
            "runtime probe evidence differs",
        )
    return rows


def terminal_files(
    *,
    selection_root: Path,
    scored_root: Path,
    future_root: Path,
    probe_root: Path,
    allow_test_double: bool = False,
) -> dict[str, bytes]:
    """Validate all immutable stage roots and return the exact terminal byte map."""

    selection_manifest, selections = _load_selections(selection_root)
    base._readonly_root(scored_root, "G2-3B scored root")
    scored_manifest = _json(scored_root / "manifest.json")
    base._readonly_root(future_root, "G2-3B future root")
    future_manifest = _json(future_root / "manifest.json")
    base._readonly_root(probe_root, "G2-3B probe root")
    probe_manifest = _json(probe_root / "manifest.json")
    _require(
        scored_manifest.get("schema_version") == SCORED_SCHEMA
        and future_manifest.get("schema_version") == FUTURE_SCHEMA
        and probe_manifest.get("schema_version") == PROBE_SCHEMA
        and scored_manifest.get("contract_sha256")
        == future_manifest.get("contract_sha256")
        == probe_manifest.get("contract_sha256")
        == CONTRACT_SHA256,
        "terminal stage identity differs",
    )
    canonical_source = selection_manifest["canonical_source_sha256"]
    _require(
        scored_manifest.get("canonical_source_sha256")
        == future_manifest.get("canonical_source_sha256")
        == probe_manifest.get("canonical_source_sha256")
        == canonical_source,
        "terminal stage source lineage differs",
    )
    _require(
        scored_manifest.get("root_instance_sha256")
        == future_manifest.get("root_instance_sha256")
        == probe_manifest.get("root_instance_sha256")
        == selection_manifest["root_instance_sha256"],
        "terminal stage root instance differs",
    )
    _require(
        probe_manifest.get("status") == "G2_3B_LOCKED_RUNTIME_PROBES_COMPLETE"
        and probe_manifest.get("counts")
        == {"real_catboost_fits": 14, "configuration_forms": 12, "model_seeds": 3},
        "terminal runtime probe count differs",
    )
    if not allow_test_double:
        _require(probe_manifest.get("test_double") is not True, "test-double probe cannot enter acceptance")
        _require(probe_manifest.get("runtime") == _runtime_identity(), "terminal runtime differs")
    probe_bytes = (probe_root / "g1_synthetic_runtime_probes.json").read_bytes()
    _require(
        base.sha256_bytes(probe_bytes)
        == probe_manifest["output_receipts"]["g1_synthetic_runtime_probes.json"],
        "terminal runtime probe receipt differs",
    )
    _validate_probe_rows(probe_bytes)
    future_tokens = _rows(future_root / "future_configuration_tokens.csv", FUTURE_TOKEN_COLUMNS)
    _require(
        len(future_tokens) == 4
        and base.sha256_path(future_root / "future_configuration_tokens.csv")
        == future_manifest["output_receipts"]["future_configuration_tokens.csv"],
        "future token receipt differs",
    )
    summary: list[dict[str, object]] = [
        {
            "scope": "outer_cell",
            "endpoint": row["endpoint"],
            "repeat": row["repeat"],
            "outer_fold": row["outer_fold"],
            "configuration_id": row["configuration_id"],
            "tutorial_st_rae": row["tutorial_st_rae"],
            "component_macro_mae": row["component_macro_mae"],
            "token_sha256": row["selection_token_sha256"],
        }
        for row in selections
    ]
    summary.extend(
        {
            "scope": "future_endpoint",
            "endpoint": row["endpoint"],
            "repeat": "",
            "outer_fold": "",
            "configuration_id": row["configuration_id"],
            "tutorial_st_rae": row["tutorial_st_rae"],
            "component_macro_mae": row["component_macro_mae"],
            "token_sha256": row["future_configuration_token_sha256"],
        }
        for row in future_tokens
    )
    summary.sort(
        key=lambda row: (
            row["scope"],
            row["endpoint"],
            str(row["repeat"]),
            str(row["outer_fold"]),
        )
    )
    selection_csv = base.csv_bytes(SELECTION_SUMMARY_COLUMNS, summary)
    copied = {
        name: (scored_root / name).read_bytes()
        for name in (
            "g1_synthetic_outer_cell_metrics.csv",
            "g1_synthetic_endpoint_metrics.csv",
            "g1_synthetic_bootstrap_summary.json",
        )
    }
    for name, value in copied.items():
        _require(
            base.sha256_bytes(value) == scored_manifest["output_receipts"][name],
            f"terminal scored receipt differs: {name}",
        )
    outer_result = _json(scored_root / "g1_synthetic_result.json")
    result = {
        "schema_version": TERMINAL_SCHEMA,
        "status": "G2_3B_EXP_G1_SYNTHETIC_ACCEPTED",
        "scientific_interpretation": "Synthetic mechanics and locked-runtime compatibility only; no result may select or rank a model.",
        "outer_mechanics": outer_result,
        "expected_inner_selections_match": True,
        "expected_future_endpoint_tokens_match": True,
        "family_and_capability_adversaries_required": True,
        "identity_and_numeric_adversaries_required": True,
        "accounting_cleanup_and_no_replace_adversaries_required": True,
    }
    result_json = base.json_bytes(result)
    files: dict[str, bytes] = {
        "g1_synthetic_selection_summary.csv": selection_csv,
        **copied,
        "g1_synthetic_runtime_probes.json": probe_bytes,
        "g1_synthetic_result.json": result_json,
    }
    accounting = {
        "synthetic_source_rows_opened": 1600,
        "synthetic_model_double_invocations": 8820,
        "synthetic_catboost_fits": 14,
        "synthetic_predictions_generated": 141120,
        "synthetic_tutorial_metric_evaluations": 888,
        **{name: 0 for name in OFFICIAL_ZERO_FIELDS},
    }
    manifest = {
        "schema_version": TERMINAL_SCHEMA,
        "status": "G2_3B_EXP_G1_SYNTHETIC_ACCEPTED",
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "parent_sha256": PARENT_SHA256,
        "canonical_source_sha256": canonical_source,
        "implementation_receipts": {
            "g1_runner_source_sha256": base.sha256_path(SCRIPT),
            "accepted_maplight_runner_source_sha256": base.sha256_path(base.SCRIPT),
            "tutorial_metric_source_sha256": base.sha256_path(METRIC_SOURCE),
            "research_uv_lock_sha256": base.sha256_path(LOCK),
        },
        "canonical_stage_output_receipts": {
            "selection_tokens_sha256": selection_manifest["output_receipts"]["selection_tokens.csv"],
            "scored_result_sha256": scored_manifest["output_receipts"]["g1_synthetic_result.json"],
            "future_tokens_sha256": future_manifest["output_receipts"]["future_configuration_tokens.csv"],
            "runtime_probes_sha256": probe_manifest["output_receipts"]["g1_synthetic_runtime_probes.json"],
        },
        "counts": {
            "molecules": 80,
            "components": 40,
            "inner_model_double_invocations": 8640,
            "outer_model_double_invocations": 180,
            "model_double_invocations": 8820,
            "real_catboost_fits": 14,
            "inner_raw_prediction_rows": 138240,
            "inner_frozen_prediction_rows": 46080,
            "complete_selection_projection_rows": 11520,
            "outer_raw_prediction_rows": 2880,
            "outer_frozen_prediction_rows": 960,
            "selection_tokens": 60,
            "future_endpoint_tokens": 4,
            "bootstrap_accepted_replicates": 2000,
        },
        "accounting": accounting,
        "private_roots_retained": 0,
        "runtime_probe_test_double": probe_manifest.get("test_double") is True,
        "relative_output_receipts": {
            name: base.sha256_bytes(value) for name, value in sorted(files.items())
        },
        "authority": dict(DENIED_AUTHORITY),
    }
    files["manifest.json"] = base.json_bytes(manifest)
    _require(
        set(files)
        == {
            "g1_synthetic_selection_summary.csv",
            "g1_synthetic_outer_cell_metrics.csv",
            "g1_synthetic_endpoint_metrics.csv",
            "g1_synthetic_bootstrap_summary.json",
            "g1_synthetic_runtime_probes.json",
            "g1_synthetic_result.json",
            "manifest.json",
        },
        "terminal file set differs",
    )
    return files


def relative_byte_map(root: Path) -> dict[str, str]:
    """Return the canonical relative-file SHA-256 map for one immutable root."""

    base._readonly_root(root, "G2-3B evidence root")
    return {
        path.relative_to(root).as_posix(): base.sha256_path(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


__all__ = [
    "G1SyntheticError",
    "compile_capabilities",
    "expected_outer_configuration",
    "freeze_future_configurations",
    "freeze_inner_predictions",
    "freeze_outer_predictions",
    "publish_fake_runtime_probes",
    "relative_byte_map",
    "run_inner_models",
    "run_outer_models",
    "run_runtime_probes",
    "score_outer_predictions",
    "select_inner_configurations",
    "terminal_files",
]
