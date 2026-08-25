from __future__ import annotations

import csv
import importlib
import io
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).parents[1]
RESEARCH = ROOT / "research" / "lightgbm-global"
sys.path.insert(0, str(RESEARCH))
g3 = importlib.import_module("g3_runner")
compiler = importlib.import_module("g3_execution_compiler")
wrapper = importlib.import_module("g3_execution_wrapper")
synthetic = importlib.import_module("run_g3_execution_synthetic")


def _rows(value: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(value.decode(), newline="")))


def _tree_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): g3.sha256_path(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _source_and_baseline(
    root: Path, *, reverse: bool = False
) -> tuple[Path, Path, dict[str, str]]:
    source, features, folds = synthetic.publish_source(
        root=root / "source", reverse=reverse
    )
    baseline, receipts = synthetic.publish_baseline(
        root=root / "baseline", features=features, folds=folds
    )
    return source, baseline, receipts


def _compile(root: Path, *, reverse: bool = False):  # type: ignore[no-untyped-def]
    source, baseline, receipts = _source_and_baseline(root, reverse=reverse)
    return compiler.compile_capabilities(
        source_root=source,
        baseline_terminal_root=baseline,
        output_root=root / "capabilities",
        expected_compiler_sha256=g3.sha256_path(compiler.SCRIPT),
        mode="synthetic",
        synthetic_baseline_receipts=receipts,
    )


def test_exact_parent_contract_and_unconsumed_claim_are_bound() -> None:
    assert g3.sha256_path(compiler.EXECUTION_CONTRACT) == (
        "be9dccf0e1c83aa626550bcabd14dceb12e5f466306f82af7a211b7a28f87e57"
    )
    assert g3.sha256_path(compiler.TRACKED_CLAIM) == (
        "71fc023160b5d9da6c620f246ff134ea2e790159bfb675aac33aa4a6c3025f9b"
    )
    claim = compiler._load_json(compiler.TRACKED_CLAIM)
    assert claim["status"] == "G2_6T_G3_CLAIM_UNCONSUMED"
    assert all(claim[name] is None for name in compiler.FUTURE_FIELDS)
    assert g3.sha256_path(g3.SCRIPT) == (
        "a639c2f21022b79ebcfbe5187190cd5bf6698628e29d8a364873200118db3415"
    )


def test_official_shaped_source_has_exact_population_and_opaque_confirmatory() -> None:
    features, folds, direct, descriptors = synthetic.fixture(reverse=False)
    assert len(features) == 1200
    assert len(folds) == 18_000
    assert len(direct) == 4_800
    assert len({row["standardized_structure_hash"] for row in features}) == 1200
    assert len(descriptors) > 1_900_000
    confirmatory = [
        row
        for row in direct
        if compiler.is_confirmatory(str(row["similarity_component_hash"]))
    ]
    assert len(confirmatory) == 960
    assert all(
        row["point"] == "CONFIRMATORY_SENTINEL_MUST_REMAIN_OPAQUE"
        for row in confirmatory
    )


def test_compiler_reconstructs_exact_nan_preserving_capabilities(
    tmp_path: Path,
) -> None:
    model, scorer, preflight = _compile(tmp_path)
    assert preflight["status"] == "G2_6T_G3_PREFLIGHT_PASS"
    assert preflight["accounting"]["confirmatory_rows_kept_opaque"] == 960
    assert preflight["accounting"]["confirmatory_target_values_parsed"] == 0
    matrix = np.load(model / "features.npy", allow_pickle=False)
    assert matrix.shape == (960, 2248)
    assert matrix.dtype == np.float64
    assert matrix.flags.c_contiguous
    assert np.isnan(matrix[:, 2048:]).any()
    assert not np.isinf(matrix).any()
    assert np.equal(matrix[:, :2048], np.floor(matrix[:, :2048])).all()
    model_files = _tree_map(model)
    scorer_files = _tree_map(scorer)
    assert sum(name.startswith("targets/") for name in model_files) == 60
    assert "outer_truth.csv" not in model_files
    assert "outer_truth.csv" in scorer_files
    assert not any(name.startswith("targets/") for name in scorer_files)
    assert not any("baseline" in name for name in model_files)


def test_compiler_does_not_open_baseline_before_prediction_freeze(
    tmp_path: Path,
) -> None:
    source, _baseline, receipts = _source_and_baseline(tmp_path)
    absent = tmp_path / "baseline-must-remain-absent"
    model, scorer, _preflight = compiler.compile_capabilities(
        source_root=source,
        baseline_terminal_root=absent,
        output_root=tmp_path / "capabilities",
        expected_compiler_sha256=g3.sha256_path(compiler.SCRIPT),
        mode="synthetic",
        synthetic_baseline_receipts=receipts,
    )
    assert model.exists() and scorer.exists() and not absent.exists()


def test_reversed_source_order_compiles_byte_identically(tmp_path: Path) -> None:
    _compile(tmp_path / "a", reverse=False)
    _compile(tmp_path / "b", reverse=True)
    assert _tree_map(tmp_path / "a" / "capabilities") == _tree_map(
        tmp_path / "b" / "capabilities"
    )


def test_raw_structure_receipt_tamper_fails_closed(tmp_path: Path) -> None:
    source, baseline, receipts = _source_and_baseline(tmp_path / "original")
    files = {name: (source / name).read_bytes() for name in compiler.SOURCE_FILES}
    direct = _rows(files["direct_observations.csv"])
    row = next(
        item
        for item in direct
        if not compiler.is_confirmatory(item["similarity_component_hash"])
    )
    row["raw_structure_sha256"] = "0" * 64
    files["direct_observations.csv"] = g3.csv_bytes(compiler.DIRECT_COLUMNS, direct)
    manifest = compiler._load_json(source / "manifest.json")
    manifest["source_receipts"] = {
        name: g3.sha256_bytes(value) for name, value in files.items()
    }
    tampered = compiler._publish_files(
        tmp_path / "tampered",
        {**files, "manifest.json": g3.json_bytes(manifest)},
    )
    with pytest.raises(compiler.G3ExecutionCompilerError, match="raw structure"):
        compiler.compile_capabilities(
            source_root=tampered,
            baseline_terminal_root=baseline,
            output_root=tmp_path / "must-not-publish",
            expected_compiler_sha256=g3.sha256_path(compiler.SCRIPT),
            mode="synthetic",
            synthetic_baseline_receipts=receipts,
        )
    assert not (tmp_path / "must-not-publish").exists()


def test_writable_source_leaf_fails_before_parsing(tmp_path: Path) -> None:
    source, baseline, receipts = _source_and_baseline(tmp_path)
    leaf = source / "feature_rows.csv"
    leaf.chmod(0o644)
    with pytest.raises(compiler.G3ExecutionCompilerError, match="source .* writable"):
        compiler.compile_capabilities(
            source_root=source,
            baseline_terminal_root=baseline,
            output_root=tmp_path / "must-not-publish",
            expected_compiler_sha256=g3.sha256_path(compiler.SCRIPT),
            mode="synthetic",
            synthetic_baseline_receipts=receipts,
        )
    assert not (tmp_path / "must-not-publish").exists()


def test_underpowered_preflight_publishes_no_capability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, baseline, receipts = _source_and_baseline(tmp_path)
    monkeypatch.setattr(
        compiler,
        "MINIMA",
        {
            "development_finite_targets_per_endpoint": 10_000,
            "outer_training_targets_per_endpoint_repeat_fold": 400,
            "outer_validation_targets_per_endpoint_repeat_fold": 75,
        },
    )
    with pytest.raises(compiler.G3ExecutionUnderpowered) as caught:
        compiler.compile_capabilities(
            source_root=source,
            baseline_terminal_root=baseline,
            output_root=tmp_path / "capabilities",
            expected_compiler_sha256=g3.sha256_path(compiler.SCRIPT),
            mode="synthetic",
            synthetic_baseline_receipts=receipts,
        )
    assert caught.value.preflight["status"] == "G2_6R_G3_UNDERPOWERED"
    assert not (tmp_path / "capabilities").exists()


def test_full_topology_freezes_before_scorer_and_exercises_all_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, baseline, receipts = _source_and_baseline(tmp_path)
    model, scorer, _preflight = compiler.compile_capabilities(
        source_root=source,
        baseline_terminal_root=baseline,
        output_root=tmp_path / "capabilities",
        expected_compiler_sha256=g3.sha256_path(compiler.SCRIPT),
        mode="synthetic",
        synthetic_baseline_receipts=receipts,
    )
    opened: list[str] = []
    original = compiler._readonly_root

    def observed(root: Path, label: str) -> Path:
        opened.append(label)
        return original(root, label)

    monkeypatch.setattr(compiler, "_readonly_root", observed)
    terminal = wrapper.run_compiled_replay(
        model_capability_root=model,
        scorer_capability_root=scorer,
        baseline_terminal_root=baseline,
        work_root=tmp_path / "execution",
        predictor=wrapper.deterministic_test_predictor,
    )
    assert opened.index("frozen candidate") < opened.index("G3 scorer capability")
    assert opened.index("G3 scorer capability") < opened.index(
        "fixed baseline terminal"
    )
    manifest = compiler._load_json(terminal / "manifest.json")
    result = compiler._load_json(terminal / "g3_result.json")
    assert set(_tree_map(terminal)) == set(wrapper.TERMINAL_NAMES)
    assert manifest["counts"]["model_fits"] == 60
    assert manifest["counts"]["candidate_outer_prediction_rows"] == 11_520
    assert manifest["counts"]["baseline_outer_prediction_rows"] == 11_520
    assert manifest["counts"]["tutorial_metric_calls"] == 24
    assert manifest["counts"]["bootstrap_accepted_replicates"] == 2_000
    assert result["all_promotion_gates_pass"] is True
    assert all(result["promotion_gates"].values())
    assert all(manifest["accounting"][name] == 0 for name in wrapper.FORBIDDEN_COUNTERS)


def test_failure_and_underpowered_terminals_are_aggregate_only() -> None:
    for status in ("G2_6R_G3_FAILED", "G2_6R_G3_UNDERPOWERED"):
        files = wrapper._status_terminal_files(
            status=status,
            failure_type="SyntheticTestFailure",
            preflight={"status": status, "failures": ["aggregate-only"]},
            completed_fits=7,
            completed_predictions=123,
        )
        assert set(files) == set(wrapper.TERMINAL_NAMES)
        assert _rows(files[wrapper.TERMINAL_NAMES[0]]) == []
        manifest = json.loads(files["manifest.json"])
        assert manifest["status"] == status
        assert manifest["counts"]["model_fits"] == 7
        assert manifest["counts"]["candidate_outer_prediction_rows"] == 123
        assert all(
            manifest["accounting"][name] == 0 for name in wrapper.FORBIDDEN_COUNTERS
        )


def test_atomic_publication_refuses_replacement(tmp_path: Path) -> None:
    destination = compiler._publish_files(tmp_path / "published", {"value": b"first"})
    before = (destination / "value").read_bytes()
    with pytest.raises(compiler.G3ExecutionCompilerError, match="publication exists"):
        compiler._publish_files(destination, {"value": b"second"})
    assert (destination / "value").read_bytes() == before == b"first"


def test_real_predictor_has_no_validation_or_early_stopping_capability() -> None:
    source = wrapper.SCRIPT.read_text(encoding="utf-8")
    predictor = source[
        source.index("def real_predictor") : source.index(
            "def deterministic_test_predictor"
        )
    ]
    assert (
        "lgb.train(parameters, dataset, num_boost_round=g3.NUM_BOOST_ROUND)"
        in predictor
    )
    for forbidden in (
        "valid_sets=",
        "callbacks=",
        "early_stopping",
        "init_model=",
        "fobj=",
    ):
        assert forbidden not in predictor


def test_official_fixed_paths_and_attempt_policy_are_nonreplaceable() -> None:
    assert compiler.OFFICIAL_SOURCE_ROOT.name == "g2-2c-maplight-development-source-v1"
    assert compiler.OFFICIAL_BASELINE_ROOT.name == "terminal"
    assert wrapper.OFFICIAL_ATTEMPT_ROOT.name == "g2-6t-g3-development-attempt-1"
    source = wrapper.SCRIPT.read_text(encoding="utf-8")
    assert "os.O_EXCL" in source
    attempt = source[source.index("def run_official_attempt") :]
    assert "while " not in attempt and "for attempt" not in attempt


def test_tracked_acceptance_binds_exact_final_sources_and_zero_authority() -> None:
    acceptance = compiler._load_json(compiler.TRACKED_ACCEPTANCE)
    assert g3.sha256_path(compiler.TRACKED_ACCEPTANCE) == (
        "4bdc758a51eb3cd2ebca7d5154f531567a07542cb419d2539924fd42859e2636"
    )
    assert acceptance["status"] == "G2_6T_G3_OFFICIAL_SHAPED_SYNTHETIC_ACCEPTED"
    assert acceptance["official_compiler_source_sha256"] == g3.sha256_path(
        compiler.SCRIPT
    )
    assert acceptance["execution_wrapper_source_sha256"] == g3.sha256_path(
        wrapper.SCRIPT
    )
    assert acceptance["official_shaped_synthetic_driver_source_sha256"] == (
        g3.sha256_path(synthetic.SCRIPT)
    )
    assert acceptance["relative_terminal_maps_byte_identical"] is True
    assert acceptance["terminal_files_compared"] == 6
    assert acceptance["network_namespace_isolated"] is True
    assert acceptance["claim_consumptions"] == 0
    assert acceptance["official_operations"] == 0
    assert acceptance["model_quality_authority"] is False


def test_consumed_claim_fills_exactly_four_fields_and_cannot_replace(
    tmp_path: Path,
) -> None:
    template_bytes = compiler.TRACKED_CLAIM.read_bytes()
    template = json.loads(template_bytes)
    consumed = wrapper.derive_consumed_claim()
    changed = {name for name in consumed if consumed[name] != template[name]}
    assert changed == set(compiler.FUTURE_FIELDS)
    assert all(consumed[name] is not None for name in compiler.FUTURE_FIELDS)
    attempt = tmp_path / "g2-6t-g3-development-attempt-1"
    claim_path = wrapper.consume_claim(attempt_root=attempt)
    assert claim_path.read_bytes() == g3.json_bytes(consumed)
    with pytest.raises(wrapper.G3ExecutionWrapperError, match="attempt root exists"):
        wrapper.consume_claim(attempt_root=attempt)
    assert compiler.TRACKED_CLAIM.read_bytes() == template_bytes
