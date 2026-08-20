from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path

import pytest

import cypshift.openadmet_transformation_compiler as transformation_compiler
from cypshift.chemistry import standardize_molecule
from cypshift.openadmet_transformation_compiler import (
    PAIR_COLUMNS,
    CompiledTransformationPair,
    compile_transformation_geometry,
)
from cypshift.openadmet_transformation_coverage import (
    OpenADMETTransformationCoverageError,
    load_transformation_projection,
)
from cypshift.openadmet_transformation_io import (
    OBSERVATION_COLUMNS,
    TransformationSourcePaths,
    canonical_csv_bytes,
    canonical_json_bytes,
)
from cypshift.openadmet_transformation_projection import (
    project_openadmet_transformation_inputs,
)
from cypshift.openadmet_transformation_types import TransformationPairResult
from cypshift.openadmet_validation import FOLD_COLUMNS
from cypshift.openadmet_validation_contract import MASK_COLUMNS, PUBLIC_EPISODE_COLUMNS
from cypshift.schema import MoleculeInput, MoleculeRecord

ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _fixture(
    root: Path, *, reverse: bool = False
) -> tuple[TransformationSourcePaths, dict[str, str]]:
    root.mkdir(parents=True)
    molecules = {"anchor": "CCO", "query": "CCN", "foreign": "C=O"}
    component = _digest("component-a")
    foreign_component = _digest("component-b")
    structures = []
    for molecule_id, smiles in molecules.items():
        structures.append(
            {
                "molecule_id": molecule_id,
                "raw_smiles": smiles,
                "raw_structure_sha256": _digest(smiles),
                "standardized_smiles": smiles,
                "standardized_structure_hash": _digest(smiles),
                "similarity_component_hash": (
                    foreign_component if molecule_id == "foreign" else component
                ),
            }
        )
    by_id = {row["molecule_id"]: row for row in structures}
    direct = []
    for molecule_id in molecules:
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            structure = by_id[molecule_id]
            direct.append(
                {
                    "observation_id": _digest(f"obs:{molecule_id}:{endpoint}"),
                    "molecule_id": molecule_id,
                    "source_row_id": f"source:{molecule_id}",
                    "source_file": "source.csv",
                    "source_row": str(endpoint_index + 1),
                    "source_sha256": "0" * 64,
                    "endpoint": endpoint,
                    "raw_smiles": molecules[molecule_id],
                    "raw_point": "POISON",
                    "raw_low": "POISON",
                    "raw_high": "POISON",
                    "raw_std": "POISON",
                    "point": "POISON",
                    "low": "POISON",
                    "high": "POISON",
                    "std": "POISON",
                    "raw_structure_sha256": structure["raw_structure_sha256"],
                    "standardized_structure_hash": structure[
                        "standardized_structure_hash"
                    ],
                    "similarity_component_hash": structure["similarity_component_hash"],
                    "scaffold_group_hash": "1" * 64,
                    "value_state": "complete",
                    "point_eligible": "POISON",
                    "anchor_eligible": "POISON",
                }
            )
    folds = []
    for molecule_id in molecules:
        structure = by_id[molecule_id]
        outer = 1 if molecule_id == "foreign" else 0
        for repeat in range(3):
            for validation in range(5):
                folds.append(
                    {
                        "molecule_id": molecule_id,
                        "similarity_component_hash": structure[
                            "similarity_component_hash"
                        ],
                        "repeat": str(repeat),
                        "seed": str(20260810 + repeat),
                        "outer_fold": str(outer),
                        "outer_validation_fold": str(validation),
                        "inner_fold": "" if validation == outer else "0",
                    }
                )
    episode = {
        "episode_id": _digest("episode-a"),
        "protocol": "ANCHOR_EXPANSION_HOLDOUT",
        "repeat": "0",
        "outer_fold": "0",
        "outer_group_id": component,
        "query_molecule_ids": '["query"]',
        "candidate_pool_id": "DEFERRED_NO_INFERRED_POOL_V1",
        "episode_policy_id": "selected_anchor",
    }
    mask = {
        "episode_id": episode["episode_id"],
        "anchor_molecule_id_truth": "anchor",
        "anchor_observation_references": "POISON",
        "anchor_value_availability_mask": "POISON",
    }
    values = {
        "direct_observations.csv": canonical_csv_bytes(
            OBSERVATION_COLUMNS, list(reversed(direct)) if reverse else direct
        ),
        "group_folds.csv": canonical_csv_bytes(
            FOLD_COLUMNS, list(reversed(folds)) if reverse else folds
        ),
        "public_episodes.csv": canonical_csv_bytes(PUBLIC_EPISODE_COLUMNS, [episode]),
        "masks.csv": canonical_csv_bytes(MASK_COLUMNS, [mask]),
        "structure.csv": canonical_csv_bytes(
            (
                "molecule_id",
                "raw_smiles",
                "raw_structure_sha256",
                "standardized_smiles",
                "standardized_structure_hash",
                "similarity_component_hash",
            ),
            list(reversed(structures)) if reverse else structures,
        ),
    }
    paths = TransformationSourcePaths(*(root / name for name in values))
    for (_, path), data in zip(paths.items(), values.values(), strict=True):
        path.write_bytes(data)
    return paths, {
        name: hashlib.sha256(data).hexdigest() for name, data in values.items()
    }


def _projection(root: Path, *, reverse: bool = False) -> Path:
    paths, receipts = _fixture(root / "source", reverse=reverse)
    output = root / "projection"
    project_openadmet_transformation_inputs(
        direct_observations_path=paths.direct_observations,
        group_folds_path=paths.group_folds,
        public_episodes_path=paths.public_episodes,
        masks_path=paths.masks,
        structure_path=paths.structure,
        output_directory=output,
        expected_receipts=receipts,
    )
    return output


def _writable(root: Path) -> None:
    for path in root.iterdir():
        path.chmod(0o644)
    root.chmod(0o755)


def test_projection_bundle_is_receipt_safe_and_canonical(tmp_path: Path) -> None:
    bundle = load_transformation_projection(_projection(tmp_path))
    assert [row.molecule.molecule_id for row in bundle.molecules] == [
        "anchor",
        "foreign",
        "query",
    ]
    assert len(bundle.direct_availability) == 12
    assert len(bundle.folds) == 45
    assert len(bundle.episodes) == 1
    episode = bundle.episodes[0]
    assert (episode.anchor_molecule_id, episode.query_molecule_id) == (
        "anchor",
        "query",
    )
    assert episode.query_rank == 1
    assert {receipt.name for receipt in bundle.input_receipts} == {
        "direct_projection.csv",
        "fold_projection.csv",
        "manifest.json",
        "mask_projection.csv",
        "public_projection.csv",
        "structure_projection.csv",
    }
    assert all(row.value_state == "complete" for row in bundle.direct_availability)


def test_projection_bundle_is_invariant_to_source_row_order(tmp_path: Path) -> None:
    first = load_transformation_projection(_projection(tmp_path / "first"))
    second = load_transformation_projection(
        _projection(tmp_path / "second", reverse=True)
    )
    assert first.molecules == second.molecules
    assert first.direct_availability == second.direct_availability
    assert first.folds == second.folds
    assert first.episodes == second.episodes


@pytest.mark.parametrize("mutation", ["extra", "symlink", "manifest", "bool_alias"])
def test_projection_bundle_rejects_file_and_manifest_drift(
    tmp_path: Path, mutation: str
) -> None:
    projection = _projection(tmp_path)
    _writable(projection)
    if mutation == "extra":
        (projection / "extra.txt").write_text("x")
    elif mutation == "symlink":
        path = projection / "direct_projection.csv"
        data = path.read_bytes()
        path.unlink()
        target = tmp_path / "outside.csv"
        target.write_bytes(data)
        path.symlink_to(target)
    else:
        manifest = projection / "manifest.json"
        value = json.loads(manifest.read_bytes())
        if mutation == "manifest":
            value["accounting"]["numeric_target_magnitudes_parsed"] = 1
        else:
            value["accounting"]["numeric_target_magnitudes_parsed"] = False
        manifest.write_bytes(canonical_json_bytes(value))
    with pytest.raises(OpenADMETTransformationCoverageError):
        load_transformation_projection(projection)


def test_projection_bundle_rejects_noncanonical_fold_after_receipt_repair(
    tmp_path: Path,
) -> None:
    projection = _projection(tmp_path)
    _writable(projection)
    fold_path = projection / "fold_projection.csv"
    data = fold_path.read_bytes().replace(b",0,20260810,", b",00,20260810,", 1)
    fold_path.write_bytes(data)
    manifest_path = projection / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    receipt = manifest["output_receipts"]["fold_projection.csv"]
    receipt["sha256"] = hashlib.sha256(data).hexdigest()
    receipt["bytes"] = len(data)
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    with pytest.raises(OpenADMETTransformationCoverageError, match="repeat"):
        load_transformation_projection(projection)


def test_projection_bundle_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    projection = _projection(tmp_path)
    _writable(projection)
    manifest = projection / "manifest.json"
    manifest.write_bytes(b'{"schema_version":"x","schema_version":"y"}\n')
    with pytest.raises(OpenADMETTransformationCoverageError):
        load_transformation_projection(projection)


def test_projection_receipt_failure_precedes_csv_parse(tmp_path: Path) -> None:
    projection = _projection(tmp_path)
    _writable(projection)
    (projection / "direct_projection.csv").write_bytes(b"malformed")
    with pytest.raises(OpenADMETTransformationCoverageError, match="pre-parse receipt"):
        load_transformation_projection(projection)


def test_projection_bundle_rejects_symlink_parent(tmp_path: Path) -> None:
    _projection(tmp_path / "real")
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path / "real", target_is_directory=True)
    with pytest.raises(OpenADMETTransformationCoverageError, match="real directory"):
        load_transformation_projection(alias / "projection")


def test_projection_bundle_rejects_self_consistent_empty_projection(
    tmp_path: Path,
) -> None:
    projection = _projection(tmp_path)
    _writable(projection)
    manifest_path = projection / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    for name, receipt in manifest["output_receipts"].items():
        data = canonical_csv_bytes(tuple(receipt["columns"]), [])
        (projection / name).write_bytes(data)
        receipt.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), rows=0)
    for key in manifest["counts"]:
        manifest["counts"][key] = 0
    for receipt in manifest["source_receipts"].values():
        receipt["rows"] = 0
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    with pytest.raises(OpenADMETTransformationCoverageError, match="empty"):
        load_transformation_projection(projection)


def test_geometry_unions_episode_pair_once_and_preserves_direction(
    tmp_path: Path,
) -> None:
    bundle = load_transformation_projection(_projection(tmp_path))
    geometry = compile_transformation_geometry(bundle)
    assert len(geometry.pairs) == len(geometry.episodes) == 1
    pair = geometry.pairs[0]
    assert (pair.local_pair, pair.episode_pair) == (False, True)
    episode = geometry.episodes[0]
    assert episode.pair is pair
    assert (
        episode.direction.anchor_molecule_id,
        episode.direction.analog_molecule_id,
    ) == ("anchor", "query")
    rows = list(
        csv.DictReader(io.StringIO(geometry.transformation_pairs_csv.decode("utf-8")))
    )
    assert tuple(rows[0]) == PAIR_COLUMNS
    assert rows[0]["local_pair"] == "false"
    assert rows[0]["episode_pair"] == "true"
    assert b"CYP3A4" not in geometry.transformation_pairs_csv


def test_geometry_is_invariant_to_projection_row_order(tmp_path: Path) -> None:
    first = compile_transformation_geometry(
        load_transformation_projection(_projection(tmp_path / "first"))
    )
    second = compile_transformation_geometry(
        load_transformation_projection(_projection(tmp_path / "second", reverse=True))
    )
    assert first == second
    assert first.transformation_pairs_csv == second.transformation_pairs_csv


def test_geometry_inclusive_boundary_is_local_and_extracted_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_transformation_projection(_projection(tmp_path))
    real_extractor = transformation_compiler.extract_transformation_pair
    calls: list[tuple[str, str]] = []

    def boundary_extractor(
        left: MoleculeRecord, right: MoleculeRecord
    ) -> TransformationPairResult:
        calls.append((left.molecule_id, right.molecule_id))
        return replace(real_extractor(left, right), similarity=0.60)

    monkeypatch.setattr(transformation_compiler, "_similarity", lambda _a, _b: 0.60)
    monkeypatch.setattr(
        transformation_compiler, "extract_transformation_pair", boundary_extractor
    )
    geometry = compile_transformation_geometry(bundle)
    assert len(calls) == 1
    assert geometry.pairs[0].local_pair is True
    assert geometry.pairs[0].episode_pair is True


def test_pair_csv_invalid_status_uses_frozen_empty_sentinels() -> None:
    left = standardize_molecule(
        MoleculeInput("left", "CCO.CN", "smiles", "synthetic", "fixture")
    )
    right = standardize_molecule(
        MoleculeInput("right", "CCN.CN", "smiles", "synthetic", "fixture")
    )
    result = transformation_compiler.extract_transformation_pair(left, right)
    row = transformation_compiler._pair_row(  # noqa: SLF001
        CompiledTransformationPair(
            result=result,
            similarity_component_hash=_digest("component-a"),
            local_pair=False,
            episode_pair=True,
        )
    )
    assert row["extraction_status"] == "STANDARDIZATION_HAZARD"
    assert row["failure_code"] == "C2"
    assert row["cut_count"] == ""
    assert row["candidate_material"] == ""
    assert row["changed_left_atom_indices"] == ""
    assert row["left_virtual_h_eligible"] == ""
