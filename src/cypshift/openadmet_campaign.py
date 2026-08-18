"""Receipt-bound OpenADMET campaign episodes, masks, and viability facts."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import rdFingerprintGenerator

from cypshift.chemistry import standardize_molecule
from cypshift.openadmet_campaign_io import (
    R2B_SCHEMA_VERSION,
    CampaignIOError,
    bool_text,
    build_manifest,
    compact_json,
    csv_bytes,
    csv_rows,
    is_digest,
    json_bytes,
    json_data,
    json_list,
    read_bytes,
    validate_generated_projections,
    verify_r2a_receipts,
    write_new,
)
from cypshift.openadmet_topology import (
    MORGAN_FP_SIZE,
    MORGAN_INCLUDE_CHIRALITY,
    MORGAN_RADIUS,
    SIMILARITY_THRESHOLD,
)
from cypshift.openadmet_validation import (
    FOLD_COLUMNS,
    OBSERVATION_COLUMNS,
)
from cypshift.openadmet_validation_contract import (
    CANDIDATE_POOL_ID,
    ENDPOINTS,
    MASK_COLUMNS,
    PROTOCOL,
    PUBLIC_EPISODE_COLUMNS,
    SEEDS,
    SELECTED_ANCHOR_POLICY,
    SELECTOR_ENDPOINTS,
    STRESS_ANCHOR_POLICY,
    TRUTH_COLUMNS,
    VALUE_FIELDS,
    ValidationContractError,
    verify_r2b_contract,
)
from cypshift.openadmet_viability import (
    TOPOLOGY_VIABILITY_SCHEMA_VERSION,
    DirectPair,
    ViabilityError,
    build_topology_viability,
    compute_viability,
    verify_frozen_facts,
)
from cypshift.schema import MoleculeInput, MoleculeStatus

R2A_FILES = ("manifest.json", "direct_observations.csv", "group_folds.csv")


class OpenADMETCampaignError(CampaignIOError):
    """Unsafe or inconsistent R2B input or derived artifact."""


@dataclass(frozen=True, slots=True)
class CampaignArtifactResult:
    """Paths and counts for one completed R2B artifact build."""

    output_directory: Path
    manifest_path: Path
    episode_count: int
    expanded_query_count: int


@dataclass(frozen=True, slots=True)
class _Molecule:
    molecule_id: str
    raw_smiles: str
    standardized_smiles: str
    standardized_hash: str
    component: str


@dataclass(frozen=True, slots=True)
class _BaseEpisode:
    component: str
    selector: str
    anchor: str
    policy: str
    queries: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Inputs:
    observations: dict[str, dict[str, dict[str, str]]]
    molecules: dict[str, _Molecule]
    component_members: dict[str, tuple[str, ...]]
    outer_folds: dict[tuple[str, int], int]
    pairs: tuple[DirectPair, ...]


def build_openadmet_campaign_artifacts(
    *,
    validation_contract_path: Path,
    r2a_directory: Path,
    output_directory: Path,
    source_revision: str,
) -> CampaignArtifactResult:
    """Build the complete deterministic R2B artifact set without fitting."""

    if output_directory.exists():
        raise OpenADMETCampaignError(
            f"output path already exists: {output_directory}; refusing overwrite"
        )
    if not source_revision:
        raise OpenADMETCampaignError("source_revision must not be empty")
    contract_bytes = read_bytes(validation_contract_path, "validation contract")
    contract_hash = sha256(contract_bytes).hexdigest()
    contract = json_data(contract_bytes, "validation contract")
    try:
        verify_r2b_contract(contract, source_revision)
    except ValidationContractError as exc:
        raise OpenADMETCampaignError(str(exc)) from exc

    r2a_bytes = {
        name: read_bytes(r2a_directory / name, f"R2A {name}") for name in R2A_FILES
    }
    r2a_hashes = {name: sha256(data).hexdigest() for name, data in r2a_bytes.items()}
    r2a_manifest = json_data(r2a_bytes["manifest.json"], "R2A manifest")
    verify_r2a_receipts(
        contract=contract,
        contract_hash=contract_hash,
        source_revision=source_revision,
        manifest=r2a_manifest,
        hashes=r2a_hashes,
        data=r2a_bytes,
    )
    observations = csv_rows(
        r2a_bytes["direct_observations.csv"],
        OBSERVATION_COLUMNS,
        "direct_observations.csv",
    )
    folds = csv_rows(r2a_bytes["group_folds.csv"], FOLD_COLUMNS, "group_folds.csv")
    inputs = _validated_inputs(contract, source_revision, observations, folds)

    base_episodes = _base_episodes(inputs)
    public_rows, truth_rows, mask_rows = _episode_rows(
        base_episodes, inputs, source_revision
    )
    episode_diagnostics = _episode_diagnostics(base_episodes, inputs)
    selector_diagnostics: dict[str, dict[str, int]] = {}
    for selector in SELECTOR_ENDPOINTS:
        selected = [
            item
            for item in base_episodes
            if item.policy == SELECTED_ANCHOR_POLICY and item.selector == selector
        ]
        selector_diagnostics[selector] = {
            "selected_episodes": len(selected),
            "queries": sum(len(item.queries) for item in selected),
            "selector_labeled_query_cells": sum(
                bool(inputs.observations[query][selector]["point"])
                for item in selected
                for query in item.queries
            ),
        }
    endpoint_map, cliff_counts = compute_viability(
        inputs.pairs, inputs.observations, inputs.outer_folds, contract
    )
    expanded_queries = sum(
        len(json_list(row["query_molecule_ids"], "query molecule IDs"))
        for row in public_rows
    )
    artifact_counts = {
        "campaign_episodes_public_rows": len(public_rows),
        "campaign_episodes_truth_rows": len(truth_rows),
        "episode_label_masks_rows": len(mask_rows),
        "unique_episode_ids": len({row["episode_id"] for row in public_rows}),
        "expanded_queries": expanded_queries,
        "anchor_observation_references": len(mask_rows) * len(ENDPOINTS),
        "query_observation_references": expanded_queries * len(ENDPOINTS),
    }
    try:
        verify_frozen_facts(
            contract,
            episode_diagnostics,
            selector_diagnostics,
            endpoint_map,
            cliff_counts,
            artifact_counts,
        )
    except ViabilityError as exc:
        raise OpenADMETCampaignError(str(exc)) from exc

    public_bytes = csv_bytes(PUBLIC_EPISODE_COLUMNS, public_rows)
    truth_bytes = csv_bytes(TRUTH_COLUMNS, truth_rows)
    mask_bytes = csv_bytes(MASK_COLUMNS, mask_rows)
    validate_generated_projections(
        public_bytes,
        truth_bytes,
        mask_bytes,
        inputs.observations,
        inputs.component_members,
        inputs.outer_folds,
        source_revision,
    )
    viability = build_topology_viability(
        contract,
        contract_hash,
        r2a_hashes,
        endpoint_map,
        cliff_counts,
        episode_diagnostics,
    )
    viability_bytes = json_bytes(viability)
    output_bytes = {
        "direct_observations.csv": r2a_bytes["direct_observations.csv"],
        "group_folds.csv": r2a_bytes["group_folds.csv"],
        "campaign_episodes_public.csv": public_bytes,
        "campaign_episodes_truth.csv": truth_bytes,
        "episode_label_masks.csv": mask_bytes,
        "topology_viability.json": viability_bytes,
    }
    manifest = build_manifest(
        schema_version=R2B_SCHEMA_VERSION,
        contract=contract,
        contract_hash=contract_hash,
        source_revision=source_revision,
        r2a_hashes=r2a_hashes,
        outputs=output_bytes,
        observation_count=len(observations),
        fold_count=len(folds),
        public_rows=public_rows,
    )
    manifest_bytes = json_bytes(manifest)

    output_directory.mkdir(parents=True)
    for name, data in output_bytes.items():
        write_new(output_directory / name, data)
    manifest_path = output_directory / "manifest.json"
    write_new(manifest_path, manifest_bytes)
    return CampaignArtifactResult(
        output_directory=output_directory,
        manifest_path=manifest_path,
        episode_count=len(public_rows),
        expanded_query_count=sum(
            len(json_list(row["query_molecule_ids"], "query molecule IDs"))
            for row in public_rows
        ),
    )


def _validated_inputs(
    contract: Mapping[str, Any],
    source_revision: str,
    observation_rows: Sequence[dict[str, str]],
    fold_rows: Sequence[dict[str, str]],
) -> _Inputs:
    expected = _mapping(_mapping(contract, "direct_compiler"), "row_contract")
    direct = _mapping(_mapping(contract, "input_chain"), "direct_source")
    direct_path = cast(str, direct["path"])
    direct_hash = cast(str, direct["sha256"])
    if len(observation_rows) != expected.get("expected_rows"):
        raise OpenADMETCampaignError("direct-observation row-count mismatch")
    by_molecule: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    metadata: dict[str, tuple[str, str, str, str, str, str]] = {}
    seen_observations: set[str] = set()
    for row in observation_rows:
        molecule_id = row["molecule_id"]
        endpoint = row["endpoint"]
        if (
            not molecule_id
            or endpoint not in ENDPOINTS
            or endpoint in by_molecule[molecule_id]
        ):
            raise OpenADMETCampaignError("observation cardinality or endpoint defect")
        if not is_digest(row["observation_id"]):
            raise OpenADMETCampaignError("invalid observation ID")
        try:
            source_row = int(row["source_row"])
        except ValueError as exc:
            raise OpenADMETCampaignError("invalid observation source row") from exc
        if (
            source_row < 2
            or row["source_file"] != direct_path
            or row["source_row_id"] != f"{direct_path}:{source_row}"
            or row["source_sha256"] != direct_hash
            or row["raw_structure_sha256"]
            != sha256(row["raw_smiles"].encode()).hexdigest()
        ):
            raise OpenADMETCampaignError("observation source receipt mismatch")
        expected_id = sha256(
            f"{source_revision}|{row['source_file']}|{row['source_row']}|{endpoint}".encode()
        ).hexdigest()
        if row["observation_id"] != expected_id or expected_id in seen_observations:
            raise OpenADMETCampaignError("observation identity mismatch")
        seen_observations.add(expected_id)
        _validate_observation_values(row)
        values = (
            row["raw_smiles"],
            row["standardized_structure_hash"],
            row["similarity_component_hash"],
            row["scaffold_group_hash"],
            row["source_row_id"],
            row["raw_structure_sha256"],
        )
        if molecule_id in metadata and metadata[molecule_id] != values:
            raise OpenADMETCampaignError("molecule metadata differs across endpoints")
        metadata[molecule_id] = values
        by_molecule[molecule_id][endpoint] = row
    if any(set(rows) != set(ENDPOINTS) for rows in by_molecule.values()):
        raise OpenADMETCampaignError(
            "one observation per molecule and endpoint required"
        )
    if len(by_molecule) != expected.get("source_identities"):
        raise OpenADMETCampaignError("direct molecule identity count mismatch")

    molecules: dict[str, _Molecule] = {}
    components: dict[str, list[str]] = defaultdict(list)
    for molecule_id in sorted(by_molecule):
        raw_smiles, expected_hash, component, scaffold, _source_row, _raw_hash = (
            metadata[molecule_id]
        )
        if (
            not is_digest(expected_hash)
            or not is_digest(component)
            or not is_digest(scaffold)
        ):
            raise OpenADMETCampaignError("invalid chemistry or component digest")
        record = standardize_molecule(
            MoleculeInput(molecule_id, raw_smiles, "smiles", "openadmet-r2b", "{}")
        )
        if (
            record.status is not MoleculeStatus.ACCEPTED
            or record.standardized_structure is None
            or record.standardized_structure_hash != expected_hash
        ):
            raise OpenADMETCampaignError(
                f"standardized-structure receipt mismatch for {molecule_id}"
            )
        molecules[molecule_id] = _Molecule(
            molecule_id,
            raw_smiles,
            record.standardized_structure,
            expected_hash,
            component,
        )
        components[component].append(molecule_id)
    component_members = {
        component: tuple(sorted(members)) for component, members in components.items()
    }
    outer_folds = _validate_folds(fold_rows, molecules)
    pairs = _direct_pairs(molecules, component_members)
    return _Inputs(by_molecule, molecules, component_members, outer_folds, pairs)


def _validate_observation_values(row: Mapping[str, str]) -> None:
    present: dict[str, bool] = {}
    numbers: dict[str, float | None] = {}
    for field in VALUE_FIELDS:
        text = row[field]
        raw_text = row[f"raw_{field}"]
        present[field] = bool(text)
        if bool(raw_text) != present[field]:
            raise OpenADMETCampaignError("raw and parsed value presence mismatch")
        if text:
            try:
                value = float(text)
                raw_value = float(raw_text)
            except ValueError as exc:
                raise OpenADMETCampaignError(
                    "invalid parsed observation value"
                ) from exc
            if not math.isfinite(value) or not math.isfinite(raw_value):
                raise OpenADMETCampaignError("non-finite parsed observation value")
            if value != raw_value:
                raise OpenADMETCampaignError("raw and parsed value mismatch")
            numbers[field] = value
        else:
            numbers[field] = None
    point, low, high, std = (numbers[field] for field in VALUE_FIELDS)
    if (
        (std is not None and std < 0)
        or (low is not None and high is not None and low > high)
        or (point is not None and low is not None and low > point)
        or (point is not None and high is not None and point > high)
    ):
        raise OpenADMETCampaignError("invalid parsed observation bounds")
    if row["point_eligible"] != bool_text(present["point"]):
        raise OpenADMETCampaignError("point eligibility mismatch")
    if row["anchor_eligible"] != bool_text(row["value_state"] == "complete"):
        raise OpenADMETCampaignError("anchor eligibility mismatch")
    state = (
        "missing"
        if not any(present.values())
        else "orphan_auxiliary"
        if not present["point"]
        else "complete"
        if all(present.values())
        else "partial"
    )
    if row["value_state"] != state:
        raise OpenADMETCampaignError("observation state mismatch")


def _validate_folds(
    rows: Sequence[dict[str, str]], molecules: Mapping[str, _Molecule]
) -> dict[tuple[str, int], int]:
    if len(rows) != len(molecules) * len(SEEDS) * 5:
        raise OpenADMETCampaignError("group-fold row-count mismatch")
    seen: set[tuple[str, int, int]] = set()
    outer: dict[tuple[str, int], int] = {}
    inner: dict[tuple[str, int, int], str] = {}
    for row in rows:
        molecule_id = row["molecule_id"]
        if molecule_id not in molecules:
            raise OpenADMETCampaignError("fold contains unknown molecule")
        try:
            repeat = int(row["repeat"])
            seed = int(row["seed"])
            outer_fold = int(row["outer_fold"])
            validation_fold = int(row["outer_validation_fold"])
        except ValueError as exc:
            raise OpenADMETCampaignError("fold integer field is invalid") from exc
        if (
            repeat not in range(len(SEEDS))
            or seed != SEEDS[repeat]
            or outer_fold not in range(5)
            or validation_fold not in range(5)
        ):
            raise OpenADMETCampaignError("fold value is outside contract")
        component = molecules[molecule_id].component
        if row["similarity_component_hash"] != component:
            raise OpenADMETCampaignError("fold component mismatch")
        key = (molecule_id, repeat, validation_fold)
        if key in seen:
            raise OpenADMETCampaignError("duplicate fold row")
        seen.add(key)
        group_key = (component, repeat)
        if group_key in outer and outer[group_key] != outer_fold:
            raise OpenADMETCampaignError("component crosses an outer fold")
        outer[group_key] = outer_fold
        expected_blank = outer_fold == validation_fold
        inner_fold = row["inner_fold"]
        if expected_blank != (inner_fold == ""):
            raise OpenADMETCampaignError("inner-fold holdout mismatch")
        if inner_fold and inner_fold not in {"0", "1", "2", "3"}:
            raise OpenADMETCampaignError("inner fold is outside contract")
        inner_key = (component, repeat, validation_fold)
        if inner_key in inner and inner[inner_key] != inner_fold:
            raise OpenADMETCampaignError("component crosses an inner fold")
        inner[inner_key] = inner_fold
    if len(seen) != len(rows):
        raise OpenADMETCampaignError("fold identity coverage mismatch")
    return outer


def _direct_pairs(
    molecules: Mapping[str, _Molecule], components: Mapping[str, tuple[str, ...]]
) -> tuple[DirectPair, ...]:
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=MORGAN_RADIUS,
        fpSize=MORGAN_FP_SIZE,
        includeChirality=MORGAN_INCLUDE_CHIRALITY,
    )
    fingerprints: dict[str, Any] = {}
    with rdBase.BlockLogs():
        for molecule_id in sorted(molecules):
            molecule = Chem.MolFromSmiles(molecules[molecule_id].standardized_smiles)
            if molecule is None:
                raise OpenADMETCampaignError(
                    "cannot parse recomputed standardized SMILES"
                )
            fingerprints[molecule_id] = generator.GetFingerprint(molecule)
    pairs: list[DirectPair] = []
    for component in sorted(components):
        members = components[component]
        for index, left in enumerate(members[:-1]):
            similarities = DataStructs.BulkTanimotoSimilarity(
                fingerprints[left],
                [fingerprints[right] for right in members[index + 1 :]],
            )
            for right, similarity in zip(
                members[index + 1 :], similarities, strict=True
            ):
                if similarity >= SIMILARITY_THRESHOLD:
                    pairs.append(DirectPair(left, right, component, float(similarity)))
    return tuple(pairs)


def _base_episodes(inputs: _Inputs) -> tuple[_BaseEpisode, ...]:
    similarities = {
        (pair.left, pair.right): pair.similarity for pair in inputs.pairs
    } | {(pair.right, pair.left): pair.similarity for pair in inputs.pairs}
    episodes: list[_BaseEpisode] = []
    for component in sorted(inputs.component_members):
        members = inputs.component_members[component]
        for selector in SELECTOR_ENDPOINTS:
            complete = [
                molecule_id
                for molecule_id in members
                if inputs.observations[molecule_id][selector]["value_state"]
                == "complete"
            ]
            if not complete:
                continue
            selected = min(
                complete,
                key=lambda molecule_id: (
                    -float(inputs.observations[molecule_id][selector]["point"]),
                    float(inputs.observations[molecule_id][selector]["high"])
                    - float(inputs.observations[molecule_id][selector]["low"]),
                    molecule_id,
                ),
            )
            selected_queries = _queries(selected, members, inputs, similarities)
            if not selected_queries:
                continue
            episodes.append(
                _BaseEpisode(
                    component,
                    selector,
                    selected,
                    SELECTED_ANCHOR_POLICY,
                    selected_queries,
                )
            )
            stress_candidates = [
                molecule_id
                for molecule_id in complete
                if _queries(molecule_id, members, inputs, similarities)
            ]
            stress = min(
                stress_candidates,
                key=lambda molecule_id: (
                    sha256(
                        (
                            "20260818|deterministic-random-anchor-stress-v1|"
                            f"{component}|{selector}|{molecule_id}"
                        ).encode()
                    ).hexdigest(),
                    molecule_id,
                ),
            )
            episodes.append(
                _BaseEpisode(
                    component,
                    selector,
                    stress,
                    STRESS_ANCHOR_POLICY,
                    _queries(stress, members, inputs, similarities),
                )
            )
    return tuple(episodes)


def _queries(
    anchor: str,
    members: Sequence[str],
    inputs: _Inputs,
    similarities: Mapping[tuple[str, str], float],
) -> tuple[str, ...]:
    candidates = [
        molecule_id
        for molecule_id in members
        if molecule_id != anchor
        and (anchor, molecule_id) in similarities
        and any(
            inputs.observations[molecule_id][endpoint]["point"]
            for endpoint in ENDPOINTS
        )
    ]
    return tuple(
        sorted(candidates, key=lambda item: (-similarities[(anchor, item)], item))[:10]
    )


def _episode_rows(
    base_episodes: Sequence[_BaseEpisode], inputs: _Inputs, source_revision: str
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    public: list[dict[str, str]] = []
    truth: list[dict[str, str]] = []
    masks: list[dict[str, str]] = []
    for episode in base_episodes:
        for repeat in range(len(SEEDS)):
            outer_fold = inputs.outer_folds[(episode.component, repeat)]
            material = "|".join(
                (
                    source_revision,
                    PROTOCOL,
                    str(repeat),
                    episode.component,
                    episode.selector,
                    episode.policy,
                )
            )
            episode_id = sha256(material.encode()).hexdigest()
            public.append(
                {
                    "episode_id": episode_id,
                    "protocol": PROTOCOL,
                    "repeat": str(repeat),
                    "outer_fold": str(outer_fold),
                    "outer_group_id": episode.component,
                    "query_molecule_ids": compact_json(list(episode.queries)),
                    "candidate_pool_id": CANDIDATE_POOL_ID,
                    "episode_policy_id": episode.policy,
                }
            )
            truth.append(
                {
                    "episode_id": episode_id,
                    "selector_cyp_truth": episode.selector,
                    "anchor_molecule_id_truth": episode.anchor,
                    "query_truth_references": compact_json(
                        [_references(item, inputs) for item in episode.queries]
                    ),
                    "query_truth_availability_masks": compact_json(
                        [_availability(item, inputs) for item in episode.queries]
                    ),
                }
            )
            masks.append(
                {
                    "episode_id": episode_id,
                    "anchor_molecule_id_truth": episode.anchor,
                    "anchor_observation_references": compact_json(
                        _references(episode.anchor, inputs)
                    ),
                    "anchor_value_availability_mask": compact_json(
                        _availability(episode.anchor, inputs)
                    ),
                }
            )
    public.sort(key=lambda row: row["episode_id"])
    truth.sort(key=lambda row: row["episode_id"])
    masks.sort(key=lambda row: row["episode_id"])
    ids = [row["episode_id"] for row in public]
    if (
        len(ids) != len(set(ids))
        or ids != [row["episode_id"] for row in truth]
        or ids != [row["episode_id"] for row in masks]
    ):
        raise OpenADMETCampaignError("episode IDs are not a unique one-to-one join")
    return public, truth, masks


def _references(molecule_id: str, inputs: _Inputs) -> dict[str, str]:
    return {
        endpoint: inputs.observations[molecule_id][endpoint]["observation_id"]
        for endpoint in ENDPOINTS
    }


def _availability(molecule_id: str, inputs: _Inputs) -> dict[str, dict[str, bool]]:
    return {
        endpoint: {
            field: bool(inputs.observations[molecule_id][endpoint][field])
            for field in VALUE_FIELDS
        }
        for endpoint in ENDPOINTS
    }


def _episode_diagnostics(
    base_episodes: Sequence[_BaseEpisode], inputs: _Inputs
) -> dict[str, Any]:
    primary = [item for item in base_episodes if item.policy == SELECTED_ANCHOR_POLICY]
    stress = [item for item in base_episodes if item.policy == STRESS_ANCHOR_POLICY]
    inference: dict[str, int] = {}
    for name, episodes in (
        ("primary_anchor_inference", primary),
        ("stress_anchor_inference", stress),
    ):
        inference[name] = sum(
            set(inputs.component_members[item.component]) - set(item.queries)
            == {item.anchor}
            for item in episodes
        )
    return {
        "primary_base": {
            "selected_episodes": len(primary),
            "queries": sum(len(item.queries) for item in primary),
        },
        "stress_base": {
            "selected_episodes": len(stress),
            "queries": sum(len(item.queries) for item in stress),
        },
        "expanded_artifact_rows_each": len(base_episodes) * len(SEEDS),
        "total_expanded_queries": sum(len(item.queries) for item in base_episodes)
        * len(SEEDS),
        "anchor_observation_references": len(base_episodes)
        * len(SEEDS)
        * len(ENDPOINTS),
        "query_observation_references": sum(len(item.queries) for item in base_episodes)
        * len(SEEDS)
        * len(ENDPOINTS),
        "primary_anchor_inference": f"{inference['primary_anchor_inference']}/{len(primary)}",
        "stress_anchor_inference": f"{inference['stress_anchor_inference']}/{len(stress)}",
    }


def _mapping(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise OpenADMETCampaignError(f"{key} must be an object")
    return cast(dict[str, Any], item)


__all__ = [
    "CampaignArtifactResult",
    "OpenADMETCampaignError",
    "R2B_SCHEMA_VERSION",
    "TOPOLOGY_VIABILITY_SCHEMA_VERSION",
    "build_openadmet_campaign_artifacts",
]
