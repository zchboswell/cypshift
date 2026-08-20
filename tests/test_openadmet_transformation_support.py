from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

import cypshift.openadmet_transformation_support as support_module
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
from cypshift.openadmet_transformation_support import (
    EndpointLocalSupport,
    LocalSupportCell,
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


def _compiled_pair(
    component: str,
    left_id: str,
    left_smiles: str,
    right_id: str,
    right_smiles: str,
    *,
    local: bool = True,
    episode: bool = False,
) -> tuple[CompiledTransformationPair, tuple[MoleculeRecord, MoleculeRecord]]:
    left = _record(left_id, left_smiles)
    right = _record(right_id, right_smiles)
    result = extract_transformation_pair(left, right)
    return (
        CompiledTransformationPair(result, component, local, episode),
        (left, right),
    )


def _molecule(record: MoleculeRecord, component: str) -> ProjectionMolecule:
    return ProjectionMolecule(record, _digest(record.raw_structure), component)


def _folds(
    records: list[tuple[MoleculeRecord, str, int]],
) -> tuple[ProjectionFold, ...]:
    rows: list[ProjectionFold] = []
    for record, component, outer in records:
        for repeat in range(3):
            for validation in range(5):
                rows.append(
                    ProjectionFold(
                        record.molecule_id,
                        component,
                        repeat,
                        20260810 + repeat,
                        outer,
                        validation,
                        None if validation == outer else 0,
                    )
                )
    return tuple(rows)


def _bundle(
    records: list[tuple[MoleculeRecord, str, int]],
    *,
    complete_endpoints: tuple[str, ...] = ("CYP2D6", "CYP3A4"),
    episodes: tuple[ProjectionEpisode, ...] = (),
) -> ProjectionBundle:
    direct = tuple(
        DirectAvailability(
            _digest(f"obs:{record.molecule_id}:{endpoint}"),
            record.molecule_id,
            endpoint,
            "complete" if endpoint in complete_endpoints else "missing",
        )
        for record, _, _ in records
        for endpoint in ENDPOINTS
    )
    return ProjectionBundle(
        (),
        (),
        tuple(_molecule(record, component) for record, component, _ in records),
        direct,
        _folds(records),
        episodes,
    )


def _episode(
    pair: CompiledTransformationPair,
    *,
    episode_id: str,
    repeat: int = 0,
    outer_fold: int = 0,
    policy: str = "selected_anchor",
) -> tuple[ProjectionEpisode, CompiledEpisodeDirection]:
    direction = pair.result.a_to_b
    row = ProjectionEpisode(
        _digest(episode_id),
        "ANCHOR_EXPANSION_HOLDOUT",
        repeat,
        outer_fold,
        pair.similarity_component_hash,
        direction.analog_molecule_id,
        1,
        direction.anchor_molecule_id,
        "DEFERRED_NO_INFERRED_POOL_V1",
        policy,
    )
    return row, CompiledEpisodeDirection(row, pair, direction)


def _support_fixture() -> tuple[ProjectionBundle, TransformationGeometry]:
    specifications = (
        ("family-0", 0, "CCO", "CCN"),
        ("family-1", 0, "CCCO", "CCCN"),
        ("family-2", 1, "CCCCO", "CCCCN"),
    )
    pairs: list[CompiledTransformationPair] = []
    records: list[tuple[MoleculeRecord, str, int]] = []
    for index, (family, outer, left, right) in enumerate(specifications):
        component = _digest(family)
        pair, pair_records = _compiled_pair(
            component,
            f"left-{index}",
            left,
            f"right-{index}",
            right,
            episode=index == 0,
        )
        pairs.append(pair)
        records.extend((record, component, outer) for record in pair_records)
    invalid, invalid_records = _compiled_pair(
        _digest("family-invalid"),
        "invalid-left",
        "CCO",
        "invalid-right",
        "c1ccccc1",
    )
    assert invalid.result.extraction_status == "UNSUPPORTED"
    pairs.append(invalid)
    records.extend(
        (record, invalid.similarity_component_hash, 2) for record in invalid_records
    )
    episode_row, episode_geometry = _episode(pairs[0], episode_id="episode-0")
    stress_row, stress_geometry = _episode(
        pairs[0],
        episode_id="episode-stress",
        policy="deterministic_random_anchor_stress",
    )
    bundle = _bundle(records, episodes=(episode_row, stress_row))
    geometry = TransformationGeometry(
        tuple(pairs + [pairs[0]]),
        (episode_geometry, episode_geometry, stress_geometry, stress_geometry),
        b"",
    )
    return bundle, geometry


def test_support_deduplicates_and_excludes_held_out_families() -> None:
    bundle, geometry = _support_fixture()
    result = compile_transformation_support(bundle, geometry)
    assert result.status == "R4_TRANSFORMATION_COVERAGE_UNDERPOWERED"
    union = result.status_partition_union
    assert union.denominator_rows == 4
    assert union.count("VALID_SINGLE") == 3
    assert union.count("UNSUPPORTED") == 1
    cyp3a4_partition = dict(result.status_partition_local_by_endpoint)["CYP3A4"]
    assert cyp3a4_partition.denominator_rows == 4
    assert cyp3a4_partition.count("VALID_SINGLE") == 3

    exact_frequency = dict(result.exact_transformation_frequency)
    assert {record.denominator_rows for record in exact_frequency.values()} == {6}
    assert sorted(record.rows for record in exact_frequency.values()) == [3, 3]
    class_frequency = dict(result.transformation_class_frequency)
    assert set(class_frequency) == {"single_cut_exchange"}
    assert class_frequency["single_cut_exchange"].rows == 6

    independent = result.independent_group_support
    assert {count for _, count in independent.exact} == {3}
    assert independent.transformation_class == (("single_cut_exchange", 3),)
    sharing = dict(result.cross_cyp_valid_transformation_sharing)
    assert all(endpoints == ("CYP2D6", "CYP3A4") for endpoints in sharing.values())

    episode = result.episode_training_support[0]
    assert (episode.exact, episode.transformation_class) == (1, 1)
    assert result.selected_anchor_structural_coverage.rows == 1
    assert result.selected_anchor_structural_coverage.valid_rows == 1
    assert result.status_partition_stress.denominator_rows == 1
    assert result.valid_changed_heavy_atom_fraction_distribution.count == 3


def test_empty_partitions_and_zero_distribution_use_exact_sentinels() -> None:
    invalid, pair_records = _compiled_pair(
        _digest("invalid"), "left", "CCO", "right", "c1ccccc1"
    )
    records = [
        (record, invalid.similarity_component_hash, 0) for record in pair_records
    ]
    result = compile_transformation_support(
        _bundle(records, complete_endpoints=()),
        TransformationGeometry((invalid,), (), b""),
    )
    assert result.status_partition_selected_primary.denominator_rows == 0
    assert set(dict(result.status_partition_selected_primary.fractions).values()) == {
        "0/1"
    }
    assert result.valid_changed_heavy_atom_fraction_distribution == (
        support_module.RationalDistribution(0, 0, None, None, None, ())
    )
    assert result.exact_transformation_frequency == ()
    assert result.transformation_class_frequency == ()


def test_support_rejects_episode_geometry_not_in_projection() -> None:
    bundle, geometry = _support_fixture()
    altered = replace(
        geometry.episodes[0],
        episode=replace(geometry.episodes[0].episode, outer_group_id=_digest("wrong")),
    )
    with pytest.raises(
        OpenADMETTransformationCoverageError, match="episode geometry differs"
    ):
        compile_transformation_support(
            bundle,
            replace(geometry, episodes=(altered, geometry.episodes[2])),
        )


def test_fraction_distribution_is_numeric_but_histogram_is_lexical() -> None:
    pair, _ = _compiled_pair(_digest("family"), "left", "CCO", "right", "CCN")
    values = ("2/3", "10/11", "1/2", "3/4")
    pairs = tuple(
        replace(pair, result=replace(pair.result, changed_heavy_atom_fraction=value))
        for value in values
    )
    distribution = support_module._changed_fraction_distribution(pairs)  # noqa: SLF001
    assert (distribution.minimum, distribution.median, distribution.maximum) == (
        "1/2",
        "17/24",
        "10/11",
    )
    assert [key for key, _ in distribution.histogram] == ["1/2", "10/11", "2/3", "3/4"]


def test_local_cyp3a4_gate_is_exact_at_threshold_and_one_below() -> None:
    cells = tuple(
        LocalSupportCell("CYP3A4", repeat, fold, 20, 5, True)
        for repeat in range(3)
        for fold in range(5)
    )
    supported = support_module._local_cyp3a4_state(  # noqa: SLF001
        EndpointLocalSupport("CYP3A4", 200, 50, cells)
    )
    assert supported.status == "LOCAL_SUPPORTED"
    assert supported.meets_gate is True
    underpowered = support_module._local_cyp3a4_state(  # noqa: SLF001
        EndpointLocalSupport("CYP3A4", 199, 50, cells)
    )
    assert underpowered.status == "LOCAL_UNDERPOWERED"
    assert underpowered.meets_gate is False


def test_selected_cells_keep_rows_and_valid_rows_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(support_module, "SELECTED_FAMILY_MIN", 1)
    monkeypatch.setattr(support_module, "SELECTED_FAMILY_OVERALL_MIN", 1)
    valid, _ = _compiled_pair(_digest("valid"), "left", "CCO", "right", "CCN")
    invalid, _ = _compiled_pair(
        _digest("invalid"), "invalid-left", "CCO", "invalid-right", "c1ccccc1"
    )
    rows: list[CompiledEpisodeDirection] = []
    for repeat in range(3):
        for fold in range(5):
            _, episode = _episode(
                valid,
                episode_id=f"valid:{repeat}:{fold}",
                repeat=repeat,
                outer_fold=fold,
            )
            rows.append(episode)
    _, invalid_episode = _episode(invalid, episode_id="invalid")
    rows.append(invalid_episode)
    selected = support_module._selected_coverage(tuple(rows))  # noqa: SLF001
    assert selected.meets_gate is True
    assert selected.rows == 16
    assert selected.valid_rows == 15
    first = selected.cell_support[0]
    assert (first.rows, first.valid_rows, first.distinct_families) == (2, 1, 1)


@pytest.mark.parametrize("value", ["01/2", "+1/2", "-0/1", "1/0", "2/4"])
def test_changed_fraction_parser_rejects_noncanonical_values(value: str) -> None:
    with pytest.raises(OpenADMETTransformationCoverageError, match="changed fraction"):
        support_module._parse_fraction(value)  # noqa: SLF001
