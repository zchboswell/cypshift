#!/usr/bin/env python3
"""Compile sparse, development-only G2-3C EXP-G1 capabilities.

The compiler is additive to the accepted G2-3B runner.  It preserves every
finite central point for training and component-equal MAE while publishing a
separate tutorial mask that requires finite point, lower, and upper values.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Final

import global_v2_g1_runner as g1
import global_v2_maplight_runner as runner
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
EXECUTION_CONTRACT: Final = (
    ROOT / "benchmarks" / "openadmet_cyp_2026" / "global_v2_g1_execution_contract.json"
)
EXECUTION_CONTRACT_SHA256: Final = (
    "c75cb01e3d4fec1595c17d5b0f0bd4369c8424ef7dbf4f8fd1fe2112fd20b869"
)
TRACKED_CLAIM: Final = EXECUTION_CONTRACT.with_name("global_v2_g1_execution_claim.json")
TRACKED_CLAIM_SHA256: Final = (
    "1c9f34388290c3992ae9346fbb9b4a71602d3d12b44a619f425ac93dec946154"
)
OFFICIAL_WRAPPER: Final = SCRIPT.with_name("global_v2_g1_execution_wrapper.py")
OFFICIAL_SYNTHETIC_DRIVER: Final = SCRIPT.with_name(
    "run_global_v2_g1_execution_synthetic.py"
)
TRACKED_ACCEPTANCE: Final = EXECUTION_CONTRACT.with_name(
    "global_v2_g1_execution_synthetic_acceptance.json"
)
OFFICIAL_SOURCE_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/g2-2c-maplight-development-source-v1"
)
OFFICIAL_BASELINE_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/"
    "g2-2c-maplight-development-attempt-1/terminal"
)
G2A_CONTRACT_SHA256: Final = runner.CONTRACT_SHA256
SOURCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_source.v1"
)
MODEL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_execution_model_capability.v1"
)
SELECTOR_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_execution_selector_capability.v1"
)
SCORER_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_execution_scorer_capability.v1"
)
PREFLIGHT_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_execution_preflight.v1"
)
SOURCE_FEATURE_COLUMNS: Final = (
    "molecule_id",
    "raw_structure_sha256",
    "standardized_structure_hash",
    "similarity_component_hash",
)
SOURCE_FOLD_COLUMNS: Final = (
    "molecule_id",
    "similarity_component_hash",
    "repeat",
    "seed",
    "outer_fold",
    "outer_validation_fold",
    "inner_fold",
)
DIRECT_COLUMNS: Final = (
    "observation_id",
    "molecule_id",
    "source_row_id",
    "source_file",
    "source_row",
    "source_sha256",
    "endpoint",
    "raw_smiles",
    "raw_point",
    "raw_low",
    "raw_high",
    "raw_std",
    "point",
    "low",
    "high",
    "std",
    "raw_structure_sha256",
    "standardized_structure_hash",
    "similarity_component_hash",
    "scaffold_group_hash",
    "value_state",
    "point_eligible",
    "anchor_eligible",
)
SOURCE_FILES: Final = (
    "direct_observations.csv",
    "group_folds.csv",
    "feature_rows.csv",
    "maplight_morgan_count.npy",
    "maplight_avalon_count.npy",
    "maplight_erg.npy",
    "maplight_rdkit_descriptors.npy",
)
SEEDS: Final = (20260810, 20260811, 20260812)
SYNTHETIC_MINIMA: Final = {
    "development_finite_targets_per_endpoint": 200,
    "outer_validation_targets_per_endpoint_repeat_fold": 24,
    "inner_training_targets_per_endpoint_repeat_outer_inner": 120,
}
OFFICIAL_MINIMA: Final = {
    "development_finite_targets_per_endpoint": 750,
    "outer_validation_targets_per_endpoint_repeat_fold": 75,
    "inner_training_targets_per_endpoint_repeat_outer_inner": 400,
}
TRUTH_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "value_state",
    "point_eligible",
    "tutorial_eligible",
    "point",
    "low",
    "high",
)
INNER_TRUTH_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "inner_fold",
    "value_state",
    "point_eligible",
    "tutorial_eligible",
    "point",
    "low",
    "high",
)
OUTER_TRUTH_COLUMNS: Final = tuple(
    name for name in INNER_TRUTH_COLUMNS if name != "inner_fold"
)
BASELINE_COLUMNS: Final = g1.BASELINE_COLUMNS
OFFICIAL_RECEIPT_KEYS: Final = {
    "direct_observations.csv": "direct_observations_sha256",
    "group_folds.csv": "group_folds_sha256",
    "feature_rows.csv": "feature_rows_sha256",
    "maplight_morgan_count.npy": "maplight_morgan_count_sha256",
    "maplight_avalon_count.npy": "maplight_avalon_count_sha256",
    "maplight_erg.npy": "maplight_erg_sha256",
    "maplight_rdkit_descriptors.npy": "maplight_rdkit_descriptors_sha256",
}
OFFICIAL_PARENT_RECEIPT_KEYS: Final = {
    "r2b_manifest_sha256": "r2b_manifest_sha256",
    "r3a_feature_manifest_sha256": "r3a_feature_manifest_sha256",
}
R2B_PARENT_MANIFEST: Final = "manifest.json"
R3A_PARENT_MANIFEST: Final = "feature_manifest.json"


class MapLightExecutionCompilerError(RuntimeError):
    """A source, split, target, preflight, or publication invariant failed."""


class MapLightExecutionUnderpowered(MapLightExecutionCompilerError):
    """The frozen support gate failed before capability publication."""

    def __init__(
        self,
        preflight: Mapping[str, object],
        source_receipts: Mapping[str, str],
    ) -> None:
        super().__init__("development support is underpowered")
        self.preflight = dict(preflight)
        self.source_receipts = dict(source_receipts)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MapLightExecutionCompilerError(message)


def _is_sha(value: object, length: int = 64) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_confirmatory(component_hash: str) -> bool:
    _require(_is_sha(component_hash), "component hash differs")
    material = (
        "openadmet-global-v2-confirmatory-v1|20260824|" + component_hash
    ).encode("utf-8")
    return int.from_bytes(sha256(material).digest()[:8], "big") % 5 == 0


def _npy_bytes(array: np.ndarray[Any, Any]) -> bytes:
    stream = io.BytesIO()
    np.lib.format.write_array(
        stream,
        np.ascontiguousarray(array),
        version=(1, 0),
        allow_pickle=False,
    )
    return stream.getvalue()


def _authority(synthetic: bool, stage: str = "model") -> dict[str, bool]:
    _require(stage in {"model", "selector", "scorer"}, "authority stage differs")
    authority = dict(g1.DENIED_AUTHORITY)
    authority["official_baseline_prediction_access"] = False
    if not synthetic:
        authority["official_target_access"] = True
        if stage == "model":
            authority["official_feature_access"] = True
        else:
            authority["development_metric_evaluation"] = True
        if stage == "scorer":
            authority["official_baseline_prediction_access"] = True
    return authority


def _source_authority(synthetic: bool) -> dict[str, bool]:
    authority = dict(runner.DENIED_AUTHORITY)
    if not synthetic:
        authority["official_target_access"] = True
        authority["official_feature_access"] = True
    return authority


def _validate_consumed_claim(
    claim: Mapping[str, Any], expected_compiler_sha256: str
) -> dict[str, str]:
    receipts = claim.get("official_input_receipts")
    _require(
        claim.get("schema_version")
        == "cypshift.openadmet_cyp_2026.global_v2_g1_execution_claim.v1"
        and claim.get("status") == "G2_3C_CLAIM_CONSUMED"
        and claim.get("claim_id") == "g2-3c-g1-development-attempt-1"
        and claim.get("contract_sha256") == EXECUTION_CONTRACT_SHA256
        and claim.get("g1_runner_source_sha256") == runner.sha256_path(g1.SCRIPT)
        and claim.get("runtime_lock_sha256") == g1.LOCK_SHA256
        and claim.get("future_official_compiler_source_sha256")
        == expected_compiler_sha256
        and claim.get("future_attempt_wrapper_source_sha256")
        == runner.sha256_path(OFFICIAL_WRAPPER)
        and claim.get("future_official_shaped_synthetic_driver_source_sha256")
        == runner.sha256_path(OFFICIAL_SYNTHETIC_DRIVER)
        and claim.get("future_official_shaped_synthetic_acceptance_sha256")
        == runner.sha256_path(TRACKED_ACCEPTANCE)
        and claim.get("maximum_consumptions") == 1
        and isinstance(receipts, Mapping),
        "consumed claim differs",
    )
    assert isinstance(receipts, Mapping)
    normalized = {str(name): str(value) for name, value in receipts.items()}
    _require(
        normalized.get("dataset_revision") == "85f8b358d0a2056a98b990dd75d3b3ec9247862b"
        and all(
            normalized.get(key) is not None and _is_sha(normalized[key])
            for key in (
                *OFFICIAL_RECEIPT_KEYS.values(),
                *OFFICIAL_PARENT_RECEIPT_KEYS.values(),
                "baseline_manifest_sha256",
                "baseline_outer_oof_sha256",
            )
        ),
        "official claim receipts differ",
    )
    _require(
        runner.sha256_path(TRACKED_CLAIM) == TRACKED_CLAIM_SHA256,
        "tracked claim receipt differs",
    )
    template, _template_raw = runner._load_json(TRACKED_CLAIM)
    expected = dict(template)
    expected.update(
        {
            "status": "G2_3C_CLAIM_CONSUMED",
            "future_official_compiler_source_sha256": expected_compiler_sha256,
            "future_attempt_wrapper_source_sha256": runner.sha256_path(
                OFFICIAL_WRAPPER
            ),
            "future_official_shaped_synthetic_driver_source_sha256": (
                runner.sha256_path(OFFICIAL_SYNTHETIC_DRIVER)
            ),
            "future_official_shaped_synthetic_acceptance_sha256": (
                runner.sha256_path(TRACKED_ACCEPTANCE)
            ),
        }
    )
    _require(claim == expected, "consumed claim is not the exact frozen derivation")
    return normalized


def _consumed_claim(
    path: Path, expected_compiler_sha256: str
) -> tuple[dict[str, Any], dict[str, str]]:
    claim, _raw = runner._load_json(path)
    return claim, _validate_consumed_claim(claim, expected_compiler_sha256)


def _source_bytes(root: Path, manifest: Mapping[str, Any]) -> dict[str, bytes]:
    source_receipts = manifest.get("source_receipts")
    _require(isinstance(source_receipts, Mapping), "source receipts differ")
    assert isinstance(source_receipts, Mapping)
    _require(set(source_receipts) == set(SOURCE_FILES), "source receipt set differs")
    expected = {*SOURCE_FILES, "manifest.json"}
    observed = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    _require(observed == expected, "source file set differs")
    loaded: dict[str, bytes] = {}
    for name in SOURCE_FILES:
        path = runner._regular(root / name, f"source {name}")
        data = path.read_bytes()
        _require(
            runner.sha256_bytes(data) == source_receipts.get(name),
            f"source receipt differs: {name}",
        )
        loaded[name] = data
    return loaded


def _validate_official_manifest(
    manifest: Mapping[str, Any], claim_receipts: Mapping[str, str]
) -> None:
    _require(
        manifest.get("schema_version") == SOURCE_SCHEMA
        and manifest.get("synthetic") is False
        and manifest.get("semantic_source_id") == claim_receipts["dataset_revision"],
        "official source identity differs",
    )
    _require(
        manifest.get("authority") == _source_authority(False),
        "official source authority differs",
    )
    source_receipts = manifest.get("source_receipts")
    parent_receipts = manifest.get("parent_receipts")
    _require(isinstance(source_receipts, Mapping), "official source receipts differ")
    _require(isinstance(parent_receipts, Mapping), "official parent receipts differ")
    assert isinstance(source_receipts, Mapping)
    assert isinstance(parent_receipts, Mapping)
    _require(
        set(source_receipts) == set(SOURCE_FILES)
        and set(parent_receipts) == set(OFFICIAL_PARENT_RECEIPT_KEYS),
        "official source receipt set differs",
    )
    _require(
        all(
            source_receipts.get(name) == claim_receipts[key]
            for name, key in OFFICIAL_RECEIPT_KEYS.items()
        ),
        "official source leaf receipt differs",
    )
    _require(
        all(
            parent_receipts.get(name) == claim_receipts[key]
            for name, key in OFFICIAL_PARENT_RECEIPT_KEYS.items()
        ),
        "official parent manifest receipt differs",
    )
    _require(
        manifest.get("label_free_counts")
        == {
            "all_molecules": 4905,
            "all_components": 4553,
            "development_molecules": 3908,
            "development_components": 3640,
            "confirmatory_molecules": 997,
            "confirmatory_components": 913,
        },
        "official label-free cardinality differs",
    )


def authenticate_official_source(
    *,
    source_root: Path,
    consumed_claim: Mapping[str, Any],
    expected_compiler_sha256: str,
) -> dict[str, str]:
    """Authenticate every frozen official source byte before claim publication."""

    _require(
        runner.sha256_path(SCRIPT) == expected_compiler_sha256,
        "compiler source receipt differs",
    )
    _require(
        runner.sha256_path(EXECUTION_CONTRACT) == EXECUTION_CONTRACT_SHA256,
        "execution contract receipt differs",
    )
    claim_receipts = _validate_consumed_claim(consumed_claim, expected_compiler_sha256)
    runner._readonly_root(source_root, "execution source")
    manifest, _raw = runner._load_json(source_root / "manifest.json")
    _validate_official_manifest(manifest, claim_receipts)
    _source_bytes(source_root, manifest)
    return claim_receipts


def _csv_rows(
    data: bytes, columns: tuple[str, ...], label: str
) -> list[dict[str, str]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MapLightExecutionCompilerError(f"{label} is not UTF-8") from error
    reader = csv.DictReader(io.StringIO(text, newline=""))
    _require(tuple(reader.fieldnames or ()) == columns, f"{label} columns differ")
    rows = list(reader)
    _require(bool(rows), f"{label} is empty")
    _require(all(None not in row for row in rows), f"{label} row width differs")
    return rows


def _features(
    data: bytes,
) -> tuple[list[dict[str, str]], set[str], set[str], list[int]]:
    rows = _csv_rows(data, SOURCE_FEATURE_COLUMNS, "feature rows")
    molecule_ids = [row["molecule_id"] for row in rows]
    _require(len(molecule_ids) == len(set(molecule_ids)), "feature identities differ")
    development: set[str] = set()
    confirmatory: set[str] = set()
    selected: list[tuple[str, dict[str, str], int]] = []
    for index, row in enumerate(rows):
        component = row["similarity_component_hash"]
        _require(
            _is_sha(row["raw_structure_sha256"])
            and _is_sha(row["standardized_structure_hash"])
            and _is_sha(component),
            "feature identity receipt differs",
        )
        if _is_confirmatory(component):
            confirmatory.add(row["molecule_id"])
        else:
            development.add(row["molecule_id"])
            selected.append((row["molecule_id"], row, index))
    _require(
        bool(development)
        and bool(confirmatory)
        and not development.intersection(confirmatory),
        "development assignment differs",
    )
    selected.sort(key=lambda item: item[0])
    output = [
        {
            "molecule_id": row["molecule_id"],
            "similarity_component_hash": row["similarity_component_hash"],
        }
        for _molecule, row, _index in selected
    ]
    return (
        output,
        development,
        confirmatory,
        [index for _molecule, _row, index in selected],
    )


def _folds(
    data: bytes, development: set[str], components: Mapping[str, str]
) -> list[dict[str, str]]:
    rows = _csv_rows(data, SOURCE_FOLD_COLUMNS, "group folds")
    result: list[dict[str, str]] = []
    seen: set[tuple[str, int, int]] = set()
    for row in rows:
        molecule = row["molecule_id"]
        if molecule not in development:
            continue
        repeat = int(row["repeat"])
        context = int(row["outer_validation_fold"])
        outer = int(row["outer_fold"])
        _require(
            repeat in runner.REPEATS
            and context in runner.OUTER_FOLDS
            and outer in runner.OUTER_FOLDS
            and int(row["seed"]) == SEEDS[repeat],
            "fold context differs",
        )
        _require(
            row["similarity_component_hash"] == components.get(molecule),
            "fold component differs",
        )
        key = molecule, repeat, context
        _require(key not in seen, "duplicate development fold scope")
        seen.add(key)
        inner = row["inner_fold"]
        if outer == context:
            _require(inner == "", "outer validation has inner assignment")
        else:
            _require(int(inner) in runner.INNER_FOLDS, "inner fold differs")
        result.append(
            {
                "molecule_id": molecule,
                "similarity_component_hash": row["similarity_component_hash"],
                "repeat": str(repeat),
                "outer_fold": str(outer),
                "outer_validation_fold": str(context),
                "inner_fold": inner,
            }
        )
    _require(
        len(result) == len(development) * 3 * 5,
        "development fold row count differs",
    )
    result.sort(
        key=lambda row: (
            row["molecule_id"],
            int(row["repeat"]),
            int(row["outer_validation_fold"]),
        )
    )
    return result


def _direct_prefix(line: bytes) -> tuple[str, str]:
    prefix = line.split(b",", 2)
    _require(len(prefix) == 3, "direct observation prefix differs")
    _require(b'"' not in prefix[0] and b'"' not in prefix[1], "quoted identity prefix")
    try:
        return prefix[0].decode("utf-8"), prefix[1].decode("utf-8")
    except UnicodeDecodeError as error:
        raise MapLightExecutionCompilerError(
            "direct observation identity is not UTF-8"
        ) from error


def _development_truth(
    data: bytes,
    development: set[str],
    confirmatory: set[str],
    components: Mapping[str, str],
) -> tuple[dict[tuple[str, str], dict[str, str]], dict[str, int]]:
    _require(b"\r" not in data, "direct observations contain CR bytes")
    lines = data.splitlines(keepends=True)
    expected_header = (",".join(DIRECT_COLUMNS) + "\n").encode("utf-8")
    _require(bool(lines) and lines[0] == expected_header, "direct columns differ")
    truth: dict[tuple[str, str], dict[str, str]] = {}
    seen: set[tuple[str, str]] = set()
    development_rows = 0
    confirmatory_rows_opaque = 0
    point_rows = 0
    tutorial_rows = 0
    point_only_rows = 0
    tutorial_without_std_rows = 0
    for physical in lines[1:]:
        _require(physical.endswith(b"\n"), "direct row lacks final LF")
        observation_id, molecule = _direct_prefix(physical[:-1])
        _require(bool(observation_id), "observation identity is empty")
        if molecule in confirmatory:
            confirmatory_rows_opaque += 1
            continue
        _require(molecule in development, "direct molecule is absent from features")
        development_rows += 1
        try:
            parsed = next(csv.reader([physical[:-1].decode("utf-8")]))
        except (UnicodeDecodeError, csv.Error) as error:
            raise MapLightExecutionCompilerError(
                "development direct row cannot be decoded"
            ) from error
        _require(len(parsed) == len(DIRECT_COLUMNS), "development direct width differs")
        row = dict(zip(DIRECT_COLUMNS, parsed, strict=True))
        endpoint = row["endpoint"]
        key = molecule, endpoint
        _require(endpoint in runner.ENDPOINTS and key not in seen, "direct key differs")
        seen.add(key)
        _require(
            row["observation_id"] == observation_id
            and row["similarity_component_hash"] == components[molecule],
            "direct identity receipt differs",
        )

        present = {name: bool(row[name]) for name in ("point", "low", "high", "std")}
        values = {
            name: (
                runner._canonical_float(row[name], f"development {name}")
                if present[name]
                else None
            )
            for name in ("point", "low", "high", "std")
        }
        expected_state = (
            "missing"
            if not any(present.values())
            else "orphan_auxiliary"
            if not present["point"]
            else "complete"
            if all(present.values())
            else "partial"
        )
        _require(
            row["value_state"] == expected_state
            and row["point_eligible"] == ("true" if present["point"] else "false")
            and row["anchor_eligible"]
            == ("true" if expected_state == "complete" else "false"),
            "development availability state differs",
        )
        point = values["point"]
        low = values["low"]
        high = values["high"]
        std = values["std"]
        _require(
            (std is None or std >= 0.0)
            and (low is None or high is None or low <= high)
            and (point is None or low is None or low <= point)
            and (point is None or high is None or point <= high),
            "development bounds differ",
        )
        point_eligible = point is not None
        tutorial_eligible = point is not None and low is not None and high is not None
        if point_eligible:
            point_rows += 1
        if tutorial_eligible:
            tutorial_rows += 1
            if std is None:
                tutorial_without_std_rows += 1
        elif point_eligible:
            point_only_rows += 1
        truth[key] = {
            "molecule_id": molecule,
            "endpoint": endpoint,
            "similarity_component_hash": components[molecule],
            "value_state": expected_state,
            "point_eligible": "true" if point_eligible else "false",
            "tutorial_eligible": "true" if tutorial_eligible else "false",
            "point": row["point"],
            "low": row["low"],
            "high": row["high"],
        }
    _require(
        len(seen) == len(development) * len(runner.ENDPOINTS),
        "development endpoint coverage differs",
    )
    _require(
        confirmatory_rows_opaque == len(confirmatory) * len(runner.ENDPOINTS),
        "opaque confirmatory endpoint coverage differs",
    )
    return truth, {
        "development_rows_decoded": development_rows,
        "development_finite_targets": point_rows,
        "development_tutorial_eligible_rows": tutorial_rows,
        "development_point_only_rows": point_only_rows,
        "development_tutorial_without_std_rows": tutorial_without_std_rows,
        "confirmatory_rows_kept_opaque": confirmatory_rows_opaque,
        "confirmatory_target_values_parsed": 0,
    }


def _tutorial_denominator(rows: Sequence[Mapping[str, str]]) -> float:
    _require(bool(rows), "tutorial preflight population is empty")
    points = [
        runner._canonical_float(row["point"], "tutorial preflight point")
        for row in rows
    ]
    mean = math.fsum(points) / len(points)
    denominator = math.fsum(
        max(
            mean - runner._canonical_float(row["high"], "tutorial preflight high"),
            0.0,
        )
        + max(
            runner._canonical_float(row["low"], "tutorial preflight low") - mean,
            0.0,
        )
        for row in rows
    )
    _require(math.isfinite(denominator), "tutorial preflight denominator is nonfinite")
    return denominator


def _support(
    truth: Mapping[tuple[str, str], Mapping[str, str]],
    folds: list[dict[str, str]],
    minima: Mapping[str, int],
) -> dict[str, object]:
    fold_index = {
        (row["molecule_id"], int(row["repeat"]), int(row["outer_validation_fold"])): row
        for row in folds
    }
    point_by_endpoint = {
        endpoint: sum(
            row["point_eligible"] == "true"
            for (molecule, observed), row in truth.items()
            if observed == endpoint
        )
        for endpoint in runner.ENDPOINTS
    }
    tutorial_by_endpoint = {
        endpoint: sum(
            row["tutorial_eligible"] == "true"
            for (molecule, observed), row in truth.items()
            if observed == endpoint
        )
        for endpoint in runner.ENDPOINTS
    }
    outer_counts: dict[str, int] = {}
    inner_counts: dict[str, int] = {}
    selector_tutorial_counts: dict[str, int] = {}
    selector_tutorial_denominators: dict[str, float] = {}
    repeat_tutorial_counts: dict[str, int] = {}
    repeat_tutorial_denominators: dict[str, float] = {}
    failures: list[str] = []
    finite_minimum = int(minima["development_finite_targets_per_endpoint"])
    outer_minimum = int(minima["outer_validation_targets_per_endpoint_repeat_fold"])
    inner_minimum = int(
        minima["inner_training_targets_per_endpoint_repeat_outer_inner"]
    )
    for endpoint, count in point_by_endpoint.items():
        if count < finite_minimum:
            failures.append(f"finite:{endpoint}:{count}")
        point_molecules = sorted(
            molecule
            for (molecule, observed), row in truth.items()
            if observed == endpoint and row["point_eligible"] == "true"
        )
        tutorial_molecules = sorted(
            molecule
            for (molecule, observed), row in truth.items()
            if observed == endpoint and row["tutorial_eligible"] == "true"
        )
        for repeat in runner.REPEATS:
            repeat_rows = [truth[molecule, endpoint] for molecule in tutorial_molecules]
            repeat_key = f"{endpoint}|{repeat}"
            repeat_tutorial_counts[repeat_key] = len(repeat_rows)
            repeat_denominator = _tutorial_denominator(repeat_rows)
            repeat_tutorial_denominators[repeat_key] = repeat_denominator
            if repeat_denominator <= 0.0:
                failures.append(f"tutorial-repeat:{repeat_key}:{repeat_denominator}")
            for outer in runner.OUTER_FOLDS:
                outer_count = sum(
                    int(fold_index[(molecule, repeat, outer)]["outer_fold"]) == outer
                    for molecule in point_molecules
                )
                outer_key = f"{endpoint}|{repeat}|{outer}"
                outer_counts[outer_key] = outer_count
                if outer_count < outer_minimum:
                    failures.append(f"outer:{outer_key}:{outer_count}")
                selector_rows = [
                    truth[molecule, endpoint]
                    for molecule in tutorial_molecules
                    if int(fold_index[(molecule, repeat, outer)]["outer_fold"]) != outer
                ]
                selector_tutorial_counts[outer_key] = len(selector_rows)
                selector_denominator = _tutorial_denominator(selector_rows)
                selector_tutorial_denominators[outer_key] = selector_denominator
                if selector_denominator <= 0.0:
                    failures.append(
                        f"tutorial-selector:{outer_key}:{selector_denominator}"
                    )
                for inner in runner.INNER_FOLDS:
                    inner_count = sum(
                        int(fold_index[(molecule, repeat, outer)]["outer_fold"])
                        != outer
                        and int(fold_index[(molecule, repeat, outer)]["inner_fold"])
                        != inner
                        for molecule in point_molecules
                    )
                    inner_key = f"{endpoint}|{repeat}|{outer}|{inner}"
                    inner_counts[inner_key] = inner_count
                    if inner_count < inner_minimum:
                        failures.append(f"inner:{inner_key}:{inner_count}")
    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": "G2_3C_PREFLIGHT_PASS" if not failures else "G2_3_G1_UNDERPOWERED",
        "minimum_support": dict(minima),
        "finite_targets_per_endpoint": point_by_endpoint,
        "tutorial_targets_per_endpoint": tutorial_by_endpoint,
        "outer_validation_targets": outer_counts,
        "inner_training_targets": inner_counts,
        "selector_tutorial_rows": selector_tutorial_counts,
        "selector_tutorial_denominators": selector_tutorial_denominators,
        "repeat_tutorial_rows": repeat_tutorial_counts,
        "repeat_tutorial_denominators": repeat_tutorial_denominators,
        "failures": failures,
    }


def _baseline_rows(
    *,
    root: Path,
    synthetic: bool,
    claim_receipts: Mapping[str, str] | None,
    components: Mapping[str, str],
    folds: list[dict[str, str]],
) -> tuple[list[dict[str, object]], str]:
    runner._readonly_root(root, "fixed baseline terminal")
    manifest_path = runner._regular(root / "manifest.json", "fixed baseline manifest")
    prediction_path = runner._regular(
        root / "development_outer_oof.csv", "fixed baseline OOF"
    )
    if not synthetic:
        _require(root == OFFICIAL_BASELINE_ROOT, "official baseline root differs")
        _require(claim_receipts is not None, "official baseline receipts are absent")
        assert claim_receipts is not None
        _require(
            runner.sha256_path(manifest_path)
            == claim_receipts["baseline_manifest_sha256"]
            and runner.sha256_path(prediction_path)
            == claim_receipts["baseline_outer_oof_sha256"],
            "official baseline receipt differs",
        )
    manifest, _raw = runner._load_json(manifest_path)
    _require(
        manifest.get("synthetic") is synthetic,
        "fixed baseline synthetic identity differs",
    )
    rows = runner._read_csv(prediction_path, runner.OUTER_COLUMNS)
    fold_index = {
        (
            row["molecule_id"],
            int(row["repeat"]),
            int(row["outer_validation_fold"]),
        ): int(row["outer_fold"])
        for row in folds
    }
    seen: set[tuple[str, str, int]] = set()
    output: list[dict[str, object]] = []
    for row in rows:
        molecule = row["molecule_id"]
        endpoint = row["endpoint"]
        repeat = int(row["repeat"])
        outer = int(row["outer_fold"])
        key = molecule, endpoint, repeat
        _require(
            key not in seen
            and molecule in components
            and endpoint in g1.ENDPOINTS
            and repeat in g1.REPEATS
            and outer == fold_index[molecule, repeat, outer]
            and row["similarity_component_hash"] == components[molecule],
            "fixed baseline prediction identity differs",
        )
        runner._canonical_float(row["prediction"], "fixed baseline prediction")
        seen.add(key)
        output.append(
            {
                "molecule_id": molecule,
                "endpoint": endpoint,
                "similarity_component_hash": components[molecule],
                "repeat": repeat,
                "outer_fold": outer,
                "prediction": row["prediction"],
            }
        )
    expected = len(components) * len(g1.ENDPOINTS) * len(g1.REPEATS)
    _require(len(output) == len(seen) == expected, "fixed baseline topology differs")
    output.sort(key=lambda row: tuple(row[name] for name in g1.BASELINE_COLUMNS[:5]))
    return output, runner.sha256_path(prediction_path)


def compile_capabilities(
    *,
    source_root: Path,
    baseline_terminal_root: Path,
    output_root: Path,
    expected_compiler_sha256: str,
    mode: str = "synthetic",
    consumed_claim_path: Path | None = None,
) -> tuple[Path, Path, Path, dict[str, object]]:
    """Compile one authenticated source into disjoint model/selector/scorer roots."""

    _require(
        runner.sha256_path(SCRIPT) == expected_compiler_sha256,
        "compiler source receipt differs",
    )
    _require(
        runner.sha256_path(EXECUTION_CONTRACT) == EXECUTION_CONTRACT_SHA256,
        "execution contract receipt differs",
    )
    _require(mode in {"synthetic", "official"}, "compiler mode differs")
    claim_receipts: dict[str, str] | None = None
    if mode == "official":
        _require(consumed_claim_path is not None, "official consumed claim is absent")
        assert consumed_claim_path is not None
        _claim, claim_receipts = _consumed_claim(
            consumed_claim_path, expected_compiler_sha256
        )
    else:
        _require(consumed_claim_path is None, "synthetic compilation received a claim")
    runner._readonly_root(source_root, "execution source")
    manifest, _raw = runner._load_json(source_root / "manifest.json")
    synthetic = mode == "synthetic"
    _require(
        manifest.get("schema_version") == SOURCE_SCHEMA
        and manifest.get("synthetic") is synthetic,
        "source identity differs",
    )
    if synthetic:
        _require(
            manifest.get("semantic_source_id") == "g2-2c-official-shaped-synthetic-v1"
            and manifest.get("authority") == _source_authority(True),
            "synthetic source identity or authority differs",
        )
    else:
        assert claim_receipts is not None
        _require(source_root == OFFICIAL_SOURCE_ROOT, "official source root differs")
        _validate_official_manifest(manifest, claim_receipts)
    _require(not output_root.exists() and not output_root.is_symlink(), "output exists")
    source = _source_bytes(source_root, manifest)
    feature_rows, development, confirmatory, development_indices = _features(
        source["feature_rows.csv"]
    )
    if not synthetic:
        _require(
            len(development) == 3908
            and len(confirmatory) == 997
            and len({row["similarity_component_hash"] for row in feature_rows}) == 3640,
            "official development cardinality differs",
        )
    components = {
        row["molecule_id"]: row["similarity_component_hash"] for row in feature_rows
    }
    folds = _folds(source["group_folds.csv"], development, components)
    truth, target_accounting = _development_truth(
        source["direct_observations.csv"], development, confirmatory, components
    )
    preflight = _support(
        truth, folds, SYNTHETIC_MINIMA if synthetic else OFFICIAL_MINIMA
    )
    official_source_receipts = dict(claim_receipts or {})
    preflight["accounting"] = {
        **target_accounting,
        "official_target_values_opened": (
            0 if synthetic else target_accounting["development_finite_targets"]
        ),
        "official_features_opened": (
            0 if synthetic else (len(development) + len(confirmatory)) * 2563
        ),
        "official_baseline_prediction_rows_opened": 0,
        "official_model_fits": 0,
        "official_predictions_generated": 0,
        "development_metric_evaluations": 0,
        "tutorial_ma_st_rae_calls": 0,
        "official_metric_evaluations": 0,
        "confirmatory_truth_values_opened": 0,
        "historical_r3c_row_level_artifacts_opened": 0,
        "blinded_test_files_opened": 0,
        "tdi_files_opened": 0,
        "external_records_acquired": 0,
        "submissions_created": 0,
        "leaderboard_observations": 0,
        "live_uploads": 0,
    }
    if preflight["status"] != "G2_3C_PREFLIGHT_PASS":
        raise MapLightExecutionUnderpowered(preflight, official_source_receipts)

    feature_bytes = runner.csv_bytes(g1.FEATURE_COLUMNS, feature_rows)
    fold_bytes = runner.csv_bytes(g1.FOLD_COLUMNS, folds)
    model_files: dict[str, bytes] = {
        "feature_rows.csv": feature_bytes,
        "folds.csv": fold_bytes,
    }
    arrays: dict[str, dict[str, object]] = {}
    total_molecules = len(development) + len(confirmatory)
    for name, width, dtype in runner.MAP_ARRAYS:
        array = np.load(io.BytesIO(source[name]), allow_pickle=False)
        _require(
            array.shape == (total_molecules, width)
            and array.dtype == dtype
            and array.flags.c_contiguous
            and np.isfinite(array).all(),
            f"source array differs: {name}",
        )
        selected = np.ascontiguousarray(array[development_indices], dtype=dtype)
        payload = _npy_bytes(selected)
        model_files[name] = payload
        arrays[name] = {
            "sha256": runner.sha256_bytes(payload),
            "shape": [len(development), width],
            "dtype": str(dtype),
        }
    fold_scopes = {
        (
            row["molecule_id"],
            int(row["repeat"]),
            int(row["outer_validation_fold"]),
        ): row
        for row in folds
    }
    target_rows = 0
    for stage in ("outer", "inner"):
        for endpoint in g1.ENDPOINTS:
            eligible = {
                molecule
                for (molecule, observed), row in truth.items()
                if observed == endpoint and row["point_eligible"] == "true"
            }
            for repeat in g1.REPEATS:
                for outer in g1.OUTER_FOLDS:
                    scope = {
                        molecule: fold_scopes[molecule, repeat, outer]
                        for molecule in development
                    }
                    inners = (None,) if stage == "outer" else g1.INNER_FOLDS
                    for inner in inners:
                        training, _prediction = runner._cell_ids(
                            scope, stage, outer, inner
                        )
                        rows = [
                            {
                                "molecule_id": molecule,
                                "point": truth[molecule, endpoint]["point"],
                            }
                            for molecule in training
                            if molecule in eligible
                        ]
                        target_rows += len(rows)
                        path = g1._target_path(
                            Path("."),
                            stage=stage,
                            endpoint=endpoint,
                            repeat=repeat,
                            outer=outer,
                            inner=inner,
                        )
                        model_files[path.as_posix().removeprefix("./")] = (
                            runner.csv_bytes(g1.TARGET_COLUMNS, rows)
                        )
    target_material = "".join(
        f"{name}|{runner.sha256_bytes(value)}\n"
        for name, value in sorted(model_files.items())
        if name.startswith("targets/")
    ).encode("utf-8")
    common_accounting = {
        **target_accounting,
        "official_target_values_opened": (
            0 if synthetic else target_accounting["development_finite_targets"]
        ),
        "official_features_opened": (
            0 if synthetic else (len(development) + len(confirmatory)) * 2563
        ),
        "official_baseline_prediction_rows_opened": 0,
        "official_model_fits": 0,
        "official_predictions_generated": 0,
        "development_metric_evaluations": 0,
        "tutorial_ma_st_rae_calls": 0,
        "official_metric_evaluations": 0,
        "confirmatory_truth_values_opened": 0,
        "historical_r3c_row_level_artifacts_opened": 0,
        "blinded_test_files_opened": 0,
        "tdi_files_opened": 0,
        "external_records_acquired": 0,
        "submissions_created": 0,
        "leaderboard_observations": 0,
        "live_uploads": 0,
    }
    model_manifest = {
        "schema_version": MODEL_SCHEMA,
        "execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
        "g1_screen_contract_sha256": g1.PARENT_SHA256,
        "accepted_g1_runner_sha256": runner.sha256_path(g1.SCRIPT),
        "compiler_source_sha256": expected_compiler_sha256,
        "synthetic": synthetic,
        "semantic_source_id": manifest["semantic_source_id"],
        "official_source_receipts": official_source_receipts,
        "molecules": len(development),
        "components": len(set(components.values())),
        "confirmatory_molecules_excluded": len(confirmatory),
        "feature_rows_sha256": runner.sha256_bytes(feature_bytes),
        "folds_sha256": runner.sha256_bytes(fold_bytes),
        "target_tree_sha256": runner.sha256_bytes(target_material),
        "arrays": arrays,
        "preflight": preflight,
        "target_capabilities": {
            "files": 300,
            "training_rows": target_rows,
            "outer_validation_truth_rows": 0,
            "inner_validation_truth_rows": 0,
        },
        "accounting": common_accounting,
        "authority": _authority(synthetic, "model"),
    }

    inner_truth: list[dict[str, object]] = []
    outer_truth: list[dict[str, object]] = []
    for endpoint in g1.ENDPOINTS:
        for repeat in g1.REPEATS:
            for outer in g1.OUTER_FOLDS:
                scope = {
                    molecule: fold_scopes[molecule, repeat, outer]
                    for molecule in development
                }
                outer_training, outer_prediction = runner._cell_ids(
                    scope, "outer", outer, None
                )
                for molecule in outer_prediction:
                    outer_truth.append(
                        {
                            **truth[molecule, endpoint],
                            "repeat": repeat,
                            "outer_fold": outer,
                        }
                    )
                for inner in g1.INNER_FOLDS:
                    _inner_training, inner_prediction = runner._cell_ids(
                        scope, "inner", outer, inner
                    )
                    for molecule in inner_prediction:
                        inner_truth.append(
                            {
                                **truth[molecule, endpoint],
                                "repeat": repeat,
                                "outer_fold": outer,
                                "inner_fold": inner,
                            }
                        )
                _require(bool(outer_training), "outer training population is empty")
    inner_truth.sort(
        key=lambda row: tuple(row[name] for name in INNER_TRUTH_COLUMNS[:6])
    )
    outer_truth.sort(
        key=lambda row: tuple(row[name] for name in OUTER_TRUTH_COLUMNS[:5])
    )
    _require(
        len(inner_truth) == len(development) * 4 * 3 * 4
        and len(outer_truth) == len(development) * 4 * 3,
        "truth capability topology differs",
    )
    baseline_rows, baseline_sha = _baseline_rows(
        root=baseline_terminal_root,
        synthetic=synthetic,
        claim_receipts=claim_receipts,
        components=components,
        folds=folds,
    )
    inner_truth_bytes = runner.csv_bytes(INNER_TRUTH_COLUMNS, inner_truth)
    outer_truth_bytes = runner.csv_bytes(OUTER_TRUTH_COLUMNS, outer_truth)
    baseline_bytes = runner.csv_bytes(BASELINE_COLUMNS, baseline_rows)
    try:
        output_root.mkdir(parents=True)
        model_files["manifest.json"] = runner.json_bytes(model_manifest)
        model_root = runner.publish_files(output_root / "model-capability", model_files)
        model_manifest_sha = runner.sha256_path(model_root / "manifest.json")
        selector_manifest = {
            "schema_version": SELECTOR_SCHEMA,
            "execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
            "accepted_g1_runner_sha256": runner.sha256_path(g1.SCRIPT),
            "compiler_source_sha256": expected_compiler_sha256,
            "model_capability_manifest_sha256": model_manifest_sha,
            "synthetic": synthetic,
            "semantic_source_id": manifest["semantic_source_id"],
            "official_source_receipts": official_source_receipts,
            "inner_truth_sha256": runner.sha256_bytes(inner_truth_bytes),
            "inner_truth_rows": len(inner_truth),
            "model_training_files": 0,
            "feature_arrays": 0,
            "outer_truth_files": 0,
            "accounting": common_accounting,
            "authority": _authority(synthetic, "selector"),
        }
        selector_root = runner.publish_files(
            output_root / "selector-capability",
            {
                "inner_validation_truth.csv": inner_truth_bytes,
                "manifest.json": runner.json_bytes(selector_manifest),
            },
        )
        scorer_manifest = {
            "schema_version": SCORER_SCHEMA,
            "execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
            "accepted_g1_runner_sha256": runner.sha256_path(g1.SCRIPT),
            "compiler_source_sha256": expected_compiler_sha256,
            "model_capability_manifest_sha256": model_manifest_sha,
            "synthetic": synthetic,
            "semantic_source_id": manifest["semantic_source_id"],
            "official_source_receipts": official_source_receipts,
            "outer_truth_sha256": runner.sha256_bytes(outer_truth_bytes),
            "baseline_predictions_sha256": runner.sha256_bytes(baseline_bytes),
            "baseline_source_sha256": baseline_sha,
            "outer_truth_rows": len(outer_truth),
            "baseline_prediction_rows": len(baseline_rows),
            "model_training_files": 0,
            "feature_arrays": 0,
            "inner_truth_files": 0,
            "accounting": common_accounting,
            "authority": _authority(synthetic, "scorer"),
        }
        scorer_root = runner.publish_files(
            output_root / "scorer-capability",
            {
                "outer_truth.csv": outer_truth_bytes,
                "baseline_predictions.csv": baseline_bytes,
                "manifest.json": runner.json_bytes(scorer_manifest),
            },
        )
        runner.publish_files(
            output_root / "preflight",
            {"preflight.json": runner.json_bytes(preflight)},
        )
        return model_root, selector_root, scorer_root, preflight
    except BaseException:
        runner._cleanup(output_root)
        raise


__all__ = [
    "EXECUTION_CONTRACT_SHA256",
    "INNER_TRUTH_COLUMNS",
    "MODEL_SCHEMA",
    "MapLightExecutionCompilerError",
    "MapLightExecutionUnderpowered",
    "SCORER_SCHEMA",
    "SELECTOR_SCHEMA",
    "SOURCE_SCHEMA",
    "SYNTHETIC_MINIMA",
    "authenticate_official_source",
    "compile_capabilities",
]
