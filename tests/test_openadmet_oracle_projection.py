from __future__ import annotations

import hashlib
import io
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from cypshift import openadmet_oracle_projection as projection
from cypshift import openadmet_transformation_compiler as transformation_compiler
from cypshift.chemistry import standardize_molecule
from cypshift.openadmet_oracle_projection import (
    ANCHOR_CONTEXT_COLUMNS,
    C3_FILES,
    CELL_FILES,
    CLIFF_COLUMNS,
    CONTRACT_SHA256,
    GLOBAL_CONTEXT_COLUMNS,
    PUBLIC_FILES,
    PUBLIC_QUERY_COLUMNS,
    SCORER_FILES,
    SOURCE_FILES,
    TRAINING_PAIR_COLUMNS,
    TRAINING_POINT_COLUMNS,
    OpenADMETOracleProjectionError,
    project_openadmet_oracle_inputs,
)
from cypshift.openadmet_oracle_validation import (
    FEATURE_SPECS,
    G0_SYSTEM_ID,
    INNER_OOF_SCOPE,
    OUTER_OOF_SCOPE,
    SOURCE_COLUMNS,
    csv_rows,
)
from cypshift.openadmet_transformation_compiler import (
    PAIR_COLUMNS,
    CompiledTransformationPair,
)
from cypshift.openadmet_transformation_io import (
    STRUCTURE_COLUMNS,
    canonical_csv_bytes,
    canonical_json_bytes,
)
from cypshift.openadmet_transformation_projection import FOLD_PROJECTION_COLUMNS
from cypshift.openadmet_transformation_serialization import EPISODE_COLUMNS
from cypshift.openadmet_transformations import extract_transformation_pair
from cypshift.schema import MoleculeInput, MoleculeRecord


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


OUTER_OOF_RECEIPT = _sha("synthetic-outer-oof")
INNER_OOF_RECEIPT = _sha("synthetic-inner-oof")


def _record(molecule_id: str, smiles: str) -> MoleculeRecord:
    return standardize_molecule(
        MoleculeInput(molecule_id, smiles, "smiles", "synthetic", "fixture")
    )


def _structure(record: MoleculeRecord, component: str) -> dict[str, str]:
    assert record.standardized_structure is not None
    assert record.standardized_structure_hash is not None
    return {
        "molecule_id": record.molecule_id,
        "raw_smiles": record.raw_structure,
        "raw_structure_sha256": hashlib.sha256(
            record.raw_structure.encode()
        ).hexdigest(),
        "standardized_smiles": record.standardized_structure,
        "standardized_structure_hash": record.standardized_structure_hash,
        "similarity_component_hash": component,
    }


def _pair(
    left: MoleculeRecord, right: MoleculeRecord, component: str
) -> dict[str, str]:
    result = extract_transformation_pair(left, right)
    assert result.extraction_status in {"VALID_SINGLE", "VALID_DOUBLE", "VALID_STEREO"}
    return transformation_compiler._pair_row(  # noqa: SLF001
        CompiledTransformationPair(result, component, True, True)
    )


def _episode_geometry(episode: dict[str, str], pair: dict[str, str]) -> dict[str, str]:
    forward = episode["anchor_molecule_id"] == pair["left_molecule_id"]
    prefix = "a_to_b" if forward else "b_to_a"
    return {
        **episode,
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


def _npy(array: np.ndarray[Any, Any]) -> bytes:
    stream = io.BytesIO()
    np.save(stream, array, allow_pickle=False)
    return stream.getvalue()


def _scope(stage: str, outer: int, inner: int | None = None) -> dict[str, str]:
    return {
        "stage": stage,
        "repeat": "0",
        "outer_fold": str(outer),
        "inner_fold": "" if inner is None else str(inner),
    }


def _context(
    cell: dict[str, str], episode: dict[str, str], *, point: str
) -> tuple[dict[str, str], dict[str, str]]:
    outer = int(cell["outer_fold"])
    is_outer = cell["stage"] == "outer"
    measured = {
        **cell,
        "episode_id": episode["episode_id"],
        "anchor_molecule_id": episode["anchor_molecule_id"],
        "anchor_point": point,
        "anchor_point_available": "true",
        "anchor_global_oof_prediction": "0.9",
        "anchor_global_oof_source_scope": (
            OUTER_OOF_SCOPE if is_outer else INNER_OOF_SCOPE.format(outer=outer)
        ),
        "anchor_global_oof_model_id": _sha("oof-model"),
        "anchor_global_oof_receipt_sha256": (
            OUTER_OOF_RECEIPT if is_outer else INNER_OOF_RECEIPT
        ),
    }
    global_only = {
        key: value
        for key, value in measured.items()
        if key not in {"anchor_point", "anchor_point_available"}
    }
    return measured, global_only


def _add_episode_private_rows(
    episode_rows: list[dict[str, str]],
    cells: list[dict[str, str]],
    context_rows: list[dict[str, str]],
    global_rows: list[dict[str, str]],
    truth_rows: list[dict[str, str]],
    cliff_rows: list[dict[str, str]],
    *,
    anchor_point: str,
) -> None:
    for cell in cells:
        measured, global_only = _context(cell, episode_rows[0], point=anchor_point)
        context_rows.append(measured)
        global_rows.append(global_only)
        for episode in episode_rows:
            truth_rows.append(
                {
                    **cell,
                    "episode_id": episode["episode_id"],
                    "query_molecule_id": episode["query_molecule_id"],
                    "selector_cyp_truth": "CYP3A4",
                    "query_point": "2.0",
                    "query_point_available": "true",
                }
            )
            cliff_rows.append(
                {
                    **cell,
                    "episode_id": episode["episode_id"],
                    "query_molecule_id": episode["query_molecule_id"],
                    "activity_cliff": "false",
                }
            )


def _fixture(root: Path) -> tuple[Path, dict[str, str]]:
    source = root / "source"
    source.mkdir(parents=True)
    component_a = _sha("component-a")
    component_b = _sha("component-b")
    records = {
        "anchor": _record("anchor", "CCO"),
        "duplicate": _record("duplicate", "CCO"),
        "query": _record("query", "CCN"),
        "query2": _record("query2", "CCF"),
        "train": _record("train", "CCOC"),
        "train2": _record("train2", "CCNC"),
    }
    components = {
        "anchor": component_a,
        "duplicate": component_a,
        "query": component_a,
        "query2": component_a,
        "train": component_b,
        "train2": component_b,
    }
    structures = [
        _structure(records[name], components[name]) for name in sorted(records)
    ]
    folds: list[dict[str, str]] = []
    assignments = {
        "anchor": (1, 0),
        "duplicate": (1, 0),
        "query": (1, 0),
        "query2": (1, 0),
        "train": (0, 2),
        "train2": (0, 2),
    }
    for molecule in structures:
        outer, inner = assignments[molecule["molecule_id"]]
        for repeat in range(3):
            for validation in range(5):
                folds.append(
                    {
                        "molecule_id": molecule["molecule_id"],
                        "similarity_component_hash": molecule[
                            "similarity_component_hash"
                        ],
                        "repeat": str(repeat),
                        "seed": str(20260810 + repeat),
                        "outer_fold": str(outer),
                        "outer_validation_fold": str(validation),
                        "inner_fold": "" if validation == outer else str(inner),
                    }
                )

    selected_a = _sha("selected-a")
    selected_b = _sha("selected-b")
    stress_a = _sha("stress-a")
    public = [
        {
            "episode_id": selected_a,
            "episode_policy_id": "selected_anchor",
            "repeat": "0",
            "outer_fold": "1",
            "outer_group_id": component_a,
            "anchor_molecule_id": "anchor",
            "query_molecule_id": query,
            "query_rank": str(rank),
        }
        for rank, query in ((1, "query"), (2, "query2"))
    ]
    public.append(
        {
            "episode_id": selected_b,
            "episode_policy_id": "selected_anchor",
            "repeat": "0",
            "outer_fold": "0",
            "outer_group_id": component_b,
            "anchor_molecule_id": "train",
            "query_molecule_id": "train2",
            "query_rank": "1",
        }
    )
    public.append(
        {
            "episode_id": stress_a,
            "episode_policy_id": "deterministic_random_anchor_stress",
            "repeat": "0",
            "outer_fold": "1",
            "outer_group_id": component_a,
            "anchor_molecule_id": "query",
            "query_molecule_id": "anchor",
            "query_rank": "1",
        }
    )

    pair_a1 = _pair(records["anchor"], records["query"], component_a)
    pair_a2 = _pair(records["anchor"], records["query2"], component_a)
    pair_b = _pair(records["train"], records["train2"], component_b)
    pair_by_members = {
        frozenset((row["left_molecule_id"], row["right_molecule_id"])): row
        for row in (pair_a1, pair_a2, pair_b)
    }
    geometry = [
        _episode_geometry(
            episode,
            pair_by_members[
                frozenset((episode["anchor_molecule_id"], episode["query_molecule_id"]))
            ],
        )
        for episode in public
    ]

    contexts: list[dict[str, str]] = []
    global_contexts: list[dict[str, str]] = []
    truth: list[dict[str, str]] = []
    cliffs: list[dict[str, str]] = []
    _add_episode_private_rows(
        public[:2],
        [_scope("outer", 1)] + [_scope("inner", outer, 0) for outer in (0, 2, 3, 4)],
        contexts,
        global_contexts,
        truth,
        cliffs,
        anchor_point="1.0",
    )
    _add_episode_private_rows(
        [public[2]],
        [_scope("outer", 0)] + [_scope("inner", outer, 2) for outer in (1, 2, 3, 4)],
        contexts,
        global_contexts,
        truth,
        cliffs,
        anchor_point="1.1",
    )
    _add_episode_private_rows(
        [public[3]],
        [_scope("outer", 1)],
        contexts,
        global_contexts,
        truth,
        cliffs,
        anchor_point="1.2",
    )

    target_scope = _scope("outer", 1)
    point = {
        **target_scope,
        "molecule_id": "train",
        "component_id": component_b,
        "point": "2.0",
        "sample_weight": "1",
    }
    pair_forward = {
        **target_scope,
        "pair_id": pair_b["transformation_pair_id"],
        "direction_id": pair_b["a_to_b_direction_id"],
        "anchor_molecule_id": pair_b["left_molecule_id"],
        "analog_molecule_id": pair_b["right_molecule_id"],
        "component_id": component_b,
        "delta": "1",
        "sample_weight": "1/2",
    }
    pair_reverse = {
        **target_scope,
        "pair_id": pair_b["transformation_pair_id"],
        "direction_id": pair_b["b_to_a_direction_id"],
        "anchor_molecule_id": pair_b["right_molecule_id"],
        "analog_molecule_id": pair_b["left_molecule_id"],
        "component_id": component_b,
        "delta": "-1",
        "sample_weight": "1/2",
    }

    data: dict[str, bytes] = {
        "molecules.csv": canonical_csv_bytes(STRUCTURE_COLUMNS, structures),
        "folds.csv": canonical_csv_bytes(FOLD_PROJECTION_COLUMNS, folds),
        "public_episode_queries.csv": canonical_csv_bytes(PUBLIC_QUERY_COLUMNS, public),
        "transformation_pairs.csv": canonical_csv_bytes(
            PAIR_COLUMNS, [pair_a1, pair_a2, pair_b]
        ),
        "episode_transformations.csv": canonical_csv_bytes(EPISODE_COLUMNS, geometry),
        "training_points.csv": canonical_csv_bytes(
            ("stage", "repeat", "outer_fold", "inner_fold") + TRAINING_POINT_COLUMNS,
            [point],
        ),
        "training_pairs.csv": canonical_csv_bytes(
            ("stage", "repeat", "outer_fold", "inner_fold") + TRAINING_PAIR_COLUMNS,
            [pair_forward, pair_reverse],
        ),
        "episode_anchor_contexts.csv": canonical_csv_bytes(
            ("stage", "repeat", "outer_fold", "inner_fold") + ANCHOR_CONTEXT_COLUMNS,
            contexts,
        ),
        "global_anchor_contexts.csv": canonical_csv_bytes(
            ("stage", "repeat", "outer_fold", "inner_fold") + GLOBAL_CONTEXT_COLUMNS,
            global_contexts,
        ),
        "episode_truth.csv": canonical_csv_bytes(
            ("stage", "repeat", "outer_fold", "inner_fold")
            + (
                "episode_id",
                "query_molecule_id",
                "selector_cyp_truth",
                "query_point",
                "query_point_available",
            ),
            truth,
        ),
        "activity_cliffs.csv": canonical_csv_bytes(
            ("stage", "repeat", "outer_fold", "inner_fold") + CLIFF_COLUMNS,
            cliffs,
        ),
    }
    for name, (width, dtype) in FEATURE_SPECS.items():
        data[name] = _npy(np.zeros((len(structures), width), dtype=np.dtype(dtype)))
    data["manifest.json"] = _source_manifest(data)
    for name, payload in data.items():
        (source / name).write_bytes(payload)
    return source, {
        name: hashlib.sha256(data[name]).hexdigest()
        for name in (*SOURCE_FILES, "manifest.json")
    }


def _source_manifest(data: dict[str, bytes]) -> bytes:
    parent_receipts = {
        name: (
            OUTER_OOF_RECEIPT
            if name == "global_oof_predictions.csv"
            else INNER_OOF_RECEIPT
            if name == "global_inner_oof_predictions.csv"
            else _sha(f"synthetic-parent:{name}")
        )
        for name in projection.SOURCE_PARENT_FILES
    }
    parent_records = {
        name: {"sha256": digest, "bytes": 1} for name, digest in parent_receipts.items()
    }
    output_receipts = {
        name: {
            "sha256": hashlib.sha256(data[name]).hexdigest(),
            "bytes": len(data[name]),
            "rows": data[name].count(b"\n") - 1 if name.endswith(".csv") else 0,
            "columns": list(SOURCE_COLUMNS[name]) if name.endswith(".csv") else [],
        }
        for name in SOURCE_FILES
    }
    return canonical_json_bytes(
        {
            "schema_version": projection.SOURCE_MANIFEST_SCHEMA,
            "contract_sha256": CONTRACT_SHA256,
            "parent_receipts": parent_receipts,
            "input_receipts": parent_records,
            "source_receipts": parent_records,
            "output_receipts": output_receipts,
            "columns": {
                name: list(columns) for name, columns in SOURCE_COLUMNS.items()
            },
            "counts": {
                "molecules": 6,
                "direct_rows": 6,
                "fold_rows": 90,
                "selected_public_rows": 3,
                "stress_public_rows": 1,
            },
            "operation_accounting": dict.fromkeys(projection.ACCOUNTING_FIELDS, 0),
            "authority": dict(projection.DENIED_AUTHORITY),
        }
    )


def _refresh_source_manifest(source: Path, receipts: dict[str, str]) -> None:
    path = source / "manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest["output_receipts"] = {
        name: {
            "sha256": hashlib.sha256((source / name).read_bytes()).hexdigest(),
            "bytes": len((source / name).read_bytes()),
            "rows": (
                (source / name).read_bytes().count(b"\n") - 1
                if name.endswith(".csv")
                else 0
            ),
            "columns": list(SOURCE_COLUMNS[name]) if name.endswith(".csv") else [],
        }
        for name in SOURCE_FILES
    }
    payload = canonical_json_bytes(manifest)
    path.write_bytes(payload)
    receipts["manifest.json"] = hashlib.sha256(payload).hexdigest()


def _rewrite_csv(
    source: Path,
    receipts: dict[str, str],
    name: str,
    change: Callable[[list[dict[str, str]]], None],
) -> None:
    path = source / name
    rows = csv_rows(path.read_bytes(), SOURCE_COLUMNS[name], name)
    change(rows)
    payload = canonical_csv_bytes(SOURCE_COLUMNS[name], rows)
    path.write_bytes(payload)
    receipts[name] = hashlib.sha256(payload).hexdigest()
    _refresh_source_manifest(source, receipts)


def _rewrite_npy(
    source: Path, receipts: dict[str, str], name: str, array: np.ndarray[Any, Any]
) -> None:
    payload = _npy(array)
    (source / name).write_bytes(payload)
    receipts[name] = hashlib.sha256(payload).hexdigest()
    _refresh_source_manifest(source, receipts)


def _files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_projection_is_disjoint_complete_readonly_and_stress_outer_only(
    tmp_path: Path,
) -> None:
    source, receipts = _fixture(tmp_path)
    result = project_openadmet_oracle_inputs(
        source, tmp_path / "out", expected_receipts=receipts
    )
    assert len(result.manifest_paths) == 226
    assert all(path.exists() for path in result.manifest_paths)
    assert {path.name for path in result.model_public_root.iterdir()} == set(
        PUBLIC_FILES
    )
    cell = result.cell_target_root / "outer/repeat-0/outer-1"
    c3 = result.c3_target_root / "outer/repeat-0/outer-1"
    scorer = result.sealed_scorer_root / "outer/repeat-0/outer-1"
    assert {path.name for path in cell.iterdir()} == set(CELL_FILES)
    assert {path.name for path in c3.iterdir()} == set(C3_FILES)
    assert {path.name for path in scorer.iterdir()} == set(SCORER_FILES)
    stress_id = _sha("stress-a")
    assert stress_id in (cell / "episode_anchor_contexts.csv").read_text()
    assert not any(
        stress_id in path.read_text()
        for path in result.cell_target_root.glob(
            "inner/repeat-*/outer-*/inner-*/episode_anchor_contexts.csv"
        )
    )
    cell_manifest = json.loads((cell / "manifest.json").read_bytes())
    scorer_manifest = json.loads((scorer / "manifest.json").read_bytes())
    assert cell_manifest["capability_root_accounting"]["total_capability_roots"] == 226
    assert cell_manifest["fixed_oof_system_id"] == G0_SYSTEM_ID
    assert cell_manifest["source_bundle_binding"]["manifest_receipt"] == {
        "sha256": receipts["manifest.json"],
        "bytes": len((source / "manifest.json").read_bytes()),
    }
    assert cell_manifest["operation_accounting"]["direct_target_values_parsed"] == 3
    assert cell_manifest["operation_accounting"]["anchor_labels_exposed_to_models"] == 2
    assert (
        scorer_manifest["operation_accounting"]["query_truth_values_opened_by_scorers"]
        == 3
    )
    assert os.stat(cell / "manifest.json").st_mode & 0o777 == 0o444
    assert os.stat(cell).st_mode & 0o777 == 0o555


def test_two_output_roots_are_byte_deterministic(tmp_path: Path) -> None:
    source, receipts = _fixture(tmp_path)
    first = project_openadmet_oracle_inputs(
        source, tmp_path / "one", expected_receipts=receipts
    )
    second = project_openadmet_oracle_inputs(
        source, tmp_path / "two", expected_receipts=receipts
    )
    assert _files(first.output_directory) == _files(second.output_directory)


def test_no_overwrite_and_symlink_source_fail_closed(tmp_path: Path) -> None:
    source, receipts = _fixture(tmp_path)
    output = tmp_path / "out"
    project_openadmet_oracle_inputs(source, output, expected_receipts=receipts)
    with pytest.raises(OpenADMETOracleProjectionError, match="already exists"):
        project_openadmet_oracle_inputs(source, output, expected_receipts=receipts)

    other = tmp_path / "other"
    source2, receipts2 = _fixture(other)
    path = source2 / "molecules.csv"
    payload = path.read_bytes()
    path.unlink()
    target = other / "molecules-real.csv"
    target.write_bytes(payload)
    path.symlink_to(target)
    with pytest.raises(OpenADMETOracleProjectionError, match="not regular"):
        project_openadmet_oracle_inputs(
            source2, other / "out", expected_receipts=receipts2
        )


def test_source_and_output_symlink_ancestry_fail_closed(tmp_path: Path) -> None:
    source, receipts = _fixture(tmp_path / "fixture")
    source_alias = tmp_path / "source-alias"
    source_alias.symlink_to(source, target_is_directory=True)
    with pytest.raises(OpenADMETOracleProjectionError, match="contains a symlink"):
        project_openadmet_oracle_inputs(
            source_alias, tmp_path / "source-bad", expected_receipts=receipts
        )

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    output_alias = tmp_path / "output-alias"
    output_alias.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(OpenADMETOracleProjectionError, match="contains a symlink"):
        project_openadmet_oracle_inputs(
            source, output_alias / "out", expected_receipts=receipts
        )


def test_stale_and_forged_source_manifests_fail_closed(tmp_path: Path) -> None:
    source, receipts = _fixture(tmp_path)
    molecule_path = source / "molecules.csv"
    poisoned = molecule_path.read_bytes().replace(b"CCO", b"CCS", 1)
    molecule_path.write_bytes(poisoned)
    receipts["molecules.csv"] = hashlib.sha256(poisoned).hexdigest()
    with pytest.raises(OpenADMETOracleProjectionError, match="output SHA binding"):
        project_openadmet_oracle_inputs(
            source, tmp_path / "stale", expected_receipts=receipts
        )

    source2, receipts2 = _fixture(tmp_path / "other")
    manifest_path = source2 / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["authority"]["model_fits"] = True
    forged = canonical_json_bytes(manifest)
    manifest_path.write_bytes(forged)
    receipts2["manifest.json"] = hashlib.sha256(forged).hexdigest()
    with pytest.raises(OpenADMETOracleProjectionError, match="source authority"):
        project_openadmet_oracle_inputs(
            source2, tmp_path / "forged", expected_receipts=receipts2
        )


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_source_manifest_parent_key_set_is_exact(tmp_path: Path, change: str) -> None:
    source, receipts = _fixture(tmp_path)
    path = source / "manifest.json"
    manifest = json.loads(path.read_bytes())
    if change == "missing":
        name = "direct_observations.csv"
        manifest["parent_receipts"].pop(name)
        manifest["input_receipts"].pop(name)
        manifest["source_receipts"].pop(name)
    else:
        name = "unexpected.csv"
        digest = _sha(name)
        manifest["parent_receipts"][name] = digest
        manifest["input_receipts"][name] = {"sha256": digest, "bytes": 1}
        manifest["source_receipts"][name] = {"sha256": digest, "bytes": 1}
    forged = canonical_json_bytes(manifest)
    path.write_bytes(forged)
    receipts["manifest.json"] = hashlib.sha256(forged).hexdigest()
    with pytest.raises(OpenADMETOracleProjectionError, match="parent binding"):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


def test_stage_is_cleaned_after_verification_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, receipts = _fixture(tmp_path)

    def fail(*_args: object) -> None:
        raise OpenADMETOracleProjectionError("synthetic verification failure")

    monkeypatch.setattr(projection, "_verify_stage", fail)
    with pytest.raises(OpenADMETOracleProjectionError, match="verification failure"):
        project_openadmet_oracle_inputs(
            source, tmp_path / "out", expected_receipts=receipts
        )
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".r5b-projection-*"))


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda rows: rows.pop(), "fold cardinality"),
        (lambda rows: rows[0].__setitem__("seed", "1"), "fold value"),
        (lambda rows: rows[0].__setitem__("outer_fold", "2"), "component crosses"),
    ],
)
def test_fold_poison_fails_closed(
    tmp_path: Path,
    mutation: Callable[[list[dict[str, str]]], Any],
    match: str,
) -> None:
    source, receipts = _fixture(tmp_path)
    _rewrite_csv(source, receipts, "folds.csv", mutation)
    with pytest.raises(OpenADMETOracleProjectionError, match=match):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


@pytest.mark.parametrize("kind", ["shape", "dtype", "nonfinite", "fortran", "binary"])
def test_npy_shape_dtype_finite_order_and_binary_fail_closed(
    tmp_path: Path, kind: str
) -> None:
    source, receipts = _fixture(tmp_path)
    name = "maplight_erg.npy" if kind != "binary" else "morgan_binary.npy"
    width, dtype = FEATURE_SPECS[name]
    array = np.zeros((6, width), dtype=np.dtype(dtype))
    if kind == "shape":
        array = array[:-1]
    elif kind == "dtype":
        array = array.astype(np.float32)
    elif kind == "nonfinite":
        array[0, 0] = np.nan
    elif kind == "fortran":
        array = np.asfortranarray(array)
    else:
        array[0, 0] = 2
    _rewrite_npy(source, receipts, name, array)
    with pytest.raises(OpenADMETOracleProjectionError, match="feature"):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


def test_descriptor_nan_policy_is_exact(tmp_path: Path) -> None:
    source, receipts = _fixture(tmp_path)
    name = "maplight_rdkit_descriptors.npy"
    array = np.zeros((6, 200), dtype=np.dtype("<f8"))
    array[0, 39] = np.nan
    _rewrite_npy(source, receipts, name, array)
    project_openadmet_oracle_inputs(
        source, tmp_path / "allowed", expected_receipts=receipts
    )

    source2, receipts2 = _fixture(tmp_path / "other")
    array[0, 38] = np.nan
    _rewrite_npy(source2, receipts2, name, array)
    with pytest.raises(OpenADMETOracleProjectionError, match="NaN mask"):
        project_openadmet_oracle_inputs(
            source2, tmp_path / "bad", expected_receipts=receipts2
        )


def test_feature_row_order_requires_canonical_molecule_order(tmp_path: Path) -> None:
    source, receipts = _fixture(tmp_path)

    def swap(rows: list[dict[str, str]]) -> None:
        rows[0], rows[1] = rows[1], rows[0]

    _rewrite_csv(source, receipts, "molecules.csv", swap)
    with pytest.raises(OpenADMETOracleProjectionError, match="feature-row order"):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


def test_exact_duplicate_identity_must_remain_in_one_component(tmp_path: Path) -> None:
    source, receipts = _fixture(tmp_path)

    def split_duplicate(rows: list[dict[str, str]]) -> None:
        duplicate = next(row for row in rows if row["molecule_id"] == "duplicate")
        duplicate["similarity_component_hash"] = _sha("component-b")

    _rewrite_csv(source, receipts, "molecules.csv", split_duplicate)
    with pytest.raises(OpenADMETOracleProjectionError, match="crosses a component"):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


@pytest.mark.parametrize(
    ("name", "mutation", "match"),
    [
        (
            "transformation_pairs.csv",
            lambda rows: rows[0].__setitem__("left_standardized_structure_hash", ""),
            "structure receipt",
        ),
        (
            "transformation_pairs.csv",
            lambda rows: rows[0].__setitem__("a_to_b_direction_id", ""),
            "grammar is blank",
        ),
        (
            "episode_transformations.csv",
            lambda rows: rows[0].__setitem__("anchor_molecule_id", "train"),
            "episode metadata",
        ),
        (
            "episode_transformations.csv",
            lambda rows: rows[0].__setitem__("exact_transformation_id", "wrong"),
            "episode grammar",
        ),
    ],
)
def test_r4_geometry_poison_fails_closed(
    tmp_path: Path,
    name: str,
    mutation: Callable[[list[dict[str, str]]], Any],
    match: str,
) -> None:
    source, receipts = _fixture(tmp_path)
    _rewrite_csv(source, receipts, name, mutation)
    with pytest.raises(OpenADMETOracleProjectionError, match=match):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda rows: rows.pop(), "two directions"),
        (
            lambda rows: rows[1].__setitem__("direction_id", rows[0]["direction_id"]),
            "direction differs|duplicate",
        ),
        (lambda rows: rows[0].__setitem__("sample_weight", "-1"), "not positive"),
        (lambda rows: rows[0].__setitem__("sample_weight", "1/3"), "weight differs"),
        (
            lambda rows: rows[1].__setitem__("delta", "-1.0000000000001"),
            "antisymmetric",
        ),
    ],
)
def test_training_pair_arithmetic_poison_fails_closed(
    tmp_path: Path,
    mutation: Callable[[list[dict[str, str]]], Any],
    match: str,
) -> None:
    source, receipts = _fixture(tmp_path)
    _rewrite_csv(source, receipts, "training_pairs.csv", mutation)
    with pytest.raises(OpenADMETOracleProjectionError, match=match):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda rows: rows.append(dict(rows[0])), "duplicate training point"),
        (lambda rows: rows[0].__setitem__("sample_weight", "-1"), "not positive"),
        (lambda rows: rows[0].__setitem__("point", "nan"), "not finite"),
    ],
)
def test_training_point_duplicate_negative_and_nonfinite_fail_closed(
    tmp_path: Path,
    mutation: Callable[[list[dict[str, str]]], Any],
    match: str,
) -> None:
    source, receipts = _fixture(tmp_path)
    _rewrite_csv(source, receipts, "training_points.csv", mutation)
    with pytest.raises(OpenADMETOracleProjectionError, match=match):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("anchor_global_oof_model_id", "other"),
        ("anchor_global_oof_source_scope", "wrong"),
        ("anchor_global_oof_receipt_sha256", "0" * 64),
    ],
)
def test_oof_identity_poison_fails_closed(
    tmp_path: Path, field: str, value: str
) -> None:
    source, receipts = _fixture(tmp_path)
    _rewrite_csv(
        source,
        receipts,
        "global_anchor_contexts.csv",
        lambda rows: rows[0].__setitem__(field, value),
    )
    with pytest.raises(OpenADMETOracleProjectionError, match="OOF"):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


def test_oof_model_id_is_cryptographic_and_scope_consistent(tmp_path: Path) -> None:
    source, receipts = _fixture(tmp_path)

    def change_one_outer_model(rows: list[dict[str, str]]) -> None:
        matching = [
            row for row in rows if row["stage"] == "outer" and row["outer_fold"] == "1"
        ]
        assert len(matching) == 2
        matching[1]["anchor_global_oof_model_id"] = _sha("different-oof-model")

    _rewrite_csv(source, receipts, "global_anchor_contexts.csv", change_one_outer_model)
    with pytest.raises(OpenADMETOracleProjectionError, match="changes within scope"):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


@pytest.mark.parametrize(
    "name",
    [
        "episode_anchor_contexts.csv",
        "global_anchor_contexts.csv",
        "episode_truth.csv",
        "activity_cliffs.csv",
    ],
)
def test_fixed_superset_rejects_omission(tmp_path: Path, name: str) -> None:
    source, receipts = _fixture(tmp_path)
    _rewrite_csv(source, receipts, name, lambda rows: rows.pop())
    with pytest.raises(OpenADMETOracleProjectionError, match="superset|membership"):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


def test_random_anchor_stress_is_rejected_from_inner_cells(tmp_path: Path) -> None:
    source, receipts = _fixture(tmp_path)

    def add_inner(rows: list[dict[str, str]]) -> None:
        stress = next(row for row in rows if row["episode_id"] == _sha("stress-a"))
        rows.append({**stress, **_scope("inner", 0, 0)})

    _rewrite_csv(source, receipts, "episode_anchor_contexts.csv", add_inner)
    with pytest.raises(OpenADMETOracleProjectionError, match="anchor context"):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


def test_false_availability_requires_empty_value(tmp_path: Path) -> None:
    source, receipts = _fixture(tmp_path)

    def poison(rows: list[dict[str, str]]) -> None:
        rows[0]["query_point_available"] = "false"

    _rewrite_csv(source, receipts, "episode_truth.csv", poison)
    with pytest.raises(OpenADMETOracleProjectionError, match="unavailable"):
        project_openadmet_oracle_inputs(
            source, tmp_path / "bad", expected_receipts=receipts
        )


def test_contract_hash_binds_the_frozen_v2_clarification() -> None:
    assert CONTRACT_SHA256 == (
        "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
    )
