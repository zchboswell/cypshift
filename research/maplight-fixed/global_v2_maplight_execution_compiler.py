#!/usr/bin/env python3
"""Compile sparse, development-only G2-2C MapLight capabilities."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_runner as runner
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
EXECUTION_CONTRACT: Final = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_v2_maplight_execution_contract.json"
)
EXECUTION_CONTRACT_SHA256: Final = (
    "962484b7e8f20ca9b9e37735e82c4db62766116a47c49c44dbc90d14db7985c2"
)
TRACKED_CLAIM: Final = EXECUTION_CONTRACT.with_name(
    "global_v2_maplight_execution_claim.json"
)
TRACKED_CLAIM_SHA256: Final = (
    "59d7d6915fc3f9e8ae0cb1fef2af805eb3d4d68c641091d518e4e02683730659"
)
OFFICIAL_WRAPPER: Final = SCRIPT.with_name("global_v2_maplight_execution_wrapper.py")
TRACKED_ACCEPTANCE: Final = EXECUTION_CONTRACT.with_name(
    "global_v2_maplight_execution_synthetic_acceptance.json"
)
OFFICIAL_SOURCE_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/g2-2c-maplight-development-source-v1"
)
G2A_CONTRACT_SHA256: Final = runner.CONTRACT_SHA256
SOURCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_source.v1"
)
MODEL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_model_capability.v1"
)
SCORER_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_scorer_capability.v1"
)
PREFLIGHT_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_preflight.v1"
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


def _authority(synthetic: bool) -> dict[str, bool]:
    authority = dict(runner.DENIED_AUTHORITY)
    if not synthetic:
        authority.update(
            {
                "official_target_access": True,
                "official_feature_access": True,
            }
        )
    return authority


def _validate_consumed_claim(
    claim: Mapping[str, Any], expected_compiler_sha256: str
) -> dict[str, str]:
    receipts = claim.get("official_input_receipts")
    _require(
        claim.get("schema_version")
        == "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_claim.v1"
        and claim.get("status") == "G2_2C_CLAIM_CONSUMED"
        and claim.get("claim_id") == "g2-2c-maplight-development-attempt-1"
        and claim.get("contract_sha256") == EXECUTION_CONTRACT_SHA256
        and claim.get("runner_source_sha256") == runner.sha256_path(runner.SCRIPT)
        and claim.get("runtime_lock_sha256") == runner.LOCK_SHA256
        and claim.get("future_official_compiler_source_sha256")
        == expected_compiler_sha256
        and claim.get("future_attempt_wrapper_source_sha256")
        == runner.sha256_path(OFFICIAL_WRAPPER)
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
            "status": "G2_2C_CLAIM_CONSUMED",
            "future_official_compiler_source_sha256": expected_compiler_sha256,
            "future_attempt_wrapper_source_sha256": runner.sha256_path(
                OFFICIAL_WRAPPER
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
        manifest.get("authority") == _authority(False),
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


def publish_official_source(
    *,
    r2b_root: Path,
    r3a_root: Path,
    output_root: Path,
    consumed_claim: Mapping[str, Any],
    expected_compiler_sha256: str,
) -> Path:
    """Publish the fixed, authenticated R2B/R3A source view without parsing it."""

    claim_receipts = _validate_consumed_claim(consumed_claim, expected_compiler_sha256)
    _require(
        runner.sha256_path(SCRIPT) == expected_compiler_sha256,
        "compiler source receipt differs",
    )
    _require(
        runner.sha256_path(EXECUTION_CONTRACT) == EXECUTION_CONTRACT_SHA256,
        "execution contract receipt differs",
    )
    _require(
        output_root == OFFICIAL_SOURCE_ROOT,
        "official source root is not the frozen private root",
    )
    resolved_output = output_root.parent.resolve(strict=True) / output_root.name
    repository = ROOT.resolve(strict=True)
    _require(
        resolved_output != repository and repository not in resolved_output.parents,
        "official source root is inside Git",
    )
    runner._destination(output_root)
    runner._readonly_root(r2b_root, "accepted R2B root")
    runner._readonly_root(r3a_root, "accepted R3A root")
    _require(
        runner.sha256_path(runner._regular(r2b_root / "manifest.json", "R2B manifest"))
        == claim_receipts["r2b_manifest_sha256"],
        "R2B parent manifest receipt differs",
    )
    _require(
        runner.sha256_path(runner._regular(r3a_root / "manifest.json", "R3A manifest"))
        == claim_receipts["r3a_feature_manifest_sha256"],
        "R3A parent manifest receipt differs",
    )
    parents = {
        "direct_observations.csv": r2b_root / "direct_observations.csv",
        "group_folds.csv": r2b_root / "group_folds.csv",
        "feature_rows.csv": r3a_root / "feature_rows.csv",
        "maplight_morgan_count.npy": r3a_root / "maplight_morgan_count.npy",
        "maplight_avalon_count.npy": r3a_root / "maplight_avalon_count.npy",
        "maplight_erg.npy": r3a_root / "maplight_erg.npy",
        "maplight_rdkit_descriptors.npy": (r3a_root / "maplight_rdkit_descriptors.npy"),
    }
    files: dict[str, bytes] = {}
    for name, path in parents.items():
        data = runner._regular(path, f"official source {name}").read_bytes()
        _require(
            runner.sha256_bytes(data) == claim_receipts[OFFICIAL_RECEIPT_KEYS[name]],
            f"official source receipt differs: {name}",
        )
        files[name] = data
    manifest = {
        "schema_version": SOURCE_SCHEMA,
        "synthetic": False,
        "semantic_source_id": claim_receipts["dataset_revision"],
        "source_receipts": {
            name: claim_receipts[key] for name, key in OFFICIAL_RECEIPT_KEYS.items()
        },
        "parent_receipts": {
            name: claim_receipts[key]
            for name, key in OFFICIAL_PARENT_RECEIPT_KEYS.items()
        },
        "label_free_counts": {
            "all_molecules": 4905,
            "all_components": 4553,
            "development_molecules": 3908,
            "development_components": 3640,
            "confirmatory_molecules": 997,
            "confirmatory_components": 913,
        },
        "authority": _authority(False),
    }
    return cast(
        Path,
        runner.publish_files(
            output_root, {**files, "manifest.json": runner.json_bytes(manifest)}
        ),
    )


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
) -> tuple[dict[tuple[str, str], float], dict[str, int]]:
    _require(b"\r" not in data, "direct observations contain CR bytes")
    lines = data.splitlines(keepends=True)
    expected_header = (",".join(DIRECT_COLUMNS) + "\n").encode("utf-8")
    _require(bool(lines) and lines[0] == expected_header, "direct columns differ")
    truth: dict[tuple[str, str], float] = {}
    seen: set[tuple[str, str]] = set()
    development_rows = 0
    confirmatory_rows_opaque = 0
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
        eligible = row["point_eligible"] == "true" and row["value_state"] == "complete"
        if eligible:
            point = runner._canonical_float(row["point"], "development point")
            truth[key] = point
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
        "development_finite_targets": len(truth),
        "confirmatory_rows_kept_opaque": confirmatory_rows_opaque,
        "confirmatory_target_values_parsed": 0,
    }


def _support(
    truth: Mapping[tuple[str, str], float],
    folds: list[dict[str, str]],
    minima: Mapping[str, int],
) -> dict[str, object]:
    fold_index = {
        (row["molecule_id"], int(row["repeat"]), int(row["outer_validation_fold"])): row
        for row in folds
    }
    finite_by_endpoint = {
        endpoint: sum(1 for molecule, observed in truth if observed == endpoint)
        for endpoint in runner.ENDPOINTS
    }
    outer_counts: dict[str, int] = {}
    inner_counts: dict[str, int] = {}
    failures: list[str] = []
    finite_minimum = int(minima["development_finite_targets_per_endpoint"])
    outer_minimum = int(minima["outer_validation_targets_per_endpoint_repeat_fold"])
    inner_minimum = int(
        minima["inner_training_targets_per_endpoint_repeat_outer_inner"]
    )
    for endpoint, count in finite_by_endpoint.items():
        if count < finite_minimum:
            failures.append(f"finite:{endpoint}:{count}")
        molecules = sorted(
            molecule for molecule, observed in truth if observed == endpoint
        )
        for repeat in runner.REPEATS:
            for outer in runner.OUTER_FOLDS:
                outer_count = sum(
                    int(fold_index[(molecule, repeat, outer)]["outer_fold"]) == outer
                    for molecule in molecules
                )
                outer_key = f"{endpoint}|{repeat}|{outer}"
                outer_counts[outer_key] = outer_count
                if outer_count < outer_minimum:
                    failures.append(f"outer:{outer_key}:{outer_count}")
                for inner in runner.INNER_FOLDS:
                    inner_count = sum(
                        int(fold_index[(molecule, repeat, outer)]["outer_fold"])
                        != outer
                        and int(fold_index[(molecule, repeat, outer)]["inner_fold"])
                        != inner
                        for molecule in molecules
                    )
                    inner_key = f"{endpoint}|{repeat}|{outer}|{inner}"
                    inner_counts[inner_key] = inner_count
                    if inner_count < inner_minimum:
                        failures.append(f"inner:{inner_key}:{inner_count}")
    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": "G2_2C_PREFLIGHT_PASS" if not failures else "G2_2_UNDERPOWERED",
        "minimum_support": dict(minima),
        "finite_targets_per_endpoint": finite_by_endpoint,
        "outer_validation_targets": outer_counts,
        "inner_training_targets": inner_counts,
        "failures": failures,
        "maplight_model_fits": 0,
    }


def compile_capabilities(
    *,
    source_root: Path,
    output_root: Path,
    expected_compiler_sha256: str,
    mode: str = "synthetic",
    consumed_claim_path: Path | None = None,
) -> tuple[Path, Path, dict[str, object]]:
    """Compile one authenticated source root into disjoint capabilities."""

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
            manifest.get("semantic_source_id") == "g2-2c-official-shaped-synthetic-v1",
            "synthetic source identity differs",
        )
        _require(
            manifest.get("authority") == runner.DENIED_AUTHORITY,
            "synthetic source authority differs",
        )
    else:
        assert claim_receipts is not None
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
        source["direct_observations.csv"],
        development,
        confirmatory,
        components,
    )
    preflight = _support(
        truth, folds, SYNTHETIC_MINIMA if synthetic else OFFICIAL_MINIMA
    )
    official_source_receipts = dict(claim_receipts or {})
    preflight["accounting"] = {
        **target_accounting,
        "official_target_values_opened": 0 if synthetic else len(truth),
        "official_features_opened": (
            0 if synthetic else (len(development) + len(confirmatory)) * 2563
        ),
        "official_model_fits": 0,
        "official_predictions_generated": 0,
        "official_residual_values_computed": 0,
        "official_diagnostics_computed": 0,
        "official_metric_evaluations": 0,
        "confirmatory_truth_values_opened": 0,
        "external_records_acquired": 0,
        "live_uploads": 0,
    }
    if preflight["status"] != "G2_2C_PREFLIGHT_PASS":
        raise MapLightExecutionUnderpowered(preflight, official_source_receipts)
    feature_bytes = runner.csv_bytes(runner.FEATURE_COLUMNS, feature_rows)
    fold_bytes = runner.csv_bytes(runner.FOLD_COLUMNS, folds)
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
            and array.flags.c_contiguous,
            f"source array differs: {name}",
        )
        selected = np.ascontiguousarray(array[development_indices])
        payload = _npy_bytes(selected)
        model_files[name] = payload
        arrays[name] = {
            "sha256": runner.sha256_bytes(payload),
            "shape": [len(development), width],
            "dtype": str(dtype),
        }
    fold_scopes = {
        (row["molecule_id"], int(row["repeat"]), int(row["outer_validation_fold"])): row
        for row in folds
    }
    target_rows = 0
    for stage in ("outer", "inner"):
        for endpoint in runner.ENDPOINTS:
            eligible = {
                molecule for molecule, observed in truth if observed == endpoint
            }
            for repeat in runner.REPEATS:
                for outer in runner.OUTER_FOLDS:
                    scope = {
                        molecule: fold_scopes[(molecule, repeat, outer)]
                        for molecule in development
                    }
                    inners = (None,) if stage == "outer" else tuple(runner.INNER_FOLDS)
                    for inner in inners:
                        training, _prediction = runner._cell_ids(
                            scope, stage, outer, inner
                        )
                        rows = [
                            {
                                "molecule_id": molecule,
                                "point": format(truth[(molecule, endpoint)], ".17g"),
                            }
                            for molecule in training
                            if molecule in eligible
                        ]
                        target_rows += len(rows)
                        path = runner._cell_target_path(
                            Path("."), stage, endpoint, repeat, outer, inner
                        )
                        model_files[path.as_posix()] = runner.csv_bytes(
                            runner.TARGET_COLUMNS, rows
                        )
    target_material = "".join(
        f"{name}|{runner.sha256_bytes(value)}\n"
        for name, value in sorted(model_files.items())
        if name.startswith("targets/")
    ).encode("utf-8")
    model_manifest = {
        "schema_version": MODEL_SCHEMA,
        "execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
        "g2a_contract_sha256": G2A_CONTRACT_SHA256,
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
        "accounting": {
            **target_accounting,
            "official_target_values_opened": 0 if synthetic else len(truth),
            "official_features_opened": (
                0 if synthetic else (len(development) + len(confirmatory)) * 2563
            ),
            "official_model_fits": 0,
            "official_predictions_generated": 0,
            "official_residual_values_computed": 0,
            "official_diagnostics_computed": 0,
            "official_metric_evaluations": 0,
            "confirmatory_truth_values_opened": 0,
            "historical_r3c_row_level_artifacts_opened": 0,
            "blinded_test_files_opened": 0,
            "tdi_files_opened": 0,
            "tutorial_ma_st_rae_calls": 0,
            "external_records_acquired": 0,
            "submissions_created": 0,
            "leaderboard_observations": 0,
            "live_uploads": 0,
        },
        "authority": _authority(synthetic),
    }
    truth_rows = [
        {
            "molecule_id": molecule,
            "endpoint": endpoint,
            "similarity_component_hash": components[molecule],
            "point": format(point, ".17g"),
        }
        for (molecule, endpoint), point in sorted(truth.items())
    ]
    truth_bytes = runner.csv_bytes(runner.TRUTH_COLUMNS, truth_rows)
    try:
        output_root.mkdir(parents=True)
        model_files["manifest.json"] = runner.json_bytes(model_manifest)
        model_root = runner.publish_files(output_root / "model-capability", model_files)
        scorer_manifest = {
            "schema_version": SCORER_SCHEMA,
            "execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
            "g2a_contract_sha256": G2A_CONTRACT_SHA256,
            "compiler_source_sha256": expected_compiler_sha256,
            "model_capability_manifest_sha256": runner.sha256_path(
                model_root / "manifest.json"
            ),
            "synthetic": synthetic,
            "semantic_source_id": manifest["semantic_source_id"],
            "official_source_receipts": official_source_receipts,
            "truth_sha256": runner.sha256_bytes(truth_bytes),
            "truth_rows": len(truth_rows),
            "model_training_files": 0,
            "feature_arrays": 0,
            "confirmatory_truth_values": 0,
            "accounting": {
                "confirmatory_truth_values_opened": 0,
                "historical_r3c_row_level_artifacts_opened": 0,
                "blinded_test_files_opened": 0,
                "tdi_files_opened": 0,
                "tutorial_ma_st_rae_calls": 0,
                "official_metric_evaluations": 0,
                "official_model_fits": 0,
                "official_predictions_generated": 0,
                "official_residual_values_computed": 0,
                "official_diagnostics_computed": 0,
                "external_records_acquired": 0,
                "submissions_created": 0,
                "leaderboard_observations": 0,
                "live_uploads": 0,
            },
            "authority": _authority(synthetic),
        }
        scorer_root = runner.publish_files(
            output_root / "scorer-capability",
            {
                "truth.csv": truth_bytes,
                "manifest.json": runner.json_bytes(scorer_manifest),
            },
        )
        runner.publish_files(
            output_root / "preflight",
            {"preflight.json": runner.json_bytes(preflight)},
        )
        return model_root, scorer_root, preflight
    except BaseException:
        runner._cleanup(output_root)
        raise


__all__ = [
    "EXECUTION_CONTRACT_SHA256",
    "MODEL_SCHEMA",
    "MapLightExecutionCompilerError",
    "MapLightExecutionUnderpowered",
    "SCORER_SCHEMA",
    "SOURCE_SCHEMA",
    "SYNTHETIC_MINIMA",
    "authenticate_official_source",
    "compile_capabilities",
    "publish_official_source",
]
