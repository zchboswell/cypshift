"""Production-shaped, redistributable supported R5C acceptance fixture."""

from __future__ import annotations

import io
import json
from hashlib import sha256
from itertools import combinations
from pathlib import Path

import numpy as np
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator

from cypshift import openadmet_transformation_compiler as compiler
from cypshift.chemistry import standardize_molecule
from cypshift.openadmet_oracle_source import INPUT_FILES, OOF_COLUMNS
from cypshift.openadmet_transformation_compiler import (
    PAIR_COLUMNS,
    CompiledTransformationPair,
)
from cypshift.openadmet_transformation_io import canonical_csv_bytes
from cypshift.openadmet_transformation_serialization import EPISODE_COLUMNS
from cypshift.openadmet_transformations import extract_transformation_pair
from cypshift.openadmet_validation import FOLD_COLUMNS, OBSERVATION_COLUMNS
from cypshift.openadmet_validation_contract import (
    MASK_COLUMNS,
    PUBLIC_EPISODE_COLUMNS,
    TRUTH_COLUMNS,
)
from cypshift.schema import MoleculeInput, MoleculeRecord

ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
SUBSTITUENTS = ("O", "N", "F", "Cl", "Br")
COMPONENTS = 70


def _digest(value: bytes | str) -> str:
    return sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def _json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def _npy(value: np.ndarray) -> bytes:
    stream = io.BytesIO()
    np.lib.format.write_array(stream, value, version=(1, 0), allow_pickle=False)
    return stream.getvalue()


def _point(component: int, variant: int, endpoint: int) -> str:
    return format(1.0 + component * 0.01 + variant * 0.2 + endpoint * 0.03, ".17g")


def _records() -> tuple[
    dict[str, MoleculeRecord], dict[str, int], dict[int, tuple[str, ...]]
]:
    records: dict[str, MoleculeRecord] = {}
    component_by_molecule: dict[str, int] = {}
    molecules_by_component: dict[int, tuple[str, ...]] = {}
    for component in range(COMPONENTS):
        molecules: list[str] = []
        for variant, substituent in enumerate(SUBSTITUENTS):
            molecule = f"m{component:02d}-v{variant}"
            smiles = f"[{component + 10}CH3]c1ccc({substituent})cc1"
            record = standardize_molecule(
                MoleculeInput(molecule, smiles, "smiles", "r5c", "synthetic")
            )
            if record.standardized_structure is None:
                raise ValueError("supported fixture standardization failed")
            records[molecule] = record
            component_by_molecule[molecule] = component
            molecules.append(molecule)
        molecules_by_component[component] = tuple(molecules)
    return records, component_by_molecule, molecules_by_component


def _fold_assignments(
    episode_pools: dict[int, tuple[int, ...]],
) -> dict[tuple[int, int, int], int]:
    result: dict[tuple[int, int, int], int] = {}
    for repeat in range(3):
        for validation in range(5):
            training = [
                component
                for component in range(COMPONENTS)
                if (component + repeat) % 5 != validation
            ]
            selected = [
                component
                for component in episode_pools[repeat]
                if component in training
            ]
            remainder = [item for item in training if item not in selected]
            for index, component in enumerate(selected):
                result[(component, repeat, validation)] = index % 4
            for index, component in enumerate(remainder):
                result[(component, repeat, validation)] = index % 4
    return result


def supported_fixture(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    """Write one deterministic supported source fixture and return exact receipts."""

    root.mkdir()
    records, component_by_molecule, molecules_by_component = _records()
    episode_pools = {
        0: tuple(range(25)),
        1: tuple(range(25, 50)),
        2: tuple(range(25)),
    }
    inner = _fold_assignments(episode_pools)
    component_ids = {
        component: _digest(f"component-{component}") for component in range(COMPONENTS)
    }
    direct: list[dict[str, str]] = []
    references: dict[str, dict[str, str]] = {}
    availability: dict[str, dict[str, dict[str, bool]]] = {}
    source_row = 0
    for molecule, record in records.items():
        component = component_by_molecule[molecule]
        variant = int(molecule.rsplit("v", 1)[1])
        references[molecule] = {}
        availability[molecule] = {}
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            source_row += 1
            point = _point(component, variant, endpoint_index)
            low = format(float(point) - 0.1, ".17g")
            high = format(float(point) + 0.1, ".17g")
            observation = _digest(f"observation|{molecule}|{endpoint}")
            references[molecule][endpoint] = observation
            availability[molecule][endpoint] = dict.fromkeys(
                ("point", "low", "high", "std"), True
            )
            raw = record.raw_structure
            assert record.standardized_structure_hash is not None
            direct.append(
                {
                    "observation_id": observation,
                    "molecule_id": molecule,
                    "source_row_id": str(source_row),
                    "source_file": "cyp-challenge-TRAIN_inhibition.csv",
                    "source_row": str(source_row),
                    "source_sha256": "a" * 64,
                    "endpoint": endpoint,
                    "raw_smiles": raw,
                    "raw_point": point,
                    "raw_low": low,
                    "raw_high": high,
                    "raw_std": "0.1",
                    "point": point,
                    "low": low,
                    "high": high,
                    "std": "0.1",
                    "raw_structure_sha256": _digest(raw),
                    "standardized_structure_hash": record.standardized_structure_hash,
                    "similarity_component_hash": component_ids[component],
                    "scaffold_group_hash": _digest(f"scaffold-{component}"),
                    "value_state": "complete",
                    "point_eligible": "true",
                    "anchor_eligible": "true",
                }
            )
    folds: list[dict[str, str]] = []
    for molecule, component in component_by_molecule.items():
        for repeat in range(3):
            assigned = (component + repeat) % 5
            for validation in range(5):
                folds.append(
                    {
                        "molecule_id": molecule,
                        "similarity_component_hash": component_ids[component],
                        "repeat": str(repeat),
                        "seed": str(20260810 + repeat),
                        "outer_fold": str(assigned),
                        "outer_validation_fold": str(validation),
                        "inner_fold": (
                            ""
                            if assigned == validation
                            else str(inner[(component, repeat, validation)])
                        ),
                    }
                )
    pair_rows: list[dict[str, str]] = []
    pair_index: dict[frozenset[str], dict[str, str]] = {}
    for component, molecules in molecules_by_component.items():
        for left, right in combinations(molecules, 2):
            result = extract_transformation_pair(records[left], records[right])
            if result.extraction_status not in {"VALID_SINGLE", "VALID_DOUBLE"}:
                raise ValueError("supported fixture transformation failed")
            row = compiler._pair_row(  # noqa: SLF001
                CompiledTransformationPair(result, component_ids[component], True, True)
            )
            pair_rows.append(row)
            pair_index[frozenset((left, right))] = row
    public: list[dict[str, str]] = []
    truth: list[dict[str, str]] = []
    masks: list[dict[str, str]] = []
    episode_rows: list[dict[str, str]] = []
    for repeat, pool in episode_pools.items():
        for component in pool:
            molecules = molecules_by_component[component]
            _append_episode(
                public,
                truth,
                masks,
                episode_rows,
                episode_id=_digest(f"selected|{repeat}|{component}"),
                policy="selected_anchor",
                repeat=repeat,
                outer=(component + repeat) % 5,
                component_id=component_ids[component],
                anchor=molecules[0],
                queries=molecules[1:],
                references=references,
                availability=availability,
                pair_index=pair_index,
            )
        for outer in range(5):
            component = next(item for item in pool if (item + repeat) % 5 == outer)
            molecules = molecules_by_component[component]
            _append_episode(
                public,
                truth,
                masks,
                episode_rows,
                episode_id=_digest(f"stress|{repeat}|{component}"),
                policy="deterministic_random_anchor_stress",
                repeat=repeat,
                outer=outer,
                component_id=component_ids[component],
                anchor=molecules[0],
                queries=(molecules[1],),
                references=references,
                availability=availability,
                pair_index=pair_index,
            )
    molecule_order = tuple(records)
    feature_rows = []
    for molecule in molecule_order:
        record = records[molecule]
        component = component_by_molecule[molecule]
        assert record.standardized_structure_hash is not None
        feature_rows.append(
            {
                "molecule_id": molecule,
                "raw_structure_sha256": _digest(record.raw_structure),
                "standardized_structure_hash": record.standardized_structure_hash,
                "similarity_component_hash": component_ids[component],
            }
        )
    morgan = rdFingerprintGenerator.GetMorganGenerator(
        radius=2, fpSize=4096, includeChirality=True
    )
    morgan_rows = []
    for molecule in molecule_order:
        mol = Chem.MolFromSmiles(records[molecule].standardized_structure or "")
        if mol is None:
            raise ValueError("supported fixture molecule parse failed")
        morgan_rows.append(morgan.GetFingerprintAsNumPy(mol).astype(np.uint8))
    morgan_binary = np.stack(morgan_rows)
    rng = np.random.default_rng(20260821)
    arrays = {
        "morgan_binary.npy": _npy(morgan_binary),
        "maplight_morgan_count.npy": _npy(
            rng.integers(0, 4, (len(records), 1024), dtype=np.int8)
        ),
        "maplight_avalon_count.npy": _npy(
            rng.integers(0, 3, (len(records), 1024), dtype=np.int8)
        ),
        "maplight_erg.npy": _npy(rng.normal(size=(len(records), 315))),
        "maplight_rdkit_descriptors.npy": _npy(rng.normal(size=(len(records), 200))),
    }
    feature_rows_data = canonical_csv_bytes(
        (
            "molecule_id",
            "raw_structure_sha256",
            "standardized_structure_hash",
            "similarity_component_hash",
        ),
        feature_rows,
    )
    feature_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1",
        "rows": {
            "path": "feature_rows.csv",
            "columns": list(feature_rows[0]),
            "rows": len(feature_rows),
            "sha256": _digest(feature_rows_data),
        },
        "arrays": {
            Path(name).stem: {"path": name, "npy_sha256": _digest(data)}
            for name, data in arrays.items()
        },
        "accounting": dict.fromkeys(
            ("target_values_parsed", "model_fits", "predictions", "metric_evaluations"),
            0,
        ),
        "authority": {
            "targets": False,
            "features": False,
            "models": False,
            "predictions": False,
            "metrics": False,
            "fold_assignments": False,
            "submissions": False,
            "tdi": False,
            "test": False,
            "transduction": False,
        },
    }
    outer_oof, inner_oof = _oof_rows(
        molecule_order, component_by_molecule, component_ids
    )
    data = {
        "direct_observations.csv": canonical_csv_bytes(OBSERVATION_COLUMNS, direct),
        "group_folds.csv": canonical_csv_bytes(FOLD_COLUMNS, folds),
        "campaign_episodes_public.csv": canonical_csv_bytes(
            PUBLIC_EPISODE_COLUMNS, public
        ),
        "campaign_episodes_truth.csv": canonical_csv_bytes(TRUTH_COLUMNS, truth),
        "episode_label_masks.csv": canonical_csv_bytes(MASK_COLUMNS, masks),
        "feature_manifest.json": _json(feature_manifest),
        "feature_rows.csv": feature_rows_data,
        **arrays,
        "global_oof_predictions.csv": canonical_csv_bytes(OOF_COLUMNS, outer_oof),
        "global_inner_oof_predictions.csv": canonical_csv_bytes(OOF_COLUMNS, inner_oof),
        "transformation_pairs.csv": canonical_csv_bytes(PAIR_COLUMNS, pair_rows),
        "episode_transformations.csv": canonical_csv_bytes(
            EPISODE_COLUMNS, episode_rows
        ),
        "transformation_coverage.json": _json(
            {"status": "R4_TRANSFORMATION_COVERAGE_SUPPORTED"}
        ),
    }
    paths = {}
    for name in INPUT_FILES:
        path = root / name
        path.write_bytes(data[name])
        paths[name] = path
    return paths, {name: _digest(data[name]) for name in INPUT_FILES}


def _append_episode(
    public: list[dict[str, str]],
    truth: list[dict[str, str]],
    masks: list[dict[str, str]],
    episode_rows: list[dict[str, str]],
    *,
    episode_id: str,
    policy: str,
    repeat: int,
    outer: int,
    component_id: str,
    anchor: str,
    queries: tuple[str, ...],
    references: dict[str, dict[str, str]],
    availability: dict[str, dict[str, dict[str, bool]]],
    pair_index: dict[frozenset[str], dict[str, str]],
) -> None:
    public.append(
        {
            "episode_id": episode_id,
            "protocol": "ANCHOR_EXPANSION_HOLDOUT",
            "repeat": str(repeat),
            "outer_fold": str(outer),
            "outer_group_id": component_id,
            "query_molecule_ids": json.dumps(list(queries), separators=(",", ":")),
            "candidate_pool_id": "DEFERRED_NO_INFERRED_POOL_V1",
            "episode_policy_id": policy,
        }
    )
    truth.append(
        {
            "episode_id": episode_id,
            "selector_cyp_truth": "CYP3A4",
            "anchor_molecule_id_truth": anchor,
            "query_truth_references": json.dumps(
                [references[item] for item in queries], separators=(",", ":")
            ),
            "query_truth_availability_masks": json.dumps(
                [availability[item] for item in queries], separators=(",", ":")
            ),
        }
    )
    masks.append(
        {
            "episode_id": episode_id,
            "anchor_molecule_id_truth": anchor,
            "anchor_observation_references": json.dumps(
                references[anchor], sort_keys=True, separators=(",", ":")
            ),
            "anchor_value_availability_mask": json.dumps(
                availability[anchor], sort_keys=True, separators=(",", ":")
            ),
        }
    )
    for rank, query in enumerate(queries, 1):
        pair = pair_index[frozenset((anchor, query))]
        prefix = "a_to_b" if pair["left_molecule_id"] == anchor else "b_to_a"
        episode_rows.append(
            {
                "episode_id": episode_id,
                "episode_policy_id": policy,
                "repeat": str(repeat),
                "outer_fold": str(outer),
                "outer_group_id": component_id,
                "query_molecule_id": query,
                "query_rank": str(rank),
                "anchor_molecule_id": anchor,
                "transformation_pair_id": pair["transformation_pair_id"],
                "direction_id": pair[f"{prefix}_direction_id"],
                "extraction_status": pair["extraction_status"],
                "failure_code": pair["failure_code"],
                "cut_count": pair["cut_count"],
                "exact_transformation_id": pair[f"{prefix}_exact_transformation_id"],
                "transformation_class_id": pair[f"{prefix}_transformation_class_id"],
                "environment_level_1_id": pair[f"{prefix}_environment_level_1_id"],
                "environment_level_2_id": pair[f"{prefix}_environment_level_2_id"],
                "changed_heavy_atom_fraction": pair["changed_heavy_atom_fraction"],
                "cyp3a4_training_family_exact_support_count": "0",
                "cyp3a4_training_family_class_support_count": "0",
                "tie_count": pair["tie_count"],
                "tie_material": pair["tie_material"],
                "tie_digest": pair["tie_digest"],
                "ambiguous": pair["ambiguous"],
                "warnings": pair["warnings"],
            }
        )


def _oof_rows(
    molecules: tuple[str, ...],
    component_by_molecule: dict[str, int],
    component_ids: dict[int, str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    outer_rows: list[dict[str, str]] = []
    inner_rows: list[dict[str, str]] = []
    model_id = _digest("synthetic-oof-model")
    for molecule in molecules:
        component = component_by_molecule[molecule]
        prediction = _point(component, int(molecule.rsplit("v", 1)[1]), 3)
        for repeat in range(3):
            for outer in range(5):
                base = {
                    "molecule_id": molecule,
                    "endpoint": "CYP3A4",
                    "component_id": component_ids[component],
                    "repeat": str(repeat),
                    "outer_fold": str(outer),
                    "system_id": "TRACE-G0-MAPL-FIXED",
                    "prediction": prediction,
                    "applicability_score": "1.0",
                    "model_id": model_id,
                    "feature_spec_id": "maplight-fixed-stage-a-v1",
                    "split_id": "s" * 64,
                }
                outer_rows.append(
                    {
                        **base,
                        "inner_fold": "",
                        "scope": "openadmet-direct-outer-v1",
                    }
                )
                for inner in range(4):
                    inner_rows.append(
                        {
                            **base,
                            "inner_fold": str(inner),
                            "scope": f"openadmet-direct-inner-v1|outer={outer}",
                        }
                    )
    return outer_rows, inner_rows


__all__ = ["supported_fixture"]
