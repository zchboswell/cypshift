#!/usr/bin/env python3
"""Compile the minimal G2-7E scorer-enrichment capability.

The accepted D-126 model and scorer capabilities stay unchanged.  This trusted
adapter joins their exact development identities to reported bounds and source
provenance without exposing a scoring row to a model process.  Synthetic mode
is the only currently authorized execution mode; official mode additionally
requires a future corrected consumed-claim authorization.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_execution_compiler as accepted_compiler
import global_v2_maplight_robustness_execution_compiler as capability_compiler
import global_v2_maplight_runner as maplight

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
BENCHMARK: Final = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT: Final = (
    BENCHMARK / "global_v2_maplight_robustness_scoring_capability_contract.json"
)
CONTRACT_SHA256: Final = (
    "b1cb08665c762c736c8dc277522fc5acba3e06af2a66952f276112dd26adac9f"
)
D127_CLAIM: Final = BENCHMARK / "global_v2_maplight_robustness_execution_claim.json"
D127_CLAIM_SHA256: Final = (
    "da0104bc8d297904fc26e019f1717fee38411d9aa741c774f2185090bcceb334"
)
D126_ACCEPTANCE: Final = (
    BENCHMARK / "global_v2_maplight_robustness_no_fit_acceptance.json"
)
D126_ACCEPTANCE_SHA256: Final = (
    "ca722b265f751ad6efe58017b0106fbca35be4ee04e46d129ed7e8a51c231e0e"
)
SYNTHETIC_SOURCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_scoring_source.v1"
)
CAPABILITY_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_scoring_capability.v1"
)
OFFICIAL_AUTHORIZATION_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_scoring_authorization.v1"
)
OUTPUT_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "standardized_structure_hash",
    "primary_component_hash",
    "source_file",
    "point",
    "low",
    "high",
)
DIRECT_SOURCE_FILE: Final = "cyp-challenge-TRAIN_inhibition.csv"
SYNTHETIC_POPULATION: Final = {
    "all_molecules": 1200,
    "all_endpoint_rows": 4800,
    "development_molecules": 960,
    "development_rows_decoded": 3840,
    "finite_development_point_rows_emitted": 3840,
    "confirmatory_molecules": 240,
    "confirmatory_rows_prefix_checked_suffix_opaque": 960,
    "confirmatory_value_fields_decoded": 0,
}
OFFICIAL_POPULATION: Final = {
    "all_molecules": 4905,
    "all_endpoint_rows": 19620,
    "development_molecules": 3908,
    "development_rows_decoded": 15632,
    "finite_development_point_rows_emitted": 5197,
    "confirmatory_molecules": 997,
    "confirmatory_rows_prefix_checked_suffix_opaque": 3988,
    "confirmatory_value_fields_decoded": 0,
}
DENIED_ACCOUNTING: Final = (
    "official_source_rows_opened",
    "official_target_values_opened",
    "official_feature_rows_opened",
    "official_baseline_rows_opened",
    "official_model_fits",
    "official_predictions_generated",
    "development_metric_evaluations",
    "confirmatory_truth_values_opened",
    "historical_row_level_artifacts_opened",
    "blinded_test_rows_opened",
    "tdi_rows_opened",
    "external_records_acquired",
    "submission_rows_generated",
    "official_metric_calls",
    "leaderboard_observations_used_for_selection",
    "live_uploads",
    "claims_created",
    "claims_consumed",
    "private_portal_observations_recorded",
)


class RobustnessScoringCompilerError(RuntimeError):
    """A parent, row, capability, chronology, or publication check failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RobustnessScoringCompilerError(message)


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _load_json(path: Path) -> dict[str, Any]:
    value, _raw = maplight._load_json(path)
    return cast(dict[str, Any], value)


def _zero_accounting() -> dict[str, int]:
    return {name: 0 for name in DENIED_ACCOUNTING}


def authenticate_static_boundary() -> dict[str, Any]:
    """Authenticate every accepted immutable parent before parsing a row."""

    _require(maplight.sha256_path(CONTRACT) == CONTRACT_SHA256, "contract differs")
    _require(
        maplight.sha256_path(D127_CLAIM) == D127_CLAIM_SHA256,
        "D-127 claim differs",
    )
    claim = _load_json(D127_CLAIM)
    _require(
        claim.get("status") == "G2_7D_MAPLIGHT_ROBUSTNESS_CLAIM_UNCONSUMED"
        and claim.get("consumptions") == 0
        and claim.get("usable") is False
        and all(
            claim.get(name) is None
            for name in (
                "future_scientific_runner_source_sha256",
                "future_official_attempt_driver_source_sha256",
                "future_official_shaped_acceptance_driver_source_sha256",
                "future_official_shaped_execution_acceptance_sha256",
                "future_focused_tests_sha256",
            )
        ),
        "D-127 claim disposition differs",
    )
    _require(
        maplight.sha256_path(D126_ACCEPTANCE) == D126_ACCEPTANCE_SHA256,
        "D-126 acceptance differs",
    )
    _require(
        maplight.sha256_path(capability_compiler.SCRIPT)
        == "029afd827e3a86718e7e2493594bbc6e6ed78e258534221e32acc2027ace72a7",
        "D-126 compiler differs",
    )
    _require(
        tuple(accepted_compiler.DIRECT_COLUMNS)
        == (
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
        ),
        "direct-observation schema differs",
    )
    return {
        "scoring_contract_sha256": CONTRACT_SHA256,
        "d127_claim_sha256": D127_CLAIM_SHA256,
        "d126_acceptance_sha256": D126_ACCEPTANCE_SHA256,
        "d126_compiler_sha256": maplight.sha256_path(capability_compiler.SCRIPT),
    }


def _validate_mode(
    *,
    mode: str,
    direct_source_root: Path,
    authorization: Mapping[str, Any] | None,
) -> None:
    _require(mode in {"synthetic", "official"}, "scoring mode differs")
    if mode == "synthetic":
        _require(authorization is None, "synthetic mode received authorization")
        return
    _require(authorization is not None, "corrected official authorization is absent")
    assert authorization is not None
    _require(
        authorization.get("schema_version") == OFFICIAL_AUTHORIZATION_SCHEMA
        and authorization.get("status") == "G2_7F_SCORING_AUTHORIZED"
        and authorization.get("scoring_contract_sha256") == CONTRACT_SHA256
        and authorization.get("permanently_unusable_d127_claim_sha256")
        == D127_CLAIM_SHA256
        and _is_sha(authorization.get("corrected_consumed_claim_sha256"))
        and _is_sha(authorization.get("corrected_execution_contract_sha256"))
        and authorization.get("official_source_root")
        == str(capability_compiler.OFFICIAL_SOURCE_ROOT)
        and authorization.get("direct_observations_sha256")
        == "00b1ac95cc73dda2699f2f05bc33200d1119a197d7a92ae900cde78d722f00b7",
        "corrected official authorization differs",
    )
    _require(
        direct_source_root.resolve(strict=True)
        == capability_compiler.OFFICIAL_SOURCE_ROOT,
        "official scoring source root differs",
    )


def _source_bytes(
    *, direct_source_root: Path, mode: str
) -> tuple[bytes, str, dict[str, Any] | None]:
    if mode == "synthetic":
        maplight._readonly_root(direct_source_root, "synthetic scoring source")
        _require(
            {path.name for path in direct_source_root.iterdir()}
            == {"direct_observations.csv", "manifest.json"},
            "synthetic scoring source file set differs",
        )
        manifest = _load_json(direct_source_root / "manifest.json")
        direct_path = maplight._regular(
            direct_source_root / "direct_observations.csv",
            "synthetic direct observations",
        )
        raw = direct_path.read_bytes()
        _require(
            manifest.get("schema_version") == SYNTHETIC_SOURCE_SCHEMA
            and manifest.get("synthetic") is True
            and manifest.get("scoring_contract_sha256") == CONTRACT_SHA256
            and _is_sha(manifest.get("semantic_source_id"))
            and manifest.get("population") == SYNTHETIC_POPULATION
            and manifest.get("direct_observations_sha256")
            == maplight.sha256_bytes(raw),
            "synthetic scoring source manifest differs",
        )
        return raw, cast(str, manifest["semantic_source_id"]), manifest

    direct_path = maplight._regular(
        direct_source_root / "direct_observations.csv",
        "official direct observations",
    )
    _require(
        not direct_path.is_symlink() and not bool(direct_path.stat().st_mode & 0o222),
        "official direct observations are mutable",
    )
    raw = direct_path.read_bytes()
    _require(
        maplight.sha256_bytes(raw)
        == "00b1ac95cc73dda2699f2f05bc33200d1119a197d7a92ae900cde78d722f00b7",
        "official direct observations differ",
    )
    return raw, "85f8b358d0a2056a98b990dd75d3b3ec9247862b", None


def _model_identities(
    model_root: Path, *, synthetic: bool
) -> tuple[dict[str, Any], dict[str, tuple[str, str]]]:
    maplight._readonly_root(model_root, "D-126 model capability")
    manifest = _load_json(model_root / "manifest.json")
    _require(
        manifest.get("schema_version") == capability_compiler.MODEL_SCHEMA
        and manifest.get("synthetic") is synthetic
        and manifest.get("bounded_contract_sha256")
        == capability_compiler.BOUNDED_CONTRACT_SHA256
        and manifest.get("parent_contract_sha256")
        == capability_compiler.PARENT_CONTRACT_SHA256
        and manifest.get("compiler_source_sha256")
        == maplight.sha256_path(capability_compiler.SCRIPT)
        and manifest.get("accounting") == capability_compiler._zero_accounting(),
        "D-126 model capability identity differs",
    )
    folds = maplight._read_csv(
        model_root / "folds.csv", capability_compiler.CAPABILITY_FOLD_COLUMNS
    )
    _require(
        maplight.sha256_path(model_root / "folds.csv") == manifest.get("folds_sha256"),
        "D-126 fold receipt differs",
    )
    identities: dict[str, tuple[str, str]] = {}
    repeats: dict[str, set[int]] = {}
    for row in folds:
        if row["group_id"] != "PRIMARY_D032":
            continue
        molecule = row["molecule_id"]
        value = row["standardized_structure_hash"], row["component_hash"]
        _require(
            all(_is_sha(item) for item in value),
            "D-126 structure or component identity differs",
        )
        _require(
            identities.setdefault(molecule, value) == value,
            "D-126 primary identity differs by repeat",
        )
        repeats.setdefault(molecule, set()).add(int(row["repeat"]))
    expected = SYNTHETIC_POPULATION if synthetic else OFFICIAL_POPULATION
    _require(
        len(identities) == manifest.get("molecules") == expected["development_molecules"]
        and all(values == {0, 1, 2} for values in repeats.values()),
        "D-126 development population differs",
    )
    return manifest, identities


def _central_truth(
    scorer_root: Path, *, synthetic: bool
) -> tuple[dict[str, Any], dict[tuple[str, str], float]]:
    maplight._readonly_root(scorer_root, "D-126 scorer capability")
    manifest = _load_json(scorer_root / "manifest.json")
    _require(
        manifest.get("schema_version") == capability_compiler.SCORER_SCHEMA
        and manifest.get("synthetic") is synthetic
        and manifest.get("bounded_contract_sha256")
        == capability_compiler.BOUNDED_CONTRACT_SHA256
        and manifest.get("parent_contract_sha256")
        == capability_compiler.PARENT_CONTRACT_SHA256
        and manifest.get("compiler_source_sha256")
        == maplight.sha256_path(capability_compiler.SCRIPT)
        and manifest.get("confirmatory_target_values_parsed") == 0
        and manifest.get("accounting") == capability_compiler._zero_accounting(),
        "D-126 scorer capability identity differs",
    )
    stage_bytes: list[bytes] = []
    truth: dict[tuple[str, str], float] = {}
    receipts = manifest.get("truth_receipts")
    _require(isinstance(receipts, Mapping), "D-126 truth receipts differ")
    assert isinstance(receipts, Mapping)
    for stage in ("stage_a", "stage_b", "stage_c"):
        path = maplight._regular(scorer_root / f"{stage}_truth.csv", "stage truth")
        raw = path.read_bytes()
        _require(
            maplight.sha256_bytes(raw) == receipts.get(stage),
            "D-126 stage truth receipt differs",
        )
        stage_bytes.append(raw)
        rows = maplight._read_csv(path, capability_compiler.TARGET_COLUMNS)
        observed: dict[tuple[str, str], float] = {}
        for row in rows:
            key = row["molecule_id"], row["endpoint"]
            _require(
                key not in observed and row["endpoint"] in capability_compiler.ENDPOINTS,
                "D-126 central truth key differs",
            )
            observed[key] = maplight._canonical_float(row["point"], "central point")
        if not truth:
            truth = observed
        else:
            _require(observed == truth, "D-126 stage truths differ")
    _require(
        stage_bytes[0] == stage_bytes[1] == stage_bytes[2]
        and len(truth) == manifest.get("truth_rows"),
        "D-126 central truth population differs",
    )
    return manifest, truth


def _direct_prefix(line: bytes) -> tuple[str, str]:
    prefix = line.split(b",", 2)
    _require(len(prefix) == 3, "direct observation prefix differs")
    _require(b'"' not in prefix[0] and b'"' not in prefix[1], "quoted identity prefix")
    try:
        return prefix[0].decode("utf-8"), prefix[1].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RobustnessScoringCompilerError(
            "direct observation identity is not UTF-8"
        ) from exc


def _reported_bounds(row: Mapping[str, str], point: float) -> tuple[str, str]:
    low_text, high_text = row["low"], row["high"]
    if not low_text or not high_text:
        return "", ""
    try:
        low, high = float(low_text), float(high_text)
    except ValueError as exc:
        raise RobustnessScoringCompilerError("reported bound is malformed") from exc
    if not math.isfinite(low) or not math.isfinite(high):
        return "", ""
    _require(low <= point <= high, "reported bounds do not contain point")
    return format(low, ".17g"), format(high, ".17g")


def _compile_rows(
    *,
    raw: bytes,
    identities: Mapping[str, tuple[str, str]],
    truth: Mapping[tuple[str, str], float],
    synthetic: bool,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    _require(b"\r" not in raw, "direct observations contain CR bytes")
    lines = raw.splitlines(keepends=True)
    expected_header = (",".join(accepted_compiler.DIRECT_COLUMNS) + "\n").encode()
    _require(bool(lines) and lines[0] == expected_header, "direct columns differ")
    expected = SYNTHETIC_POPULATION if synthetic else OFFICIAL_POPULATION
    _require(len(lines) - 1 == expected["all_endpoint_rows"], "direct row count differs")
    decoded_keys: set[tuple[str, str]] = set()
    emitted: dict[tuple[str, str], dict[str, object]] = {}
    skipped = 0
    source_values: set[str] = set()
    for physical in lines[1:]:
        _require(physical.endswith(b"\n"), "direct row lacks final LF")
        observation_id, molecule = _direct_prefix(physical[:-1])
        _require(bool(observation_id), "observation identity is empty")
        if molecule not in identities:
            skipped += 1
            continue
        try:
            parsed = next(csv.reader([physical[:-1].decode("utf-8")]))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise RobustnessScoringCompilerError(
                "development direct row cannot be decoded"
            ) from exc
        _require(
            len(parsed) == len(accepted_compiler.DIRECT_COLUMNS),
            "development direct width differs",
        )
        row = dict(zip(accepted_compiler.DIRECT_COLUMNS, parsed, strict=True))
        endpoint = row["endpoint"]
        key = molecule, endpoint
        structure_hash, component_hash = identities[molecule]
        _require(
            row["observation_id"] == observation_id
            and endpoint in capability_compiler.ENDPOINTS
            and key not in decoded_keys
            and row["standardized_structure_hash"] == structure_hash
            and row["similarity_component_hash"] == component_hash,
            "development direct identity differs",
        )
        decoded_keys.add(key)
        source_values.add(row["source_file"])
        eligible = row["point_eligible"] == "true" and row["value_state"] == "complete"
        if eligible:
            _require(key in truth, "eligible point is absent from D-126 truth")
            point = maplight._canonical_float(row["point"], "reported point")
            _require(point == truth[key], "reported point differs from D-126 truth")
            low, high = _reported_bounds(row, point)
            emitted[key] = {
                "molecule_id": molecule,
                "endpoint": endpoint,
                "standardized_structure_hash": structure_hash,
                "primary_component_hash": component_hash,
                "source_file": row["source_file"],
                "point": format(point, ".17g"),
                "low": low,
                "high": high,
            }
        else:
            _require(key not in truth, "D-126 truth contains an ineligible point")

    expected_keys = {
        (molecule, endpoint)
        for molecule in identities
        for endpoint in capability_compiler.ENDPOINTS
    }
    _require(
        decoded_keys == expected_keys
        and len(decoded_keys) == expected["development_rows_decoded"]
        and skipped == expected["confirmatory_rows_prefix_checked_suffix_opaque"]
        and set(emitted) == set(truth)
        and len(emitted) == expected["finite_development_point_rows_emitted"],
        "development/confirmatory scoring population differs",
    )
    _require(
        source_values == {DIRECT_SOURCE_FILE}, "accepted source provenance differs"
    )
    rows = [emitted[key] for key in sorted(emitted)]
    tutorial_eligible = sum(bool(row["low"] and row["high"]) for row in rows)
    return rows, {
        "all_endpoint_rows": len(lines) - 1,
        "development_rows_decoded": len(decoded_keys),
        "finite_development_point_rows_emitted": len(rows),
        "tutorial_eligible_rows": tutorial_eligible,
        "confirmatory_rows_prefix_checked_suffix_opaque": skipped,
        "confirmatory_value_fields_decoded": 0,
    }


def compile_scoring_capability(
    *,
    direct_source_root: Path,
    model_capability_root: Path,
    scorer_capability_root: Path,
    output_root: Path,
    mode: str,
    expected_compiler_sha256: str,
    authorization: Mapping[str, Any] | None = None,
) -> Path:
    """Publish one immutable scorer-only capability without fitting or scoring."""

    _require(
        maplight.sha256_path(SCRIPT) == expected_compiler_sha256,
        "scoring compiler source differs",
    )
    parents = authenticate_static_boundary()
    _validate_mode(
        mode=mode,
        direct_source_root=direct_source_root,
        authorization=authorization,
    )
    synthetic = mode == "synthetic"
    raw, semantic_source_id, source_manifest = _source_bytes(
        direct_source_root=direct_source_root, mode=mode
    )
    model_manifest, identities = _model_identities(
        model_capability_root, synthetic=synthetic
    )
    scorer_manifest, truth = _central_truth(
        scorer_capability_root, synthetic=synthetic
    )
    rows, counts = _compile_rows(
        raw=raw,
        identities=identities,
        truth=truth,
        synthetic=synthetic,
    )
    truth_bytes = maplight.csv_bytes(OUTPUT_COLUMNS, rows)
    accounting = _zero_accounting()
    if synthetic:
        accounting = {
            **accounting,
            "synthetic_source_rows_opened": counts["all_endpoint_rows"],
            "synthetic_development_rows_decoded": counts[
                "development_rows_decoded"
            ],
            "synthetic_scoring_rows_emitted": counts[
                "finite_development_point_rows_emitted"
            ],
        }
    manifest = {
        "schema_version": CAPABILITY_SCHEMA,
        "status": (
            "G2_7E_SYNTHETIC_SCORING_CAPABILITY_FROZEN"
            if synthetic
            else "G2_7E_DEVELOPMENT_SCORING_CAPABILITY_FROZEN"
        ),
        "synthetic": synthetic,
        **parents,
        "scoring_compiler_source_sha256": expected_compiler_sha256,
        "semantic_source_id": semantic_source_id,
        "source_capability_schema": (
            SYNTHETIC_SOURCE_SCHEMA
            if source_manifest is not None
            else "accepted_fixed_official_source"
        ),
        "d126_model_manifest_sha256": maplight.sha256_path(
            model_capability_root / "manifest.json"
        ),
        "d126_scorer_manifest_sha256": maplight.sha256_path(
            scorer_capability_root / "manifest.json"
        ),
        "d126_science_identity_sha256": model_manifest["science_identity_sha256"],
        "d126_scorer_science_identity_sha256": scorer_manifest[
            "science_identity_sha256"
        ],
        "output_columns": list(OUTPUT_COLUMNS),
        "counts": counts,
        "source_file_values": [DIRECT_SOURCE_FILE],
        "output_receipts": {
            "scoring_truth.csv": maplight.sha256_bytes(truth_bytes)
        },
        "confirmatory_suffixes_opaque": True,
        "model_capability_fields": 0,
        "feature_arrays": 0,
        "training_target_files": 0,
        "real_catboost_fits": 0,
        "development_metric_evaluations": 0,
        "model_quality_authority": False,
        "claim_authority": False,
        "accounting": accounting,
        "authority": dict(maplight.DENIED_AUTHORITY),
    }
    _require(
        model_manifest["science_identity_sha256"]
        == scorer_manifest["science_identity_sha256"],
        "D-126 model/scorer science binding differs",
    )
    return cast(
        Path,
        maplight.publish_files(
            output_root,
            {
                "scoring_truth.csv": truth_bytes,
                "manifest.json": maplight.json_bytes(manifest),
            },
        ),
    )


__all__ = [
    "CAPABILITY_SCHEMA",
    "CONTRACT_SHA256",
    "DIRECT_SOURCE_FILE",
    "OFFICIAL_AUTHORIZATION_SCHEMA",
    "OFFICIAL_POPULATION",
    "OUTPUT_COLUMNS",
    "RobustnessScoringCompilerError",
    "SCRIPT",
    "SYNTHETIC_POPULATION",
    "SYNTHETIC_SOURCE_SCHEMA",
    "authenticate_static_boundary",
    "compile_scoring_capability",
]
