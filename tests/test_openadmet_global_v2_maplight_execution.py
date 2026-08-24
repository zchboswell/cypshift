from __future__ import annotations

import importlib
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).parents[1]
RESEARCH = ROOT / "research" / "maplight-fixed"
sys.path.insert(0, str(RESEARCH))
runner = importlib.import_module("global_v2_maplight_runner")
compiler = importlib.import_module("global_v2_maplight_execution_compiler")
wrapper = importlib.import_module("global_v2_maplight_execution_wrapper")
synthetic = importlib.import_module("run_global_v2_maplight_execution_synthetic")


def _fake_predictor(
    training: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], str]:
    assert training.shape[1] == prediction.shape[1] == 2563
    assert len(training) == len(targets)
    return (
        np.full(len(prediction), float(np.mean(targets)), dtype=np.float64),
        runner.PARAMETER_SHA256,
    )


@contextmanager
def _make_writable(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts)):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(root, 0o755)
    yield root


def _reseal(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(root, 0o555)


def _compile(
    tmp_path: Path, *, reverse: bool = False
) -> tuple[Path, Path, dict[str, object]]:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=reverse)
    return compiler.compile_capabilities(
        source_root=source,
        output_root=tmp_path / "compiled",
        expected_compiler_sha256=runner.sha256_path(compiler.SCRIPT),
    )


def _fake_terminal(tmp_path: Path, *, reverse: bool = False) -> Path:
    model, scorer, _preflight = _compile(tmp_path, reverse=reverse)
    predictions = wrapper._run_predictions(
        model_capability_root=model,
        output_root=tmp_path / "predictions",
        predictor=_fake_predictor,
        runtime={"synthetic_test": "fake"},
    )
    return wrapper.score_predictions(
        prediction_root=predictions,
        scorer_capability_root=scorer,
        output_root=tmp_path / "terminal",
    )


def test_compiler_binds_exact_contract_and_accepted_runner() -> None:
    assert runner.sha256_path(compiler.EXECUTION_CONTRACT) == (
        compiler.EXECUTION_CONTRACT_SHA256
    )
    contract = json.loads(compiler.EXECUTION_CONTRACT.read_text(encoding="utf-8"))
    assert contract["accepted_implementation"]["runner_sha256"] == (
        runner.sha256_path(runner.SCRIPT)
    )
    assert contract["population_and_preflight"]["minimum_support"] == {
        "development_finite_targets_per_endpoint": 750,
        "outer_validation_targets_per_endpoint_repeat_fold": 75,
        "inner_training_targets_per_endpoint_repeat_outer_inner": 400,
    }


def test_tracked_acceptance_derives_exact_private_claim_without_consuming_template() -> (
    None
):
    assert runner.sha256_path(wrapper.TRACKED_ACCEPTANCE) == (
        "c57845989a29208f240151ab1b585f64f737b82f008dd2b7df62fd9764e50fa5"
    )
    before = compiler.TRACKED_CLAIM.read_bytes()
    consumed = wrapper.derive_consumed_claim(
        tracked_claim_path=compiler.TRACKED_CLAIM,
        acceptance_path=wrapper.TRACKED_ACCEPTANCE,
    )
    assert consumed["status"] == "G2_2C_CLAIM_CONSUMED"
    assert consumed["future_official_compiler_source_sha256"] == (
        "67fb59abcb7062c896306832ab1241200e653723c5346f3c0ae99bd82abc3d75"
    )
    assert consumed["future_attempt_wrapper_source_sha256"] == (
        "3d161a438df2fabe822c3e6d321f95b5690f3e3461087632d8cc8b53bbe3ac52"
    )
    assert consumed["future_official_shaped_synthetic_acceptance_sha256"] == (
        "c57845989a29208f240151ab1b585f64f737b82f008dd2b7df62fd9764e50fa5"
    )
    assert consumed["maximum_consumptions"] == 1
    assert compiler.TRACKED_CLAIM.read_bytes() == before
    assert runner.sha256_path(compiler.TRACKED_CLAIM) == compiler.TRACKED_CLAIM_SHA256


def test_official_authority_is_scoped_to_completed_stage() -> None:
    capability = wrapper._authority(False, "capability")
    prediction = wrapper._authority(False, "prediction")
    terminal = wrapper._authority(False, "terminal")
    assert capability["official_target_access"] is True
    assert capability["official_model_fitting"] is False
    assert prediction["official_model_fitting"] is True
    assert prediction["official_prediction_generation"] is True
    assert "official_residual_or_diagnostic_computation" not in prediction
    assert terminal["official_residual_or_diagnostic_computation"] is True


def test_official_source_builder_binds_exact_claim_parents_and_leaves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = synthetic.publish_source(root=tmp_path / "fixture", reverse=False)
    r2b_manifest = runner.json_bytes({"synthetic_parent": "r2b"})
    r3a_manifest = runner.json_bytes({"synthetic_parent": "r3a"})
    r2b = runner.publish_files(
        tmp_path / "r2b",
        {
            "manifest.json": r2b_manifest,
            "direct_observations.csv": (
                fixture / "direct_observations.csv"
            ).read_bytes(),
            "group_folds.csv": (fixture / "group_folds.csv").read_bytes(),
        },
    )
    r3a_files = {
        name: (fixture / name).read_bytes()
        for name in (
            "feature_rows.csv",
            "maplight_morgan_count.npy",
            "maplight_avalon_count.npy",
            "maplight_erg.npy",
            "maplight_rdkit_descriptors.npy",
        )
    }
    r3a = runner.publish_files(
        tmp_path / "r3a", {"manifest.json": r3a_manifest, **r3a_files}
    )
    acceptance_root = runner.publish_files(
        tmp_path / "tracked-acceptance", {"acceptance.json": b"{}\n"}
    )
    acceptance_path = acceptance_root / "acceptance.json"
    template = json.loads(compiler.TRACKED_CLAIM.read_text(encoding="utf-8"))
    receipts = dict(template["official_input_receipts"])
    receipts.update(
        {
            "r2b_manifest_sha256": runner.sha256_bytes(r2b_manifest),
            "r3a_feature_manifest_sha256": runner.sha256_bytes(r3a_manifest),
            "direct_observations_sha256": runner.sha256_path(
                fixture / "direct_observations.csv"
            ),
            "group_folds_sha256": runner.sha256_path(fixture / "group_folds.csv"),
            "feature_rows_sha256": runner.sha256_path(fixture / "feature_rows.csv"),
            "maplight_morgan_count_sha256": runner.sha256_path(
                fixture / "maplight_morgan_count.npy"
            ),
            "maplight_avalon_count_sha256": runner.sha256_path(
                fixture / "maplight_avalon_count.npy"
            ),
            "maplight_erg_sha256": runner.sha256_path(fixture / "maplight_erg.npy"),
            "maplight_rdkit_descriptors_sha256": runner.sha256_path(
                fixture / "maplight_rdkit_descriptors.npy"
            ),
        }
    )
    template["official_input_receipts"] = receipts
    tracked_root = runner.publish_files(
        tmp_path / "tracked-claim",
        {"claim.json": runner.json_bytes(template)},
    )
    tracked_path = tracked_root / "claim.json"
    monkeypatch.setattr(compiler, "TRACKED_CLAIM", tracked_path)
    monkeypatch.setattr(
        compiler, "TRACKED_CLAIM_SHA256", runner.sha256_path(tracked_path)
    )
    monkeypatch.setattr(compiler, "TRACKED_ACCEPTANCE", acceptance_path)
    output = tmp_path / "official-source"
    monkeypatch.setattr(compiler, "OFFICIAL_SOURCE_ROOT", output)
    consumed = dict(template)
    consumed.update(
        {
            "status": "G2_2C_CLAIM_CONSUMED",
            "future_official_compiler_source_sha256": runner.sha256_path(
                compiler.SCRIPT
            ),
            "future_attempt_wrapper_source_sha256": runner.sha256_path(wrapper.SCRIPT),
            "future_official_shaped_synthetic_acceptance_sha256": runner.sha256_path(
                acceptance_path
            ),
        }
    )
    result = compiler.publish_official_source(
        r2b_root=r2b,
        r3a_root=r3a,
        output_root=output,
        consumed_claim=consumed,
        expected_compiler_sha256=runner.sha256_path(compiler.SCRIPT),
    )
    manifest = json.loads((result / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_receipts"] == {
        name: receipts[key] for name, key in compiler.OFFICIAL_RECEIPT_KEYS.items()
    }
    assert manifest["parent_receipts"] == {
        name: receipts[key]
        for name, key in compiler.OFFICIAL_PARENT_RECEIPT_KEYS.items()
    }
    assert (
        compiler.authenticate_official_source(
            source_root=result,
            consumed_claim=consumed,
            expected_compiler_sha256=runner.sha256_path(compiler.SCRIPT),
        )
        == receipts
    )


def test_compiler_keeps_confirmatory_suffixes_opaque_and_capabilities_disjoint(
    tmp_path: Path,
) -> None:
    model, scorer, preflight = _compile(tmp_path)
    model_manifest = json.loads((model / "manifest.json").read_text(encoding="utf-8"))
    scorer_manifest = json.loads((scorer / "manifest.json").read_text(encoding="utf-8"))
    assert preflight["status"] == "G2_2C_PREFLIGHT_PASS"
    assert model_manifest["accounting"]["confirmatory_target_values_parsed"] == 0
    assert model_manifest["accounting"]["confirmatory_rows_kept_opaque"] > 0
    assert model_manifest["target_capabilities"]["files"] == 300
    assert len(list((model / "targets").rglob("*.csv"))) == 300
    assert not (model / "truth.csv").exists()
    assert model_manifest["official_source_receipts"] == {}
    assert {path.name for path in scorer.iterdir()} == {"truth.csv", "manifest.json"}
    assert scorer_manifest["model_training_files"] == 0
    assert scorer_manifest["feature_arrays"] == 0
    assert scorer_manifest["confirmatory_truth_values"] == 0
    assert scorer_manifest["official_source_receipts"] == {}
    for accounting in (model_manifest["accounting"], scorer_manifest["accounting"]):
        assert accounting["official_model_fits"] == 0
        assert accounting["official_predictions_generated"] == 0
        assert accounting["official_residual_values_computed"] == 0
        assert accounting["official_diagnostics_computed"] == 0
        assert accounting["official_metric_evaluations"] == 0
        assert accounting["external_records_acquired"] == 0
        assert accounting["live_uploads"] == 0
    assert not any(model_manifest["authority"].values())
    assert not any(scorer_manifest["authority"].values())


def test_reverse_physical_source_order_compiles_to_identical_capabilities(
    tmp_path: Path,
) -> None:
    compiled = []
    for name, reverse in (("a", False), ("b", True)):
        model, scorer, _preflight = _compile(tmp_path / name, reverse=reverse)
        compiled.append(
            {
                "model": runner.relative_byte_map(model),
                "scorer": runner.relative_byte_map(scorer),
                "preflight": runner.relative_byte_map(model.parent / "preflight"),
            }
        )
    assert compiled[0] == compiled[1]


def test_sparse_fake_prediction_and_scoring_is_exactly_cross_fitted(
    tmp_path: Path,
) -> None:
    terminal = _fake_terminal(tmp_path)
    manifest = json.loads((terminal / "manifest.json").read_text(encoding="utf-8"))
    counts = manifest["counts"]
    assert counts["outer_maplight_fits"] == 60
    assert counts["inner_maplight_fits"] == 240
    assert counts["outer_prediction_rows"] == counts["molecules"] * 4 * 3
    assert counts["inner_prediction_rows"] == counts["molecules"] * 4 * 3 * 4
    assert counts["finite_truth_rows"] < counts["molecules"] * 4
    assert counts["residual_rows"] == counts["finite_truth_rows"] * 3
    assert manifest["accounting"]["residual_values_computed"] == (
        counts["finite_truth_rows"] * (3 + 12)
    )
    assert counts["q90_contexts"] == 60
    assert counts["component_metric_rows"] == 60
    assert manifest["accounting"]["external_records_acquired"] == 0
    assert manifest["accounting"]["live_uploads"] == 0
    assert manifest["source_receipts"].keys() == {
        "model_capability_manifest_sha256",
        "scorer_capability_manifest_sha256",
    }
    assert not any(manifest["authority"].values())


def test_reverse_sparse_fake_replays_have_identical_terminal_bytes(
    tmp_path: Path,
) -> None:
    terminal_a = _fake_terminal(tmp_path / "a", reverse=False)
    terminal_b = _fake_terminal(tmp_path / "b", reverse=True)
    assert runner.relative_byte_map(terminal_a) == runner.relative_byte_map(terminal_b)


def test_model_loader_rejects_inner_family_split_tamper(tmp_path: Path) -> None:
    model, _scorer, _preflight = _compile(tmp_path)
    with _make_writable(model):
        rows = runner._read_csv(model / "folds.csv", runner.FOLD_COLUMNS)
        first = next(row for row in rows if row["inner_fold"] != "")
        component = first["similarity_component_hash"]
        candidates = [
            row
            for row in rows
            if row["similarity_component_hash"] == component
            and row["repeat"] == first["repeat"]
            and row["outer_validation_fold"] == first["outer_validation_fold"]
            and row["inner_fold"] != ""
        ]
        assert len(candidates) == 2
        candidates[0]["inner_fold"] = str((int(candidates[0]["inner_fold"]) + 1) % 4)
        (model / "folds.csv").write_bytes(runner.csv_bytes(runner.FOLD_COLUMNS, rows))
        manifest = json.loads((model / "manifest.json").read_text(encoding="utf-8"))
        manifest["folds_sha256"] = runner.sha256_path(model / "folds.csv")
        (model / "manifest.json").write_bytes(runner.json_bytes(manifest))
    _reseal(model)
    with pytest.raises(wrapper.MapLightExecutionWrapperError, match="inner fold"):
        wrapper._run_predictions(
            model_capability_root=model,
            output_root=tmp_path / "predictions",
            predictor=_fake_predictor,
            runtime={"synthetic_test": "fake"},
        )


def test_scorer_rejects_forged_prediction_identity(tmp_path: Path) -> None:
    model, scorer, _preflight = _compile(tmp_path)
    predictions = wrapper._run_predictions(
        model_capability_root=model,
        output_root=tmp_path / "predictions",
        predictor=_fake_predictor,
        runtime={"synthetic_test": "fake"},
    )
    with _make_writable(predictions):
        rows = runner._read_csv(
            predictions / "development_outer_oof.csv", runner.OUTER_COLUMNS
        )
        rows[0]["model_id"] = "0" * 64
        (predictions / "development_outer_oof.csv").write_bytes(
            runner.csv_bytes(runner.OUTER_COLUMNS, rows)
        )
        manifest = json.loads(
            (predictions / "manifest.json").read_text(encoding="utf-8")
        )
        manifest["output_receipts"]["development_outer_oof.csv"] = runner.sha256_path(
            predictions / "development_outer_oof.csv"
        )
        (predictions / "manifest.json").write_bytes(runner.json_bytes(manifest))
    _reseal(predictions)
    with pytest.raises(
        wrapper.MapLightExecutionWrapperError, match="outer prediction identity"
    ):
        wrapper.score_predictions(
            prediction_root=predictions,
            scorer_capability_root=scorer,
            output_root=tmp_path / "terminal",
        )


def test_wrong_compiler_receipt_fails_before_source_parse(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    with pytest.raises(
        compiler.MapLightExecutionCompilerError, match="compiler source"
    ):
        compiler.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "compiled",
            expected_compiler_sha256="0" * 64,
        )
    assert not (tmp_path / "compiled").exists()


def test_tracked_unconsumed_claim_cannot_open_official_source(tmp_path: Path) -> None:
    with pytest.raises(compiler.MapLightExecutionCompilerError, match="consumed claim"):
        compiler.compile_capabilities(
            source_root=tmp_path / "official-source-must-not-open",
            output_root=tmp_path / "compiled",
            expected_compiler_sha256=runner.sha256_path(compiler.SCRIPT),
            mode="official",
            consumed_claim_path=compiler.TRACKED_CLAIM,
        )
    assert not (tmp_path / "official-source-must-not-open").exists()
    assert not (tmp_path / "compiled").exists()
