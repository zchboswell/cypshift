#!/usr/bin/env python3
"""Compile least-privilege G2-7C MapLight robustness capabilities.

This implementation is derived from the frozen D-122 scientific contract and
the accepted MapLight publication primitives.  It does not import or execute
the rejected G2-7B implementation.  The current accepted operation is
synthetic, no-fit capability compilation only; official authority remains
closed until a later immutable claim authenticates this exact source.
"""

from __future__ import annotations

import importlib.metadata
import io
import math
import platform
from collections import defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_execution_compiler as accepted_compiler
import global_v2_maplight_runner as maplight
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
BENCHMARK: Final = ROOT / "benchmarks" / "openadmet_cyp_2026"
PARENT_CONTRACT: Final = BENCHMARK / "global_v2_maplight_robustness_contract.json"
PARENT_CONTRACT_SHA256: Final = (
    "ad9aef871ab06e5082568f20a9a6d293897924bdfeda2fb341685cffaa7a45af"
)
BOUNDED_CONTRACT: Final = (
    BENCHMARK / "global_v2_maplight_robustness_bounded_execution_contract.json"
)
BOUNDED_CONTRACT_SHA256: Final = (
    "55fafa1d9806ba3221c26b8cd71d077ad61a0f485e51defbae21cbd4b5806527"
)
SOURCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_source.v1"
)
CAPABILITY_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_capabilities.v1"
)
MODEL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_model_capability.v1"
)
SCORER_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_scorer_capability.v1"
)
OFFICIAL_AUTHORIZATION_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_authorization.v1"
)
OFFICIAL_SOURCE_ROOT: Final = accepted_compiler.OFFICIAL_SOURCE_ROOT
ENDPOINTS: Final = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
REPEATS: Final = range(3)
OUTER_FOLDS: Final = range(5)
REPEAT_SEEDS: Final = (20260810, 20260811, 20260812)
GROUPS: Final = (
    "PRIMARY_D032",
    "THRESHOLD_0_55",
    "THRESHOLD_0_50",
    "TAUTOMER_MERGED",
)
GROUP_COLUMNS: Final = {
    "PRIMARY_D032": "primary_component_hash",
    "THRESHOLD_0_55": "threshold_0_55_component_hash",
    "THRESHOLD_0_50": "threshold_0_50_component_hash",
    "TAUTOMER_MERGED": "tautomer_component_hash",
}
CANDIDATES: Final = (
    "G2-7-M0-FULL",
    "G2-7-M1-DROP-MORGAN",
    "G2-7-M2-DROP-AVALON",
    "G2-7-M3-DROP-ERG",
    "G2-7-M4-DROP-DESCRIPTORS",
)
SEED_PERTURBATIONS: Final = (
    2026082411,
    2026082412,
    2026082413,
    2026082414,
    2026082415,
)
MOLECULE_COLUMNS: Final = (
    "molecule_id",
    "standardized_structure_hash",
    "standardized_smiles",
    "primary_component_hash",
    "threshold_0_55_component_hash",
    "threshold_0_50_component_hash",
    "tautomer_component_hash",
    "tautomer_key",
    "confirmatory",
)
PRIMARY_FOLD_COLUMNS: Final = (
    "molecule_id",
    "repeat",
    "outer_fold",
)
TARGET_COLUMNS: Final = ("molecule_id", "endpoint", "point")
CAPABILITY_FOLD_COLUMNS: Final = (
    "molecule_id",
    "standardized_structure_hash",
    "group_id",
    "component_hash",
    "repeat",
    "outer_fold",
)
FEATURE_FILES: Final = (
    ("maplight_morgan_count.npy", 1024, np.dtype("int8")),
    ("maplight_avalon_count.npy", 1024, np.dtype("int8")),
    ("maplight_erg.npy", 315, np.dtype("<f8")),
    ("maplight_rdkit_descriptors.npy", 200, np.dtype("<f8")),
)
OVERLAY_FINGERPRINT_FILE: Final = "overlay_morgan_4096_packed.npy"
SOURCE_FILES: Final = (
    "molecules.csv",
    "primary_folds.csv",
    "targets.csv",
    OVERLAY_FINGERPRINT_FILE,
    *(item[0] for item in FEATURE_FILES),
)
MINIMA: Final = {
    "development_finite_targets_per_endpoint": 750,
    "outer_validation_targets_per_endpoint_repeat_fold": 75,
    "outer_training_targets_per_endpoint_repeat_fold": 400,
}
DENIED_ACCOUNTING: Final = (
    "official_source_rows_opened",
    "official_target_values_opened",
    "official_feature_rows_opened",
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


class RobustnessExecutionCompilerError(RuntimeError):
    """A source, family, capability, authority, or publication check failed."""


class RobustnessExecutionUnderpowered(RobustnessExecutionCompilerError):
    """A frozen D-122 support minimum failed before publication."""

    def __init__(self, preflight: Mapping[str, Any]) -> None:
        super().__init__("robustness source is underpowered")
        self.preflight = dict(preflight)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RobustnessExecutionCompilerError(message)


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _load_json(path: Path) -> dict[str, Any]:
    value, _raw = maplight._load_json(path)
    return value


def _read_csv(path: Path, columns: Sequence[str]) -> list[dict[str, str]]:
    return maplight._read_csv(path, columns)


def _zero_accounting() -> dict[str, int]:
    return {name: 0 for name in DENIED_ACCOUNTING}


def _npy_bytes(array: np.ndarray[Any, Any]) -> bytes:
    stream = io.BytesIO()
    np.lib.format.write_array(
        stream, np.ascontiguousarray(array), version=(1, 0), allow_pickle=False
    )
    return stream.getvalue()


def _component_digest(group_id: str, structure_hashes: Sequence[str]) -> str:
    _require(bool(structure_hashes), "component membership is empty")
    material = f"g2-7c-component-v1|{group_id}|" + "|".join(sorted(structure_hashes))
    return sha256(material.encode()).hexdigest()


def _similarity_components(
    *,
    structure_hashes: Sequence[str],
    packed_fingerprints: np.ndarray[Any, Any],
    threshold: float,
    group_id: str,
) -> dict[str, str]:
    """Build inclusive-Tanimoto connected components deterministically."""

    _require(
        len(structure_hashes) == len(set(structure_hashes))
        and packed_fingerprints.shape == (len(structure_hashes), 512)
        and packed_fingerprints.dtype == np.uint8
        and threshold in {0.55, 0.50},
        "overlay fingerprint input differs",
    )
    parent = list(range(len(structure_hashes)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    popcount = np.asarray([index.bit_count() for index in range(256)], dtype=np.uint8)
    bit_counts = popcount[packed_fingerprints].sum(axis=1, dtype=np.int64)
    _require(bool(np.all(bit_counts > 0)), "overlay fingerprint is empty")
    for index in range(len(structure_hashes) - 1):
        intersections = popcount[
            np.bitwise_and(packed_fingerprints[index], packed_fingerprints[index + 1 :])
        ].sum(axis=1, dtype=np.int64)
        unions = bit_counts[index] + bit_counts[index + 1 :] - intersections
        similarities = intersections / unions
        for offset in np.flatnonzero(similarities >= threshold):
            union(index, index + 1 + int(offset))
    members: dict[int, list[str]] = defaultdict(list)
    for index, structure_hash in enumerate(structure_hashes):
        members[find(index)].append(structure_hash)
    result: dict[str, str] = {}
    for values in members.values():
        digest = _component_digest(group_id, values)
        for structure_hash in values:
            result[structure_hash] = digest
    _require(set(result) == set(structure_hashes), "overlay components are incomplete")
    return result


def _tautomer_components(
    *,
    structure_primary: Mapping[str, str],
    structure_tautomer: Mapping[str, str],
) -> dict[str, str]:
    """Merge primary components connected by one canonical-tautomer key."""

    primary_ids = sorted(set(structure_primary.values()))
    positions = {component: index for index, component in enumerate(primary_ids)}
    parent = list(range(len(primary_ids)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    by_tautomer: dict[str, set[str]] = defaultdict(set)
    for structure_hash, tautomer_key in structure_tautomer.items():
        _require(_is_sha(tautomer_key), "tautomer key differs")
        by_tautomer[tautomer_key].add(structure_primary[structure_hash])
    for components in by_tautomer.values():
        ordered = sorted(components)
        for component in ordered[1:]:
            union(positions[ordered[0]], positions[component])
    merged: dict[int, list[str]] = defaultdict(list)
    for component in primary_ids:
        merged[find(positions[component])].append(component)
    primary_to_overlay: dict[str, str] = {}
    for components in merged.values():
        digest = _component_digest("TAUTOMER_MERGED", components)
        for component in components:
            primary_to_overlay[component] = digest
    return {
        structure_hash: primary_to_overlay[primary]
        for structure_hash, primary in structure_primary.items()
    }


def _canonical_point(value: str) -> float:
    try:
        point = float(value)
    except ValueError as exc:
        raise RobustnessExecutionCompilerError(
            "development target is not numeric"
        ) from exc
    _require(
        math.isfinite(point) and value == format(point, ".17g"),
        "development target is nonfinite or noncanonical",
    )
    return point


def _source_bytes(root: Path, manifest: Mapping[str, Any]) -> dict[str, bytes]:
    receipts = manifest.get("source_receipts")
    _require(isinstance(receipts, Mapping), "source receipts differ")
    _require(set(receipts) == set(SOURCE_FILES), "source receipt set differs")
    observed = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    _require(observed == {*SOURCE_FILES, "manifest.json"}, "source file set differs")
    loaded: dict[str, bytes] = {}
    for name in SOURCE_FILES:
        path = maplight._regular(root / name, f"source {name}")
        raw = path.read_bytes()
        _require(
            maplight.sha256_bytes(raw) == receipts.get(name), f"{name} receipt differs"
        )
        loaded[name] = raw
    return loaded


def _science_identity(parent: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fixed_maplight": parent["fixed_maplight"],
        "drop_one_candidates": parent["drop_one_candidates"],
        "stage_a_selection": parent["stage_a_selection"],
        "stage_b_selected_robustness": parent["stage_b_selected_robustness"],
        "stage_c_conditional_selected_seed_check": parent[
            "stage_c_conditional_selected_seed_check"
        ],
        "diagnostics_without_additional_fits": parent[
            "diagnostics_without_additional_fits"
        ],
        "metrics": parent["metrics"],
        "robustness_acceptance": parent["robustness_acceptance"],
        "workload": parent["workload"],
        "terminal_contract": parent["terminal_contract"],
    }


def authenticate_static_boundary() -> dict[str, Any]:
    """Authenticate D-122/D-125 and prove rejected-source non-reuse."""

    _require(
        maplight.sha256_path(PARENT_CONTRACT) == PARENT_CONTRACT_SHA256,
        "D-122 contract receipt differs",
    )
    _require(
        maplight.sha256_path(BOUNDED_CONTRACT) == BOUNDED_CONTRACT_SHA256,
        "D-125 contract receipt differs",
    )
    bounded = _load_json(BOUNDED_CONTRACT)
    parent = _load_json(PARENT_CONTRACT)
    primitives = bounded["accepted_runtime_primitives"]
    for item in ("runner", "official_compiler", "official_wrapper", "research_uv_lock"):
        receipt = cast(Mapping[str, str], primitives[item])
        _require(
            maplight.sha256_path(ROOT / receipt["path"]) == receipt["sha256"],
            f"accepted primitive differs: {item}",
        )
    rejected = cast(Mapping[str, Any], bounded["rejected_g2_7b_non_reuse"])
    for role in ("runner", "driver"):
        path = ROOT / cast(str, rejected[f"{role}_path"])
        _require(
            maplight.sha256_path(path) == rejected[f"{role}_sha256"],
            f"rejected {role} history differs",
        )
        _require(
            maplight.sha256_path(SCRIPT) != rejected[f"{role}_sha256"],
            f"compiler reuses rejected {role}",
        )
    inherited = bounded["exact_scientific_inheritance"]
    _require(
        inherited["default_candidate"] == parent["fixed_maplight"]["candidate_id"]
        and inherited["drop_one_candidates"]
        == [item["candidate_id"] for item in parent["drop_one_candidates"]]
        and inherited["seed_perturbation_values"]
        == parent["stage_a_selection"]["seed_perturbation_values"]
        and inherited["group_perturbations"]
        == [
            item["id"]
            for item in parent["stage_b_selected_robustness"]["group_perturbations"]
        ],
        "D-122 scientific inheritance differs",
    )
    return _science_identity(parent)


def _validate_authorization(
    authorization: Mapping[str, Any] | None,
    *,
    mode: str,
    source_root: Path,
) -> None:
    if mode == "synthetic":
        _require(authorization is None, "synthetic compilation has authorization")
        return
    _require(mode == "official", "compiler mode differs")
    _require(source_root == OFFICIAL_SOURCE_ROOT, "official source root differs")
    _require(isinstance(authorization, Mapping), "official authorization is absent")
    assert authorization is not None
    receipts = authorization.get("official_input_receipts")
    _require(
        authorization.get("schema_version") == OFFICIAL_AUTHORIZATION_SCHEMA
        and authorization.get("status") == "G2_7C_OFFICIAL_AUTHORIZED"
        and authorization.get("bounded_contract_sha256") == BOUNDED_CONTRACT_SHA256
        and authorization.get("compiler_source_sha256") == maplight.sha256_path(SCRIPT)
        and _is_sha(authorization.get("claim_sha256"))
        and _is_sha(authorization.get("claim_contract_sha256"))
        and authorization.get("maximum_consumptions") == 1,
        "official authorization differs",
    )
    _require(isinstance(receipts, Mapping), "official input receipts are absent")
    parent_inputs = _load_json(PARENT_CONTRACT)["accepted_inputs"]
    required = (
        "dataset_revision",
        "direct_observations_sha256",
        "group_folds_sha256",
        "feature_rows_sha256",
        "maplight_morgan_count_sha256",
        "maplight_avalon_count_sha256",
        "maplight_erg_sha256",
        "maplight_rdkit_descriptors_sha256",
    )
    _require(
        all(receipts.get(key) == parent_inputs[key] for key in required),
        "official authorization receipts differ from D-122",
    )
    _require(
        platform.python_version() == "3.12.3"
        and importlib.metadata.version("rdkit") == "2026.3.5"
        and maplight.sha256_path(ROOT / "uv.lock")
        == "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6"
        and maplight.sha256_path(ROOT / "src/cypshift/chemistry.py")
        == "21d8df35f001c790290d3ef2c836c9f459015b5db0f48c8f6e44436f9181103a",
        "trusted official compiler runtime differs",
    )


def _validate_source_manifest(
    manifest: Mapping[str, Any], *, mode: str, source_root: Path
) -> None:
    expected_synthetic = mode == "synthetic"
    _require(
        manifest.get("schema_version") == SOURCE_SCHEMA
        and manifest.get("synthetic") is expected_synthetic
        and manifest.get("bounded_contract_sha256") == BOUNDED_CONTRACT_SHA256
        and manifest.get("parent_contract_sha256") == PARENT_CONTRACT_SHA256
        and _is_sha(manifest.get("semantic_source_id")),
        "source manifest identity differs",
    )
    if mode == "official":
        _require(source_root == OFFICIAL_SOURCE_ROOT, "official source root differs")
        _require(
            manifest.get("population")
            == {
                "all_molecules": 4905,
                "development_molecules": 3908,
                "confirmatory_molecules": 997,
            },
            "official population differs",
        )


def _csv_prefix(line: bytes, fields_required: int) -> list[str]:
    """Decode only a fixed CSV prefix, leaving all later bytes opaque."""

    fields: list[bytes] = []
    field = bytearray()
    quoted = False
    index = 0
    while index < len(line):
        value = line[index]
        if quoted:
            if value == 0x22:
                if index + 1 < len(line) and line[index + 1] == 0x22:
                    field.append(0x22)
                    index += 2
                    continue
                quoted = False
            else:
                field.append(value)
        elif value == 0x22 and not field:
            quoted = True
        elif value == 0x2C:
            fields.append(bytes(field))
            field.clear()
            if len(fields) == fields_required:
                break
        else:
            field.append(value)
        index += 1
    _require(
        len(fields) == fields_required and not quoted,
        "direct structure prefix differs",
    )
    try:
        return [value.decode("utf-8") for value in fields]
    except UnicodeDecodeError as exc:
        raise RobustnessExecutionCompilerError(
            "direct structure prefix is not UTF-8"
        ) from exc


def _rdkit_overlay_inputs(
    structures: Mapping[str, str],
) -> tuple[np.ndarray[Any, Any], dict[str, str]]:
    """Compile exact D-122 fingerprints and canonical-tautomer keys."""

    from rdkit import Chem, DataStructs, rdBase
    from rdkit.Chem import rdFingerprintGenerator
    from rdkit.Chem.MolStandardize import rdMolStandardize

    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=2, fpSize=4096, includeChirality=True
    )
    enumerator = rdMolStandardize.TautomerEnumerator()
    ordered = sorted(structures)
    packed = np.empty((len(ordered), 512), dtype=np.uint8)
    tautomer_keys: dict[str, str] = {}
    with rdBase.BlockLogs():
        for index, structure_hash in enumerate(ordered):
            molecule = Chem.MolFromSmiles(structures[structure_hash])
            _require(molecule is not None, "accepted standardized structure is invalid")
            assert molecule is not None
            fingerprint = generator.GetFingerprint(molecule)
            binary = DataStructs.BitVectToBinaryText(fingerprint)
            _require(len(binary) == 512, "RDKit overlay fingerprint width differs")
            packed[index] = np.frombuffer(binary, dtype=np.uint8)
            canonical = enumerator.Canonicalize(molecule)
            smiles = Chem.MolToSmiles(canonical, isomericSmiles=True)
            tautomer_keys[structure_hash] = sha256(smiles.encode()).hexdigest()
    return packed, tautomer_keys


def _parse_official_source(
    root: Path,
    authorization: Mapping[str, Any],
) -> tuple[
    list[dict[str, str]],
    dict[tuple[str, int], int],
    dict[tuple[str, str], float],
    dict[str, np.ndarray[Any, Any]],
    int,
]:
    """Adapt the immutable accepted G2-2C source without confirmatory truth."""

    from cypshift.chemistry import standardize_molecule
    from cypshift.schema import MoleculeInput

    receipts = authorization.get("official_input_receipts")
    _require(isinstance(receipts, Mapping), "official input receipts are absent")
    normalized = {str(key): str(value) for key, value in receipts.items()}
    manifest = _load_json(root / "manifest.json")
    try:
        accepted_compiler._validate_official_manifest(manifest, normalized)
        loaded = accepted_compiler._source_bytes(root, manifest)
        feature_rows = accepted_compiler._csv_rows(
            loaded["feature_rows.csv"],
            accepted_compiler.SOURCE_FEATURE_COLUMNS,
            "official feature rows",
        )
    except accepted_compiler.MapLightExecutionCompilerError as exc:
        raise RobustnessExecutionCompilerError(
            "accepted official source differs"
        ) from exc
    source_ids = [row["molecule_id"] for row in feature_rows]
    _require(
        len(source_ids) == len(set(source_ids)), "official molecule identities differ"
    )
    components = {
        row["molecule_id"]: row["similarity_component_hash"] for row in feature_rows
    }
    development = {
        molecule
        for molecule, component in components.items()
        if not accepted_compiler._is_confirmatory(component)
    }
    confirmatory = set(source_ids) - development
    try:
        truth, truth_accounting = accepted_compiler._development_truth(
            loaded["direct_observations.csv"],
            development,
            confirmatory,
            components,
        )
        fold_rows = accepted_compiler._folds(
            loaded["group_folds.csv"], development, components
        )
    except accepted_compiler.MapLightExecutionCompilerError as exc:
        raise RobustnessExecutionCompilerError(
            "accepted targets or folds differ"
        ) from exc
    _require(
        truth_accounting["confirmatory_target_values_parsed"] == 0,
        "confirmatory target value was parsed",
    )
    primary_folds: dict[tuple[str, int], int] = {}
    for row in fold_rows:
        key = row["molecule_id"], int(row["repeat"])
        fold = int(row["outer_fold"])
        previous = primary_folds.setdefault(key, fold)
        _require(previous == fold, "accepted primary fold differs by context")

    raw = loaded["direct_observations.csv"]
    lines = raw.splitlines()
    expected_header = ",".join(accepted_compiler.DIRECT_COLUMNS).encode()
    _require(
        bool(lines) and lines[0] == expected_header, "official direct header differs"
    )
    raw_smiles: dict[str, str] = {}
    for line in lines[1:]:
        prefix = _csv_prefix(line + b",", 8)
        molecule = prefix[1]
        _require(molecule in components, "official direct molecule differs")
        previous = raw_smiles.setdefault(molecule, prefix[7])
        _require(previous == prefix[7], "official raw structure differs by endpoint")
    _require(
        set(raw_smiles) == set(source_ids), "official raw structures are incomplete"
    )

    feature_by_id = {row["molecule_id"]: row for row in feature_rows}
    standardized: dict[str, str] = {}
    for molecule in sorted(source_ids):
        record = standardize_molecule(
            MoleculeInput(
                molecule_id=molecule,
                structure=raw_smiles[molecule],
                structure_format="smiles",
                source="accepted-openadmet-development-source",
                provenance=normalized["dataset_revision"],
            )
        )
        _require(
            record.standardized_structure is not None
            and record.standardized_structure_hash
            == feature_by_id[molecule]["standardized_structure_hash"],
            "official standardized structure differs",
        )
        assert record.standardized_structure is not None
        standardized[record.standardized_structure_hash] = record.standardized_structure
    packed_unique, tautomer_keys = _rdkit_overlay_inputs(standardized)
    unique_hashes = sorted(standardized)
    threshold_55 = _similarity_components(
        structure_hashes=unique_hashes,
        packed_fingerprints=packed_unique,
        threshold=0.55,
        group_id="THRESHOLD_0_55",
    )
    threshold_50 = _similarity_components(
        structure_hashes=unique_hashes,
        packed_fingerprints=packed_unique,
        threshold=0.50,
        group_id="THRESHOLD_0_50",
    )
    structure_primary = {
        row["standardized_structure_hash"]: row["similarity_component_hash"]
        for row in feature_rows
    }
    tautomer = _tautomer_components(
        structure_primary=structure_primary,
        structure_tautomer=tautomer_keys,
    )
    molecules = []
    structure_position = {value: index for index, value in enumerate(unique_hashes)}
    packed_by_source = np.empty((len(source_ids), 512), dtype=np.uint8)
    for index, molecule in enumerate(source_ids):
        feature = feature_by_id[molecule]
        structure_hash = feature["standardized_structure_hash"]
        packed_by_source[index] = packed_unique[structure_position[structure_hash]]
        molecules.append(
            {
                "molecule_id": molecule,
                "standardized_structure_hash": structure_hash,
                "standardized_smiles": standardized[structure_hash],
                "primary_component_hash": feature["similarity_component_hash"],
                "threshold_0_55_component_hash": threshold_55[structure_hash],
                "threshold_0_50_component_hash": threshold_50[structure_hash],
                "tautomer_component_hash": tautomer[structure_hash],
                "tautomer_key": tautomer_keys[structure_hash],
                "confirmatory": "1" if molecule in confirmatory else "0",
            }
        )
    source_positions = {molecule: index for index, molecule in enumerate(source_ids)}
    canonical_ids = sorted(source_ids)
    take = np.asarray(
        [source_positions[molecule] for molecule in canonical_ids], dtype=np.int64
    )
    arrays: dict[str, np.ndarray[Any, Any]] = {
        OVERLAY_FINGERPRINT_FILE: np.ascontiguousarray(packed_by_source[take])
    }
    for name, columns, dtype in FEATURE_FILES:
        stream = io.BytesIO(loaded[name])
        array = np.lib.format.read_array(stream, allow_pickle=False)
        _require(
            array.shape == (len(source_ids), columns)
            and array.dtype == dtype
            and stream.read() == b"",
            f"official {name} differs",
        )
        arrays[name] = np.ascontiguousarray(array[take])
    molecules.sort(key=lambda row: row["molecule_id"])
    return molecules, primary_folds, truth, arrays, 0


def _parse_source(
    root: Path, manifest: Mapping[str, Any], loaded: Mapping[str, bytes]
) -> tuple[
    list[dict[str, str]],
    dict[tuple[str, int], int],
    dict[tuple[str, str], float],
    dict[str, np.ndarray[Any, Any]],
    int,
]:
    molecules = _read_csv(root / "molecules.csv", MOLECULE_COLUMNS)
    ids = [row["molecule_id"] for row in molecules]
    _require(bool(ids) and len(ids) == len(set(ids)), "molecule identities differ")
    _require(
        all(
            _is_sha(row["standardized_structure_hash"])
            and bool(row["standardized_smiles"])
            and all(_is_sha(row[column]) for column in GROUP_COLUMNS.values())
            and _is_sha(row["tautomer_key"])
            and row["confirmatory"] in {"0", "1"}
            for row in molecules
        ),
        "molecule family identity differs",
    )
    by_id = {row["molecule_id"]: row for row in molecules}
    structures = sorted({row["standardized_structure_hash"] for row in molecules})
    source_positions = {molecule: index for index, molecule in enumerate(ids)}
    representative_ids = {
        structure_hash: min(
            row["molecule_id"]
            for row in molecules
            if row["standardized_structure_hash"] == structure_hash
        )
        for structure_hash in structures
    }
    fingerprint_stream = io.BytesIO(loaded[OVERLAY_FINGERPRINT_FILE])
    source_fingerprints = np.lib.format.read_array(
        fingerprint_stream, allow_pickle=False
    )
    _require(
        source_fingerprints.shape == (len(molecules), 512)
        and source_fingerprints.dtype == np.uint8
        and fingerprint_stream.read() == b"",
        "overlay fingerprint matrix differs",
    )
    packed = np.ascontiguousarray(
        source_fingerprints[
            np.asarray(
                [source_positions[representative_ids[value]] for value in structures],
                dtype=np.int64,
            )
        ]
    )
    threshold_55 = _similarity_components(
        structure_hashes=structures,
        packed_fingerprints=packed,
        threshold=0.55,
        group_id="THRESHOLD_0_55",
    )
    threshold_50 = _similarity_components(
        structure_hashes=structures,
        packed_fingerprints=packed,
        threshold=0.50,
        group_id="THRESHOLD_0_50",
    )
    structure_primary = {
        row["standardized_structure_hash"]: row["primary_component_hash"]
        for row in molecules
    }
    structure_tautomer = {
        row["standardized_structure_hash"]: row["tautomer_key"] for row in molecules
    }
    tautomer = _tautomer_components(
        structure_primary=structure_primary,
        structure_tautomer=structure_tautomer,
    )
    for row in molecules:
        structure_hash = row["standardized_structure_hash"]
        _require(
            row["threshold_0_55_component_hash"] == threshold_55[structure_hash]
            and row["threshold_0_50_component_hash"] == threshold_50[structure_hash]
            and row["tautomer_component_hash"] == tautomer[structure_hash],
            "derived overlay component differs",
        )
    for column in GROUP_COLUMNS.values():
        structures_by_component: dict[str, set[str]] = defaultdict(set)
        for row in molecules:
            structures_by_component[row[column]].add(row["standardized_structure_hash"])
        structure_components: dict[str, set[str]] = defaultdict(set)
        for row in molecules:
            structure_components[row["standardized_structure_hash"]].add(row[column])
        _require(
            all(len(values) == 1 for values in structure_components.values()),
            f"exact duplicate crosses {column}",
        )

    fold_rows = _read_csv(root / "primary_folds.csv", PRIMARY_FOLD_COLUMNS)
    _require(len(fold_rows) == len(molecules) * 3, "primary fold count differs")
    primary_folds: dict[tuple[str, int], int] = {}
    for row in fold_rows:
        molecule = row["molecule_id"]
        repeat = int(row["repeat"])
        fold = int(row["outer_fold"])
        _require(
            molecule in by_id and repeat in REPEATS and fold in OUTER_FOLDS,
            "primary fold differs",
        )
        key = molecule, repeat
        _require(key not in primary_folds, "duplicate primary fold")
        primary_folds[key] = fold
    for repeat in REPEATS:
        component_folds: dict[str, set[int]] = defaultdict(set)
        for row in molecules:
            component_folds[row["primary_component_hash"]].add(
                primary_folds[(row["molecule_id"], repeat)]
            )
        _require(
            all(len(values) == 1 for values in component_folds.values()),
            "primary component crosses a fold",
        )

    target_rows = _read_csv(root / "targets.csv", TARGET_COLUMNS)
    _require(
        len(target_rows) == len(molecules) * len(ENDPOINTS), "target row count differs"
    )
    targets: dict[tuple[str, str], float] = {}
    confirmatory_values_parsed = 0
    for row in target_rows:
        molecule = row["molecule_id"]
        endpoint = row["endpoint"]
        _require(molecule in by_id and endpoint in ENDPOINTS, "target identity differs")
        key = molecule, endpoint
        _require(key not in targets, "duplicate target identity")
        if by_id[molecule]["confirmatory"] == "1":
            _require(
                row["point"] == "CONFIRMATORY_SENTINEL_MUST_REMAIN_OPAQUE",
                "confirmatory target sentinel differs",
            )
            continue
        targets[key] = _canonical_point(row["point"])
    expected_development = sum(row["confirmatory"] == "0" for row in molecules)
    _require(
        len(targets) == expected_development * len(ENDPOINTS)
        and confirmatory_values_parsed == 0,
        "development/confirmatory target boundary differs",
    )

    arrays: dict[str, np.ndarray[Any, Any]] = {}
    source_order = ids
    canonical_order = sorted(ids)
    positions = {molecule: index for index, molecule in enumerate(source_order)}
    take = np.asarray(
        [positions[molecule] for molecule in canonical_order], dtype=np.int64
    )
    for name, columns, dtype in FEATURE_FILES:
        stream = io.BytesIO(loaded[name])
        array = np.lib.format.read_array(stream, allow_pickle=False)
        _require(
            array.shape == (len(molecules), columns)
            and array.dtype == dtype
            and stream.read() == b"",
            f"{name} shape or dtype differs",
        )
        arrays[name] = np.ascontiguousarray(array[take])
    molecules.sort(key=lambda row: row["molecule_id"])
    return molecules, primary_folds, targets, arrays, confirmatory_values_parsed


def _overlay_fold(group_id: str, component_hash: str, repeat: int) -> int:
    material = (
        f"g2-7c-overlay-fold-v1|{group_id}|{REPEAT_SEEDS[repeat]}|{component_hash}"
    ).encode()
    return int.from_bytes(sha256(material).digest()[:8], "big") % 5


def _active_folds(
    molecules: Sequence[Mapping[str, str]],
    primary_folds: Mapping[tuple[str, int], int],
) -> tuple[list[dict[str, object]], dict[tuple[str, int, str], int]]:
    confirmatory_groups: dict[str, set[str]] = {}
    for group_id, column in GROUP_COLUMNS.items():
        confirmatory_groups[group_id] = {
            row[column] for row in molecules if row["confirmatory"] == "1"
        }
    rows: list[dict[str, object]] = []
    folds: dict[tuple[str, int, str], int] = {}
    for group_id, column in GROUP_COLUMNS.items():
        for repeat in REPEATS:
            for row in molecules:
                if row["confirmatory"] == "1":
                    continue
                component = row[column]
                if (
                    group_id != "PRIMARY_D032"
                    and component in confirmatory_groups[group_id]
                ):
                    continue
                molecule = row["molecule_id"]
                fold = (
                    primary_folds[(molecule, repeat)]
                    if group_id == "PRIMARY_D032"
                    else _overlay_fold(group_id, component, repeat)
                )
                key = molecule, repeat, group_id
                _require(key not in folds, "duplicate active fold")
                folds[key] = fold
                rows.append(
                    {
                        "molecule_id": molecule,
                        "standardized_structure_hash": row[
                            "standardized_structure_hash"
                        ],
                        "group_id": group_id,
                        "component_hash": component,
                        "repeat": repeat,
                        "outer_fold": fold,
                    }
                )
            component_folds: dict[str, set[int]] = defaultdict(set)
            duplicate_folds: dict[str, set[int]] = defaultdict(set)
            for item in rows:
                if item["group_id"] == group_id and item["repeat"] == repeat:
                    component_folds[cast(str, item["component_hash"])].add(
                        cast(int, item["outer_fold"])
                    )
                    duplicate_folds[cast(str, item["standardized_structure_hash"])].add(
                        cast(int, item["outer_fold"])
                    )
            _require(
                bool(component_folds)
                and all(len(values) == 1 for values in component_folds.values()),
                f"{group_id} component crosses a fold",
            )
            _require(
                all(len(values) == 1 for values in duplicate_folds.values()),
                f"{group_id} duplicate crosses a fold",
            )
    rows.sort(
        key=lambda row: (
            cast(str, row["group_id"]),
            cast(int, row["repeat"]),
            cast(int, row["outer_fold"]),
            cast(str, row["molecule_id"]),
        )
    )
    return rows, folds


def _preflight(
    molecules: Sequence[Mapping[str, str]],
    targets: Mapping[tuple[str, str], float],
    folds: Mapping[tuple[str, int, str], int],
) -> dict[str, Any]:
    development = [
        row["molecule_id"] for row in molecules if row["confirmatory"] == "0"
    ]
    failures: list[str] = []
    support: dict[str, dict[str, int]] = {}
    confirmatory_touch_exclusions: dict[str, int] = {}
    for endpoint in ENDPOINTS:
        finite = sum((molecule, endpoint) in targets for molecule in development)
        if finite < MINIMA["development_finite_targets_per_endpoint"]:
            failures.append(f"{endpoint}:development")
    for group_id in GROUPS:
        active_once = {
            molecule for molecule in development if (molecule, 0, group_id) in folds
        }
        confirmatory_touch_exclusions[group_id] = len(development) - len(active_once)
        if group_id == "PRIMARY_D032" and confirmatory_touch_exclusions[group_id] != 0:
            failures.append("PRIMARY_D032:confirmatory_touch")
        if group_id != "PRIMARY_D032" and confirmatory_touch_exclusions[group_id] <= 0:
            failures.append(f"{group_id}:confirmatory_touch_not_exercised")
        for repeat in REPEATS:
            active = [
                molecule
                for molecule in development
                if (molecule, repeat, group_id) in folds
            ]
            for fold in OUTER_FOLDS:
                for endpoint in ENDPOINTS:
                    validation = sum(
                        (molecule, endpoint) in targets
                        and folds[(molecule, repeat, group_id)] == fold
                        for molecule in active
                    )
                    training = sum(
                        (molecule, endpoint) in targets
                        and folds[(molecule, repeat, group_id)] != fold
                        for molecule in active
                    )
                    key = f"{group_id}|{endpoint}|r{repeat}|f{fold}"
                    support[key] = {
                        "training": training,
                        "validation": validation,
                    }
                    if (
                        validation
                        < MINIMA["outer_validation_targets_per_endpoint_repeat_fold"]
                    ):
                        failures.append(f"{key}:validation")
                    if (
                        training
                        < MINIMA["outer_training_targets_per_endpoint_repeat_fold"]
                    ):
                        failures.append(f"{key}:training")
    return {
        "status": (
            "G2_7C_NO_FIT_PREFLIGHT_PASS"
            if not failures
            else "G2_7C_NO_FIT_UNDERPOWERED"
        ),
        "failures": failures,
        "support": support,
        "confirmatory_touch_excluded_molecules": confirmatory_touch_exclusions,
        "minima": dict(MINIMA),
    }


def _target_files(
    *,
    targets: Mapping[tuple[str, str], float],
    folds: Mapping[tuple[str, int, str], int],
) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for group_id in GROUPS:
        for repeat in REPEATS:
            active = sorted(
                molecule
                for molecule, observed_repeat, observed_group in folds
                if observed_repeat == repeat and observed_group == group_id
            )
            for fold in OUTER_FOLDS:
                for endpoint in ENDPOINTS:
                    rows = [
                        {
                            "molecule_id": molecule,
                            "point": format(targets[(molecule, endpoint)], ".17g"),
                        }
                        for molecule in active
                        if folds[(molecule, repeat, group_id)] != fold
                        and (molecule, endpoint) in targets
                    ]
                    name = f"model/targets/{group_id}/r{repeat}/f{fold}/{endpoint}.csv"
                    files[name] = maplight.csv_bytes(maplight.TARGET_COLUMNS, rows)
    return files


def compile_capabilities(
    *,
    source_root: Path,
    output_root: Path,
    mode: str,
    authorization: Mapping[str, Any] | None = None,
    expected_compiler_sha256: str,
) -> tuple[Path, Path, dict[str, Any]]:
    """Compile one atomic model/scorer capability root without fitting."""

    _require(
        maplight.sha256_path(SCRIPT) == expected_compiler_sha256,
        "compiler source receipt differs",
    )
    science = authenticate_static_boundary()
    _validate_authorization(authorization, mode=mode, source_root=source_root)
    maplight._readonly_root(source_root, "robustness source")
    source_manifest = _load_json(source_root / "manifest.json")
    if mode == "synthetic":
        _validate_source_manifest(source_manifest, mode=mode, source_root=source_root)
        loaded = _source_bytes(source_root, source_manifest)
        molecules, primary_folds, targets, arrays, confirmatory_parsed = _parse_source(
            source_root, source_manifest, loaded
        )
        semantic_source_id = source_manifest["semantic_source_id"]
    else:
        assert authorization is not None
        molecules, primary_folds, targets, arrays, confirmatory_parsed = (
            _parse_official_source(source_root, authorization)
        )
        semantic_source_id = cast(Mapping[str, Any], authorization)[
            "official_input_receipts"
        ]["dataset_revision"]
    fold_rows, folds = _active_folds(molecules, primary_folds)
    preflight = _preflight(molecules, targets, folds)
    if preflight["failures"]:
        raise RobustnessExecutionUnderpowered(preflight)

    files = _target_files(targets=targets, folds=folds)
    development_ids = [
        row["molecule_id"] for row in molecules if row["confirmatory"] == "0"
    ]
    canonical_positions = {
        molecule: index
        for index, molecule in enumerate(
            sorted(row["molecule_id"] for row in molecules)
        )
    }
    take = np.asarray(
        [canonical_positions[molecule] for molecule in development_ids], dtype=np.int64
    )
    feature_receipts: dict[str, str] = {}
    for name, _columns, _dtype in FEATURE_FILES:
        data = _npy_bytes(arrays[name][take])
        files[f"model/{name}"] = data
        feature_receipts[name] = maplight.sha256_bytes(data)
    files["model/folds.csv"] = maplight.csv_bytes(CAPABILITY_FOLD_COLUMNS, fold_rows)
    truth_rows = [
        {
            "molecule_id": molecule,
            "endpoint": endpoint,
            "point": format(targets[(molecule, endpoint)], ".17g"),
        }
        for molecule in sorted(development_ids)
        for endpoint in ENDPOINTS
        if (molecule, endpoint) in targets
    ]
    truth_bytes = maplight.csv_bytes(TARGET_COLUMNS, truth_rows)
    for stage in ("stage_a", "stage_b", "stage_c"):
        files[f"scorer/{stage}_truth.csv"] = truth_bytes
    if mode == "synthetic":
        files["scorer/selection_oracles.json"] = maplight.json_bytes(
            {
                "deletion_selected": "G2-7-M1-DROP-MORGAN",
                "full_retained": "G2-7-M0-FULL",
                "meaning": "mechanics-only branch oracle; no metric value",
            }
        )

    science_sha = maplight.sha256_bytes(maplight.json_bytes(science))
    model_manifest = {
        "schema_version": MODEL_SCHEMA,
        "synthetic": mode == "synthetic",
        "bounded_contract_sha256": BOUNDED_CONTRACT_SHA256,
        "parent_contract_sha256": PARENT_CONTRACT_SHA256,
        "compiler_source_sha256": expected_compiler_sha256,
        "science_identity_sha256": science_sha,
        "molecules": len(development_ids),
        "feature_receipts": feature_receipts,
        "folds_sha256": maplight.sha256_bytes(files["model/folds.csv"]),
        "target_capabilities": {
            name.removeprefix("model/"): maplight.sha256_bytes(value)
            for name, value in files.items()
            if name.startswith("model/targets/")
        },
        "preflight": preflight,
        "accounting": _zero_accounting(),
        "authority": dict(maplight.DENIED_AUTHORITY),
    }
    scorer_manifest = {
        "schema_version": SCORER_SCHEMA,
        "synthetic": mode == "synthetic",
        "bounded_contract_sha256": BOUNDED_CONTRACT_SHA256,
        "parent_contract_sha256": PARENT_CONTRACT_SHA256,
        "compiler_source_sha256": expected_compiler_sha256,
        "science_identity_sha256": science_sha,
        "truth_receipts": {
            stage: maplight.sha256_bytes(files[f"scorer/{stage}_truth.csv"])
            for stage in ("stage_a", "stage_b", "stage_c")
        },
        "truth_rows": len(truth_rows),
        "confirmatory_target_values_parsed": confirmatory_parsed,
        "accounting": _zero_accounting(),
        "authority": dict(maplight.DENIED_AUTHORITY),
    }
    files["model/manifest.json"] = maplight.json_bytes(model_manifest)
    files["scorer/manifest.json"] = maplight.json_bytes(scorer_manifest)
    root_manifest = {
        "schema_version": CAPABILITY_SCHEMA,
        "synthetic": mode == "synthetic",
        "bounded_contract_sha256": BOUNDED_CONTRACT_SHA256,
        "parent_contract_sha256": PARENT_CONTRACT_SHA256,
        "compiler_source_sha256": expected_compiler_sha256,
        "semantic_source_id": semantic_source_id,
        "science_identity_sha256": science_sha,
        "model_manifest_sha256": maplight.sha256_bytes(files["model/manifest.json"]),
        "scorer_manifest_sha256": maplight.sha256_bytes(files["scorer/manifest.json"]),
        "preflight": preflight,
        "accounting": _zero_accounting(),
    }
    files["manifest.json"] = maplight.json_bytes(root_manifest)
    published = maplight.publish_files(output_root, files)
    return published / "model", published / "scorer", preflight
