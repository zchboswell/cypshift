from __future__ import annotations

import csv
import importlib
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).parents[1]
RESEARCH = ROOT / "research" / "maplight-fixed"
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
ACCEPTANCE_PATH = BENCHMARK / "global_v2_maplight_synthetic_acceptance.json"
ACCEPTANCE_SHA256 = "1a498f21dc227884b27476e9b753a03f984cac656548394fd440b65dc8a3a3bb"
sys.path.insert(0, str(RESEARCH))
runner = importlib.import_module("global_v2_maplight_runner")
synthetic = importlib.import_module("run_global_v2_maplight_synthetic")


def _fake_predictor(
    training: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], str]:
    assert training.shape[1] == prediction.shape[1] == 2563
    return (
        np.full(len(prediction), float(np.mean(targets)), dtype=np.float64),
        runner.PARAMETER_SHA256,
    )


def _compiler_sha() -> str:
    return runner.sha256_path(RESEARCH / "run_global_v2_maplight_synthetic.py")


def _compile(root: Path, *, reverse: bool = False) -> tuple[Path, Path]:
    return synthetic.compile_capabilities(
        root=root,
        reverse=reverse,
        expected_compiler_sha256=_compiler_sha(),
    )


def _make_writable(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts)):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(root, 0o755)
    yield root


def _reseal(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(root, 0o555)


def test_tracked_acceptance_binds_exact_sources_and_two_real_replays() -> None:
    acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    assert runner.sha256_path(ACCEPTANCE_PATH) == ACCEPTANCE_SHA256
    assert acceptance["status"] == "G2_2B_SYNTHETIC_RUNNER_ACCEPTED"
    assert acceptance["contract_sha256"] == runner.CONTRACT_SHA256
    assert acceptance["runner_source_sha256"] == runner.sha256_path(runner.SCRIPT)
    assert acceptance["compiler_source_sha256"] == runner.sha256_path(
        RESEARCH / "run_global_v2_maplight_synthetic.py"
    )
    assert acceptance["roots"] == 2
    assert acceptance["second_source_order_reversed"]
    assert acceptance["relative_byte_maps_identical"]
    assert acceptance["files_compared"] == 318
    assert acceptance["combined_tree_sha256"] == (
        "e81bfb922a0f8588d1e88c8b5c2edefbbe3455bd6caf677e66a5d3dcaf65de06"
    )
    assert acceptance["counts"]["outer_maplight_fits"] == 60
    assert acceptance["counts"]["inner_maplight_fits"] == 240
    assert (
        acceptance["roots"]
        * (
            acceptance["counts"]["outer_maplight_fits"]
            + acceptance["counts"]["inner_maplight_fits"]
        )
        == 600
    )
    assert not any(acceptance["authority"].values())
    assert all(
        acceptance["accounting"][name] == 0
        for name in (
            "official_target_values_opened",
            "official_features_opened",
            "official_model_fits",
            "official_predictions_generated",
            "official_metric_evaluations",
            "confirmatory_truth_values_opened",
            "historical_r3c_row_level_artifacts_opened",
            "blinded_test_files_opened",
            "tdi_files_opened",
            "submissions_created",
            "leaderboard_observations",
            "tutorial_ma_st_rae_calls",
        )
    )


def test_failed_and_rejected_synthetic_attempts_remain_auditable() -> None:
    blocker = json.loads(
        (BENCHMARK / "global_v2_maplight_synthetic_blocker.json").read_text(
            encoding="utf-8"
        )
    )
    assert blocker["status"] == "G2_2B_SYNTHETIC_BLOCKED"
    assert blocker["accounting"]["maplight_model_fits"] == 1
    assert blocker["accounting"]["prediction_roots_published"] == 0
    assert blocker["parameter_delta"] == {
        "subsample": {"expected": 0.800000011920929, "observed": 1}
    }

    rejection = json.loads(
        (BENCHMARK / "global_v2_maplight_synthetic_audit_rejection.json").read_text(
            encoding="utf-8"
        )
    )
    assert rejection["status"] == "G2_2B_SYNTHETIC_REJECTED"
    assert rejection["evidence_that_passed"]["fresh_roots"] == 2
    assert rejection["evidence_that_passed"]["maplight_fits_per_root"] == 300
    assert "did not explicitly enforce" in rejection["rejection"]
    assert rejection["accounting"]["official_model_fits"] == 0


def test_synthetic_compiler_emits_disjoint_receipt_bound_capabilities(
    tmp_path: Path,
) -> None:
    model, scorer = _compile(tmp_path / "replay")
    model_files = [path for path in model.rglob("*") if path.is_file()]
    scorer_files = [path for path in scorer.rglob("*") if path.is_file()]
    assert len(model_files) == 307
    assert len(list((model / "targets").rglob("*.csv"))) == 300
    assert {path.name for path in scorer_files} == {"truth.csv", "manifest.json"}
    assert not any(path.name == "truth.csv" for path in model_files)
    assert not any("target" in path.name for path in scorer_files)

    manifest = json.loads((model / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["target_capabilities"] == {
        "files": 300,
        "training_rows": 38400,
        "outer_validation_truth_rows": 0,
        "inner_validation_truth_rows": 0,
    }
    assert manifest["components"] == 100
    assert manifest["authority"] == runner.DENIED_AUTHORITY
    assert all(not path.stat().st_mode & 0o222 for path in model.rglob("*"))
    assert all(not path.stat().st_mode & 0o222 for path in scorer.rglob("*"))


def test_fake_prediction_and_scorer_path_is_exactly_cross_fitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, scorer = _compile(tmp_path / "replay")
    calls: list[tuple[int, int, int]] = []

    def observed(
        training: np.ndarray[Any, Any],
        targets: np.ndarray[Any, Any],
        prediction: np.ndarray[Any, Any],
    ) -> tuple[np.ndarray[Any, Any], str]:
        calls.append((len(training), len(targets), len(prediction)))
        return _fake_predictor(training, targets, prediction)

    predictions = runner._run_predictions(
        model_capability_root=model,
        output_root=tmp_path / "replay" / "predictions",
        predictor=observed,
        runtime={"synthetic_test": "fake"},
    )
    terminal = runner.score_predictions(
        prediction_root=predictions,
        scorer_capability_root=scorer,
        output_root=tmp_path / "replay" / "terminal",
    )
    assert len(calls) == 300
    assert calls[:60] == [(160, 160, 40)] * 60
    assert calls[60:] == [(120, 120, 40)] * 240

    receipt = json.loads((terminal / "manifest.json").read_text(encoding="utf-8"))
    assert receipt["counts"] == {
        "molecules": 200,
        "outer_maplight_fits": 60,
        "inner_maplight_fits": 240,
        "outer_prediction_rows": 2400,
        "inner_prediction_rows": 9600,
        "residual_rows": 2400,
        "uncertainty_rows": 2400,
        "component_metric_rows": 60,
        "q90_contexts": 60,
    }
    accounting = receipt["accounting"]
    assert accounting["maplight_model_fits"] == 300
    assert accounting["outer_truth_values_opened_by_model"] == 0
    assert accounting["inner_truth_values_opened_by_model"] == 0
    assert accounting["scorer_truth_values_opened_after_prediction_freeze"] == 800
    assert accounting["residual_values_computed"] == 12000
    assert accounting["tutorial_ma_st_rae_calls"] == 0
    assert all(
        accounting[name] == 0
        for name in (
            "official_target_values_opened",
            "official_features_opened",
            "official_model_fits",
            "official_predictions_generated",
            "official_metric_evaluations",
            "confirmatory_truth_values_opened",
            "historical_r3c_row_level_artifacts_opened",
            "blinded_test_files_opened",
            "tdi_files_opened",
            "submissions_created",
            "leaderboard_observations",
        )
    )


def test_reversed_source_order_replays_all_evidence_bytes(tmp_path: Path) -> None:
    maps = []
    for name, reverse in (("a", False), ("b", True)):
        root = tmp_path / name
        model, scorer = _compile(root, reverse=reverse)
        predictions = runner._run_predictions(
            model_capability_root=model,
            output_root=root / "predictions",
            predictor=_fake_predictor,
            runtime={"synthetic_test": "fake"},
        )
        runner.score_predictions(
            prediction_root=predictions,
            scorer_capability_root=scorer,
            output_root=root / "terminal",
        )
        maps.append(synthetic._tree_maps(root))
    assert maps[0] == maps[1]


def test_component_equal_q90_is_deterministic_and_does_not_interpolate() -> None:
    component_a = "a" * 64
    component_b = "b" * 64
    assert (
        runner._weighted_q90(
            [
                (1.0, component_a, "molecule-a1"),
                (3.0, component_a, "molecule-a2"),
                (2.0, component_b, "molecule-b1"),
            ]
        )
        == 3.0
    )
    with pytest.raises(runner.GlobalV2MapLightError, match="empty"):
        runner._weighted_q90([])
    with pytest.raises(runner.GlobalV2MapLightError, match="invalid"):
        runner._weighted_q90([(float("nan"), component_a, "molecule-a")])


def test_training_value_tamper_fails_before_any_fit(tmp_path: Path) -> None:
    model, _scorer = _compile(tmp_path / "replay")
    target = next((model / "targets").rglob("*.csv"))
    list(_make_writable(model))
    rows = list(csv.DictReader(target.read_text(encoding="utf-8").splitlines()))
    rows[0]["point"] = "999"
    target.write_bytes(runner.csv_bytes(runner.TARGET_COLUMNS, rows))
    _reseal(model)

    calls = 0

    def forbidden(*_args: object) -> tuple[np.ndarray[Any, Any], str]:
        nonlocal calls
        calls += 1
        raise AssertionError("fit should not execute")

    with pytest.raises(runner.GlobalV2MapLightError, match="target tree receipt"):
        runner._run_predictions(
            model_capability_root=model,
            output_root=tmp_path / "predictions",
            predictor=forbidden,
            runtime={"synthetic_test": "fake"},
        )
    assert calls == 0


def test_inner_component_split_fails_before_any_fit(tmp_path: Path) -> None:
    model, _scorer = _compile(tmp_path / "replay")
    list(_make_writable(model))
    folds_path = model / "folds.csv"
    folds = list(csv.DictReader(folds_path.read_text(encoding="utf-8").splitlines()))
    first = next(
        row
        for row in folds
        if row["repeat"] == "0"
        and row["outer_validation_fold"] == "0"
        and row["outer_fold"] != "0"
    )
    peer = next(
        row
        for row in folds
        if row is not first
        and row["similarity_component_hash"] == first["similarity_component_hash"]
        and row["repeat"] == first["repeat"]
        and row["outer_validation_fold"] == first["outer_validation_fold"]
    )
    peer["inner_fold"] = str((int(first["inner_fold"]) + 1) % 4)
    fold_bytes = runner.csv_bytes(runner.FOLD_COLUMNS, folds)
    folds_path.write_bytes(fold_bytes)
    manifest_path = model / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["folds_sha256"] = runner.sha256_bytes(fold_bytes)
    manifest_path.write_bytes(runner.json_bytes(manifest))
    _reseal(model)

    with pytest.raises(runner.GlobalV2MapLightError, match="crosses an inner fold"):
        runner._run_predictions(
            model_capability_root=model,
            output_root=tmp_path / "predictions",
            predictor=_fake_predictor,
            runtime={"synthetic_test": "fake"},
        )


def test_symlink_writable_prediction_and_overwrite_fail_closed(tmp_path: Path) -> None:
    model, scorer = _compile(tmp_path / "replay")
    predictions = runner._run_predictions(
        model_capability_root=model,
        output_root=tmp_path / "replay" / "predictions",
        predictor=_fake_predictor,
        runtime={"synthetic_test": "fake"},
    )
    with pytest.raises(runner.GlobalV2MapLightError, match="destination exists"):
        runner._run_predictions(
            model_capability_root=model,
            output_root=predictions,
            predictor=_fake_predictor,
            runtime={"synthetic_test": "fake"},
        )

    os.chmod(predictions, 0o755)
    with pytest.raises(
        runner.GlobalV2MapLightError, match="prediction root is writable"
    ):
        runner.score_predictions(
            prediction_root=predictions,
            scorer_capability_root=scorer,
            output_root=tmp_path / "terminal",
        )

    symlink = tmp_path / "symlink-model"
    symlink.symlink_to(model, target_is_directory=True)
    with pytest.raises(runner.GlobalV2MapLightError, match="not a directory"):
        runner._run_predictions(
            model_capability_root=symlink,
            output_root=tmp_path / "other-predictions",
            predictor=_fake_predictor,
            runtime={"synthetic_test": "fake"},
        )


def test_acceptance_rejects_nonidentical_and_same_roots(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    for root, reverse in ((root_a, False), (root_b, True)):
        model, scorer = _compile(root, reverse=reverse)
        predictions = runner._run_predictions(
            model_capability_root=model,
            output_root=root / "predictions",
            predictor=_fake_predictor,
            runtime={"synthetic_test": "fake"},
        )
        runner.score_predictions(
            prediction_root=predictions,
            scorer_capability_root=scorer,
            output_root=root / "terminal",
        )
    with pytest.raises(runner.GlobalV2MapLightError, match="not distinct"):
        synthetic.accept_replays(
            root_a=root_a,
            root_b=root_a,
            output_root=tmp_path / "accept-same",
            expected_compiler_sha256=_compiler_sha(),
            expected_runner_sha256=runner.sha256_path(runner.SCRIPT),
        )

    terminal = root_b / "terminal"
    list(_make_writable(terminal))
    manifest = terminal / "manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b"\n")
    _reseal(terminal)
    with pytest.raises(runner.GlobalV2MapLightError, match="byte maps differ"):
        synthetic.accept_replays(
            root_a=root_a,
            root_b=root_b,
            output_root=tmp_path / "accept-different",
            expected_compiler_sha256=_compiler_sha(),
            expected_runner_sha256=runner.sha256_path(runner.SCRIPT),
        )
