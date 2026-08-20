"""Pure structural-union and extraction-once compiler for R4.

The compiler consumes only the immutable projection bundle, constructs the
frozen local-plus-episode pair union, invokes the accepted pair extractor once
per structural pair, and emits canonical pair bytes plus directional episode
records.  Endpoint support arithmetic and publication remain separate.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Final

from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

from cypshift.openadmet_transformation_coverage import (
    OpenADMETTransformationCoverageError,
    ProjectionBundle,
    ProjectionEpisode,
    ProjectionMolecule,
)
from cypshift.openadmet_transformation_io import canonical_csv_bytes
from cypshift.openadmet_transformation_types import (
    DirectionalTransformation,
    TransformationPairResult,
    canonical_json,
)
from cypshift.openadmet_transformations import extract_transformation_pair

PAIR_COLUMNS: Final[tuple[str, ...]] = (
    "transformation_pair_id",
    "left_molecule_id",
    "right_molecule_id",
    "left_standardized_structure_hash",
    "right_standardized_structure_hash",
    "similarity",
    "similarity_component_hash",
    "local_pair",
    "episode_pair",
    "extraction_status",
    "failure_code",
    "cut_count",
    "conserved_core_smiles",
    "left_removed_fragment_smiles",
    "right_removed_fragment_smiles",
    "left_attachment_environment_radius_1",
    "right_attachment_environment_radius_1",
    "left_attachment_environment_radius_2",
    "right_attachment_environment_radius_2",
    "left_virtual_h_eligible",
    "right_virtual_h_eligible",
    "changed_left_atom_indices",
    "changed_right_atom_indices",
    "conserved_heavy_atoms",
    "left_heavy_atoms",
    "right_heavy_atoms",
    "changed_heavy_atom_fraction",
    "stereo_changed",
    "stereo_elements",
    "a_to_b_direction_id",
    "b_to_a_direction_id",
    "a_to_b_exact_transformation_id",
    "b_to_a_exact_transformation_id",
    "a_to_b_transformation_class_id",
    "b_to_a_transformation_class_id",
    "a_to_b_environment_level_1_id",
    "b_to_a_environment_level_1_id",
    "a_to_b_environment_level_2_id",
    "b_to_a_environment_level_2_id",
    "undirected_exchange_id",
    "candidate_material",
    "candidate_digest",
    "tie_count",
    "tie_material",
    "tie_digest",
    "ambiguous",
    "warnings",
)

_MORGAN_GENERATOR: Final = rdFingerprintGenerator.GetMorganGenerator(
    radius=2, fpSize=4096, includeChirality=True
)


@dataclass(frozen=True, slots=True)
class CompiledTransformationPair:
    """One extracted union pair plus compiler-owned structural membership."""

    result: TransformationPairResult
    similarity_component_hash: str
    local_pair: bool
    episode_pair: bool


@dataclass(frozen=True, slots=True)
class CompiledEpisodeDirection:
    """One public episode expanded to its exact anchor-to-query direction."""

    episode: ProjectionEpisode
    pair: CompiledTransformationPair
    direction: DirectionalTransformation


@dataclass(frozen=True, slots=True)
class TransformationGeometry:
    """Deterministic geometry outputs before endpoint support arithmetic."""

    pairs: tuple[CompiledTransformationPair, ...]
    episodes: tuple[CompiledEpisodeDirection, ...]
    transformation_pairs_csv: bytes


def compile_transformation_geometry(bundle: ProjectionBundle) -> TransformationGeometry:
    """Construct the structural union and extract each canonical pair once."""

    molecules = {row.molecule.molecule_id: row for row in bundle.molecules}
    fingerprints = {
        molecule_id: _fingerprint(row) for molecule_id, row in molecules.items()
    }
    local_keys = _local_pair_keys(bundle.molecules, fingerprints)
    episode_keys = {
        _pair_key(molecules[row.anchor_molecule_id], molecules[row.query_molecule_id])
        for row in bundle.episodes
    }
    union_keys = sorted(local_keys | episode_keys)
    compiled: list[CompiledTransformationPair] = []
    by_key: dict[tuple[str, str], CompiledTransformationPair] = {}
    for key in union_keys:
        left = molecules[key[0]]
        right = molecules[key[1]]
        similarity = _similarity(fingerprints[key[0]], fingerprints[key[1]])
        result = extract_transformation_pair(left.molecule, right.molecule)
        if {
            result.left_molecule_id,
            result.right_molecule_id,
        } != {key[0], key[1]}:
            raise OpenADMETTransformationCoverageError(
                "extractor pair identity differs"
            )
        if result.similarity != similarity:
            raise OpenADMETTransformationCoverageError(
                "extractor pair similarity differs"
            )
        item = CompiledTransformationPair(
            result=result,
            similarity_component_hash=left.similarity_component_hash,
            local_pair=key in local_keys,
            episode_pair=key in episode_keys,
        )
        compiled.append(item)
        by_key[key] = item
    episodes = tuple(
        _episode_direction(row, by_key, molecules)
        for row in sorted(
            bundle.episodes, key=lambda item: (item.episode_id, item.query_rank)
        )
    )
    pairs = tuple(sorted(compiled, key=lambda item: item.result.transformation_pair_id))
    return TransformationGeometry(pairs, episodes, _pair_csv(pairs))


def _local_pair_keys(
    molecules: tuple[ProjectionMolecule, ...], fingerprints: dict[str, Any]
) -> set[tuple[str, str]]:
    by_component: dict[str, list[ProjectionMolecule]] = defaultdict(list)
    for row in molecules:
        by_component[row.similarity_component_hash].append(row)
    keys: set[tuple[str, str]] = set()
    for members in by_component.values():
        ordered = sorted(members, key=lambda row: _molecule_order(row))
        for left, right in combinations(ordered, 2):
            left_id = left.molecule.molecule_id
            right_id = right.molecule.molecule_id
            if _similarity(fingerprints[left_id], fingerprints[right_id]) >= 0.60:
                keys.add(_pair_key(left, right))
    return keys


def _fingerprint(row: ProjectionMolecule) -> Any:
    smiles = row.molecule.standardized_structure
    if smiles is None:
        raise OpenADMETTransformationCoverageError("missing standardized structure")
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise OpenADMETTransformationCoverageError("invalid standardized structure")
    return _MORGAN_GENERATOR.GetFingerprint(molecule)


def _similarity(left: Any, right: Any) -> float:
    value = float(DataStructs.TanimotoSimilarity(left, right))
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise OpenADMETTransformationCoverageError("invalid pair similarity")
    return value


def _pair_key(left: ProjectionMolecule, right: ProjectionMolecule) -> tuple[str, str]:
    if left.similarity_component_hash != right.similarity_component_hash:
        raise OpenADMETTransformationCoverageError("pair crosses a component")
    ordered = sorted((left, right), key=_molecule_order)
    return ordered[0].molecule.molecule_id, ordered[1].molecule.molecule_id


def _molecule_order(row: ProjectionMolecule) -> tuple[str, str]:
    structure_hash = row.molecule.standardized_structure_hash
    if structure_hash is None:
        raise OpenADMETTransformationCoverageError("missing standardized hash")
    return structure_hash, row.molecule.molecule_id


def _episode_direction(
    episode: ProjectionEpisode,
    pairs: dict[tuple[str, str], CompiledTransformationPair],
    molecules: dict[str, ProjectionMolecule],
) -> CompiledEpisodeDirection:
    key = _pair_key(
        molecules[episode.anchor_molecule_id], molecules[episode.query_molecule_id]
    )
    pair = pairs[key]
    directions = (pair.result.a_to_b, pair.result.b_to_a)
    matching = [
        direction
        for direction in directions
        if direction.anchor_molecule_id == episode.anchor_molecule_id
        and direction.analog_molecule_id == episode.query_molecule_id
    ]
    if len(matching) != 1:
        raise OpenADMETTransformationCoverageError("episode direction differs")
    return CompiledEpisodeDirection(episode, pair, matching[0])


def _pair_csv(pairs: tuple[CompiledTransformationPair, ...]) -> bytes:
    rows = [_pair_row(item) for item in pairs]
    return canonical_csv_bytes(PAIR_COLUMNS, rows)


def _pair_row(item: CompiledTransformationPair) -> dict[str, str]:
    pair = item.result
    valid = pair.extraction_status in {"VALID_DOUBLE", "VALID_SINGLE", "VALID_STEREO"}
    return {
        "transformation_pair_id": pair.transformation_pair_id,
        "left_molecule_id": pair.left_molecule_id,
        "right_molecule_id": pair.right_molecule_id,
        "left_standardized_structure_hash": pair.left_standardized_structure_hash,
        "right_standardized_structure_hash": pair.right_standardized_structure_hash,
        "similarity": format(pair.similarity, ".17g"),
        "similarity_component_hash": item.similarity_component_hash,
        "local_pair": _boolean(item.local_pair),
        "episode_pair": _boolean(item.episode_pair),
        "extraction_status": pair.extraction_status,
        "failure_code": pair.failure_code,
        "cut_count": _optional_integer(pair.cut_count),
        "conserved_core_smiles": pair.conserved_core_smiles,
        "left_removed_fragment_smiles": pair.left_removed_fragment,
        "right_removed_fragment_smiles": pair.right_removed_fragment,
        "left_attachment_environment_radius_1": _transform_json(
            pair.left_attachment_environment_radius_1, valid
        ),
        "right_attachment_environment_radius_1": _transform_json(
            pair.right_attachment_environment_radius_1, valid
        ),
        "left_attachment_environment_radius_2": _transform_json(
            pair.left_attachment_environment_radius_2, valid
        ),
        "right_attachment_environment_radius_2": _transform_json(
            pair.right_attachment_environment_radius_2, valid
        ),
        "left_virtual_h_eligible": _optional_boolean(pair.left_virtual_h_eligible),
        "right_virtual_h_eligible": _optional_boolean(pair.right_virtual_h_eligible),
        "changed_left_atom_indices": _transform_json(
            pair.changed_left_atom_indices, valid
        ),
        "changed_right_atom_indices": _transform_json(
            pair.changed_right_atom_indices, valid
        ),
        "conserved_heavy_atoms": _optional_integer(pair.conserved_heavy_atoms),
        "left_heavy_atoms": _optional_integer(pair.left_heavy_atoms),
        "right_heavy_atoms": _optional_integer(pair.right_heavy_atoms),
        "changed_heavy_atom_fraction": pair.changed_heavy_atom_fraction,
        "stereo_changed": _optional_boolean(pair.stereo_changed),
        "stereo_elements": _transform_json(
            tuple(element.as_dict() for element in pair.stereo_elements), valid
        ),
        "a_to_b_direction_id": pair.a_to_b.direction_id,
        "b_to_a_direction_id": pair.b_to_a.direction_id,
        "a_to_b_exact_transformation_id": pair.a_to_b.exact_transformation_id,
        "b_to_a_exact_transformation_id": pair.b_to_a.exact_transformation_id,
        "a_to_b_transformation_class_id": pair.a_to_b.transformation_class_id,
        "b_to_a_transformation_class_id": pair.b_to_a.transformation_class_id,
        "a_to_b_environment_level_1_id": pair.a_to_b.environment_level_1_id,
        "b_to_a_environment_level_1_id": pair.b_to_a.environment_level_1_id,
        "a_to_b_environment_level_2_id": pair.a_to_b.environment_level_2_id,
        "b_to_a_environment_level_2_id": pair.b_to_a.environment_level_2_id,
        "undirected_exchange_id": pair.a_to_b.undirected_exchange_id,
        "candidate_material": (
            "" if pair.candidate_material is None else _json(pair.candidate_material)
        ),
        "candidate_digest": pair.candidate_digest,
        "tie_count": str(pair.tie_count),
        "tie_material": _json(pair.tie_material),
        "tie_digest": pair.tie_digest,
        "ambiguous": _boolean(pair.ambiguous),
        "warnings": _json(pair.warnings),
    }


def _json(value: Any) -> str:
    return canonical_json(value).decode("utf-8")


def _transform_json(value: Any, valid: bool) -> str:
    return _json(value) if valid else ""


def _boolean(value: bool) -> str:
    return "true" if value else "false"


def _optional_boolean(value: bool | None) -> str:
    return "" if value is None else _boolean(value)


def _optional_integer(value: int | None) -> str:
    return "" if value is None else str(value)


__all__ = [
    "CompiledEpisodeDirection",
    "CompiledTransformationPair",
    "PAIR_COLUMNS",
    "TransformationGeometry",
    "compile_transformation_geometry",
]
