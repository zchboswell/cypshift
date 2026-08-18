"""Synthetic firewall tests for the R3B cell/freezer slice."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

ROOT = Path(__file__).parents[1]
RUNNER_PATH = ROOT / "research/maplight-fixed/run_r3b_cells.py"
spec = importlib.util.spec_from_file_location("r3b_cells", RUNNER_PATH)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
SCORER_PATH = ROOT / "research/maplight-fixed/run_r3b_scoring.py"
scorer_spec = importlib.util.spec_from_file_location(
    "r3b_scoring_integration", SCORER_PATH
)
assert scorer_spec is not None and scorer_spec.loader is not None
scorer = importlib.util.module_from_spec(scorer_spec)
sys.modules[scorer_spec.name] = scorer
scorer_spec.loader.exec_module(scorer)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _component(molecule: str) -> str:
    return _sha(molecule.encode("utf-8"))


def _seal(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _unseal(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        path.chmod(0o755 if path.is_dir() else 0o644)
    root.chmod(0o755)


def _model_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    assignments = {"m0": "1", "m1": "0", "m2": "2"}
    for molecule in ("m0", "m1", "m2"):
        for repeat in range(3):
            for validation in range(5):
                rows.append(
                    {
                        "molecule_id": molecule,
                        "similarity_component_hash": _component(molecule),
                        "repeat": str(repeat),
                        "seed": str(20260810 + repeat),
                        "outer_fold": assignments[molecule],
                        "outer_validation_fold": str(validation),
                        "inner_fold": ""
                        if assignments[molecule] == str(validation)
                        else str((int(molecule[-1]) + validation) % 4),
                    }
                )
    return rows


def _receipt() -> dict[str, object]:
    scope = runner.OUTER_SCOPE
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_cell.v5",
        "contract_sha256": runner.V5_SHA256,
        "stage": "outer",
        "cell_id": runner._cell_id(
            runner.V5_SHA256, "outer", "CYP1A2", 0, 0, None, scope
        ),
        "runner_source_sha256": runner._source_bundle_sha(
            [
                RUNNER_PATH,
                RUNNER_PATH.with_name("r3b_cell_io.py"),
                RUNNER_PATH.with_name("r3b_cell_freezer.py"),
            ]
        ),
        "preflight_receipt_sha256": "1" * 64,
        "model_public_manifest_sha256": "2" * 64,
        "target_receipt": {
            "stage": "outer",
            "cell_id": runner._cell_id(
                runner.V5_SHA256, "outer", "CYP1A2", 0, 0, None, scope
            ),
            "endpoint": "CYP1A2",
            "repeat": 0,
            "outer_fold": 0,
            "inner_fold": "",
            "relative_path": "outer_targets/CYP1A2/repeat-0/outer-0.csv",
            "sha256": "3" * 64,
            "rows": 0,
            "identity_sha256": "4" * 64,
        },
        "feature_receipts": {"feature_manifest_sha256": "5" * 64},
        "system_ids": list(runner.OUTER_SYSTEMS),
        "resolved_catboost_parameters": [
            {
                "system_id": system,
                "canonical_get_all_params_json": {"loss_function": "MAE"},
                "canonical_get_all_params_sha256": _sha(
                    runner._json_bytes({"loss_function": "MAE"})
                ),
            }
            for system in (runner.OUTER_SYSTEMS[1], runner.OUTER_SYSTEMS[2])
        ],
        "counts": {
            "training_targets": 1,
            "prediction_molecules": 1,
            "prediction_rows": 4,
            "model_fits": 2,
        },
        "accounting": {
            "target_files_opened": 1,
            "truth_files_opened": 0,
            "private_audit_files_opened": 0,
            "other_target_files_opened": 0,
            "feature_arrays_opened": 5,
            "score_files_opened": 0,
            "tdi_files_opened": 0,
            "blinded_test_files_opened": 0,
            "episode_or_anchor_files_opened": 0,
            "submission_files_opened": 0,
            "transductive_operations": 0,
        },
        "inner_selection_token_sha256": "",
        "authority": runner.INHERITED_AUTHORITY,
    }


def _fragment_rows() -> tuple[dict[str, object], list[dict[str, str]]]:
    receipt = _receipt()
    valid = []
    for system in runner.OUTER_SYSTEMS:
        valid.append(
            {
                "molecule_id": "m1",
                "endpoint": "CYP1A2",
                "component_id": _component("m1"),
                "repeat": "0",
                "outer_fold": "0",
                "inner_fold": "",
                "scope": runner.OUTER_SCOPE,
                "system_id": system,
                "prediction": "1",
                "applicability_score": "0.5",
                "model_id": runner._model_id(
                    runner.V5_SHA256,
                    system,
                    "CYP1A2",
                    0,
                    0,
                    None,
                    runner.OUTER_SCOPE,
                ),
                "feature_spec_id": runner.FEATURE_SPECS[system],
                "split_id": runner._split_id("", 0, 0, None, runner.OUTER_SCOPE),
            }
        )
    return receipt, valid


def test_exact_median_and_tanimoto_policies() -> None:
    assert runner._median([7.0, 1.0, 3.0, 9.0]) == 5.0
    assert runner._median([7.0, 1.0, 3.0]) == 3.0
    zeros = np.array([0, 0], dtype=np.uint8)
    assert runner._tanimoto(zeros, zeros) == 1.0
    assert (
        runner._tanimoto(
            np.array([1, 0], dtype=np.uint8), np.array([0, 1], dtype=np.uint8)
        )
        == 0.0
    )


def test_model_rows_require_outer_context_identity() -> None:
    rows = _model_rows()
    keys = {(r["molecule_id"], r["repeat"], r["outer_validation_fold"]) for r in rows}
    assert len(keys) == len(rows)
    assert len({(r["molecule_id"], r["repeat"]) for r in rows}) < len(rows)


def test_target_receipt_happy_path_uses_named_model_rows(tmp_path: Path) -> None:
    target_rows = [{"observation_id": "obs-m0", "molecule_id": "m0", "point": "1.25"}]
    payload = runner._csv_bytes(("observation_id", "molecule_id", "point"), target_rows)
    target_path = tmp_path / "outer_targets/CYP1A2/repeat-0/outer-0.csv"
    target_path.parent.mkdir(parents=True)
    target_path.write_bytes(payload)
    identity = runner._csv_bytes(("observation_id", "molecule_id"), target_rows)
    cell = runner._cell_id(
        runner.V4_SHA256, "outer", "CYP1A2", 0, 0, None, runner.OUTER_SCOPE
    )
    receipt = {
        "stage": "outer",
        "cell_id": cell,
        "endpoint": "CYP1A2",
        "repeat": 0,
        "outer_fold": 0,
        "inner_fold": "",
        "relative_path": "outer_targets/CYP1A2/repeat-0/outer-0.csv",
        "sha256": _sha(payload),
        "rows": 1,
        "identity_sha256": _sha(identity),
    }
    result = runner._verify_target(
        tmp_path,
        receipt,
        "CYP1A2",
        "outer",
        0,
        0,
        None,
        _model_rows(),
        "",
        cell,
        runner.V4_SHA256,
    )
    assert result == target_rows


def test_target_rows_must_be_sorted_and_receipt_path_exact(tmp_path: Path) -> None:
    target_rows = [
        {"observation_id": "obs-m1", "molecule_id": "m1", "point": "1"},
        {"observation_id": "obs-m0", "molecule_id": "m0", "point": "2"},
    ]
    payload = runner._csv_bytes(("observation_id", "molecule_id", "point"), target_rows)
    target_path = tmp_path / "outer_targets/CYP1A2/repeat-0/outer-0.csv"
    target_path.parent.mkdir(parents=True)
    target_path.write_bytes(payload)
    identity = runner._csv_bytes(("observation_id", "molecule_id"), target_rows)
    cell = runner._cell_id(
        runner.V4_SHA256, "outer", "CYP1A2", 0, 0, None, runner.OUTER_SCOPE
    )
    receipt = {
        "stage": "outer",
        "cell_id": cell,
        "endpoint": "CYP1A2",
        "repeat": 0,
        "outer_fold": 0,
        "inner_fold": "",
        "relative_path": "outer_targets/CYP1A2/repeat-0/outer-0.csv",
        "sha256": _sha(payload),
        "rows": 2,
        "identity_sha256": _sha(identity),
    }
    with pytest.raises(runner.R3BError, match="order"):
        runner._verify_target(
            tmp_path,
            receipt,
            "CYP1A2",
            "outer",
            0,
            0,
            None,
            _model_rows(),
            "",
            cell,
            runner.V4_SHA256,
        )


def test_fragment_membership_uses_validation_context_then_assignment() -> None:
    receipt, valid = _fragment_rows()
    runner._validate_fragment_rows(
        valid, receipt, "outer", runner.V5_SHA256, "", _model_rows()
    )
    crossed = [dict(item) for item in valid]
    crossed[0]["outer_fold"] = "1"
    with pytest.raises(runner.R3BError, match="context|membership"):
        runner._validate_fragment_rows(
            crossed, receipt, "outer", runner.V5_SHA256, "", _model_rows()
        )


def test_fragment_applicability_is_shared_across_outer_systems() -> None:
    receipt, rows = _fragment_rows()
    rows[1]["applicability_score"] = "0.6"
    with pytest.raises(runner.R3BError, match="applicability"):
        runner._validate_fragment_rows(
            rows, receipt, "outer", runner.V5_SHA256, "", _model_rows()
        )


def test_inner_prediction_membership_partitions_outer_training() -> None:
    assignments = {"m0": "1", "m1": "2", "m2": "3", "m3": "4", "m4": "0"}
    rows: list[dict[str, str]] = []
    for molecule, assigned in assignments.items():
        for validation in range(5):
            rows.append(
                {
                    "molecule_id": molecule,
                    "similarity_component_hash": _component(molecule),
                    "repeat": "0",
                    "seed": "20260810",
                    "outer_fold": assigned,
                    "outer_validation_fold": str(validation),
                    "inner_fold": ""
                    if assigned == str(validation)
                    else str(int(molecule[-1]) % 4),
                }
            )
    observed: set[str] = set()
    for inner in range(4):
        scope = "openadmet-direct-inner-v1|outer=0"
        receipt = _receipt()
        receipt.update(
            {
                "stage": "inner",
                "cell_id": runner._cell_id(
                    runner.V5_SHA256, "inner", "CYP1A2", 0, 0, inner, scope
                ),
                "target_receipt": {
                    "stage": "inner",
                    "cell_id": runner._cell_id(
                        runner.V5_SHA256, "inner", "CYP1A2", 0, 0, inner, scope
                    ),
                    "endpoint": "CYP1A2",
                    "repeat": 0,
                    "outer_fold": 0,
                    "inner_fold": inner,
                    "relative_path": f"inner_targets/CYP1A2/repeat-0/outer-0/inner-{inner}.csv",
                    "sha256": "3" * 64,
                    "rows": 0,
                    "identity_sha256": "4" * 64,
                },
                "system_ids": [runner.MAPLIGHT],
                "inner_selection_token_sha256": "token",
            }
        )
        molecule = f"m{inner}"
        row = {
            "molecule_id": molecule,
            "endpoint": "CYP1A2",
            "component_id": _component(molecule),
            "repeat": "0",
            "outer_fold": "0",
            "inner_fold": str(inner),
            "scope": scope,
            "system_id": runner.MAPLIGHT,
            "prediction": "1",
            "applicability_score": "0.5",
            "model_id": runner._model_id(
                runner.V5_SHA256, runner.MAPLIGHT, "CYP1A2", 0, 0, inner, scope
            ),
            "feature_spec_id": runner.FEATURE_SPECS[runner.MAPLIGHT],
            "split_id": runner._split_id("", 0, 0, inner, scope),
        }
        runner._validate_fragment_rows(
            [row], receipt, "inner", runner.V5_SHA256, "", rows, "token"
        )
        observed.add(molecule)
    assert observed == {"m0", "m1", "m2", "m3"}


def test_fragment_rejects_duplicate_missing_and_nonfinite_rows() -> None:
    receipt, valid = _fragment_rows()
    with pytest.raises(runner.R3BError, match="duplicate|population|order"):
        runner._validate_fragment_rows(
            valid + [dict(valid[0])],
            receipt,
            "outer",
            runner.V5_SHA256,
            "",
            _model_rows(),
        )
    with pytest.raises(runner.R3BError, match="population"):
        runner._validate_fragment_rows(
            valid[:-1], receipt, "outer", runner.V5_SHA256, "", _model_rows()
        )
    nonfinite = [dict(item) for item in valid]
    nonfinite[0]["prediction"] = "nan"
    with pytest.raises(runner.R3BError, match="nonfinite"):
        runner._validate_fragment_rows(
            nonfinite, receipt, "outer", runner.V5_SHA256, "", _model_rows()
        )


def test_model_public_forbids_private_audit_before_rows_parse(tmp_path: Path) -> None:
    root = tmp_path / "model-public"
    root.mkdir()
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_model_public.v1",
        "private_audit_path": "/secret/audit.json",
    }
    path = root / "model_public_manifest.json"
    path.write_bytes(runner._json_bytes(manifest))
    _seal(root)
    with pytest.raises(runner.R3BError, match="forbidden"):
        runner._load_public(root, _sha(path.read_bytes()), synthetic=True)


def _public_fixture(
    tmp_path: Path,
    populated: dict[str, list[dict[str, str]]] | None = None,
) -> tuple[Path, str]:
    root = tmp_path / "model-public"
    root.mkdir()
    model_payload = runner._csv_bytes(runner.MODEL_ROWS_COLUMNS, _model_rows())
    (root / "model_rows.csv").write_bytes(model_payload)
    outer: list[dict[str, object]] = []
    inner: list[dict[str, object]] = []
    for endpoint in runner.ENDPOINTS:
        for repeat in range(3):
            for outer_fold in range(5):
                outer_path = (
                    f"outer_targets/{endpoint}/repeat-{repeat}/outer-{outer_fold}.csv"
                )
                (root / outer_path).parent.mkdir(parents=True, exist_ok=True)
                rows = (populated or {}).get(outer_path, [])
                target_payload = runner._csv_bytes(
                    ("observation_id", "molecule_id", "point"), rows
                )
                identity_payload = runner._csv_bytes(
                    ("observation_id", "molecule_id"), rows
                )
                (root / outer_path).write_bytes(target_payload)
                outer.append(
                    {
                        "stage": "outer",
                        "cell_id": runner._cell_id(
                            runner.V5_SHA256,
                            "outer",
                            endpoint,
                            repeat,
                            outer_fold,
                            None,
                            runner.OUTER_SCOPE,
                        ),
                        "endpoint": endpoint,
                        "repeat": repeat,
                        "outer_fold": outer_fold,
                        "inner_fold": "",
                        "relative_path": outer_path,
                        "sha256": _sha(target_payload),
                        "rows": len(rows),
                        "identity_sha256": _sha(identity_payload),
                    }
                )
                for inner_fold in range(4):
                    inner_path = (
                        f"inner_targets/{endpoint}/repeat-{repeat}/"
                        f"outer-{outer_fold}/inner-{inner_fold}.csv"
                    )
                    (root / inner_path).parent.mkdir(parents=True, exist_ok=True)
                    rows = (populated or {}).get(inner_path, [])
                    target_payload = runner._csv_bytes(
                        ("observation_id", "molecule_id", "point"), rows
                    )
                    identity_payload = runner._csv_bytes(
                        ("observation_id", "molecule_id"), rows
                    )
                    (root / inner_path).write_bytes(target_payload)
                    scope = f"openadmet-direct-inner-v1|outer={outer_fold}"
                    inner.append(
                        {
                            "stage": "inner",
                            "cell_id": runner._cell_id(
                                runner.V5_SHA256,
                                "inner",
                                endpoint,
                                repeat,
                                outer_fold,
                                inner_fold,
                                scope,
                            ),
                            "endpoint": endpoint,
                            "repeat": repeat,
                            "outer_fold": outer_fold,
                            "inner_fold": inner_fold,
                            "relative_path": inner_path,
                            "sha256": _sha(target_payload),
                            "rows": len(rows),
                            "identity_sha256": _sha(identity_payload),
                        }
                    )
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_model_public.v5",
        "contract_sha256": runner.V5_SHA256,
        "parent_contract_sha256": runner.V4_SHA256,
        "projector_source_sha256": "f" * 64,
        "model_rows": {
            "path": "model_rows.csv",
            "sha256": _sha(model_payload),
            "bytes": len(model_payload),
            "rows": len(_model_rows()),
            "columns": list(runner.MODEL_ROWS_COLUMNS),
            "schema_version": "",
        },
        "outer_target_receipts": outer,
        "inner_target_receipts": inner,
        "accounting": {
            "truth_paths": 0,
            "truth_hashes": 0,
            "scores": 0,
            "metrics": 0,
        },
        "authority": runner.INHERITED_AUTHORITY,
    }
    path = root / "model_public_manifest.json"
    path.write_bytes(runner._json_bytes(manifest))
    return root, _sha(path.read_bytes())


def _feature_fixture(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "features"
    root.mkdir()
    rows = [
        {
            "molecule_id": molecule,
            "raw_structure_sha256": _sha((molecule + "-raw").encode()),
            "standardized_structure_hash": _sha((molecule + "-std").encode()),
            "similarity_component_hash": _component(molecule),
        }
        for molecule in ("m0", "m1", "m2")
    ]
    row_payload = runner._csv_bytes(runner._io.FEATURE_COLUMNS, rows)
    (root / "feature_rows.csv").write_bytes(row_payload)
    specs = {
        "morgan_binary": (np.uint8, 4096),
        "maplight_morgan_count": (np.int8, 1024),
        "maplight_avalon_count": (np.int8, 1024),
        "maplight_erg": (np.dtype("<f8"), 315),
        "maplight_rdkit_descriptors": (np.dtype("<f8"), 200),
    }
    arrays: dict[str, dict[str, object]] = {}
    for name, (dtype, width) in specs.items():
        array = np.zeros((len(rows), width), dtype=cast(Any, dtype))
        if name == "morgan_binary":
            array[1, 0] = 1
            array[2, 0] = 1
        stream = io.BytesIO()
        np.save(stream, array, allow_pickle=False)
        payload = stream.getvalue()
        (root / f"{name}.npy").write_bytes(payload)
        arrays[name] = {
            "path": f"{name}.npy",
            "shape": [len(rows), width],
            "dtype": runner._io.FEATURE_DTYPE_STR[name],
            "npy_version": "1.0",
            "c_contiguous": True,
            "npy_sha256": _sha(payload),
        }
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1",
        "rows": {
            "path": "feature_rows.csv",
            "columns": list(runner._io.FEATURE_COLUMNS),
            "rows": len(rows),
            "sha256": _sha(row_payload),
        },
        "arrays": arrays,
    }
    path = root / "feature_manifest.json"
    path.write_bytes(runner._json_bytes(manifest))
    digest = _sha(path.read_bytes())
    _seal(root)
    return root, digest


def test_run_cell_outer_path_and_fragment_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_path = "outer_targets/CYP1A2/repeat-0/outer-0.csv"
    populated = {
        target_path: [
            {"observation_id": "obs-m0", "molecule_id": "m0", "point": "1"},
            {"observation_id": "obs-m2", "molecule_id": "m2", "point": "3"},
        ]
    }
    public_root, public_sha = _public_fixture(tmp_path, populated)
    _seal(public_root)
    feature_root, feature_sha = _feature_fixture(tmp_path)
    preflight = tmp_path / "preflight.json"
    preflight.write_bytes(runner._json_bytes(_preflight_payload(public_sha)))

    def fake_catboost(
        _x: np.ndarray[Any, Any], _y: np.ndarray[Any, Any], x_pred: np.ndarray[Any, Any]
    ) -> tuple[np.ndarray[Any, Any], dict[str, Any]]:
        return np.full(len(x_pred), 1.5, dtype=np.float64), {"loss_function": "MAE"}

    monkeypatch.setattr(runner, "_catboost_predict", fake_catboost)
    output = runner.run_cell(
        stage="outer",
        endpoint="CYP1A2",
        repeat=0,
        outer_fold=0,
        inner_fold=None,
        feature_root=feature_root,
        feature_manifest_sha256=feature_sha,
        model_public_root=public_root,
        model_public_manifest_sha256=public_sha,
        preflight_receipt=preflight,
        output_root=tmp_path / "cell-output",
        synthetic=True,
    )
    receipt, rows = runner._load_fragment(output)
    assert receipt["counts"]["training_targets"] == 2
    assert len(rows) == 4
    assert {row["molecule_id"] for row in rows} == {"m1"}
    assert {row["applicability_score"] for row in rows} == {"1"}


def test_freezers_replay_all_synthetic_outer_and_inner_cells(tmp_path: Path) -> None:
    public_root, public_sha = _public_fixture(tmp_path)
    _seal(public_root)
    preflight = tmp_path / "preflight.json"
    preflight.write_bytes(runner._json_bytes(_preflight_payload(public_sha)))
    preflight_sha = _sha(preflight.read_bytes())
    feature_sha = "f" * 64
    public, model_rows, _receipts, _ = runner._load_public(
        public_root, public_sha, synthetic=True, verify_target_payloads=False
    )
    index = runner._fold_index(public_sha)
    source_sha = runner._source_bundle_sha(
        [
            RUNNER_PATH,
            RUNNER_PATH.with_name("r3b_cell_io.py"),
            RUNNER_PATH.with_name("r3b_cell_freezer.py"),
        ]
    )
    params = {
        system: {
            "system_id": system,
            "canonical_get_all_params_json": {"loss_function": "MAE"},
            "canonical_get_all_params_sha256": _sha(
                runner._json_bytes({"loss_function": "MAE"})
            ),
        }
        for system in (runner.OUTER_SYSTEMS[1], runner.MAPLIGHT)
    }
    token = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_inner_selection_token.v1",
        "contract_sha256": runner.V5_SHA256,
        "token_writer_source_sha256": "a" * 64,
        "outer_assessment_sha256": "b" * 64,
        "selected_system_id": runner.MAPLIGHT,
        "outer_outcome": "PASS",
        "authority": runner.INHERITED_AUTHORITY,
    }
    token_path = tmp_path / "inner-selection-token.json"
    token_path.write_bytes(runner._json_bytes(token))
    token_sha = _sha(token_path.read_bytes())

    def make_cells(stage: str) -> list[Path]:
        roots: list[Path] = []
        systems = runner.OUTER_SYSTEMS if stage == "outer" else (runner.MAPLIGHT,)
        for endpoint in runner.ENDPOINTS:
            for repeat in range(3):
                for outer in range(5):
                    inner_values = (None,) if stage == "outer" else range(4)
                    for inner in inner_values:
                        scope = (
                            runner.OUTER_SCOPE
                            if stage == "outer"
                            else f"openadmet-direct-inner-v1|outer={outer}"
                        )
                        target_path = (
                            f"outer_targets/{endpoint}/repeat-{repeat}/outer-{outer}.csv"
                            if stage == "outer"
                            else (
                                f"inner_targets/{endpoint}/repeat-{repeat}/"
                                f"outer-{outer}/inner-{inner}.csv"
                            )
                        )
                        context_rows = index["by_context"][(repeat, outer)]
                        molecule_ids = sorted(
                            row["molecule_id"]
                            for row in context_rows
                            if (
                                int(row["outer_fold"]) == outer
                                if stage == "outer"
                                else int(row["outer_fold"]) != outer
                                and row["inner_fold"] == str(inner)
                            )
                        )
                        component = {
                            row["molecule_id"]: row["similarity_component_hash"]
                            for row in context_rows
                        }
                        fragment_rows = [
                            {
                                "molecule_id": molecule,
                                "endpoint": endpoint,
                                "component_id": component[molecule],
                                "repeat": str(repeat),
                                "outer_fold": str(outer),
                                "inner_fold": "" if inner is None else str(inner),
                                "scope": scope,
                                "system_id": system,
                                "prediction": "1",
                                "applicability_score": "0.5",
                                "model_id": runner._model_id(
                                    runner.V5_SHA256,
                                    system,
                                    endpoint,
                                    repeat,
                                    outer,
                                    inner,
                                    scope,
                                ),
                                "feature_spec_id": runner.FEATURE_SPECS[system],
                                "split_id": runner._split_id(
                                    runner.GROUP_FOLDS_SHA256,
                                    repeat,
                                    outer,
                                    inner,
                                    scope,
                                ),
                            }
                            for system in systems
                            for molecule in molecule_ids
                        ]
                        fragment = runner._csv_bytes(
                            runner.FRAGMENT_COLUMNS, fragment_rows
                        )
                        cell_id = runner._cell_id(
                            runner.V5_SHA256,
                            stage,
                            endpoint,
                            repeat,
                            outer,
                            inner,
                            scope,
                        )
                        receipt = {
                            "schema_version": "cypshift.openadmet_cyp_2026.r3b_cell.v5",
                            "contract_sha256": runner.V5_SHA256,
                            "stage": stage,
                            "cell_id": cell_id,
                            "runner_source_sha256": source_sha,
                            "preflight_receipt_sha256": preflight_sha,
                            "model_public_manifest_sha256": public_sha,
                            "target_receipt": {
                                "stage": stage,
                                "cell_id": cell_id,
                                "endpoint": endpoint,
                                "repeat": repeat,
                                "outer_fold": outer,
                                "inner_fold": "" if inner is None else inner,
                                "relative_path": target_path,
                                "sha256": "1" * 64,
                                "rows": 0,
                                "identity_sha256": "2" * 64,
                            },
                            "feature_receipts": {
                                "feature_manifest_sha256": feature_sha
                            },
                            "inner_selection_token_sha256": ""
                            if inner is None
                            else token_sha,
                            "system_ids": list(systems),
                            "resolved_catboost_parameters": [
                                params[system]
                                for system in (
                                    (runner.OUTER_SYSTEMS[1], runner.MAPLIGHT)
                                    if stage == "outer"
                                    else (runner.MAPLIGHT,)
                                )
                            ],
                            "prediction_fragment": {
                                "path": "prediction_fragment.csv",
                                "sha256": _sha(fragment),
                                "bytes": len(fragment),
                                "rows": len(fragment_rows),
                                "columns": list(runner.FRAGMENT_COLUMNS),
                                "schema_version": "",
                            },
                            "counts": {
                                "training_targets": 1,
                                "prediction_molecules": len(molecule_ids),
                                "prediction_rows": len(fragment_rows),
                                "model_fits": 2 if stage == "outer" else 1,
                            },
                            "accounting": {
                                "target_files_opened": 1,
                                "truth_files_opened": 0,
                                "private_audit_files_opened": 0,
                                "other_target_files_opened": 0,
                                "feature_arrays_opened": 5,
                                "score_files_opened": 0,
                                "tdi_files_opened": 0,
                                "blinded_test_files_opened": 0,
                                "episode_or_anchor_files_opened": 0,
                                "submission_files_opened": 0,
                                "transductive_operations": 0,
                            },
                            "authority": runner.INHERITED_AUTHORITY,
                        }
                        root = tmp_path / f"{stage}-{endpoint}-{repeat}-{outer}-{inner}"
                        root.mkdir()
                        (root / "prediction_fragment.csv").write_bytes(fragment)
                        (root / "cell_receipt.json").write_bytes(
                            runner._json_bytes(receipt)
                        )
                        _seal(root)
                        roots.append(root)
        return roots

    outer_roots = make_cells("outer")
    inner_roots = make_cells("inner")
    outer_output = runner.freeze_outer(
        cell_roots=outer_roots,
        output_root=tmp_path / "outer-freeze",
        model_public_root=public_root,
        model_public_manifest_sha256=public_sha,
        preflight_receipt=preflight,
        preflight_receipt_sha256=preflight_sha,
        feature_manifest_sha256=feature_sha,
        synthetic=True,
    )
    inner_output = runner.freeze_inner(
        cell_roots=inner_roots,
        output_root=tmp_path / "inner-freeze",
        model_public_root=public_root,
        model_public_manifest_sha256=public_sha,
        preflight_receipt=preflight,
        preflight_receipt_sha256=preflight_sha,
        feature_manifest_sha256=feature_sha,
        inner_selection_token=token_path,
        synthetic=True,
    )
    assert len(outer_roots) == 60 and len(inner_roots) == 240
    assert outer_output.is_dir() and inner_output.is_dir()
    for output in (outer_output, inner_output):
        assert not output.stat().st_mode & 0o222
        assert all(not path.stat().st_mode & 0o222 for path in output.rglob("*"))
    scorer._load_freeze(
        outer_output,
        _sha((outer_output / "global_oof_freeze_manifest.json").read_bytes()),
        "outer",
        scorer.V5_SHA256,
        True,
    )
    scorer._load_freeze(
        inner_output,
        _sha((inner_output / "global_inner_oof_freeze_manifest.json").read_bytes()),
        "inner",
        scorer.V5_SHA256,
        True,
    )


def test_fragment_replay_bytes_are_receipt_bound(tmp_path: Path) -> None:
    receipt, rows = _fragment_rows()
    payload = runner._csv_bytes(runner.FRAGMENT_COLUMNS, rows)
    receipt["prediction_fragment"] = {
        "path": "prediction_fragment.csv",
        "sha256": _sha(payload),
        "bytes": len(payload),
        "rows": len(rows),
        "columns": list(runner.FRAGMENT_COLUMNS),
        "schema_version": "",
    }
    root = tmp_path / "cell"
    root.mkdir()
    (root / "prediction_fragment.csv").write_bytes(payload)
    (root / "cell_receipt.json").write_bytes(runner._json_bytes(receipt))
    _seal(root)
    loaded_receipt, loaded_rows = runner._load_fragment(root)
    assert loaded_receipt["prediction_fragment"]["columns"] == list(
        runner.FRAGMENT_COLUMNS
    )
    assert {row["applicability_score"] for row in loaded_rows} == {"0.5"}
    _unseal(root)
    (root / "prediction_fragment.csv").write_bytes(payload + b" ")
    _seal(root)
    with pytest.raises(runner.R3BError, match="receipt"):
        runner._load_fragment(root)


def test_fragment_forbidden_metadata_is_recursive(tmp_path: Path) -> None:
    receipt, rows = _fragment_rows()
    payload = runner._csv_bytes(runner.FRAGMENT_COLUMNS, rows)
    receipt["prediction_fragment"] = {
        "path": "prediction_fragment.csv",
        "sha256": _sha(payload),
        "bytes": len(payload),
        "rows": len(rows),
        "columns": list(runner.FRAGMENT_COLUMNS),
        "schema_version": "",
    }
    receipt["feature_receipts"] = {"nested": {"score": 1}}
    root = tmp_path / "cell"
    root.mkdir()
    (root / "prediction_fragment.csv").write_bytes(payload)
    (root / "cell_receipt.json").write_bytes(runner._json_bytes(receipt))
    _seal(root)
    with pytest.raises(runner.R3BError, match="forbidden"):
        runner._load_fragment(root)


def test_fragment_unknown_scalar_leakage_is_rejected(tmp_path: Path) -> None:
    receipt, rows = _fragment_rows()
    payload = runner._csv_bytes(runner.FRAGMENT_COLUMNS, rows)
    receipt["prediction_fragment"] = {
        "path": "prediction_fragment.csv",
        "sha256": _sha(payload),
        "bytes": len(payload),
        "rows": len(rows),
        "columns": list(runner.FRAGMENT_COLUMNS),
        "schema_version": "",
    }
    receipt["feature_receipts"] = {
        "feature_manifest_sha256": "5" * 64,
        "nested": {"note": "sealed_truth=/tmp/truth.csv"},
    }
    root = tmp_path / "cell"
    root.mkdir()
    (root / "prediction_fragment.csv").write_bytes(payload)
    (root / "cell_receipt.json").write_bytes(runner._json_bytes(receipt))
    _seal(root)
    with pytest.raises(runner.R3BError, match="forbidden"):
        runner._load_fragment(root)


def test_target_mutation_cannot_change_fragment_bytes(tmp_path: Path) -> None:
    receipt, rows = _fragment_rows()
    payload = runner._csv_bytes(runner.FRAGMENT_COLUMNS, rows)
    receipt["prediction_fragment"] = {
        "path": "prediction_fragment.csv",
        "sha256": _sha(payload),
        "bytes": len(payload),
        "rows": len(rows),
        "columns": list(runner.FRAGMENT_COLUMNS),
        "schema_version": "",
    }
    root = tmp_path / "cell"
    root.mkdir()
    (root / "prediction_fragment.csv").write_bytes(payload)
    (root / "cell_receipt.json").write_bytes(runner._json_bytes(receipt))
    target_receipt = cast(dict[str, Any], receipt["target_receipt"])
    target = root / str(target_receipt["relative_path"])
    target.parent.mkdir(parents=True)
    target.write_text("observation_id,molecule_id,point\nx,m1,1\n", encoding="utf-8")
    _seal(root)
    first = runner._load_fragment(root)
    _unseal(root)
    target.write_text("observation_id,molecule_id,point\nx,m1,999\n", encoding="utf-8")
    _seal(root)
    assert runner._load_fragment(root) == first


def test_private_truth_mutation_cannot_change_public_model_bytes(
    tmp_path: Path,
) -> None:
    root, public_sha = _public_fixture(tmp_path)
    _seal(root)
    first = runner._load_public(root, public_sha, synthetic=True)[1]
    sealed = tmp_path / "sealed_truth.csv"
    sealed.write_text("point\n1.0\n", encoding="utf-8")
    sealed.write_text("point\n999.0\n", encoding="utf-8")
    second = runner._load_public(root, public_sha, synthetic=True)[1]
    assert first == second


def test_target_mutation_after_public_load_is_rejected(tmp_path: Path) -> None:
    root, public_sha = _public_fixture(tmp_path)
    _seal(root)
    public, model_rows, receipts, loaded_sha = runner._load_public(
        root, public_sha, synthetic=True, verify_target_payloads=False
    )
    assert loaded_sha == public_sha
    target = cast(dict[str, Any], receipts[0])
    target_path = root / str(target["relative_path"])
    _unseal(root)
    target_path.write_text(
        "observation_id,molecule_id,point\nobs,m0,1\n", encoding="utf-8"
    )
    _seal(root)
    with pytest.raises(runner.R3BError, match="receipt"):
        runner._verify_target(
            root,
            target,
            str(target["endpoint"]),
            str(target["stage"]),
            int(target["repeat"]),
            int(target["outer_fold"]),
            None,
            model_rows,
            runner._group_sha(public, synthetic=True),
            str(target["cell_id"]),
            runner.V5_SHA256,
            runner._fold_index(public_sha),
        )


def test_runner_runs_in_fresh_subprocess_and_binds_source_and_target(
    tmp_path: Path,
) -> None:
    target_path = "outer_targets/CYP1A2/repeat-0/outer-0.csv"
    populated = {
        target_path: [
            {"observation_id": "obs-m0", "molecule_id": "m0", "point": "1"},
            {"observation_id": "obs-m2", "molecule_id": "m2", "point": "3"},
        ]
    }
    public_root, public_sha = _public_fixture(tmp_path, populated)
    _seal(public_root)
    feature_root, feature_sha = _feature_fixture(tmp_path)
    preflight = tmp_path / "subprocess-preflight.json"
    preflight.write_bytes(runner._json_bytes(_preflight_payload(public_sha)))

    def run_cell(output_root: Path) -> subprocess.CompletedProcess[str]:
        code = f"""
import importlib.util
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location("fresh", {str(RUNNER_PATH)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def fake_catboost(_x, _y, x_pred):
    return np.full(len(x_pred), 1.5, dtype=np.float64), {{"loss_function": "MAE"}}

module._catboost_predict = fake_catboost
module.run_cell(
    stage="outer",
    endpoint="CYP1A2",
    repeat=0,
    outer_fold=0,
    inner_fold=None,
    feature_root=Path({str(feature_root)!r}),
    feature_manifest_sha256={feature_sha!r},
    model_public_root=Path({str(public_root)!r}),
    model_public_manifest_sha256={public_sha!r},
    preflight_receipt=Path({str(preflight)!r}),
    output_root=Path({str(output_root)!r}),
    synthetic=True,
)
print(module._source_bundle_sha([
    Path({str(RUNNER_PATH)!r}),
    Path({str(RUNNER_PATH.with_name("r3b_cell_io.py"))!r}),
    Path({str(RUNNER_PATH.with_name("r3b_cell_freezer.py"))!r}),
]))
"""
        return subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )

    output_root = tmp_path / "subprocess-cell"
    result = run_cell(output_root)
    assert result.returncode == 0, result.stderr
    receipt, rows = runner._load_fragment(output_root)
    assert receipt["runner_source_sha256"] == result.stdout.strip()
    assert {row["molecule_id"] for row in rows} == {"m1"}

    _unseal(public_root)
    (public_root / target_path).write_text(
        "observation_id,molecule_id,point\nobs-m0,m0,999\nobs-m2,m2,3\n",
        encoding="utf-8",
    )
    _seal(public_root)
    target_result = run_cell(tmp_path / "subprocess-cell-target-mutated")
    assert target_result.returncode != 0
    assert "target payload receipt" in target_result.stderr

    _unseal(output_root)
    cell_receipt_path = output_root / "cell_receipt.json"
    mutated_receipt, _ = runner._read_json(cell_receipt_path)
    mutated_receipt["runner_source_sha256"] = "0" * 64
    cell_receipt_path.write_bytes(runner._json_bytes(mutated_receipt))
    _seal(output_root)
    source_code = f"""
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("fresh_source", {str(RUNNER_PATH)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module._load_fragment(Path({str(output_root)!r}))
"""
    source_result = subprocess.run(
        [sys.executable, "-c", source_code],
        capture_output=True,
        text=True,
    )
    assert source_result.returncode != 0
    assert "source receipt" in source_result.stderr


def _preflight_payload(public_sha: str) -> dict[str, object]:
    contexts = [
        {"endpoint": endpoint, "repeat": repeat, "outer_fold": outer}
        for endpoint in runner.ENDPOINTS
        for repeat in range(3)
        for outer in range(5)
    ]
    support = [
        dict(item, component_count=10, minimum_components=10, passes=True)
        for item in contexts
    ]
    outer = [
        dict(
            item,
            stage="outer",
            inner_fold="",
            eligible_targets=1,
            minimum_eligible_targets=1,
            passes=True,
        )
        for item in contexts
    ]
    inner = [
        dict(
            item,
            stage="inner",
            inner_fold=inner_fold,
            eligible_targets=1,
            minimum_eligible_targets=1,
            passes=True,
        )
        for item in contexts
        for inner_fold in range(4)
    ]
    q90 = [
        dict(item, eligible_residuals=1, minimum_eligible_targets=1, passes=True)
        for item in contexts
    ]
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_preflight.v5",
        "contract_sha256": runner.V5_SHA256,
        "model_public_manifest_sha256": public_sha,
        "private_projection_audit_sha256": "a" * 64,
        "checks": {
            "outer_score_support_cells": support,
            "outer_training_populations": outer,
            "inner_training_populations": inner,
            "q90_residual_eligibility_populations": q90,
        },
        "passed": True,
        "failure_reasons": [],
        "accounting": runner._PREFLIGHT_ACCOUNTING,
        "authority": runner.INHERITED_AUTHORITY,
    }


def test_inner_token_score_leakage_is_rejected(tmp_path: Path) -> None:
    public, public_sha = _public_fixture(tmp_path)
    _seal(public)
    token = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_inner_selection_token.v1",
        "contract_sha256": runner.V5_SHA256,
        "token_writer_source_sha256": "a" * 64,
        "outer_assessment_sha256": "b" * 64,
        "selected_system_id": runner.MAPLIGHT,
        "outer_outcome": "PASS",
        "score": 0.1,
        "authority": runner.INHERITED_AUTHORITY,
    }
    path = tmp_path / "inner_selection_token.json"
    path.write_bytes(runner._json_bytes(token))
    preflight = tmp_path / "preflight.json"
    preflight.write_bytes(runner._json_bytes(_preflight_payload(public_sha)))
    with pytest.raises(runner.R3BError, match="leaks score"):
        runner._freeze(
            stage="inner",
            cell_roots=[],
            output_root=tmp_path / "out",
            model_public_root=public,
            model_public_manifest_sha256=public_sha,
            preflight_receipt=preflight,
            feature_manifest_sha256="x" * 64,
            inner_selection_token=path,
            synthetic=True,
        )


def test_noreplace_rejects_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "stage"
    source.mkdir()
    destination = tmp_path / "destination"
    destination.mkdir()
    with pytest.raises(runner.R3BError, match="appeared"):
        runner._promote_noreplace(source, destination)


def test_strict_json_csv_and_path_firewalls(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(b'{"a": 1, "a": 2}\n')
    with pytest.raises(runner.R3BError, match="duplicate"):
        runner._read_json(duplicate)
    with pytest.raises(runner.R3BError, match="malformed|columns"):
        runner._read_csv_bytes(b"a,b\n1\n", ("a", "b"), "fixture")
    with pytest.raises(runner.R3BError, match="columns"):
        runner._read_csv_bytes(b"a,b,c\n1,2,3\n", ("a", "b"), "fixture")
    root = tmp_path / "root"
    root.mkdir()
    (root / "real").mkdir()
    (root / "real" / "file").write_text("x", encoding="utf-8")
    (root / "link").symlink_to(root / "real", target_is_directory=True)
    with pytest.raises(runner.R3BError, match="symlink"):
        runner._rooted_path(root, "link/file")
    with pytest.raises(runner.R3BError, match="unsafe|escapes"):
        runner._rooted_path(root, "../file")


def test_json_rejects_nonstandard_values_and_bool_integer_aliases(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nonstandard.json"
    path.write_bytes(b'{"value": NaN}\n')
    with pytest.raises(runner.R3BError, match="nonstandard"):
        runner._read_json(path)
    with pytest.raises(runner.R3BError, match="nonstandard"):
        runner._json_bytes({"value": float("inf")})
    with pytest.raises(runner.R3BError, match="unsigned"):
        runner._parse_int(True, "fixture")


def test_forbidden_firewall_scans_scalar_values_recursively() -> None:
    tokens = ("score", "truth", "sealed", "metric", "private_audit")
    assert runner._contains_forbidden(
        {"loss_function": "sealed_truth=/tmp/truth.csv"}, tokens
    )
    assert runner._contains_forbidden(
        {"nested": [{"path": "private_audit/score.json"}]}, tokens
    )
    assert not runner._contains_forbidden({"eval_metric": "RMSE"}, tokens)
    assert runner._contains_forbidden(
        {"eval_metric": "sealed_truth=/tmp/truth.csv"}, tokens
    )
    assert not runner._contains_forbidden({"grow_policy": "SymmetricTree"}, tokens)
    assert not runner._contains_forbidden({"note": "metricized"}, tokens)
    assert runner._contains_forbidden({"note": "outer_score"}, tokens)
    assert runner._contains_forbidden({"note": "truth_path"}, tokens)
    for value in (
        "sealedTruth",
        "privateAudit/path.json",
        "private_audit",
        "private-audit",
    ):
        assert runner._contains_forbidden({"note": value}, tokens)


def test_exact_receipt_maps_reject_bool_aliases(tmp_path: Path) -> None:
    public_root, _public_sha = _public_fixture(tmp_path)
    public_manifest_path = public_root / "model_public_manifest.json"
    manifest, _ = runner._read_json(public_manifest_path)
    cast(dict[str, Any], manifest["accounting"])["truth_paths"] = False
    public_manifest_path.write_bytes(runner._json_bytes(manifest))
    _seal(public_root)
    with pytest.raises(runner.R3BError, match="accounting"):
        runner._load_public(
            public_root, _sha(public_manifest_path.read_bytes()), synthetic=True
        )

    preflight = _preflight_payload("b" * 64)
    preflight["accounting"] = dict(runner._PREFLIGHT_ACCOUNTING)
    cast(dict[str, Any], preflight["accounting"])["gpu_fits"] = False
    preflight_path = tmp_path / "preflight-bool.json"
    preflight_path.write_bytes(runner._json_bytes(preflight))
    with pytest.raises(runner.R3BError, match="accounting"):
        runner._validate_preflight(preflight_path, runner.V5_SHA256, "b" * 64)

    receipt, rows = _fragment_rows()
    payload = runner._csv_bytes(runner.FRAGMENT_COLUMNS, rows)
    receipt["prediction_fragment"] = {
        "path": "prediction_fragment.csv",
        "sha256": _sha(payload),
        "bytes": len(payload),
        "rows": len(rows),
        "columns": list(runner.FRAGMENT_COLUMNS),
        "schema_version": "",
    }
    receipt["authority"] = dict(runner.INHERITED_AUTHORITY)
    cast(dict[str, Any], receipt["authority"])["fold_assignments"] = 0
    cell_root = tmp_path / "cell-bool"
    cell_root.mkdir()
    (cell_root / "prediction_fragment.csv").write_bytes(payload)
    (cell_root / "cell_receipt.json").write_bytes(runner._json_bytes(receipt))
    _seal(cell_root)
    with pytest.raises(runner.R3BError, match="authority"):
        runner._load_fragment(cell_root)


def test_cell_feature_receipts_reject_nested_truth_metadata(tmp_path: Path) -> None:
    receipt, rows = _fragment_rows()
    payload = runner._csv_bytes(runner.FRAGMENT_COLUMNS, rows)
    receipt["prediction_fragment"] = {
        "path": "prediction_fragment.csv",
        "sha256": _sha(payload),
        "bytes": len(payload),
        "rows": len(rows),
        "columns": list(runner.FRAGMENT_COLUMNS),
        "schema_version": "",
    }
    receipt["feature_receipts"] = {"nested": {"truth_path": "/secret"}}
    root = tmp_path / "cell"
    root.mkdir()
    (root / "prediction_fragment.csv").write_bytes(payload)
    (root / "cell_receipt.json").write_bytes(runner._json_bytes(receipt))
    _seal(root)
    with pytest.raises(runner.R3BError, match="forbidden|feature receipt"):
        runner._load_fragment(root)


def test_fold_index_rejects_seed_blank_component_and_duplicates() -> None:
    rows = _model_rows()
    bad_seed = [dict(row) for row in rows]
    bad_seed[0]["seed"] = "20260811"
    with pytest.raises(runner.R3BError, match="seed"):
        runner._build_fold_index(bad_seed)
    bad_blank = [dict(row) for row in rows]
    bad_blank[0]["inner_fold"] = ""
    with pytest.raises(runner.R3BError, match="blank"):
        runner._build_fold_index(bad_blank)
    bad_component = [dict(row) for row in rows]
    bad_component[1]["similarity_component_hash"] = "other"
    with pytest.raises(runner.R3BError, match="component"):
        runner._build_fold_index(bad_component)
    with pytest.raises(runner.R3BError, match="duplicate"):
        runner._build_fold_index(rows + [dict(rows[0])])


def test_split_id_uses_frozen_group_fold_receipt() -> None:
    with pytest.raises(runner.R3BError, match="group-fold"):
        runner._group_sha({"model_rows": {"sha256": "not-the-folds"}})


def test_preflight_rejects_inner_context_replay(tmp_path: Path) -> None:
    receipt = _preflight_payload("b" * 64)
    checks = cast(dict[str, Any], receipt["checks"])
    inner = cast(list[dict[str, Any]], checks["inner_training_populations"])
    inner[1]["inner_fold"] = inner[0]["inner_fold"]
    path = tmp_path / "preflight.json"
    path.write_bytes(runner._json_bytes(receipt))
    with pytest.raises(runner.R3BError, match="duplicate|contexts"):
        runner._validate_preflight(path, runner.V5_SHA256, "b" * 64)


def test_public_forbidden_metadata_is_recursive(tmp_path: Path) -> None:
    root, public_sha = _public_fixture(tmp_path)
    path = root / "model_public_manifest.json"
    manifest, _ = runner._read_json(path)
    manifest["outer_target_receipts"][0]["nested"] = {"score": 1}
    path.write_bytes(runner._json_bytes(manifest))
    _seal(root)
    with pytest.raises(runner.R3BError, match="forbidden"):
        runner._load_public(root, _sha(path.read_bytes()), synthetic=True)
    assert public_sha != _sha(path.read_bytes())


def test_freezer_requires_readonly_cell_root(tmp_path: Path) -> None:
    receipt, rows = _fragment_rows()
    payload = runner._csv_bytes(runner.FRAGMENT_COLUMNS, rows)
    receipt["prediction_fragment"] = {
        "path": "prediction_fragment.csv",
        "sha256": _sha(payload),
        "bytes": len(payload),
        "rows": len(rows),
        "columns": list(runner.FRAGMENT_COLUMNS),
        "schema_version": "",
    }
    root = tmp_path / "cell"
    root.mkdir()
    (root / "prediction_fragment.csv").write_bytes(payload)
    (root / "cell_receipt.json").write_bytes(runner._json_bytes(receipt))
    with pytest.raises(runner.R3BError, match="writable"):
        runner._load_fragment(root)


def test_nearest_neighbor_tie_and_shared_applicability_are_deterministic() -> None:
    left = np.array([1, 0, 1], dtype=np.uint8)
    right = np.array([1, 1, 0], dtype=np.uint8)
    query = np.array([1, 1, 1], dtype=np.uint8)
    scores = [runner._tanimoto(query, base) for base in (left, right)]
    assert scores[0] == scores[1]
    assert [1.5, 2.5][
        min(i for i, score in enumerate(scores) if score == max(scores))
    ] == 1.5
    applicability = max(scores)
    assert applicability == runner._tanimoto(query, left)
    assert applicability == runner._tanimoto(query, right)
