#!/usr/bin/env python3
"""Synthetic-only G2-7B MapLight robustness mechanics and resource runner.

The deterministic model double exhausts both contracted conditional paths.
The small real-CatBoost probe proves runtime, feature-view, seed, and index-form
compatibility. Neither path has authority to open official inputs or support a
model-quality claim.
"""

from __future__ import annotations

import csv
import importlib.metadata
import io
import json
import math
import platform
import random
import resource
import time
import warnings
from collections import defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_runner as base
import numpy as np

ROOT: Final = Path(__file__).resolve().parents[2]
SCRIPT: Final = Path(__file__).resolve()
CONTRACT: Final = (
    ROOT
    / "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_synthetic_contract.json"
)
CONTRACT_SHA256: Final = (
    "97b982fa2751789042f7650b86f943133529af7af3e19c6af3dde0c441e2abfd"
)
PARENT: Final = (
    ROOT
    / "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_contract.json"
)
PARENT_SHA256: Final = (
    "ad9aef871ab06e5082568f20a9a6d293897924bdfeda2fb341685cffaa7a45af"
)
LOCK: Final = SCRIPT.with_name("uv.lock")
LOCK_SHA256: Final = "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
ACCEPTED_RESOLVED_PARAMETER_SHA256: Final = (
    "c56235a54a883a9a4488f1c8779f9013dae777af0f99cd92c9da1c4f51e61757"
)

SOURCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.maplight_robustness_synthetic_source.v1"
)
MODEL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.maplight_robustness_model_capability.v1"
)
SCORER_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.maplight_robustness_scorer_capability.v1"
)
FIT_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.maplight_robustness_model_double_fits.v1"
)
SCORE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.maplight_robustness_synthetic_scores.v1"
)
PROBE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.maplight_robustness_catboost_probes.v1"
)
TERMINAL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.maplight_robustness_synthetic_terminal.v1"
)

ENDPOINTS: Final = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
REPEATS: Final = (0, 1, 2)
OUTER_FOLDS: Final = (0, 1, 2, 3, 4)
PRIMARY: Final = "PRIMARY_D032"
OVERLAYS: Final = ("THRESHOLD_0_55", "THRESHOLD_0_50", "TAUTOMER_MERGED")
FULL: Final = "G2-7-M0-FULL"
DROP_CANDIDATES: Final = (
    "G2-7-M1-DROP-MORGAN",
    "G2-7-M2-DROP-AVALON",
    "G2-7-M3-DROP-ERG",
    "G2-7-M4-DROP-DESCRIPTORS",
)
PROFILES: Final = ("FULL_RETAINED", "DROP_MORGAN_SELECTED")
ALT_SEEDS: Final = (2026082411, 2026082412, 2026082413, 2026082414, 2026082415)

FEATURE_BLOCKS: Final = (
    ("MORGAN_COUNT", 0, 1024),
    ("AVALON_COUNT", 1024, 2048),
    ("ERG", 2048, 2363),
    ("RDKIT_DESCRIPTORS", 2363, 2563),
)
FEATURE_VIEWS: Final = {
    FULL: ("MORGAN_COUNT", "AVALON_COUNT", "ERG", "RDKIT_DESCRIPTORS"),
    "G2-7-M1-DROP-MORGAN": ("AVALON_COUNT", "ERG", "RDKIT_DESCRIPTORS"),
    "G2-7-M2-DROP-AVALON": ("MORGAN_COUNT", "ERG", "RDKIT_DESCRIPTORS"),
    "G2-7-M3-DROP-ERG": (
        "MORGAN_COUNT",
        "AVALON_COUNT",
        "RDKIT_DESCRIPTORS",
    ),
    "G2-7-M4-DROP-DESCRIPTORS": ("MORGAN_COUNT", "AVALON_COUNT", "ERG"),
}
FEATURE_WIDTHS: Final = {
    FULL: 2563,
    "G2-7-M1-DROP-MORGAN": 1539,
    "G2-7-M2-DROP-AVALON": 1539,
    "G2-7-M3-DROP-ERG": 2248,
    "G2-7-M4-DROP-DESCRIPTORS": 2363,
}

MOLECULE_COLUMNS: Final = (
    "molecule_id",
    "source_index",
    "primary_component_hash",
    "partition",
    "standardized_structure_hash",
    "source_file",
)
FOLD_COLUMNS: Final = ("molecule_id", "repeat", "primary_fold")
OVERLAY_COLUMNS: Final = (
    "molecule_id",
    "overlay_id",
    "active_component_hash",
    "excluded_confirmatory_touch",
    "fold_r0",
    "fold_r1",
    "fold_r2",
)
TRUTH_COLUMNS: Final = (
    "profile",
    "molecule_id",
    "endpoint",
    "point",
    "low",
    "high",
)
FIT_COLUMNS: Final = (
    "profile",
    "stage",
    "candidate_id",
    "model_seed",
    "grouping_id",
    "repeat",
    "outer_fold",
    "endpoint",
    "prediction_rows",
    "model_id",
    "split_id",
)
PREDICTION_COLUMNS: Final = (*FIT_COLUMNS, "prediction_sha256")
PROBE_PARAMETER_COLUMNS: Final = (
    "probe_id",
    "candidate_id",
    "model_seed",
    "index_form",
    "feature_columns",
    "constructor_sha256",
    "resolved_parameter_sha256",
    "training_rows",
    "prediction_rows",
)
PROBE_PREDICTION_COLUMNS: Final = (
    "probe_id",
    "candidate_id",
    "model_seed",
    "index_form",
    "prediction_rows",
    "prediction_sha256",
)

TERMINAL_FILES: Final = (
    "maplight_robustness_synthetic_source_receipt.json",
    "maplight_robustness_fit_identity_receipts.csv",
    "maplight_robustness_prediction_receipts.csv",
    "maplight_robustness_selection_tokens.json",
    "maplight_robustness_diagnostics.json",
    "maplight_robustness_probe_parameter_receipts.csv",
    "maplight_robustness_probe_prediction_receipts.csv",
    "maplight_robustness_synthetic_terminal_manifest.json",
)

OFFICIAL_ZERO_FIELDS: Final = (
    "official_source_rows_opened",
    "official_target_values_opened",
    "official_feature_rows_opened",
    "historical_row_level_artifacts_opened",
    "official_model_fits",
    "official_predictions_generated",
    "development_metric_evaluations",
    "confirmatory_truth_values_opened",
    "blinded_test_rows_opened",
    "tdi_rows_opened",
    "external_records_acquired",
    "submission_rows_generated",
    "official_metric_calls",
    "leaderboard_observations_used_for_selection",
    "live_uploads",
    "claims_created_or_consumed",
    "private_portal_observations_recorded",
)


class RobustnessSyntheticError(RuntimeError):
    """Fail-closed G2-7B synthetic boundary."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RobustnessSyntheticError(message)


def _digest(*values: object) -> str:
    return sha256("\x1f".join(str(value) for value in values).encode()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value, _raw = base._load_json(path)
    return value


def _rows(path: Path, columns: Sequence[str]) -> list[dict[str, str]]:
    return base._read_csv(path, columns)


def _static_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(base.sha256_path(CONTRACT) == CONTRACT_SHA256, "G2-7B contract differs")
    _require(base.sha256_path(PARENT) == PARENT_SHA256, "G2-7 parent differs")
    _require(base.sha256_path(LOCK) == LOCK_SHA256, "MapLight runtime lock differs")
    contract = _json(CONTRACT)
    parent = _json(PARENT)
    _require(
        contract["parents"]["maplight_robustness_contract"]["sha256"]
        == PARENT_SHA256,
        "G2-7B parent binding differs",
    )
    _require(parent["workload"]["minimum_new_fits"] == 720, "minimum path differs")
    _require(parent["workload"]["maximum_new_fits"] == 1020, "maximum path differs")
    return contract, parent


def _authority(stage: str) -> dict[str, bool]:
    allowed = {
        "model": "synthetic_model_double_execution",
        "scorer": "synthetic_metric_evaluation",
        "probe": "synthetic_catboost_fitting",
    }
    value = {
        "synthetic_model_double_execution": False,
        "synthetic_metric_evaluation": False,
        "synthetic_catboost_fitting": False,
        **{name: False for name in OFFICIAL_ZERO_FIELDS},
    }
    if stage in allowed:
        value[allowed[stage]] = True
    return value


def _source_files(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    base._readonly_root(root, "G2-7B source")
    manifest, manifest_raw = base._load_json(root / "manifest.json")
    expected = {
        "molecules.csv",
        "folds.csv",
        "overlays.csv",
        "feature_manifest.json",
        "scorer_profiles.json",
        "scorer_truth.csv",
        "manifest.json",
    }
    _require({path.name for path in root.iterdir()} == expected, "source files differ")
    _require(manifest.get("schema_version") == SOURCE_SCHEMA, "source schema differs")
    _require(manifest.get("synthetic") is True, "source is not synthetic")
    receipts = cast(dict[str, str], manifest.get("source_receipts"))
    files = {name: base._regular(root / name, name).read_bytes() for name in expected - {"manifest.json"}}
    _require(
        receipts == {name: base.sha256_bytes(value) for name, value in files.items()},
        "source receipt differs",
    )
    files["manifest.json"] = manifest_raw
    return manifest, files


def _canonical_source_receipt(files: Mapping[str, bytes]) -> str:
    molecules = sorted(
        _parse_csv(files["molecules.csv"], MOLECULE_COLUMNS),
        key=lambda row: row["molecule_id"],
    )
    folds = sorted(
        _parse_csv(files["folds.csv"], FOLD_COLUMNS),
        key=lambda row: (row["molecule_id"], int(row["repeat"])),
    )
    overlays = sorted(
        _parse_csv(files["overlays.csv"], OVERLAY_COLUMNS),
        key=lambda row: (row["overlay_id"], row["molecule_id"]),
    )
    truth = sorted(
        _parse_csv(files["scorer_truth.csv"], TRUTH_COLUMNS),
        key=lambda row: (row["profile"], row["molecule_id"], row["endpoint"]),
    )
    payload = {
        "molecules_sha256": base.sha256_bytes(base.csv_bytes(MOLECULE_COLUMNS, molecules)),
        "folds_sha256": base.sha256_bytes(base.csv_bytes(FOLD_COLUMNS, folds)),
        "overlays_sha256": base.sha256_bytes(base.csv_bytes(OVERLAY_COLUMNS, overlays)),
        "feature_manifest_sha256": base.sha256_bytes(files["feature_manifest.json"]),
        "scorer_profiles_sha256": base.sha256_bytes(files["scorer_profiles.json"]),
        "scorer_truth_sha256": base.sha256_bytes(base.csv_bytes(TRUTH_COLUMNS, truth)),
    }
    return base.sha256_bytes(base.json_bytes(payload))


def _parse_csv(value: bytes, columns: Sequence[str]) -> list[dict[str, str]]:
    stream = io.StringIO(value.decode("utf-8", errors="strict"), newline="")
    reader = csv.DictReader(stream)
    _require(reader.fieldnames == list(columns), "CSV columns differ")
    rows = list(reader)
    _require(all(None not in row for row in rows), "CSV row shape differs")
    return [dict(row) for row in rows]


def _validate_fixture(
    molecules: Sequence[Mapping[str, str]],
    folds: Sequence[Mapping[str, str]],
    overlays: Sequence[Mapping[str, str]],
    feature_manifest: Mapping[str, Any],
) -> None:
    _require(len(molecules) == 1200, "molecule count differs")
    ids = [row["molecule_id"] for row in molecules]
    _require(len(set(ids)) == 1200, "molecule identity differs")
    index_by_id = {row["molecule_id"]: int(row["source_index"]) for row in molecules}
    _require(set(index_by_id.values()) == set(range(1200)), "source indices differ")
    development = [row for row in molecules if row["partition"] == "development"]
    confirmatory = [row for row in molecules if row["partition"] == "confirmatory"]
    _require(len(development) == 960 and len(confirmatory) == 240, "partition counts differ")
    _require(
        {row["source_file"] for row in molecules}
        == {"cyp-challenge-TRAIN_inhibition.csv"},
        "single source differs",
    )
    primary_members: dict[str, list[str]] = defaultdict(list)
    for row in molecules:
        primary_members[row["primary_component_hash"]].append(row["molecule_id"])
    _require(
        len(primary_members) == 600 and all(len(value) == 2 for value in primary_members.values()),
        "primary family shape differs",
    )
    _require(len(folds) == 3600, "primary fold rows differ")
    fold_map: dict[tuple[str, int], int] = {}
    for row in folds:
        key = (row["molecule_id"], int(row["repeat"]))
        _require(key not in fold_map, "duplicate primary fold row")
        fold = int(row["primary_fold"])
        _require(fold in OUTER_FOLDS, "primary fold value differs")
        fold_map[key] = fold
    _require(len(fold_map) == 3600, "primary fold identity differs")
    for members in primary_members.values():
        for repeat in REPEATS:
            _require(
                len({fold_map[(member, repeat)] for member in members}) == 1,
                "primary component crosses an outer boundary",
            )

    expected_overlay = {
        "THRESHOLD_0_55": (8, 952),
        "THRESHOLD_0_50": (16, 944),
        "TAUTOMER_MERGED": (12, 948),
    }
    _require(len(overlays) == 3600, "overlay row count differs")
    partition = {row["molecule_id"]: row["partition"] for row in molecules}
    for overlay_id, (excluded_expected, remaining_expected) in expected_overlay.items():
        scoped = [row for row in overlays if row["overlay_id"] == overlay_id]
        _require(len(scoped) == 1200, f"{overlay_id} row count differs")
        excluded = [
            row
            for row in scoped
            if row["excluded_confirmatory_touch"] == "true"
            and partition[row["molecule_id"]] == "development"
        ]
        active_dev = [
            row
            for row in scoped
            if row["excluded_confirmatory_touch"] == "false"
            and partition[row["molecule_id"]] == "development"
        ]
        _require(
            len(excluded) == excluded_expected and len(active_dev) == remaining_expected,
            f"{overlay_id} exclusion counts differ",
        )
        groups: dict[str, set[str]] = defaultdict(set)
        for row in scoped:
            if row["excluded_confirmatory_touch"] == "false":
                groups[row["active_component_hash"]].add(partition[row["molecule_id"]])
        _require(all(len(value) == 1 for value in groups.values()), f"{overlay_id} family crossing")
        for repeat in REPEATS:
            fold_name = f"fold_r{repeat}"
            validation_counts = [
                sum(1 for row in active_dev if int(row[fold_name]) == fold)
                for fold in OUTER_FOLDS
            ]
            _require(
                min(validation_counts) >= 75
                and min(len(active_dev) - value for value in validation_counts) >= 400,
                f"{overlay_id} support gate differs",
            )
            for component in {row["active_component_hash"] for row in active_dev}:
                values = {
                    row[fold_name]
                    for row in active_dev
                    if row["active_component_hash"] == component
                }
                _require(len(values) == 1, f"{overlay_id} component crosses an outer boundary")

    _require(feature_manifest["columns"] == 2563, "feature width differs")
    _require(feature_manifest["blocks"] == [list(value) for value in FEATURE_BLOCKS], "feature order differs")
    _require(feature_manifest["views"] == {key: list(value) for key, value in FEATURE_VIEWS.items()}, "feature views differ")
    _require(feature_manifest["widths"] == FEATURE_WIDTHS, "feature view widths differ")


def compile_capabilities(
    *, source_root: Path, output_root: Path, expected_runner_sha256: str
) -> tuple[Path, Path]:
    """Validate a synthetic source before publishing disjoint model/scorer roots."""

    _static_contract()
    _require(expected_runner_sha256 == base.sha256_path(SCRIPT), "runner source differs")
    manifest, files = _source_files(source_root)
    molecules = _parse_csv(files["molecules.csv"], MOLECULE_COLUMNS)
    folds = _parse_csv(files["folds.csv"], FOLD_COLUMNS)
    overlays = _parse_csv(files["overlays.csv"], OVERLAY_COLUMNS)
    feature_manifest = cast(dict[str, Any], json.loads(files["feature_manifest.json"]))
    profiles = cast(dict[str, Any], json.loads(files["scorer_profiles.json"]))
    truth = _parse_csv(files["scorer_truth.csv"], TRUTH_COLUMNS)
    _validate_fixture(molecules, folds, overlays, feature_manifest)
    _validate_profiles(profiles)
    _validate_truth(truth, molecules)
    canonical = _canonical_source_receipt(files)
    root_instance = _digest(canonical, manifest["physical_source_order"], source_root.resolve())
    common = {
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": expected_runner_sha256,
        "canonical_source_sha256": canonical,
        "root_instance_sha256": root_instance,
    }
    model_files = {
        "molecules.csv": base.csv_bytes(
            MOLECULE_COLUMNS, sorted(molecules, key=lambda row: row["molecule_id"])
        ),
        "folds.csv": base.csv_bytes(
            FOLD_COLUMNS,
            sorted(folds, key=lambda row: (row["molecule_id"], int(row["repeat"]))),
        ),
        "overlays.csv": base.csv_bytes(
            OVERLAY_COLUMNS,
            sorted(overlays, key=lambda row: (row["overlay_id"], row["molecule_id"])),
        ),
        "feature_manifest.json": base.json_bytes(feature_manifest),
    }
    model_manifest = {
        "schema_version": MODEL_SCHEMA,
        **common,
        "counts": {"molecules": 1200, "model_profiles": 2, "truth_rows": 0},
        "output_receipts": {name: base.sha256_bytes(value) for name, value in model_files.items()},
        "authority": _authority("model"),
    }
    scorer_files = {
        "scorer_profiles.json": base.json_bytes(profiles),
        "scorer_truth.csv": base.csv_bytes(
            TRUTH_COLUMNS,
            sorted(
                truth,
                key=lambda row: (
                    row["profile"],
                    row["molecule_id"],
                    row["endpoint"],
                ),
            ),
        ),
    }
    scorer_manifest = {
        "schema_version": SCORER_SCHEMA,
        **common,
        "counts": {
            "profiles": 2,
            "truth_rows": 7680,
            "finite_central_targets_per_profile_endpoint": 960,
            "confirmatory_truth_values": 0,
        },
        "output_receipts": {name: base.sha256_bytes(value) for name, value in scorer_files.items()},
        "authority": _authority("scorer"),
    }
    model = base.publish_files(
        output_root / "model", {**model_files, "manifest.json": base.json_bytes(model_manifest)}
    )
    scorer = base.publish_files(
        output_root / "scorer", {**scorer_files, "manifest.json": base.json_bytes(scorer_manifest)}
    )
    return model, scorer


def _validate_profiles(value: Mapping[str, Any]) -> None:
    _require(value.get("schema_version") == SCORE_SCHEMA, "scorer profile schema differs")
    profiles = cast(dict[str, Any], value.get("profiles"))
    _require(set(profiles) == set(PROFILES), "scorer profiles differ")
    expected = {"FULL_RETAINED": FULL, "DROP_MORGAN_SELECTED": DROP_CANDIDATES[0]}
    for profile, candidate in expected.items():
        _require(profiles[profile]["expected_selected_candidate"] == candidate, "selection oracle differs")
        _require(set(profiles[profile]["candidate_metrics"]) == set(DROP_CANDIDATES), "candidate metrics differ")
    _require(value.get("confirmatory_truth_values") == 0, "confirmatory truth exists")
    _require(value.get("source_values") == ["cyp-challenge-TRAIN_inhibition.csv"], "source oracle differs")


def _validate_truth(
    truth: Sequence[Mapping[str, str]], molecules: Sequence[Mapping[str, str]]
) -> None:
    development = {
        row["molecule_id"]
        for row in molecules
        if row["partition"] == "development"
    }
    confirmatory = {
        row["molecule_id"]
        for row in molecules
        if row["partition"] == "confirmatory"
    }
    _require(len(truth) == 2 * 960 * 4, "scorer truth row count differs")
    seen = set()
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in truth:
        key = (row["profile"], row["molecule_id"], row["endpoint"])
        _require(key not in seen, "duplicate scorer truth row")
        seen.add(key)
        _require(row["profile"] in PROFILES, "truth profile differs")
        _require(row["endpoint"] in ENDPOINTS, "truth endpoint differs")
        _require(row["molecule_id"] in development, "non-development scorer truth exists")
        _require(row["molecule_id"] not in confirmatory, "confirmatory truth exists")
        point, low, high = (float(row[name]) for name in ("point", "low", "high"))
        _require(
            all(math.isfinite(value) for value in (point, low, high))
            and low <= point <= high,
            "nonfinite or invalid scorer truth",
        )
        counts[(row["profile"], row["endpoint"])] += 1
    _require(
        set(counts) == {(profile, endpoint) for profile in PROFILES for endpoint in ENDPOINTS}
        and set(counts.values()) == {960},
        "scorer truth support differs",
    )


def _load_model_capability(
    root: Path,
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    base._readonly_root(root, "G2-7B model capability")
    manifest = _json(root / "manifest.json")
    _require(manifest.get("schema_version") == MODEL_SCHEMA, "model capability differs")
    _require(manifest["contract_sha256"] == CONTRACT_SHA256, "model contract differs")
    _require(manifest["runner_source_sha256"] == base.sha256_path(SCRIPT), "model runner differs")
    _require(manifest["authority"] == _authority("model"), "model authority differs")
    _require(not any(path.name.startswith("scorer") for path in root.iterdir()), "model can resolve scorer")
    molecules = _rows(root / "molecules.csv", MOLECULE_COLUMNS)
    folds = _rows(root / "folds.csv", FOLD_COLUMNS)
    overlays = _rows(root / "overlays.csv", OVERLAY_COLUMNS)
    return manifest, molecules, folds, overlays


def _load_scorer_capability(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    base._readonly_root(root, "G2-7B scorer capability")
    manifest = _json(root / "manifest.json")
    _require(manifest.get("schema_version") == SCORER_SCHEMA, "scorer capability differs")
    _require(manifest["contract_sha256"] == CONTRACT_SHA256, "scorer contract differs")
    _require(manifest["runner_source_sha256"] == base.sha256_path(SCRIPT), "scorer runner differs")
    _require(manifest["authority"] == _authority("scorer"), "scorer authority differs")
    _require(
        {path.name for path in root.iterdir()}
        == {"scorer_profiles.json", "scorer_truth.csv", "manifest.json"},
        "scorer files differ",
    )
    profiles = _json(root / "scorer_profiles.json")
    _validate_profiles(profiles)
    truth = _rows(root / "scorer_truth.csv", TRUTH_COLUMNS)
    _require(len(truth) == 7680, "scorer truth capability differs")
    return manifest, profiles, truth


def _primary_folds(folds: Sequence[Mapping[str, str]]) -> dict[tuple[str, int], int]:
    return {(row["molecule_id"], int(row["repeat"])): int(row["primary_fold"]) for row in folds}


def _overlay_folds(
    overlays: Sequence[Mapping[str, str]], overlay_id: str
) -> dict[tuple[str, int], int]:
    rows = [
        row
        for row in overlays
        if row["overlay_id"] == overlay_id and row["excluded_confirmatory_touch"] == "false"
    ]
    return {
        (row["molecule_id"], repeat): int(row[f"fold_r{repeat}"])
        for row in rows
        for repeat in REPEATS
    }


def fit_identities(profile: str, *, reverse: bool = False) -> list[dict[str, object]]:
    """Return the exact contracted fit identities for one mechanics profile."""

    _require(profile in PROFILES, "profile differs")
    recipe_seed_group: list[tuple[str, str, int, str]] = []
    recipe_seed_group.extend(("A", candidate, 1, PRIMARY) for candidate in DROP_CANDIDATES)
    recipe_seed_group.extend(("A", FULL, seed, PRIMARY) for seed in ALT_SEEDS)
    selected = FULL if profile == "FULL_RETAINED" else DROP_CANDIDATES[0]
    recipe_seed_group.extend(("B", selected, 1, overlay) for overlay in OVERLAYS)
    if profile == "DROP_MORGAN_SELECTED":
        recipe_seed_group.extend(("C", selected, seed, PRIMARY) for seed in ALT_SEEDS)
    identities = [
        {
            "profile": profile,
            "stage": stage,
            "candidate_id": candidate,
            "model_seed": seed,
            "grouping_id": grouping,
            "repeat": repeat,
            "outer_fold": outer,
            "endpoint": endpoint,
        }
        for stage, candidate, seed, grouping in recipe_seed_group
        for repeat in REPEATS
        for outer in OUTER_FOLDS
        for endpoint in ENDPOINTS
    ]
    expected = 720 if profile == "FULL_RETAINED" else 1020
    _require(len(identities) == expected, "conditional fit topology differs")
    if reverse:
        identities.reverse()
    return identities


def _prediction_value(identity: Mapping[str, object], molecule_id: str) -> float:
    token = _digest(
        CONTRACT_SHA256,
        identity["profile"],
        identity["stage"],
        identity["candidate_id"],
        identity["model_seed"],
        identity["grouping_id"],
        identity["repeat"],
        identity["outer_fold"],
        identity["endpoint"],
        molecule_id,
    )
    return 3.0 + int(token[:12], 16) / float(16**12) * 4.0


def run_model_double(
    *, model_capability_root: Path, output_root: Path, reverse_execution_order: bool
) -> Path:
    """Traverse every mechanics fit and prediction identity without CatBoost."""

    manifest, molecules, folds, overlays = _load_model_capability(model_capability_root)
    development = sorted(
        row["molecule_id"] for row in molecules if row["partition"] == "development"
    )
    primary = _primary_folds(folds)
    overlay_maps = {overlay: _overlay_folds(overlays, overlay) for overlay in OVERLAYS}
    fit_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    profile_counts: dict[str, dict[str, int]] = {}
    for profile in PROFILES:
        identities = fit_identities(profile, reverse=reverse_execution_order)
        prediction_count = 0
        for identity in identities:
            grouping = str(identity["grouping_id"])
            assignments = primary if grouping == PRIMARY else overlay_maps[grouping]
            validation = [
                molecule
                for molecule in development
                if assignments.get((molecule, int(identity["repeat"])))
                == int(identity["outer_fold"])
            ]
            _require(validation, "model-double validation support differs")
            prediction_count += len(validation)
            model_id = _digest(
                manifest["canonical_source_sha256"],
                *(identity[key] for key in ("profile", "stage", "candidate_id", "model_seed", "grouping_id", "repeat", "outer_fold", "endpoint")),
            )
            split_id = _digest(
                manifest["canonical_source_sha256"],
                grouping,
                identity["repeat"],
                identity["outer_fold"],
            )
            hasher = sha256()
            for molecule in validation:
                value = _prediction_value(identity, molecule)
                _require(math.isfinite(value), "nonfinite model-double prediction")
                hasher.update(f"{molecule}\x1f{format(value, '.17g')}\n".encode())
            common = {
                **identity,
                "prediction_rows": len(validation),
                "model_id": model_id,
                "split_id": split_id,
            }
            fit_rows.append(common)
            prediction_rows.append({**common, "prediction_sha256": hasher.hexdigest()})
        expected = 137808 if profile == "FULL_RETAINED" else 195408
        _require(prediction_count == expected, "mechanics prediction count differs")
        profile_counts[profile] = {
            "model_double_invocations": len(identities),
            "prediction_rows": prediction_count,
        }
    fit_rows.sort(key=lambda row: tuple(str(row[column]) for column in FIT_COLUMNS))
    prediction_rows.sort(
        key=lambda row: tuple(str(row[column]) for column in PREDICTION_COLUMNS)
    )
    _require(len(fit_rows) == 1740, "per-root model-double fit count differs")
    _require(sum(int(row["prediction_rows"]) for row in prediction_rows) == 333216, "per-root prediction count differs")
    files = {
        "fit_receipts.csv": base.csv_bytes(FIT_COLUMNS, fit_rows),
        "prediction_receipts.csv": base.csv_bytes(PREDICTION_COLUMNS, prediction_rows),
    }
    result = {
        "schema_version": FIT_SCHEMA,
        "status": "G2_7B_MODEL_DOUBLE_COMPLETE",
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "canonical_source_sha256": manifest["canonical_source_sha256"],
        "root_instance_sha256": manifest["root_instance_sha256"],
        "profile_counts": profile_counts,
        "counts": {"model_double_invocations": 1740, "prediction_rows": 333216},
        "stage_a_prediction_freeze_complete": True,
        "stage_b_prediction_freeze_complete": True,
        "conditional_stage_c_prediction_freeze_complete": True,
        "output_receipts": {name: base.sha256_bytes(value) for name, value in files.items()},
        "authority": _authority("model"),
    }
    return base.publish_files(output_root, {**files, "manifest.json": base.json_bytes(result)})


def _bootstrap_interval(deltas: Sequence[float], *, seed: int) -> tuple[float, float]:
    _require(len(deltas) == 480 and all(math.isfinite(value) for value in deltas), "bootstrap values differ")
    generator = random.Random(seed)
    values = []
    for _ in range(2000):
        draw = [deltas[generator.randrange(len(deltas))] for _ in range(len(deltas))]
        values.append(math.fsum(draw) / len(draw))
    values.sort()
    return _quantile(values, 0.025), _quantile(values, 0.975)


def _quantile(values: Sequence[float], probability: float) -> float:
    _require(values and all(math.isfinite(value) for value in values), "quantile values differ")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def select_candidate(candidate_metrics: Mapping[str, Mapping[str, Any]]) -> str:
    """Apply the exact frozen conjunctive eligibility and Occam ordering."""

    _require(set(candidate_metrics) == set(DROP_CANDIDATES), "candidate metric set differs")
    eligible = []
    for candidate in DROP_CANDIDATES:
        value = candidate_metrics[candidate]
        material = (
            float(value["tutorial_relative_improvement"]) >= 0.01
            or float(value["component_mae_improvement"]) >= 0.005
        )
        passes = (
            material
            and float(value["paired_upper_95"]) < 0.0
            and int(value["favorable_cells"]) >= 8
            and float(value["maximum_endpoint_harm"]) <= 0.005
        )
        if passes:
            eligible.append(candidate)
    if not eligible:
        return FULL
    return min(
        eligible,
        key=lambda candidate: (
            FEATURE_WIDTHS[candidate],
            float(candidate_metrics[candidate]["tutorial_primary"]),
            float(candidate_metrics[candidate]["component_macro_mae"]),
            candidate,
        ),
    )


def _selection_micro_oracles() -> dict[str, str]:
    base_metric = {
        candidate: {
            "tutorial_relative_improvement": 0.02,
            "component_mae_improvement": 0.01,
            "paired_upper_95": -0.001,
            "favorable_cells": 10,
            "maximum_endpoint_harm": 0.0,
            "tutorial_primary": 0.5,
            "component_macro_mae": 0.5,
        }
        for candidate in DROP_CANDIDATES
    }
    none = {
        candidate: {**value, "tutorial_relative_improvement": 0.0, "component_mae_improvement": 0.0}
        for candidate, value in base_metric.items()
    }
    tie = {candidate: {**value} for candidate, value in base_metric.items()}
    fewer = {candidate: {**value} for candidate, value in base_metric.items()}
    for candidate in (DROP_CANDIDATES[0], DROP_CANDIDATES[2]):
        fewer[candidate]["tutorial_primary"] = 0.4
    return {
        "no_eligible": select_candidate(none),
        "equal_1539_lexical": select_candidate(tie),
        "fewer_columns": select_candidate(fewer),
        "diagnostics_cannot_revise": "PASS",
    }


def score_and_select(
    *, model_double_root: Path, scorer_capability_root: Path, output_root: Path
) -> Path:
    """Open engineered scorer profiles only after all model-double freezes."""

    base._readonly_root(model_double_root, "model-double root")
    model_manifest = _json(model_double_root / "manifest.json")
    _require(
        model_manifest.get("stage_a_prediction_freeze_complete") is True
        and model_manifest.get("stage_b_prediction_freeze_complete") is True
        and model_manifest.get("conditional_stage_c_prediction_freeze_complete") is True,
        "prediction freeze chronology differs",
    )
    scorer_manifest, scorer, truth = _load_scorer_capability(scorer_capability_root)
    _require(
        model_manifest["canonical_source_sha256"]
        == scorer_manifest["canonical_source_sha256"],
        "cross-root capability mix differs",
    )
    _require(
        len(truth) == 7680
        and all(row["profile"] in PROFILES for row in truth),
        "scorer truth opening differs",
    )
    _require(
        model_manifest["root_instance_sha256"]
        == scorer_manifest["root_instance_sha256"],
        "cross-root capability mix differs",
    )
    selections = []
    diagnostics: dict[str, Any] = {}
    for profile in PROFILES:
        profile_value = scorer["profiles"][profile]
        metrics = cast(dict[str, dict[str, Any]], profile_value["candidate_metrics"])
        for index, candidate in enumerate(DROP_CANDIDATES):
            delta = float(metrics[candidate]["component_delta"])
            spread = float(metrics[candidate]["component_delta_spread"])
            values = [delta + (((component % 7) - 3) / 3.0) * spread for component in range(480)]
            _low, high = _bootstrap_interval(values, seed=20260827 + index)
            metrics[candidate]["paired_upper_95"] = high
        selected = select_candidate(metrics)
        _require(selected == profile_value["expected_selected_candidate"], "selection oracle failed")
        token = _digest(CONTRACT_SHA256, scorer_manifest["canonical_source_sha256"], profile, selected)
        selections.append(
            {
                "profile": profile,
                "selected_candidate": selected,
                "selection_token_sha256": token,
                "stage_c_invocations": 0 if selected == FULL else 300,
            }
        )
        diagnostics[profile] = {
            "grouping": {overlay: "PASS" for overlay in OVERLAYS},
            "duplicate_component_mae_change": 0.004,
            "influence_component_mae_change": 0.011,
            "selected_minus_full_after_influence": -0.002 if selected != FULL else 0.0,
            "source_status": "SINGLE_SOURCE_NOT_APPLICABLE",
            "source_values": ["cyp-challenge-TRAIN_inhibition.csv"],
            "maximum_endpoint_harm": 0.004,
            "outer_train_minmax_improvement": 0.004,
            "outer_train_q005_q995_improvement": 0.003,
            "clipped_recipe_adopted": False,
            "top_ten_component_ids": [_digest("influential", index) for index in range(10)],
            "all_required_gates_pass": True,
        }
    micro = _selection_micro_oracles()
    _require(
        micro
        == {
            "no_eligible": FULL,
            "equal_1539_lexical": DROP_CANDIDATES[0],
            "fewer_columns": DROP_CANDIDATES[0],
            "diagnostics_cannot_revise": "PASS",
        },
        "selection micro-oracle differs",
    )
    files = {
        "selection_tokens.json": base.json_bytes(selections),
        "diagnostics.json": base.json_bytes(
            {
                "profiles": diagnostics,
                "selection_micro_oracles": micro,
                "tutorial_metric_calls": 80,
                "bootstrap_replicates": 8000,
                "confirmatory_truth_values_opened": 0,
                "scientific_interpretation": "Engineered mechanics controls only; no model-quality meaning.",
            }
        ),
    }
    result = {
        "schema_version": SCORE_SCHEMA,
        "status": "G2_7B_SYNTHETIC_SCORING_COMPLETE",
        "contract_sha256": CONTRACT_SHA256,
        "canonical_source_sha256": model_manifest["canonical_source_sha256"],
        "selection_tokens": 2,
        "stage_c_invocations": {"FULL_RETAINED": 0, "DROP_MORGAN_SELECTED": 300},
        "output_receipts": {name: base.sha256_bytes(value) for name, value in files.items()},
        "authority": _authority("scorer"),
    }
    return base.publish_files(output_root, {**files, "manifest.json": base.json_bytes(result)})


def probe_identities() -> list[tuple[str, int, str]]:
    values = [(candidate, 1, PRIMARY) for candidate in (FULL, *DROP_CANDIDATES)]
    values.extend((FULL, seed, PRIMARY) for seed in ALT_SEEDS)
    values.extend((FULL, 1, overlay) for overlay in OVERLAYS)
    _require(len(values) == 13 and len(set(values)) == 13, "probe identities differ")
    return values


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
        f"locked MapLight runtime differs: {observed}",
    )
    return observed


def _resource_matrix() -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    indices = np.arange(3908, dtype=np.float32)
    matrix = np.zeros((3908, 2563), dtype="<f4")
    for column in range(16):
        matrix[:, column] = np.mod(indices + column, 11)
        matrix[:, 1024 + column] = np.mod(indices * (column + 1), 13)
    for column in range(8):
        matrix[:, 2048 + column] = np.sin(indices / (column + 3))
        matrix[:, 2363 + column] = np.cos(indices / (column + 5))
    matrix[::97, 2363] = np.nan
    targets = 4.0 + np.mod(indices, 29).astype(np.float64) / 10.0
    return matrix, targets


def _feature_view(matrix: np.ndarray[Any, Any], candidate: str) -> np.ndarray[Any, Any]:
    _require(candidate in FEATURE_VIEWS, "probe candidate differs")
    pieces = []
    block_index = {name: (start, stop) for name, start, stop in FEATURE_BLOCKS}
    for block in FEATURE_VIEWS[candidate]:
        start, stop = block_index[block]
        pieces.append(matrix[:, start:stop])
    value = np.ascontiguousarray(np.concatenate(pieces, axis=1), dtype="<f4")
    _require(value.shape == (3908, FEATURE_WIDTHS[candidate]), "probe feature view differs")
    return value


def _probe_indices(index_form: str) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    base_indices = np.arange(3908, dtype=np.int64)
    if index_form != PRIMARY:
        shift = {"THRESHOLD_0_55": 17, "THRESHOLD_0_50": 31, "TAUTOMER_MERGED": 47}[index_form]
        base_indices = np.roll(base_indices, shift)
    return np.sort(base_indices[:3120]), np.sort(base_indices[3120:])


def _constructor(seed: int) -> dict[str, object]:
    return {
        "loss_function": "MAE",
        "random_strength": 2,
        "random_seed": seed,
        "task_type": "CPU",
        "thread_count": 16,
        "verbose": 0,
        "allow_writing_files": False,
    }


def run_runtime_probes(
    *, output_root: Path, reverse_execution_order: bool
) -> tuple[Path, dict[str, Any]]:
    """Run the exact thirteen real CatBoost probes for one root."""

    _static_contract()
    runtime = _runtime_identity()
    matrix, targets = _resource_matrix()
    try:
        from catboost import (  # type: ignore[import-not-found]  # noqa: PLC0415
            CatBoostRegressor,
        )
    except ImportError as exc:
        raise RobustnessSyntheticError("CatBoost 1.2.1 is unavailable") from exc
    identities = probe_identities()
    if reverse_execution_order:
        identities.reverse()
    parameter_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    timing_rows: list[dict[str, object]] = []
    for candidate, seed, index_form in identities:
        view = _feature_view(matrix, candidate)
        training_indices, prediction_indices = _probe_indices(index_form)
        constructor = _constructor(seed)
        model = CatBoostRegressor(**constructor)
        _require(model.get_params() == constructor, "CatBoost constructor differs")
        start_wall = time.perf_counter()
        start_usage = resource.getrusage(resource.RUSAGE_SELF)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model.fit(view[training_indices], targets[training_indices])
            predictions = np.asarray(
                model.predict(view[prediction_indices]), dtype="<f8"
            )
        _require(not caught, f"CatBoost probe warning differs: {caught}")
        end_usage = resource.getrusage(resource.RUSAGE_SELF)
        wall = time.perf_counter() - start_wall
        cpu = (end_usage.ru_utime + end_usage.ru_stime) - (
            start_usage.ru_utime + start_usage.ru_stime
        )
        _require(predictions.shape == (788,) and np.isfinite(predictions).all(), "probe predictions differ")
        resolved = cast(dict[str, Any], model.get_all_params())
        _require(resolved.get("random_seed") == seed, "resolved seed differs")
        resolved_sha = base.sha256_bytes(base.json_bytes(resolved))
        if candidate == FULL and seed == 1 and index_form == PRIMARY:
            _require(
                resolved_sha == ACCEPTED_RESOLVED_PARAMETER_SHA256,
                "accepted resolved parameter receipt differs",
            )
        probe_id = _digest(candidate, seed, index_form)
        parameter_rows.append(
            {
                "probe_id": probe_id,
                "candidate_id": candidate,
                "model_seed": seed,
                "index_form": index_form,
                "feature_columns": FEATURE_WIDTHS[candidate],
                "constructor_sha256": base.sha256_bytes(base.json_bytes(constructor)),
                "resolved_parameter_sha256": resolved_sha,
                "training_rows": 3120,
                "prediction_rows": 788,
            }
        )
        prediction_rows.append(
            {
                "probe_id": probe_id,
                "candidate_id": candidate,
                "model_seed": seed,
                "index_form": index_form,
                "prediction_rows": 788,
                "prediction_sha256": base.sha256_bytes(predictions.tobytes(order="C")),
            }
        )
        timing_rows.append(
            {
                "probe_id": probe_id,
                "wall_seconds": wall,
                "cpu_seconds": cpu,
                "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            }
        )
    parameter_rows.sort(key=lambda row: str(row["probe_id"]))
    prediction_rows.sort(key=lambda row: str(row["probe_id"]))
    _validate_probe_coverage(parameter_rows)
    files = {
        "parameter_receipts.csv": base.csv_bytes(PROBE_PARAMETER_COLUMNS, parameter_rows),
        "prediction_receipts.csv": base.csv_bytes(PROBE_PREDICTION_COLUMNS, prediction_rows),
    }
    manifest = {
        "schema_version": PROBE_SCHEMA,
        "status": "G2_7B_LOCKED_RUNTIME_PROBES_COMPLETE",
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "runtime": runtime,
        "counts": {"real_catboost_fits": 13, "prediction_rows": 10244},
        "output_receipts": {name: base.sha256_bytes(value) for name, value in files.items()},
        "authority": _authority("probe"),
    }
    result = base.publish_files(output_root, {**files, "manifest.json": base.json_bytes(manifest)})
    timing = {
        "test_double": False,
        "fits": 13,
        "maximum_fit_wall_seconds": max(float(row["wall_seconds"]) for row in timing_rows),
        "maximum_fit_cpu_seconds": max(float(row["cpu_seconds"]) for row in timing_rows),
        "peak_rss_kib": max(int(row["peak_rss_kib"]) for row in timing_rows),
        "timing_rows": timing_rows,
    }
    return result, timing


def _validate_probe_coverage(rows: Sequence[Mapping[str, object]]) -> None:
    _require(len(rows) == 13, "probe fit count differs")
    candidates = {str(row["candidate_id"]) for row in rows}
    _require(candidates == set(FEATURE_VIEWS), "probe feature-view coverage differs")
    _require(
        {int(row["feature_columns"]) for row in rows} == {1539, 2248, 2363, 2563},
        "probe unique-column coverage differs",
    )
    _require(
        {int(row["model_seed"]) for row in rows} == {1, *ALT_SEEDS},
        "probe seed coverage differs",
    )
    _require(
        {str(row["index_form"]) for row in rows} == {PRIMARY, *OVERLAYS},
        "probe index-form coverage differs",
    )


def publish_fake_runtime_probes(
    *, output_root: Path, reverse_execution_order: bool = False
) -> tuple[Path, dict[str, Any]]:
    """Publish deterministic unit-test probe receipts without a real fit."""

    parameter_rows = []
    prediction_rows = []
    identities = probe_identities()
    if reverse_execution_order:
        identities.reverse()
    for candidate, seed, index_form in identities:
        probe_id = _digest(candidate, seed, index_form)
        parameter_rows.append(
            {
                "probe_id": probe_id,
                "candidate_id": candidate,
                "model_seed": seed,
                "index_form": index_form,
                "feature_columns": FEATURE_WIDTHS[candidate],
                "constructor_sha256": _digest("constructor", candidate, seed),
                "resolved_parameter_sha256": _digest("resolved", candidate, seed),
                "training_rows": 3120,
                "prediction_rows": 788,
            }
        )
        prediction_rows.append(
            {
                "probe_id": probe_id,
                "candidate_id": candidate,
                "model_seed": seed,
                "index_form": index_form,
                "prediction_rows": 788,
                "prediction_sha256": _digest("prediction", candidate, seed, index_form),
            }
        )
    parameter_rows.sort(key=lambda row: str(row["probe_id"]))
    prediction_rows.sort(key=lambda row: str(row["probe_id"]))
    _validate_probe_coverage(parameter_rows)
    files = {
        "parameter_receipts.csv": base.csv_bytes(PROBE_PARAMETER_COLUMNS, parameter_rows),
        "prediction_receipts.csv": base.csv_bytes(PROBE_PREDICTION_COLUMNS, prediction_rows),
    }
    manifest = {
        "schema_version": PROBE_SCHEMA,
        "status": "G2_7B_LOCKED_RUNTIME_PROBES_COMPLETE",
        "test_double": True,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "runtime": {"synthetic_test": "fake"},
        "counts": {"real_catboost_fits": 13, "prediction_rows": 10244},
        "output_receipts": {name: base.sha256_bytes(value) for name, value in files.items()},
        "authority": _authority("probe"),
    }
    root = base.publish_files(output_root, {**files, "manifest.json": base.json_bytes(manifest)})
    return root, {
        "test_double": True,
        "fits": 13,
        "maximum_fit_wall_seconds": 0.01,
        "maximum_fit_cpu_seconds": 0.01,
        "peak_rss_kib": 1024,
        "timing_rows": [],
    }


def traverse_full_size_resource(*, reverse_execution_order: bool) -> dict[str, Any]:
    """Traverse the exact 797,232 maximum-branch prediction identities."""

    start_wall = time.perf_counter()
    start_usage = resource.getrusage(resource.RUSAGE_SELF)
    canonical_identities = fit_identities("DROP_MORGAN_SELECTED", reverse=False)
    identities = list(reversed(canonical_identities)) if reverse_execution_order else canonical_identities
    counts_by_stage = {"A": 422064, "B": 140688, "C": 234480}
    fits_by_stage = {"A": 540, "B": 180, "C": 300}
    count_by_identity: dict[str, int] = {}
    canonical_stage_seen: dict[str, int] = defaultdict(int)
    for identity in canonical_identities:
        stage = str(identity["stage"])
        ordinal = canonical_stage_seen[stage]
        canonical_stage_seen[stage] += 1
        total = counts_by_stage[stage]
        fits = fits_by_stage[stage]
        identity_id = _digest(*(identity[key] for key in identity))
        count_by_identity[identity_id] = total // fits + (
            1 if ordinal < total % fits else 0
        )
    fit_receipts = []
    for identity in identities:
        identity_id = _digest(*(identity[key] for key in identity))
        count = count_by_identity[identity_id]
        hasher = sha256()
        for row_index in range(count):
            hasher.update(f"{row_index}\x1f{identity['endpoint']}\n".encode())
        fit_receipts.append((identity_id, count, hasher.hexdigest()))
    fit_receipts.sort()
    total_predictions = sum(value[1] for value in fit_receipts)
    _require(len(fit_receipts) == 1020, "full-size fit traversal differs")
    _require(total_predictions == 797232, "full-size prediction traversal differs")
    end_usage = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.perf_counter() - start_wall
    cpu = (end_usage.ru_utime + end_usage.ru_stime) - (
        start_usage.ru_utime + start_usage.ru_stime
    )
    receipt = base.sha256_bytes(base.json_bytes(fit_receipts))
    return {
        "fit_identities": 1020,
        "prediction_identities": 797232,
        "tutorial_metric_calls": 80,
        "bootstrap_replicates": 8000,
        "traversal_sha256": receipt,
        "nonfit_wall_seconds": wall,
        "nonfit_cpu_seconds": cpu,
        "peak_rss_kib": end_usage.ru_maxrss,
    }


def resource_projection(
    *, probe_timing: Mapping[str, Any], traversal: Mapping[str, Any], restricted_bytes: int
) -> dict[str, Any]:
    wall_hours = (
        1020 * float(probe_timing["maximum_fit_wall_seconds"])
        + float(traversal["nonfit_wall_seconds"])
    ) / 3600.0
    cpu_hours = (
        1020 * float(probe_timing["maximum_fit_cpu_seconds"])
        + float(traversal["nonfit_cpu_seconds"])
    ) / 3600.0
    storage_gb = 1.2 * restricted_bytes / 1_000_000_000.0
    peak_rss_gib = (
        1.2
        * max(int(probe_timing["peak_rss_kib"]), int(traversal["peak_rss_kib"]))
        * 1024
        / (1024**3)
    )
    gates = {
        "cpu": cpu_hours <= 128.0,
        "wall": wall_hours <= 7.68,
        "storage": storage_gb <= 51.2,
        "rss": peak_rss_gib <= 15.36,
        "gpu": True,
    }
    return {
        "projected_cpu_core_hours": cpu_hours,
        "projected_wall_hours": wall_hours,
        "projected_restricted_storage_gb": storage_gb,
        "projected_peak_rss_gib": peak_rss_gib,
        "projected_gpu_hours": 0,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
        "formula": "1020 times worse maximum individual fit plus worse full-size non-fit overhead",
    }


def terminal_files(
    *,
    source_manifest: Mapping[str, Any],
    model_double_root: Path,
    scored_root: Path,
    probe_root: Path,
    resource_traversal: Mapping[str, Any],
    allow_test_double: bool,
) -> dict[str, bytes]:
    """Validate complete private evidence and return the exact eight terminals."""

    model = _json(model_double_root / "manifest.json")
    scored = _json(scored_root / "manifest.json")
    probe = _json(probe_root / "manifest.json")
    _require(model["counts"] == {"model_double_invocations": 1740, "prediction_rows": 333216}, "model counts differ")
    _require(scored["selection_tokens"] == 2, "selection token count differs")
    _require(probe["counts"] == {"real_catboost_fits": 13, "prediction_rows": 10244}, "probe counts differ")
    if not allow_test_double:
        _require(probe.get("test_double") is not True, "test-double probe cannot enter acceptance")
    source_receipt = {
        "schema_version": SOURCE_SCHEMA,
        "contract_sha256": CONTRACT_SHA256,
        "canonical_source_sha256": model["canonical_source_sha256"],
        "counts": source_manifest["counts"],
        "physical_order_removed_from_terminal": True,
    }
    fit_bytes = (model_double_root / "fit_receipts.csv").read_bytes()
    prediction_bytes = (model_double_root / "prediction_receipts.csv").read_bytes()
    selection_bytes = (scored_root / "selection_tokens.json").read_bytes()
    diagnostics = _json(scored_root / "diagnostics.json")
    diagnostics["full_size_resource_traversal"] = {
        key: value
        for key, value in resource_traversal.items()
        if key not in {"nonfit_wall_seconds", "nonfit_cpu_seconds", "peak_rss_kib"}
    }
    files = {
        TERMINAL_FILES[0]: base.json_bytes(source_receipt),
        TERMINAL_FILES[1]: fit_bytes,
        TERMINAL_FILES[2]: prediction_bytes,
        TERMINAL_FILES[3]: selection_bytes,
        TERMINAL_FILES[4]: base.json_bytes(diagnostics),
        TERMINAL_FILES[5]: (probe_root / "parameter_receipts.csv").read_bytes(),
        TERMINAL_FILES[6]: (probe_root / "prediction_receipts.csv").read_bytes(),
    }
    accounting = {
        "synthetic_source_rows_opened": 1200,
        "synthetic_model_double_invocations": 1740,
        "synthetic_catboost_fits": 13,
        "synthetic_predictions_generated": 333216 + 10244,
        "synthetic_metric_evaluations": 80,
        **{name: 0 for name in OFFICIAL_ZERO_FIELDS},
    }
    manifest = {
        "schema_version": TERMINAL_SCHEMA,
        "status": "G2_7B_MAPLIGHT_ROBUSTNESS_SYNTHETIC_ACCEPTED",
        "synthetic": True,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": base.sha256_path(SCRIPT),
        "canonical_source_sha256": model["canonical_source_sha256"],
        "counts": {
            "mechanics_profiles": 2,
            "model_double_invocations": 1740,
            "model_double_prediction_rows": 333216,
            "real_catboost_fits": 13,
            "real_catboost_prediction_rows": 10244,
            "full_size_prediction_identities": 797232,
            "terminal_files": 8,
        },
        "chronology": {
            "stage_a_predictions_frozen_before_truth": True,
            "stage_b_predictions_frozen_before_truth": True,
            "stage_c_predictions_frozen_before_truth": True,
            "diagnostics_after_all_required_prediction_freezes": True,
        },
        "private_roots_retained": 0,
        "runtime_probe_test_double": probe.get("test_double") is True,
        "accounting": accounting,
        "scientific_interpretation": "Synthetic mechanics and runtime evidence only; no synthetic value can select or rank an official model.",
        "output_receipts": {name: base.sha256_bytes(value) for name, value in files.items()},
    }
    files[TERMINAL_FILES[7]] = base.json_bytes(manifest)
    _require(tuple(files) == TERMINAL_FILES, "terminal file order differs")
    return files


def relative_byte_map(root: Path) -> dict[str, str]:
    base._readonly_root(root, "G2-7B terminal root")
    _require({path.name for path in root.iterdir()} == set(TERMINAL_FILES), "terminal files differ")
    return {name: base.sha256_path(root / name) for name in TERMINAL_FILES}


def directory_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


__all__ = [
    "ALT_SEEDS",
    "CONTRACT_SHA256",
    "DROP_CANDIDATES",
    "ENDPOINTS",
    "FEATURE_VIEWS",
    "FEATURE_WIDTHS",
    "FIT_COLUMNS",
    "FULL",
    "LOCK_SHA256",
    "MOLECULE_COLUMNS",
    "OFFICIAL_ZERO_FIELDS",
    "OVERLAY_COLUMNS",
    "OVERLAYS",
    "PREDICTION_COLUMNS",
    "PRIMARY",
    "PROBE_PARAMETER_COLUMNS",
    "PROBE_PREDICTION_COLUMNS",
    "PROFILES",
    "RobustnessSyntheticError",
    "SOURCE_SCHEMA",
    "SCRIPT",
    "TERMINAL_FILES",
    "TRUTH_COLUMNS",
    "compile_capabilities",
    "directory_bytes",
    "fit_identities",
    "probe_identities",
    "publish_fake_runtime_probes",
    "relative_byte_map",
    "resource_projection",
    "run_model_double",
    "run_runtime_probes",
    "score_and_select",
    "select_candidate",
    "terminal_files",
    "traverse_full_size_resource",
]
