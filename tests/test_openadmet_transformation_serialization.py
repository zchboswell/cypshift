from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import replace

import pytest

from cypshift.chemistry import standardize_molecule
from cypshift.openadmet_transformation_compiler import (
    CompiledEpisodeDirection,
    CompiledTransformationPair,
    TransformationGeometry,
)
from cypshift.openadmet_transformation_coverage import (
    DirectAvailability,
    OpenADMETTransformationCoverageError,
    ProjectionBundle,
    ProjectionEpisode,
    ProjectionFold,
    ProjectionMolecule,
)
from cypshift.openadmet_transformation_serialization import (
    CONTRACT_SHA256,
    EPISODE_COLUMNS,
    serialize_transformation_results,
)
from cypshift.openadmet_transformation_support import (
    TransformationSupport,
    compile_transformation_support,
)
from cypshift.openadmet_transformations import extract_transformation_pair
from cypshift.schema import MoleculeInput, MoleculeRecord

ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _record(molecule_id: str, smiles: str) -> MoleculeRecord:
    return standardize_molecule(
        MoleculeInput(molecule_id, smiles, "smiles", "synthetic", "fixture")
    )


def _pair(
    component: str,
    left_id: str,
    left_smiles: str,
    right_id: str,
    right_smiles: str,
    *,
    episode_pair: bool = False,
) -> tuple[CompiledTransformationPair, tuple[MoleculeRecord, MoleculeRecord]]:
    left = _record(left_id, left_smiles)
    right = _record(right_id, right_smiles)
    result = extract_transformation_pair(left, right)
    return (
        CompiledTransformationPair(result, component, True, episode_pair),
        (left, right),
    )


def _folds(
    records: list[tuple[MoleculeRecord, str, int]],
) -> tuple[ProjectionFold, ...]:
    return tuple(
        ProjectionFold(
            record.molecule_id,
            component,
            repeat,
            20260810 + repeat,
            outer,
            validation,
            None if validation == outer else 0,
        )
        for record, component, outer in records
        for repeat in range(3)
        for validation in range(5)
    )


def _episode(
    pair: CompiledTransformationPair, episode_id: str, policy: str
) -> tuple[ProjectionEpisode, CompiledEpisodeDirection]:
    direction = pair.result.a_to_b
    row = ProjectionEpisode(
        _digest(episode_id),
        "ANCHOR_EXPANSION_HOLDOUT",
        0,
        0,
        pair.similarity_component_hash,
        direction.analog_molecule_id,
        1,
        direction.anchor_molecule_id,
        "DEFERRED_NO_INFERRED_POOL_V1",
        policy,
    )
    return row, CompiledEpisodeDirection(row, pair, direction)


def _fixture() -> tuple[TransformationGeometry, TransformationSupport]:
    specifications = (
        ("family-0", 0, "CCO", "CCN"),
        ("family-1", 0, "CCCO", "CCCN"),
        ("family-2", 1, "CCCCO", "CCCCN"),
    )
    pairs: list[CompiledTransformationPair] = []
    records: list[tuple[MoleculeRecord, str, int]] = []
    for index, (family, outer, left, right) in enumerate(specifications):
        component = _digest(family)
        pair, pair_records = _pair(
            component,
            f"left-{index}",
            left,
            f"right-{index}",
            right,
            episode_pair=index == 0,
        )
        pairs.append(pair)
        records.extend((record, component, outer) for record in pair_records)
    invalid, invalid_records = _pair(
        _digest("family-invalid"),
        "invalid-left",
        "CCO",
        "invalid-right",
        "c1ccccc1",
        episode_pair=True,
    )
    pairs.append(invalid)
    records.extend(
        (record, invalid.similarity_component_hash, 2) for record in invalid_records
    )
    selected, selected_geometry = _episode(pairs[0], "selected", "selected_anchor")
    stress, stress_geometry = _episode(
        invalid, "stress", "deterministic_random_anchor_stress"
    )
    molecules = tuple(
        ProjectionMolecule(record, _digest(record.raw_structure), component)
        for record, component, _ in records
    )
    direct = tuple(
        DirectAvailability(
            _digest(f"obs:{record.molecule_id}:{endpoint}"),
            record.molecule_id,
            endpoint,
            "complete" if endpoint in {"CYP2D6", "CYP3A4"} else "missing",
        )
        for record, _, _ in records
        for endpoint in ENDPOINTS
    )
    bundle = ProjectionBundle(
        (), (), molecules, direct, _folds(records), (selected, stress)
    )
    geometry = TransformationGeometry(
        tuple(reversed(pairs)),
        (stress_geometry, selected_geometry),
        b"",
    )
    return geometry, compile_transformation_support(bundle, geometry)


def _csv_rows(data: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(data.decode(), newline="")))


def test_episode_and_coverage_bytes_follow_frozen_schemas() -> None:
    geometry, support = _fixture()
    result = serialize_transformation_results(geometry, support)
    assert result.episode_transformations_csv.endswith(b"\n")
    assert result.transformation_coverage_json.endswith(b"\n")
    rows = _csv_rows(result.episode_transformations_csv)
    assert tuple(rows[0]) == EPISODE_COLUMNS
    assert [row["episode_id"] for row in rows] == sorted(
        row["episode_id"] for row in rows
    )
    assert len(rows) == 2

    valid = next(row for row in rows if row["extraction_status"] == "VALID_SINGLE")
    assert valid["cut_count"] == "1"
    assert valid["exact_transformation_id"]
    assert valid["cyp3a4_training_family_exact_support_count"] == "1"
    assert valid["ambiguous"] == "false"

    invalid = next(row for row in rows if row["extraction_status"] == "UNSUPPORTED")
    for column in (
        "cut_count",
        "exact_transformation_id",
        "transformation_class_id",
        "environment_level_1_id",
        "environment_level_2_id",
        "changed_heavy_atom_fraction",
    ):
        assert invalid[column] == ""
    assert invalid["direction_id"]
    assert invalid["cyp3a4_training_family_exact_support_count"] == "0"
    assert json.loads(invalid["tie_material"]) == []

    coverage = json.loads(result.transformation_coverage_json)
    assert coverage["contract_sha256"] == CONTRACT_SHA256
    assert coverage["status"] == "R4_TRANSFORMATION_COVERAGE_UNDERPOWERED"
    assert coverage["counts"]["union"] == {
        "denominator_rows": 4,
        "valid_rows": 3,
        "single_cut_rows": 3,
        "double_cut_rows": 0,
    }
    assert coverage["status_partition"]["union"]["UNSUPPORTED"] == 1
    assert coverage["fractions"]["union"]["unsupported_fraction"] == "1/4"
    assert coverage["valid_changed_heavy_atom_fraction_distribution"]["count"] == 3
    assert coverage["test_query_coverage"] == {
        "status": "NOT_COMPUTED_TEST_ACCESS_FORBIDDEN",
        "values": None,
    }
    assert coverage["authority"]["geometry_coverage"] is True
    assert coverage["authority"]["oracle_contract_freeze"] is False
    assert all(value == 0 for value in coverage["accounting"].values())


def test_serialization_is_order_invariant_and_canonical() -> None:
    geometry, support = _fixture()
    first = serialize_transformation_results(geometry, support)
    second = serialize_transformation_results(
        replace(
            geometry,
            pairs=tuple(reversed(geometry.pairs)),
            episodes=tuple(reversed(geometry.episodes)),
        ),
        support,
    )
    assert first == second
    decoded = first.transformation_coverage_json.decode()
    assert decoded == json.dumps(json.loads(decoded), indent=2, sort_keys=True) + "\n"
    assert b"selector" not in first.episode_transformations_csv
    assert b"target" not in first.episode_transformations_csv
    assert b"prediction" not in first.episode_transformations_csv


def test_serialization_rejects_missing_or_duplicate_episode_support() -> None:
    geometry, support = _fixture()
    typed_support = support  # keep the fixture construction compact
    missing = replace(
        typed_support,
        episode_training_support=typed_support.episode_training_support[:1],
    )
    with pytest.raises(OpenADMETTransformationCoverageError, match="missing episode"):
        serialize_transformation_results(geometry, missing)
    duplicate = replace(
        typed_support,
        episode_training_support=(
            typed_support.episode_training_support[0],
            typed_support.episode_training_support[0],
        ),
    )
    with pytest.raises(OpenADMETTransformationCoverageError, match="duplicate episode"):
        serialize_transformation_results(geometry, duplicate)
