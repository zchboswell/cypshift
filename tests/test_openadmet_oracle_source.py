from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

import cypshift.openadmet_oracle_source as source_module
import cypshift.openadmet_oracle_source_io as source_io
from cypshift import openadmet_transformation_compiler as transformation_compiler
from cypshift.chemistry import standardize_molecule
from cypshift.openadmet_oracle_projection import (
    SOURCE_FILES,
    SOURCE_PARENT_FILES,
    project_openadmet_oracle_inputs,
)
from cypshift.openadmet_oracle_source import (
    INPUT_FILES,
    OOF_COLUMNS,
    OpenADMETOracleSourceError,
    compile_openadmet_oracle_source,
)
from cypshift.openadmet_oracle_source_io import csv_rows
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
from cypshift.schema import MoleculeInput


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, indent=2) + "\n").encode()


def _npy(array: np.ndarray) -> bytes:
    import io

    stream = io.BytesIO()
    np.lib.format.write_array(stream, array, version=(1, 0), allow_pickle=False)
    return stream.getvalue()


def _fixture(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    root.mkdir()
    molecules = ("a", "b")
    smiles = {"a": "CCO", "b": "CCN"}
    component = _sha(b"component")
    direct: list[dict[str, str]] = []
    for molecule in molecules:
        for endpoint in ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4"):
            point = "1.0" if molecule == "a" else "2.2"
            direct.append(
                {
                    "observation_id": _sha(f"{molecule}|{endpoint}".encode()),
                    "molecule_id": molecule,
                    "source_row_id": molecule,
                    "source_file": "cyp-challenge-TRAIN_inhibition.csv",
                    "source_row": "1" if molecule == "a" else "2",
                    "source_sha256": "a" * 64,
                    "endpoint": endpoint,
                    "raw_smiles": smiles[molecule],
                    "raw_point": point,
                    "raw_low": str(float(point) - 0.1),
                    "raw_high": str(float(point) + 0.1),
                    "raw_std": "0.1",
                    "point": point,
                    "low": str(float(point) - 0.1),
                    "high": str(float(point) + 0.1),
                    "std": "0.1",
                    "raw_structure_sha256": _sha(smiles[molecule].encode()),
                    "standardized_structure_hash": _sha(smiles[molecule].encode()),
                    "similarity_component_hash": component,
                    "scaffold_group_hash": _sha(b"scaffold"),
                    "value_state": "complete",
                    "point_eligible": "true",
                    "anchor_eligible": "true",
                }
            )
    folds: list[dict[str, str]] = []
    for molecule in molecules:
        for repeat in range(3):
            for validation in range(5):
                folds.append(
                    {
                        "molecule_id": molecule,
                        "similarity_component_hash": component,
                        "repeat": str(repeat),
                        "seed": str(20260810 + repeat),
                        "outer_fold": "0",
                        "outer_validation_fold": str(validation),
                        "inner_fold": "" if validation == 0 else "0",
                    }
                )
    episode = _sha(b"selected")
    stress = _sha(b"stress")
    public = [
        {
            "episode_id": episode,
            "protocol": "ANCHOR_EXPANSION_HOLDOUT",
            "repeat": "0",
            "outer_fold": "0",
            "outer_group_id": component,
            "query_molecule_ids": '["b"]',
            "candidate_pool_id": "DEFERRED_NO_INFERRED_POOL_V1",
            "episode_policy_id": "selected_anchor",
        },
        {
            "episode_id": stress,
            "protocol": "ANCHOR_EXPANSION_HOLDOUT",
            "repeat": "0",
            "outer_fold": "0",
            "outer_group_id": component,
            "query_molecule_ids": '["b"]',
            "candidate_pool_id": "DEFERRED_NO_INFERRED_POOL_V1",
            "episode_policy_id": "deterministic_random_anchor_stress",
        },
    ]
    references = {
        endpoint: next(
            row["observation_id"]
            for row in direct
            if row["molecule_id"] == "a" and row["endpoint"] == endpoint
        )
        for endpoint in ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
    }
    availability = {
        endpoint: {field: True for field in ("point", "low", "high", "std")}
        for endpoint in references
    }
    query_references = {
        endpoint: next(
            row["observation_id"]
            for row in direct
            if row["molecule_id"] == "b" and row["endpoint"] == endpoint
        )
        for endpoint in references
    }
    public_truth = [
        {
            "episode_id": item["episode_id"],
            "selector_cyp_truth": "CYP3A4",
            "anchor_molecule_id_truth": "a",
            "query_truth_references": json.dumps(
                [query_references], separators=(",", ":")
            ),
            "query_truth_availability_masks": json.dumps(
                [availability], separators=(",", ":")
            ),
        }
        for item in public
    ]
    masks = [
        {
            "episode_id": item["episode_id"],
            "anchor_molecule_id_truth": "a",
            "anchor_observation_references": json.dumps(
                references, separators=(",", ":"), sort_keys=True
            ),
            "anchor_value_availability_mask": json.dumps(
                availability, separators=(",", ":"), sort_keys=True
            ),
        }
        for item in public
    ]
    feature_rows = [
        {
            "molecule_id": molecule,
            "raw_structure_sha256": _sha(smiles[molecule].encode()),
            "standardized_structure_hash": _sha(smiles[molecule].encode()),
            "similarity_component_hash": component,
        }
        for molecule in molecules
    ]
    feature_data: dict[str, bytes] = {
        "feature_rows.csv": canonical_csv_bytes(
            (
                "molecule_id",
                "raw_structure_sha256",
                "standardized_structure_hash",
                "similarity_component_hash",
            ),
            feature_rows,
        )
    }
    arrays: dict[str, bytes] = {}
    specs = {
        "morgan_binary": (np.uint8, 4096),
        "maplight_morgan_count": (np.int8, 1024),
        "maplight_avalon_count": (np.int8, 1024),
        "maplight_erg": ("<f8", 315),
        "maplight_rdkit_descriptors": ("<f8", 200),
    }
    for stem, (dtype, width) in specs.items():
        arrays[f"{stem}.npy"] = _npy(np.zeros((2, width), dtype=dtype))
    feature_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1",
        "rows": {
            "path": "feature_rows.csv",
            "columns": list(feature_rows[0]),
            "rows": 2,
            "sha256": _sha(feature_data["feature_rows.csv"]),
        },
        "arrays": {
            Path(name).stem: {"path": name, "npy_sha256": _sha(data)}
            for name, data in arrays.items()
        },
        "accounting": {
            "target_values_parsed": 0,
            "model_fits": 0,
            "predictions": 0,
            "metric_evaluations": 0,
        },
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
    feature_data["feature_manifest.json"] = _json(feature_manifest)
    outer_oof: list[dict[str, str]] = []
    inner_oof: list[dict[str, str]] = []
    for molecule in molecules:
        outer_oof.append(
            {
                "molecule_id": molecule,
                "endpoint": "CYP3A4",
                "component_id": component,
                "repeat": "0",
                "outer_fold": "0",
                "inner_fold": "",
                "scope": "openadmet-direct-outer-v1",
                "system_id": "TRACE-G0-MAPL-FIXED",
                "prediction": "1.5",
                "applicability_score": "1.0",
                "model_id": _sha(b"oof-model"),
                "feature_spec_id": "maplight-fixed-stage-a-v1",
                "split_id": "s" * 64,
            }
        )
        for outer in range(1, 5):
            inner_oof.append(
                {
                    "molecule_id": molecule,
                    "endpoint": "CYP3A4",
                    "component_id": component,
                    "repeat": "0",
                    "outer_fold": str(outer),
                    "inner_fold": "0",
                    "scope": f"openadmet-direct-inner-v1|outer={outer}",
                    "system_id": "TRACE-G0-MAPL-FIXED",
                    "prediction": "1.5",
                    "applicability_score": "1.0",
                    "model_id": _sha(b"oof-model"),
                    "feature_spec_id": "maplight-fixed-stage-a-v1",
                    "split_id": "s" * 64,
                }
            )
    records = {
        molecule: standardize_molecule(
            MoleculeInput(molecule, smiles[molecule], "smiles", "synthetic", "fixture")
        )
        for molecule in molecules
    }
    pair_result = extract_transformation_pair(records["a"], records["b"])
    pair = transformation_compiler._pair_row(  # noqa: SLF001
        CompiledTransformationPair(pair_result, component, True, True)
    )
    pair_id = pair["transformation_pair_id"]
    episode_rows = []
    for item in public:
        forward = pair["left_molecule_id"] == "a"
        prefix = "a_to_b" if forward else "b_to_a"
        row = {
            "episode_id": item["episode_id"],
            "episode_policy_id": item["episode_policy_id"],
            "repeat": "0",
            "outer_fold": "0",
            "outer_group_id": component,
            "query_molecule_id": "b",
            "query_rank": "1",
            "anchor_molecule_id": "a",
            "transformation_pair_id": pair_id,
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
        episode_rows.append(row)
    data: dict[str, bytes] = {
        "direct_observations.csv": canonical_csv_bytes(OBSERVATION_COLUMNS, direct),
        "group_folds.csv": canonical_csv_bytes(FOLD_COLUMNS, folds),
        "campaign_episodes_public.csv": canonical_csv_bytes(
            PUBLIC_EPISODE_COLUMNS, public
        ),
        "campaign_episodes_truth.csv": canonical_csv_bytes(TRUTH_COLUMNS, public_truth),
        "episode_label_masks.csv": canonical_csv_bytes(MASK_COLUMNS, masks),
        **feature_data,
        **arrays,
        "global_oof_predictions.csv": canonical_csv_bytes(OOF_COLUMNS, outer_oof),
        "global_inner_oof_predictions.csv": canonical_csv_bytes(OOF_COLUMNS, inner_oof),
        "transformation_pairs.csv": canonical_csv_bytes(PAIR_COLUMNS, [pair]),
        "episode_transformations.csv": canonical_csv_bytes(
            EPISODE_COLUMNS, episode_rows
        ),
        "transformation_coverage.json": _json(
            {"status": "R4_TRANSFORMATION_COVERAGE_SUPPORTED"}
        ),
    }
    paths: dict[str, Path] = {}
    for name in INPUT_FILES:
        path = root / name
        path.write_bytes(data[name])
        paths[name] = path
    return paths, {name: _sha(data[name]) for name in INPUT_FILES}


def test_episode_context_is_emitted_once_for_multiple_queries() -> None:
    episode_id = _sha(b"multi-query")
    public = [
        {
            "episode_id": episode_id,
            "episode_policy_id": "deterministic_random_anchor_stress",
            "repeat": "0",
            "outer_fold": "0",
            "anchor_molecule_id": "anchor",
            "query_molecule_id": query,
            "query_rank": str(rank),
            "_selector_cyp_truth": "CYP3A4",
        }
        for rank, query in enumerate(("query-1", "query-2"), 1)
    ]
    direct = {
        molecule: {
            "CYP3A4": {
                "point": point,
                "low": format(float(point) - 0.1, ".17g"),
                "high": format(float(point) + 0.1, ".17g"),
                "std": "0.1",
                "value_state": "complete",
            }
        }
        for molecule, point in (
            ("anchor", "1"),
            ("query-1", "1.2"),
            ("query-2", "1.4"),
        )
    }
    geometry = {(episode_id, rank): {"_pair": {"similarity": "0.7"}} for rank in (1, 2)}
    oof = {
        ("anchor", 0, 0, None): {
            "prediction": "1.1",
            "scope": "openadmet-direct-outer-v1",
            "model_id": _sha(b"multi-query-model"),
        }
    }
    anchors, global_rows, truths, cliffs = source_module._episode_rows(  # noqa: SLF001
        public,
        direct,
        {},
        geometry,
        oof,
        "a" * 64,
        "b" * 64,
    )
    assert len(anchors) == len(global_rows) == 1
    assert len(truths) == len(cliffs) == 2


def test_source_compiler_emits_weighted_antisymmetric_private_bundle(
    tmp_path: Path,
) -> None:
    paths, receipts = _fixture(tmp_path / "inputs")
    result = compile_openadmet_oracle_source(
        paths, tmp_path / "out", expected_receipts=receipts
    )
    assert result.manifest_path.exists()
    assert set(path.name for path in result.output_directory.iterdir()) == set(
        SOURCE_FILES
    ) | {"manifest.json"}
    pairs = (result.output_directory / "training_pairs.csv").read_text().splitlines()
    assert ",a,b," in "\n".join(pairs)
    assert ",b,a," in "\n".join(pairs)
    assert (result.output_directory / "episode_anchor_contexts.csv").read_text().count(
        "\n"
    ) == 7
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["counts"]["selected_public_rows"] == 1
    assert manifest["counts"]["stress_public_rows"] == 1
    assert manifest["operation_accounting"]["direct_target_values_parsed"] > 0
    assert manifest["operation_accounting"]["tdi_files_opened"] == 0


def test_pair_weights_use_exact_rational_serialization() -> None:
    component = _sha(b"weight-component")
    molecules = {
        name: {"similarity_component_hash": component} for name in ("a", "b", "c", "d")
    }
    direct = {
        name: {"CYP3A4": {"value_state": "complete", "point": str(index)}}
        for index, name in enumerate(molecules, start=1)
    }
    folds = {
        (name, repeat, validation): {
            "outer_fold": "4",
            "inner_fold": "0",
        }
        for name in molecules
        for repeat in range(3)
        for validation in range(5)
    }
    pair_rows = [
        {
            "transformation_pair_id": _sha(f"pair-{analog}".encode()),
            "left_molecule_id": "a",
            "right_molecule_id": analog,
            "local_pair": "true",
            "extraction_status": "VALID_SINGLE",
            "a_to_b_direction_id": f"a-{analog}",
            "b_to_a_direction_id": f"{analog}-a",
        }
        for analog in ("b", "c", "d")
    ]
    _, pairs = source_module._training_rows(direct, molecules, folds, pair_rows)
    assert {row["sample_weight"] for row in pairs} == {"1/6"}


def test_below_threshold_episode_pair_is_not_an_activity_cliff(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path / "inputs")
    pair_path = paths["transformation_pairs.csv"]
    pair_data = (
        pair_path.read_bytes()
        .replace(b",0.8,", b",0.5,")
        .replace(b",true,true,", b",false,true,")
    )
    pair_path.write_bytes(pair_data)
    receipts["transformation_pairs.csv"] = _sha(pair_data)
    result = compile_openadmet_oracle_source(
        paths, tmp_path / "out", expected_receipts=receipts
    )
    assert ",false\n" in (result.output_directory / "activity_cliffs.csv").read_text()


def test_compiler_output_projects_through_the_capability_splitter(
    tmp_path: Path,
) -> None:
    paths, receipts = _fixture(tmp_path / "inputs")
    assert INPUT_FILES == SOURCE_PARENT_FILES
    source = compile_openadmet_oracle_source(
        paths, tmp_path / "source", expected_receipts=receipts
    )
    expected = {
        name: str(source.output_receipts[name]["sha256"]) for name in SOURCE_FILES
    }
    expected["manifest.json"] = source.manifest_sha256
    projected = project_openadmet_oracle_inputs(
        source.output_directory,
        tmp_path / "projected",
        expected_receipts=expected,
    )
    manifest = json.loads((projected.model_public_root / "manifest.json").read_bytes())
    assert manifest["source_bundle_binding"]["manifest_receipt"]["sha256"] == (
        source.manifest_sha256
    )


def test_source_receipt_is_verified_before_parse(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path / "inputs")
    poisoned = paths["direct_observations.csv"]
    poisoned.write_bytes(b"not,csv\n")
    with pytest.raises(OpenADMETOracleSourceError, match="source receipt mismatch"):
        compile_openadmet_oracle_source(
            paths, tmp_path / "out", expected_receipts=receipts
        )


def test_source_compiler_rejects_non_v2_contract_receipt(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path / "inputs")
    with pytest.raises(OpenADMETOracleSourceError, match="contract receipt differs"):
        compile_openadmet_oracle_source(
            paths,
            tmp_path / "out",
            expected_receipts=receipts,
            contract_sha256="0" * 64,
        )


def test_bad_npy_shape_fails_closed_and_does_not_publish(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path / "inputs")
    path = paths["morgan_binary.npy"]
    path.write_bytes(_npy(np.zeros((2, 8), dtype=np.uint8)))
    receipts["morgan_binary.npy"] = _sha(path.read_bytes())
    with pytest.raises(OpenADMETOracleSourceError, match="feature receipt"):
        compile_openadmet_oracle_source(
            paths, tmp_path / "out", expected_receipts=receipts
        )
    assert not (tmp_path / "out").exists()


def test_episode_direction_cannot_be_rebound_to_the_other_pair_direction(
    tmp_path: Path,
) -> None:
    paths, receipts = _fixture(tmp_path / "inputs")
    path = paths["episode_transformations.csv"]
    pair = csv_rows(
        paths["transformation_pairs.csv"].read_bytes(), PAIR_COLUMNS, "pairs"
    )[0]
    forward = pair["a_to_b_direction_id"]
    reverse = pair["b_to_a_direction_id"]
    poisoned = path.read_bytes().replace(
        f",{forward},VALID_SINGLE".encode(),
        f",{reverse},VALID_SINGLE".encode(),
    )
    path.write_bytes(poisoned)
    receipts["episode_transformations.csv"] = _sha(poisoned)
    with pytest.raises(OpenADMETOracleSourceError, match="episode direction"):
        compile_openadmet_oracle_source(
            paths, tmp_path / "out", expected_receipts=receipts
        )


def test_publication_refuses_overwrite(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path / "inputs")
    output = tmp_path / "out"
    compile_openadmet_oracle_source(paths, output, expected_receipts=receipts)
    with pytest.raises(OpenADMETOracleSourceError, match="output path already exists"):
        compile_openadmet_oracle_source(paths, output, expected_receipts=receipts)


def test_source_and_output_symlink_ancestry_fail_closed(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path / "inputs")
    source_alias = tmp_path / "source-alias"
    source_alias.symlink_to(tmp_path / "inputs", target_is_directory=True)
    aliased_paths = {name: source_alias / name for name in INPUT_FILES}
    with pytest.raises(OpenADMETOracleSourceError, match="contains a symlink"):
        compile_openadmet_oracle_source(
            aliased_paths, tmp_path / "out", expected_receipts=receipts
        )
    output_parent = tmp_path / "output-alias"
    real_parent = tmp_path / "real-output"
    real_parent.mkdir()
    output_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(OpenADMETOracleSourceError, match="contains a symlink"):
        compile_openadmet_oracle_source(
            paths, output_parent / "out", expected_receipts=receipts
        )


def test_staged_mutation_is_rejected_and_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, receipts = _fixture(tmp_path / "inputs")
    original = source_io._verify_staged_outputs

    def mutate_then_verify(stage: Path, outputs: dict[str, bytes]) -> None:
        target = stage / "training_pairs.csv"
        target.chmod(0o644)
        target.write_bytes(b"mutated\n")
        original(stage, outputs)

    monkeypatch.setattr(source_io, "_verify_staged_outputs", mutate_then_verify)
    with pytest.raises(OpenADMETOracleSourceError, match="staged output differs"):
        compile_openadmet_oracle_source(
            paths, tmp_path / "out", expected_receipts=receipts
        )
    assert not (tmp_path / "out").exists()
    assert not tuple(tmp_path.glob(".r5b-source-*"))
