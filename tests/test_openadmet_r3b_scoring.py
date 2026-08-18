from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "research/maplight-fixed/run_r3b_scoring.py"
spec = importlib.util.spec_from_file_location("r3b_scoring", SCRIPT)
assert spec and spec.loader
r3b = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r3b
spec.loader.exec_module(r3b)
manifest = sys.modules["r3b_scoring_manifest"]
terminal = sys.modules["r3b_scoring_terminal"]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_production_receipt_maps_bind_values_and_order() -> None:
    source = terminal._source_receipts(False)
    for stage in (
        "outer_freeze",
        "outer_score",
        "inner_token",
        "final_score",
        "terminal_publish",
    ):
        terminal._record_source(source, stage)
    assert (
        manifest._validate_source_receipts(
            source, status="GLOBAL_EXPERT_FROZEN", synthetic=False
        )
        == source
    )
    mutated = dict(source)
    mutated["preflight"] = source["outer_scorer"]
    with pytest.raises(r3b.R3BScoringError, match="provenance"):
        manifest._validate_source_receipts(
            mutated, status="GLOBAL_EXPERT_FROZEN", synthetic=False
        )
    reordered = {key: source[key] for key in reversed(tuple(source))}
    with pytest.raises(r3b.R3BScoringError, match="order"):
        manifest._validate_source_receipts(
            reordered, status="GLOBAL_EXPERT_FROZEN", synthetic=False
        )
    nonhex = dict(source)
    nonhex["cell_runner"] = "z" * 64
    with pytest.raises(r3b.R3BScoringError, match="cell_runner"):
        manifest._validate_source_receipts(
            nonhex, status="GLOBAL_EXPERT_FROZEN", synthetic=False
        )
    wrong_model = dict(source)
    wrong_model["cell_runner"] = "0" * 64
    with pytest.raises(r3b.R3BScoringError, match="model source"):
        manifest._validate_source_receipts(
            wrong_model, status="GLOBAL_EXPERT_FROZEN", synthetic=False
        )


def test_production_verified_receipts_require_frozen_v3_inputs() -> None:
    values = {key: "a" * 64 for key in manifest._VERIFIED_KEYS}
    values["direct_observations_sha256"] = manifest._DIRECT_OBSERVATIONS_SHA256
    values["group_folds_sha256"] = manifest._GROUP_FOLDS_SHA256
    assert (
        manifest._validate_verified_receipts(
            values, status="GLOBAL_EXPERT_FROZEN", synthetic=False
        )
        == values
    )
    values["group_folds_sha256"] = "b" * 64
    with pytest.raises(r3b.R3BScoringError, match="frozen v3"):
        manifest._validate_verified_receipts(
            values, status="GLOBAL_EXPERT_FROZEN", synthetic=False
        )


def _json(data: object) -> bytes:
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def _csv(columns: list[str], rows: list[dict[str, object]]) -> bytes:
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return stream.getvalue().encode()


def _row(path: Path, data: bytes) -> str:
    path.write_bytes(data)
    return _sha(data)


def _fixture(tmp_path: Path) -> dict[str, Path | str]:
    outer_rows: list[dict[str, object]] = []
    outer_truth: list[dict[str, object]] = []
    inner_rows: list[dict[str, object]] = []
    inner_truth: list[dict[str, object]] = []
    for endpoint in r3b.ENDPOINTS:
        for repeat in range(3):
            for outer_fold in range(5):
                for molecule_index in range(11):
                    molecule = f"{endpoint}-{outer_fold}-{molecule_index}"
                    component = f"component-{molecule_index}"
                    ineligible = molecule_index == 10
                    truth = {
                        "observation_id": f"obs-{endpoint}-{repeat}-{outer_fold}-{molecule_index}",
                        "molecule_id": molecule,
                        "endpoint": endpoint,
                        "component_id": component,
                        "repeat": repeat,
                        "outer_fold": outer_fold,
                        "inner_fold": "",
                        "scope": "outer",
                        "value_state": "missing" if ineligible else "complete",
                        "point_eligible": "false" if ineligible else "true",
                        "point": "0.0",
                        "low": "",
                        "high": "",
                        "std": "",
                    }
                    outer_truth.append(truth)
                    for system, prediction in zip(
                        r3b.SYSTEMS, (0.3, 0.4, 0.1, 0.5), strict=True
                    ):
                        outer_rows.append(
                            {
                                "molecule_id": molecule,
                                "endpoint": endpoint,
                                "component_id": component,
                                "repeat": repeat,
                                "outer_fold": outer_fold,
                                "inner_fold": "",
                                "scope": "outer",
                                "system_id": system,
                                "prediction": prediction,
                                "applicability_score": 1.0,
                                "model_id": f"model-{system}",
                                "feature_spec_id": "synthetic",
                                "split_id": "split",
                            }
                        )
                    inner_fold = molecule_index % 4
                    inner_truth.append(
                        {
                            **truth,
                            "observation_id": f"inner-{endpoint}-{repeat}-{outer_fold}-{inner_fold}-{molecule_index}",
                            "inner_fold": inner_fold,
                            "scope": "inner",
                        }
                    )
                    inner_rows.append(
                        {
                            "molecule_id": molecule,
                            "endpoint": endpoint,
                            "component_id": component,
                            "repeat": repeat,
                            "outer_fold": outer_fold,
                            "inner_fold": inner_fold,
                            "scope": "inner",
                            "system_id": r3b.MAPLIGHT,
                            "prediction": 0.05,
                            "applicability_score": 1.0,
                            "model_id": "inner-model",
                            "feature_spec_id": "synthetic",
                            "split_id": "split",
                        }
                    )
    outer_data = _csv(list(r3b.PRED_COLS), outer_rows)
    inner_data = _csv(list(r3b.PRED_COLS), inner_rows)
    outer_truth_data = _csv(list(r3b.TRUTH_COLS), outer_truth)
    inner_truth_data = _csv(list(r3b.TRUTH_COLS), inner_truth)
    outer_root = tmp_path / "outer"
    inner_root = tmp_path / "inner"
    sealed_root = tmp_path / "sealed"
    outer_root.mkdir()
    inner_root.mkdir()
    sealed_root.mkdir()
    authority = json.loads(
        (
            ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v4.json"
        ).read_text()
    )["authority"]["INHERITED_ONLY"]
    outer_parameters = [
        {
            "system_id": system,
            "canonical_get_all_params_json": {},
            "canonical_get_all_params_sha256": _sha(_json({})),
        }
        for system in (r3b.SYSTEMS[1], r3b.MAPLIGHT)
    ]
    inner_parameters = [outer_parameters[1]]
    freezer_accounting = {
        "cell_fragments_opened": 0,
        "target_files_opened": 0,
        "truth_files_opened": 0,
        "private_audit_files_opened": 0,
        "score_files_opened": 0,
        "tdi_files_opened": 0,
        "blinded_test_files_opened": 0,
        "episode_or_anchor_files_opened": 0,
        "submission_files_opened": 0,
        "transductive_operations": 0,
    }
    outer_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_outer_freeze.v2",
        "contract_sha256": r3b.V5_SHA256,
        "freezer_source_sha256": r3b._freezer_source_sha(),
        "preflight_receipt_sha256": "",
        "model_public_manifest_sha256": "",
        "feature_manifest_sha256": "",
        "cell_receipts": [""] * 60,
        "prediction_artifact": {
            "path": "global_oof_predictions.csv",
            "sha256": _sha(outer_data),
            "bytes": len(outer_data),
            "rows": len(outer_rows),
            "eligible_rows": len(outer_rows),
            "columns": list(r3b.PRED_COLS),
            "schema_version": "",
        },
        "counts": {
            "cell_receipts": 60,
            "prediction_rows": len(outer_rows),
            "systems": 4,
        },
        "resolved_catboost_parameters": outer_parameters,
        "accounting": {**freezer_accounting, "cell_fragments_opened": 60},
        "authority": authority,
    }
    inner_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_inner_freeze.v2",
        "contract_sha256": r3b.V5_SHA256,
        "freezer_source_sha256": r3b._freezer_source_sha(),
        "preflight_receipt_sha256": "",
        "model_public_manifest_sha256": "",
        "feature_manifest_sha256": "",
        "inner_selection_token_sha256": "",
        "cell_receipts": [""] * 240,
        "prediction_artifact": {
            "path": "global_inner_oof_predictions.csv",
            "sha256": _sha(inner_data),
            "bytes": len(inner_data),
            "rows": len(inner_rows),
            "eligible_rows": len(inner_rows),
            "columns": list(r3b.PRED_COLS),
            "schema_version": "",
        },
        "counts": {
            "cell_receipts": 240,
            "prediction_rows": len(inner_rows),
            "systems": 1,
        },
        "resolved_catboost_parameters": inner_parameters,
        "accounting": {**freezer_accounting, "cell_fragments_opened": 240},
        "authority": authority,
    }
    contexts = [
        (endpoint, repeat, outer_fold)
        for endpoint in r3b.ENDPOINTS
        for repeat in range(3)
        for outer_fold in range(5)
    ]
    preflight = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_preflight.v5",
        "contract_sha256": r3b.V5_SHA256,
        "model_public_manifest_sha256": "",
        "private_projection_audit_sha256": "",
        "checks": {
            "outer_score_support_cells": [
                {
                    "endpoint": endpoint,
                    "repeat": repeat,
                    "outer_fold": outer_fold,
                    "component_count": 10,
                    "minimum_components": 10,
                    "passes": True,
                }
                for endpoint, repeat, outer_fold in contexts
            ],
            "outer_training_populations": [
                {
                    "stage": "outer",
                    "endpoint": endpoint,
                    "repeat": repeat,
                    "outer_fold": outer_fold,
                    "inner_fold": "",
                    "eligible_targets": 1,
                    "minimum_eligible_targets": 1,
                    "passes": True,
                }
                for endpoint, repeat, outer_fold in contexts
            ],
            "inner_training_populations": [
                {
                    "stage": "inner",
                    "endpoint": endpoint,
                    "repeat": repeat,
                    "outer_fold": outer_fold,
                    "inner_fold": inner_fold,
                    "eligible_targets": 1,
                    "minimum_eligible_targets": 1,
                    "passes": True,
                }
                for endpoint, repeat, outer_fold in contexts
                for inner_fold in range(4)
            ],
            "q90_residual_eligibility_populations": [
                {
                    "endpoint": endpoint,
                    "repeat": repeat,
                    "outer_fold": outer_fold,
                    "eligible_residuals": 1,
                    "minimum_eligible_targets": 1,
                    "passes": True,
                }
                for endpoint, repeat, outer_fold in contexts
            ],
        },
        "passed": True,
        "failure_reasons": [],
        "accounting": {
            "preflight_target_files_opened": 300,
            "outer_model_target_files_opened": 0,
            "inner_model_target_files_opened": 0,
            "sealed_truth_files_opened": 0,
            "outer_model_fits": 0,
            "inner_model_fits": 0,
            "prediction_rows": 0,
            "provisional_metric_rows": 0,
            "tdi_files_opened": 0,
            "blinded_test_files_opened": 0,
            "episode_or_anchor_files_opened": 0,
            "official_metric_calls": 0,
            "submission_rows_opened": 0,
            "leaderboard_submissions": 0,
            "transductive_operations": 0,
            "gpu_fits": 0,
        },
        "authority": authority,
    }
    preflight_data = _json(preflight)
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_bytes(preflight_data)
    preflight_sha = _sha(preflight_data)
    outer_manifest["preflight_receipt_sha256"] = preflight_sha
    inner_manifest["preflight_receipt_sha256"] = preflight_sha
    _row(outer_root / "global_oof_predictions.csv", outer_data)
    outer_manifest_sha = _row(
        outer_root / "global_oof_freeze_manifest.json", _json(outer_manifest)
    )
    _row(inner_root / "global_inner_oof_predictions.csv", inner_data)
    inner_manifest_sha = _row(
        inner_root / "global_inner_oof_freeze_manifest.json", _json(inner_manifest)
    )
    sealed_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_sealed_truth.v5",
        "contract_sha256": r3b.V5_SHA256,
        "parent_contract_sha256": r3b.V4_SHA256,
        "projector_source_sha256": "",
        "outer_truth": {
            "path": "sealed_outer_truth.csv",
            "sha256": _sha(outer_truth_data),
            "rows": len(outer_truth),
            "eligible_rows": sum(
                row["point_eligible"] == "true" and row["value_state"] == "complete"
                for row in outer_truth
            ),
        },
        "inner_truth": {
            "path": "sealed_inner_truth.csv",
            "sha256": _sha(inner_truth_data),
            "rows": len(inner_truth),
            "eligible_rows": sum(
                row["point_eligible"] == "true" and row["value_state"] == "complete"
                for row in inner_truth
            ),
        },
        "accounting": {
            "sealed_truth_files_written": 2,
            "outer_truth_rows": len(outer_truth),
            "inner_truth_rows": len(inner_truth),
            "truth_metadata_public": 0,
            "tdi_files_opened": 0,
            "blinded_test_rows_opened": 0,
            "episode_or_anchor_files_opened": 0,
            "transductive_operations": 0,
        },
        "authority": authority,
    }
    _row(sealed_root / "sealed_outer_truth.csv", outer_truth_data)
    _row(sealed_root / "sealed_inner_truth.csv", inner_truth_data)
    sealed_manifest_sha = _row(
        sealed_root / "sealed_truth_manifest.json", _json(sealed_manifest)
    )
    return {
        "outer": outer_root,
        "inner": inner_root,
        "sealed": sealed_root,
        "outer_sha": outer_manifest_sha,
        "inner_sha": inner_manifest_sha,
        "sealed_sha": sealed_manifest_sha,
        "preflight": preflight_path,
        "preflight_sha": preflight_sha,
    }


def _bind_inner_token(fixture: dict[str, Path | str], stage: Any) -> str:
    stage_root = stage.root
    token_data = (stage_root / "inner_selection_token.json").read_bytes()
    manifest_path = Path(fixture["inner"]) / "global_inner_oof_freeze_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["inner_selection_token_sha256"] = _sha(token_data)
    manifest_data = _json(manifest)
    manifest_path.write_bytes(manifest_data)
    return _sha(manifest_data)


def _preflight_kwargs(fixture: dict[str, Path | str]) -> dict[str, object]:
    return {
        "preflight_receipt": fixture["preflight"],
        "preflight_receipt_sha256": fixture["preflight_sha"],
    }


def test_receipts_are_verified_before_json_parse_and_token_is_score_free(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(r3b.R3BScoringError, match="outer freeze manifest receipt"):
        r3b.score_outer(
            outer_root=fixture["outer"],
            sealed_root=fixture["sealed"],
            stage_root=tmp_path / "stage",
            outer_manifest_sha256="0" * 64,
            sealed_manifest_sha256=fixture["sealed_sha"],
            **_preflight_kwargs(fixture),
            synthetic=True,
        )
    stage = r3b.score_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        stage_root=tmp_path / "stage",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    token = json.loads((stage.root / "inner_selection_token.json").read_text())
    assert not r3b._forbidden(token)
    assert not any(
        name in token
        for name in ("score", "metric", "target", "comparison", "influence")
    )


def test_duplicate_manifest_json_is_rejected_before_schema_use(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    manifest = Path(fixture["outer"]) / "global_oof_freeze_manifest.json"
    duplicate = b'{"schema_version":"first","schema_version":"second"}\n'
    manifest.write_bytes(duplicate)
    with pytest.raises(r3b.R3BScoringError, match="duplicate JSON key"):
        r3b.score_outer(
            outer_root=fixture["outer"],
            sealed_root=fixture["sealed"],
            stage_root=tmp_path / "stage",
            outer_manifest_sha256=_sha(duplicate),
            sealed_manifest_sha256=fixture["sealed_sha"],
            **_preflight_kwargs(fixture),
            synthetic=True,
        )


def test_missing_inner_token_receipt_is_rejected_even_in_synthetic_mode(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    stage = r3b.score_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        stage_root=tmp_path / "stage",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    with pytest.raises(r3b.R3BScoringError, match="inner token receipt"):
        r3b.score_final(
            outer_stage_root=stage.root,
            inner_root=fixture["inner"],
            sealed_root=fixture["sealed"],
            output_root=tmp_path / "published",
            inner_manifest_sha256=fixture["inner_sha"],
            sealed_manifest_sha256=fixture["sealed_sha"],
            synthetic=True,
        )


def test_final_revalidates_private_preflight_receipt(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    stage = r3b.score_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        stage_root=tmp_path / "stage",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    _bind_inner_token(fixture, stage)
    stage.root.chmod(0o755)
    (stage.root / "preflight_receipt.json").chmod(0o644)
    (stage.root / "preflight_receipt.json").unlink()
    stage.root.chmod(0o555)
    with pytest.raises(r3b.R3BScoringError, match="preflight receipt"):
        r3b.score_final(
            outer_stage_root=stage.root,
            inner_root=fixture["inner"],
            sealed_root=fixture["sealed"],
            output_root=tmp_path / "published",
            inner_manifest_sha256=_sha(
                Path(fixture["inner"])
                .joinpath("global_inner_oof_freeze_manifest.json")
                .read_bytes()
            ),
            sealed_manifest_sha256=fixture["sealed_sha"],
            synthetic=True,
        )


def test_freezer_object_parameters_and_source_authority_are_bound(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    outer_manifest_path = Path(fixture["outer"]) / "global_oof_freeze_manifest.json"
    outer_manifest = json.loads(outer_manifest_path.read_text())
    assert isinstance(
        outer_manifest["resolved_catboost_parameters"][0][
            "canonical_get_all_params_json"
        ],
        dict,
    )
    outer_manifest["freezer_source_sha256"] = "0" * 64
    bad = _json(outer_manifest)
    outer_manifest_path.write_bytes(bad)
    with pytest.raises(r3b.R3BScoringError, match="freezer source"):
        r3b._load_freeze(fixture["outer"], _sha(bad), "outer", r3b.V5_SHA256, True)


def test_freezer_authority_bytes_must_be_exact_inherited_only(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    path = Path(fixture["outer"]) / "global_oof_freeze_manifest.json"
    manifest = json.loads(path.read_text())
    manifest["authority"]["global_model"] = True
    data = _json(manifest)
    path.write_bytes(data)
    with pytest.raises(r3b.R3BScoringError, match="authority"):
        r3b._load_freeze(fixture["outer"], _sha(data), "outer", r3b.V5_SHA256, True)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda artifact: artifact.update(bytes=artifact["bytes"] + 1), "byte count"),
        (lambda artifact: artifact.update(columns=list(r3b.PRED_COLS[:-1])), "schema"),
        (lambda artifact: artifact.update(extra="denied"), "fields"),
        (
            lambda artifact: artifact.update(
                eligible_rows=artifact["eligible_rows"] - 1
            ),
            "eligible count",
        ),
    ],
)
def test_prediction_receipt_metadata_is_exact(
    tmp_path: Path, mutation: Callable[[dict[str, object]], None], message: str
) -> None:
    fixture = _fixture(tmp_path)
    manifest_path = Path(fixture["outer"]) / "global_oof_freeze_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    mutation(cast(dict[str, object], manifest["prediction_artifact"]))
    data = _json(manifest)
    manifest_path.write_bytes(data)
    with pytest.raises(r3b.R3BScoringError, match=message):
        r3b._load_freeze(fixture["outer"], _sha(data), "outer", r3b.V5_SHA256, True)


def test_synthetic_freeze_counts_and_accounting_are_exact(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    manifest_path = Path(fixture["outer"]) / "global_oof_freeze_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["counts"]["prediction_rows"] += 1
    data = _json(manifest)
    manifest_path.write_bytes(data)
    with pytest.raises(r3b.R3BScoringError, match="prediction count"):
        r3b._load_freeze(fixture["outer"], _sha(data), "outer", r3b.V5_SHA256, True)
    manifest["counts"]["prediction_rows"] -= 1
    manifest["accounting"]["cell_fragments_opened"] = 59
    data = _json(manifest)
    manifest_path.write_bytes(data)
    with pytest.raises(r3b.R3BScoringError, match="accounting values"):
        r3b._load_freeze(fixture["outer"], _sha(data), "outer", r3b.V5_SHA256, True)


def test_truth_eligibility_and_accounting_are_recomputed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    manifest_path = Path(fixture["sealed"]) / "sealed_truth_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["outer_truth"]["eligible_rows"] -= 1
    data = _json(manifest)
    manifest_path.write_bytes(data)
    with pytest.raises(r3b.R3BScoringError, match="eligible count"):
        r3b._load_truth(
            fixture["sealed"], _sha(data), r3b.V5_SHA256, r3b.V4_SHA256, True, True
        )
    manifest["outer_truth"]["eligible_rows"] += 1
    manifest["accounting"]["outer_truth_rows"] += 1
    data = _json(manifest)
    manifest_path.write_bytes(data)
    with pytest.raises(r3b.R3BScoringError, match="accounting"):
        r3b._load_truth(
            fixture["sealed"], _sha(data), r3b.V5_SHA256, r3b.V4_SHA256, True, True
        )


def test_forbidden_firewall_scans_scalar_values_but_allows_catboost_keys() -> None:
    assert r3b._forbidden({"loss_function": "sealed_truth=/tmp/truth.csv"})
    assert r3b._forbidden({"nested": [{"path": "private_audit/score.json"}]})
    assert r3b._forbidden({"path": "privateAudit/results.json"})
    assert r3b._forbidden({"path": "private-audit/results.json"})
    assert not r3b._forbidden({"eval_metric": "RMSE"})
    assert not r3b._forbidden({"grow_policy": "SymmetricTree"})


def test_terminal_deep_compares_outer_and_inner_parameter_objects(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    stage = r3b.score_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        stage_root=tmp_path / "stage",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    inner_sha = _bind_inner_token(fixture, stage)
    inner_manifest_path = (
        Path(fixture["inner"]) / "global_inner_oof_freeze_manifest.json"
    )
    inner_manifest = json.loads(inner_manifest_path.read_text())
    changed = {"loss_function": "RMSE"}
    inner_manifest["resolved_catboost_parameters"][0][
        "canonical_get_all_params_json"
    ] = changed
    inner_manifest["resolved_catboost_parameters"][0][
        "canonical_get_all_params_sha256"
    ] = _sha(_json(changed))
    inner_data = _json(inner_manifest)
    inner_manifest_path.write_bytes(inner_data)
    with pytest.raises(r3b.R3BScoringError, match="parameter receipt"):
        r3b.score_final(
            outer_stage_root=stage.root,
            inner_root=fixture["inner"],
            sealed_root=fixture["sealed"],
            output_root=tmp_path / "published",
            inner_manifest_sha256=_sha(inner_data),
            sealed_manifest_sha256=fixture["sealed_sha"],
            synthetic=True,
        )
    assert inner_sha != _sha(inner_data)


def test_preflight_is_required_for_synthetic_scoring(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(r3b.R3BScoringError, match="validated preflight"):
        r3b.score_outer(
            outer_root=fixture["outer"],
            sealed_root=fixture["sealed"],
            stage_root=tmp_path / "stage",
            outer_manifest_sha256=fixture["outer_sha"],
            sealed_manifest_sha256=fixture["sealed_sha"],
            synthetic=True,
        )


def test_outer_macro_is_component_global_and_bootstrap_deterministic(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    first = r3b.score_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        stage_root=tmp_path / "stage1",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    first_bytes = (first.root / "global_bootstrap_summary.csv").read_bytes()
    second = r3b.score_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        stage_root=tmp_path / "stage2",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    assert first_bytes == (second.root / "global_bootstrap_summary.csv").read_bytes()
    assert first.status == "PASS"
    assert len((first.root / "global_cell_metrics.csv").read_text().splitlines()) == 241


def test_token_precedes_final_and_completion_uses_inner_truth(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    stage = r3b.score_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        stage_root=tmp_path / "stage",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    assert (stage.root / "inner_selection_token.json").is_file()
    inner_sha = _bind_inner_token(fixture, stage)
    output = r3b.score_final(
        outer_stage_root=stage.root,
        inner_root=fixture["inner"],
        sealed_root=fixture["sealed"],
        output_root=tmp_path / "published",
        inner_manifest_sha256=inner_sha,
        sealed_manifest_sha256=fixture["sealed_sha"],
        synthetic=True,
    )
    assert (output / "manifest.json").is_file()
    completion = (output / "parent_state_completion_outer_training.csv").read_text()
    assert "global_oof_completed" in completion
    assert (output / "parent_state_completion_final.csv").read_text().count(
        "global_oof_completed"
    ) > 0
    assert all(not path.stat().st_mode & 0o222 for path in output.rglob("*"))


def test_target_mutation_and_prediction_or_truth_drift_fail_without_partial_publish(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    target = Path(fixture["outer"]) / "global_oof_predictions.csv"
    original = target.read_bytes()
    target.write_bytes(original.replace(b"0.3", b"0.31", 1))
    destination = tmp_path / "published"
    with pytest.raises(r3b.R3BScoringError):
        r3b.score_outer(
            outer_root=fixture["outer"],
            sealed_root=fixture["sealed"],
            stage_root=tmp_path / "stage",
            outer_manifest_sha256=fixture["outer_sha"],
            sealed_manifest_sha256=fixture["sealed_sha"],
            **_preflight_kwargs(fixture),
            synthetic=True,
        )
    assert not destination.exists()


def test_destination_symlink_and_no_replace_race_are_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    stage = r3b.score_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        stage_root=tmp_path / "stage",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    destination = tmp_path / "published"
    destination.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(r3b.R3BScoringError):
        r3b.run_outer(
            outer_root=fixture["outer"],
            sealed_root=fixture["sealed"],
            stage_root=tmp_path / "stage-race",
            output_root=destination,
            outer_manifest_sha256=fixture["outer_sha"],
            sealed_manifest_sha256=fixture["sealed_sha"],
            **_preflight_kwargs(fixture),
            synthetic=True,
        )
    with pytest.raises(r3b.R3BScoringError):
        r3b.publish_no_advantage(
            outer_stage_root=stage.root, output_root=destination, synthetic=True
        )
    destination.unlink()
    destination.mkdir()
    sentinel = destination / "sentinel"
    sentinel.write_text("untouched")
    with pytest.raises(r3b.R3BScoringError):
        r3b.publish_no_advantage(
            outer_stage_root=stage.root, output_root=destination, synthetic=True
        )
    assert sentinel.read_text() == "untouched"


def test_q90_missing_residual_and_bootstrap_control_failure_are_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    inner_rows, _, _, _ = r3b._load_freeze(
        fixture["inner"], fixture["inner_sha"], "inner", r3b.V5_SHA256, True
    )
    inner_rows.pop(0)
    outer_rows, _, _, _ = r3b._load_freeze(
        fixture["outer"], fixture["outer_sha"], "outer", r3b.V5_SHA256, True
    )
    outer_truth_rows, _, _, _ = r3b._load_truth(
        fixture["sealed"],
        fixture["sealed_sha"],
        r3b.V5_SHA256,
        r3b.V4_SHA256,
        True,
        True,
    )
    outer_truth = r3b._truth_index(outer_truth_rows, False)
    inner_truth = r3b._truth_index(
        r3b._load_truth(
            fixture["sealed"],
            fixture["sealed_sha"],
            r3b.V5_SHA256,
            r3b.V4_SHA256,
            True,
            True,
        )[1],
        True,
    )
    with pytest.raises(r3b.R3BScoringError, match="residual population"):
        r3b._q90_completion(outer_rows, inner_rows, outer_truth, inner_truth, "0" * 64)
    aggregate = {
        system: {("CYP1A2", 0): {"component-0": 1.0}} for system in r3b.SYSTEMS
    }
    aggregate[r3b.SYSTEMS[1]][("CYP1A2", 0)] = {}
    with pytest.raises(r3b.R3BScoringError, match="bootstrap"):
        r3b._bootstrap(aggregate, accepted_target=1, maximum_attempts=1)


def test_q90_rejects_overlapping_inner_fold_partition(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    inner_rows, _, _, _ = r3b._load_freeze(
        fixture["inner"], fixture["inner_sha"], "inner", r3b.V5_SHA256, True
    )
    outer_rows, _, _, _ = r3b._load_freeze(
        fixture["outer"], fixture["outer_sha"], "outer", r3b.V5_SHA256, True
    )
    outer_truth_rows, inner_truth_rows, _, _ = r3b._load_truth(
        fixture["sealed"],
        fixture["sealed_sha"],
        r3b.V5_SHA256,
        r3b.V4_SHA256,
        True,
        True,
    )
    outer_truth = r3b._truth_index(outer_truth_rows, False)
    inner_truth = r3b._truth_index(inner_truth_rows, True)
    row = dict(inner_rows[0])
    alternate_fold = str((int(row["inner_fold"]) + 1) % 4)
    row["inner_fold"] = alternate_fold
    inner_rows.append(row)
    truth_key = (
        row["molecule_id"],
        row["endpoint"],
        row["repeat"],
        row["outer_fold"],
        alternate_fold,
    )
    source_key = next(key for key in inner_truth if key[:4] == truth_key[:4])
    inner_truth[truth_key] = dict(inner_truth[source_key], inner_fold=alternate_fold)
    with pytest.raises(r3b.R3BScoringError, match="partition"):
        r3b._q90_completion(outer_rows, inner_rows, outer_truth, inner_truth, "0" * 64)


def test_terminal_set_and_synthetic_authority_are_exact(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    stage = r3b.score_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        stage_root=tmp_path / "stage",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    contract = json.loads(
        (
            ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v4.json"
        ).read_text()
    )
    assert (
        json.loads((stage.root / "global_outer_assessment.json").read_text())[
            "authority"
        ]
        == contract["authority"]["INHERITED_ONLY"]
    )
    inner_sha = _bind_inner_token(fixture, stage)
    output = r3b.score_final(
        outer_stage_root=stage.root,
        inner_root=fixture["inner"],
        sealed_root=fixture["sealed"],
        output_root=tmp_path / "published",
        inner_manifest_sha256=inner_sha,
        sealed_manifest_sha256=fixture["sealed_sha"],
        synthetic=True,
    )
    expected = set(
        contract["publication"]["terminal_output_sets"]["GLOBAL_EXPERT_FROZEN"]
    )
    assert {
        path.relative_to(output).as_posix() for path in output.iterdir()
    } == expected | {"manifest.json"}
    result = json.loads((output / "global_result.json").read_text())
    assert result["authority"] == contract["authority"]["INHERITED_ONLY"]


def test_outer_no_advantage_promotes_and_pass_stays_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    terminal = sys.modules["r3b_scoring_terminal"]
    original = terminal._outer_metrics

    def no_advantage(*args: object, **kwargs: object) -> object:
        assessment, artifacts, _outcome = original(*args, **kwargs)
        assessment["outcome"] = "NO_ADVANTAGE"
        return assessment, artifacts, "NO_ADVANTAGE"

    monkeypatch.setattr(terminal, "_outer_metrics", no_advantage)
    output = r3b.run_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        output_root=tmp_path / "published",
        stage_root=tmp_path / "stage",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    assert (output / "global_result.json").is_file()
    assert json.loads((output / "global_result.json").read_text())["status"] == (
        "GLOBAL_NO_ADVANTAGE"
    )
    assert not (output / "inner_selection_token.json").exists()


def test_outer_and_final_defects_publish_stage_failure_receipts(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    outer_failure = r3b.run_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        output_root=tmp_path / "outer-failure",
        stage_root=tmp_path / "outer-stage",
        outer_manifest_sha256="0" * 64,
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    assert {path.name for path in outer_failure.iterdir()} == {"failure_receipt.json"}
    assert json.loads((outer_failure / "failure_receipt.json").read_text())[
        "stage"
    ] == ("outer_freeze")
    stage = r3b.score_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        stage_root=tmp_path / "stage",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    final_failure = r3b.run_final(
        outer_stage_root=stage.root,
        inner_root=fixture["inner"],
        sealed_root=fixture["sealed"],
        output_root=tmp_path / "final-failure",
        inner_manifest_sha256="0" * 64,
        sealed_manifest_sha256=fixture["sealed_sha"],
        synthetic=True,
    )
    assert {path.name for path in final_failure.iterdir()} == {"failure_receipt.json"}
    failure = json.loads((final_failure / "failure_receipt.json").read_text())
    assert failure["stage"] == "inner_freeze"
    assert failure["verified_input_receipts"]["preflight_receipt_sha256"]
    assert failure["implementation_source_receipts"]["terminal_writer"]
    assert failure["accounting"]["preflight_target_files_opened"] == 300


def test_inner_token_link_mismatch_is_recorded_as_inner_freeze(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    stage = r3b.score_outer(
        outer_root=fixture["outer"],
        sealed_root=fixture["sealed"],
        stage_root=tmp_path / "stage",
        outer_manifest_sha256=fixture["outer_sha"],
        sealed_manifest_sha256=fixture["sealed_sha"],
        **_preflight_kwargs(fixture),
        synthetic=True,
    )
    _bind_inner_token(fixture, stage)
    manifest_path = Path(fixture["inner"]) / "global_inner_oof_freeze_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["inner_selection_token_sha256"] = "0" * 64
    manifest_data = _json(manifest)
    manifest_path.write_bytes(manifest_data)
    output = r3b.run_final(
        outer_stage_root=stage.root,
        inner_root=fixture["inner"],
        sealed_root=fixture["sealed"],
        output_root=tmp_path / "published",
        inner_manifest_sha256=_sha(manifest_data),
        sealed_manifest_sha256=fixture["sealed_sha"],
        synthetic=True,
    )
    failure = json.loads((output / "failure_receipt.json").read_text())
    assert failure["stage"] == "inner_freeze"
    assert failure["implementation_source_receipts"]["freezer"]
    assert failure["accounting"]["inner_model_target_files_opened"] == 240


def test_preflight_clean_failure_publishes_underpowered_without_roots(
    tmp_path: Path,
) -> None:
    preflight = tmp_path / "preflight.json"
    authority = json.loads(
        (
            ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v4.json"
        ).read_text()
    )["authority"]["INHERITED_ONLY"]
    contexts = [
        (endpoint, repeat, outer_fold)
        for endpoint in r3b.ENDPOINTS
        for repeat in range(3)
        for outer_fold in range(5)
    ]
    checks = {
        "outer_score_support_cells": [
            {
                "endpoint": endpoint,
                "repeat": repeat,
                "outer_fold": outer_fold,
                "component_count": 0,
                "minimum_components": 10,
                "passes": False,
            }
            for endpoint, repeat, outer_fold in contexts
        ],
        "outer_training_populations": [
            {
                "stage": "outer",
                "endpoint": endpoint,
                "repeat": repeat,
                "outer_fold": outer_fold,
                "inner_fold": "",
                "eligible_targets": 1,
                "minimum_eligible_targets": 1,
                "passes": True,
            }
            for endpoint, repeat, outer_fold in contexts
        ],
        "inner_training_populations": [
            {
                "stage": "inner",
                "endpoint": endpoint,
                "repeat": repeat,
                "outer_fold": outer_fold,
                "inner_fold": inner_fold,
                "eligible_targets": 1,
                "minimum_eligible_targets": 1,
                "passes": True,
            }
            for endpoint, repeat, outer_fold in contexts
            for inner_fold in range(4)
        ],
        "q90_residual_eligibility_populations": [
            {
                "endpoint": endpoint,
                "repeat": repeat,
                "outer_fold": outer_fold,
                "eligible_residuals": 1,
                "minimum_eligible_targets": 1,
                "passes": True,
            }
            for endpoint, repeat, outer_fold in contexts
        ],
    }
    data = _json(
        {
            "schema_version": "cypshift.openadmet_cyp_2026.r3b_preflight.v5",
            "contract_sha256": r3b.V5_SHA256,
            "model_public_manifest_sha256": "",
            "private_projection_audit_sha256": "",
            "checks": checks,
            "passed": False,
            "failure_reasons": ["OUTER_COMPONENT_SUPPORT"],
            "accounting": {
                "preflight_target_files_opened": 300,
                "outer_model_target_files_opened": 0,
                "inner_model_target_files_opened": 0,
                "sealed_truth_files_opened": 0,
                "outer_model_fits": 0,
                "inner_model_fits": 0,
                "prediction_rows": 0,
                "provisional_metric_rows": 0,
                "tdi_files_opened": 0,
                "blinded_test_files_opened": 0,
                "episode_or_anchor_files_opened": 0,
                "official_metric_calls": 0,
                "submission_rows_opened": 0,
                "leaderboard_submissions": 0,
                "transductive_operations": 0,
                "gpu_fits": 0,
            },
            "authority": authority,
        }
    )
    preflight.write_bytes(data)
    output = r3b.run_outer(
        outer_root=tmp_path / "missing-outer",
        sealed_root=tmp_path / "missing-sealed",
        output_root=tmp_path / "published",
        stage_root=tmp_path / "stage",
        outer_manifest_sha256="0" * 64,
        sealed_manifest_sha256="0" * 64,
        preflight_receipt=preflight,
        preflight_receipt_sha256=_sha(data),
        synthetic=True,
    )
    assert {path.name for path in output.iterdir()} == {
        "global_result.json",
        "manifest.json",
    }
    assert (
        json.loads((output / "global_result.json").read_text())["status"]
        == "GLOBAL_UNDERPOWERED"
    )


def test_underpowered_publisher_has_no_verified_map_bypass(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    assert not hasattr(r3b, "publish_underpowered")
    terminal = sys.modules["r3b_scoring_terminal"]
    with pytest.raises(r3b.R3BScoringError, match="preflight passed"):
        terminal.publish_underpowered(
            output_root=tmp_path / "published",
            preflight_receipt=fixture["preflight"],
            preflight_receipt_sha256=fixture["preflight_sha"],
            synthetic=True,
        )
