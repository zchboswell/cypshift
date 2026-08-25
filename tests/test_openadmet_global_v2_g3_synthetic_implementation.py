from __future__ import annotations

import csv
import importlib
import io
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parents[1]
RESEARCH = ROOT / "research" / "lightgbm-global"
sys.path.insert(0, str(RESEARCH))
g3 = importlib.import_module("g3_runner")
synthetic = importlib.import_module("run_g3_synthetic")


def _rows(value: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(value.decode(), newline="")))


def test_implementation_binds_exact_contracts_and_isolated_lock() -> None:
    contract, parent = g3.static_contract()
    assert contract["status"] == "G2_6S_EXP_G3_SYNTHETIC_CONTRACT_FROZEN"
    assert parent["model_contract"]["system_id"] == g3.SYSTEM_ID
    assert g3.CONTRACT_SHA256 == g3.EXPECTED_CONTRACT_SHA256
    assert g3.PARENT_SHA256 == g3.EXPECTED_PARENT_SHA256
    project = (RESEARCH / "pyproject.toml").read_text(encoding="utf-8")
    lock = (RESEARCH / "uv.lock").read_text(encoding="utf-8")
    assert 'requires-python = "==3.12.3"' in project
    for dependency in (
        "lightgbm==4.7.0",
        "numpy==2.5.2",
        "rdkit==2026.3.5",
        "scipy==1.18.0",
    ):
        assert dependency in project
    assert "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7" in lock
    assert "3cdec01fa790a186d430433fdd4d4ffb70eed6f0eeb4bf05c8dbe2dce0a9bcb8" in lock
    assert "b75944ba959d908e97b4d68754e5950216ac08aa81faf67cfd1d7a3cb5b2bad7" in lock
    assert "1f55797419e16e7f30cf88ffb3113ce0467f00cfe3f70d5c281730b21769bfc2" in lock
    assert g3.sha256_path(ROOT / "uv.lock") == (
        "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6"
    )
    assert '"lightgbm' not in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_fixture_has_exact_population_targets_and_family_folds() -> None:
    fixture = g3.build_fixture()
    molecules = fixture["molecules"]
    truth = fixture["development_truth"]
    folds = fixture["folds"]
    assert len(molecules) == 100
    assert len({row["component"] for row in molecules}) == 50
    assert sum(row["partition"] == "development" for row in molecules) == 80
    assert sum(row["partition"] == "confirmatory" for row in molecules) == 20
    assert len(truth) == 320
    assert len(folds) == 240
    for endpoint in g3.ENDPOINTS:
        endpoint_truth = [row for row in truth if row["endpoint"] == endpoint]
        assert sum(row["central"] is not None for row in endpoint_truth) == 64
    for seed in g3.REPEAT_SEEDS:
        seed_rows = [row for row in folds if row["repeat_seed"] == seed]
        by_component: dict[str, list[dict[str, object]]] = {}
        for row in seed_rows:
            by_component.setdefault(str(row["component"]), []).append(row)
        assert len(by_component) == 40
        assert all(len(rows) == 2 for rows in by_component.values())
        assert all(
            len({row["outer_fold"] for row in rows}) == 1
            for rows in by_component.values()
        )
        assert (
            sorted(
                sum(row["outer_fold"] == fold for row in seed_rows) for fold in range(5)
            )
            == [16] * 5
        )


def test_feature_formula_is_exact_dense_nan_preserving_and_order_invariant() -> None:
    canonical = g3.build_feature_matrix(np.arange(100), reverse_physical=False)
    reverse = g3.build_feature_matrix(np.arange(100), reverse_physical=True)
    assert canonical.dtype == np.float64
    assert canonical.flags.c_contiguous
    assert canonical.shape == (100, 2248)
    assert np.array_equal(canonical, reverse, equal_nan=True)
    expression = (1315423911 * 7 + 2654435761 * 11 + 20260901) % 64
    expected_morgan = 1 + expression % 3 if expression < 2 else 0
    assert canonical[7, 11] == expected_morgan
    descriptor_expression = 37 * 7 + 53 * 5 + 20260901
    if descriptor_expression % 29 == 0:
        assert np.isnan(canonical[7, 2048 + 5])
    else:
        assert canonical[7, 2048 + 5] == ((17 * 7 + 31 * 5 + 20260901) % 1009) / 1009
    assert not np.isinf(canonical).any()
    assert np.isnan(canonical[:, 2048:]).any()
    assert np.all(canonical[:, :2048] == canonical[:, :2048].astype(np.int32))


def test_model_double_is_complete_family_safe_and_byte_stable() -> None:
    canonical = g3.model_double_files(reverse_execution_order=False)
    reverse = g3.model_double_files(reverse_execution_order=True)
    assert canonical == reverse
    assert set(canonical) == set(g3.TERMINAL_NAMES[:4])
    fits = _rows(canonical[g3.TERMINAL_NAMES[1]])
    predictions = _rows(canonical[g3.TERMINAL_NAMES[2]])
    assert len(fits) == len({row["fit_id"] for row in fits}) == 60
    assert len(predictions) == 960
    assert len({row["fit_id"] for row in predictions}) == 60
    assert all(
        sum(row["endpoint"] == endpoint for row in predictions) == 240
        for endpoint in g3.ENDPOINTS
    )
    assert all(
        sum(row["repeat_seed"] == str(seed) for row in predictions) == 320
        for seed in g3.REPEAT_SEEDS
    )
    feature = json.loads(canonical[g3.TERMINAL_NAMES[0]])
    assert feature["rows"] == 100
    assert feature["columns"] == 2248
    assert feature["components"] == 50
    assert feature["confirmatory_truth_values_parsed"] == 0
    metrics = json.loads(canonical[g3.TERMINAL_NAMES[3]])
    assert metrics["truth_resolved_after_prediction_freeze"] is True
    assert metrics["model_quality_authority"] is False


def test_model_capability_has_no_validation_truth_or_forbidden_path() -> None:
    assert tuple(g3.ModelCapability.__dataclass_fields__) == (
        "training_target_rows",
        "training_feature_rows",
        "validation_feature_rows",
        "parameter_receipt_sha256",
        "identity_token",
    )
    source = g3.SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        "validation_truth",
        "baseline_prediction",
        "leaderboard_path",
        "submission_path",
        "confirmatory_target",
    ):
        assert forbidden not in source


def test_exact_parameters_and_direct_lightgbm_api_are_frozen() -> None:
    parameters = g3.model_parameters()
    assert parameters == {
        "boosting": "gbdt",
        "objective": "regression_l1",
        "metric": "l1",
        "learning_rate": 0.03,
        "num_leaves": 31,
        "max_depth": -1,
        "min_data_in_leaf": 20,
        "min_sum_hessian_in_leaf": 0.001,
        "min_gain_to_split": 0.0,
        "max_bin": 255,
        "feature_pre_filter": False,
        "feature_fraction": 1.0,
        "feature_fraction_bynode": 1.0,
        "bagging_fraction": 1.0,
        "bagging_freq": 0,
        "lambda_l1": 0.0,
        "lambda_l2": 10.0,
        "use_missing": True,
        "zero_as_missing": False,
        "deterministic": True,
        "force_col_wise": True,
        "seed": 20260825,
        "data_random_seed": 20260825,
        "feature_fraction_seed": 20260825,
        "bagging_seed": 20260825,
        "drop_seed": 20260825,
        "extra_seed": 20260825,
        "num_threads": 16,
        "verbosity": -1,
    }
    source = g3.SCRIPT.read_text(encoding="utf-8")
    assert "lgb.train(parameters, dataset, num_boost_round=NUM_BOOST_ROUND)" in source
    for forbidden in (
        "valid_sets=",
        "callbacks=",
        "early_stopping",
        "init_model=",
        "fobj=",
    ):
        assert forbidden not in source


def test_full_width_probe_matrix_and_targets_are_order_invariant() -> None:
    train_a, predict_a, targets_a = g3.probe_matrix(reverse_physical=False)
    train_b, predict_b, targets_b = g3.probe_matrix(reverse_physical=True)
    assert train_a.shape == train_b.shape == (3120, 2248)
    assert predict_a.shape == predict_b.shape == (788, 2248)
    assert targets_a.shape == targets_b.shape == (3120, 4)
    assert np.array_equal(train_a, train_b, equal_nan=True)
    assert np.array_equal(predict_a, predict_b, equal_nan=True)
    assert np.array_equal(targets_a, targets_b)
    expected = (
        4.0
        + 0.2 * 2
        + 0.03 * np.nan_to_num(train_a[17, 2048 + 2], nan=0.0)
        + 0.01 * train_a[17, :16].sum()
        + 0.0001 * (17 % 101)
    )
    assert targets_a[17, 2] == expected


def _fake_complete_terminal() -> dict[str, bytes]:
    model_double = g3.model_double_files()
    parameter_sha = str(g3.parameter_receipt()["sha256"])
    parameters = [
        {
            "endpoint": endpoint,
            "resolved_parameter_sha256": parameter_sha,
            "num_boost_round": 1500,
            "training_rows": 3120,
            "prediction_rows": 788,
            "columns": 2248,
        }
        for endpoint in reversed(g3.ENDPOINTS)
    ]
    predictions = [
        {"endpoint": endpoint, "row_index": 3120 + index, "prediction": "4.25"}
        for endpoint in reversed(g3.ENDPOINTS)
        for index in reversed(range(788))
    ]
    return g3.complete_terminal_files(
        model_double=model_double,
        probe_parameter_rows=parameters,
        probe_prediction_rows=predictions,
    )


def test_complete_terminal_has_exact_seven_file_map_and_counts() -> None:
    files = _fake_complete_terminal()
    assert tuple(files) == g3.TERMINAL_NAMES
    manifest = json.loads(files[g3.TERMINAL_NAMES[-1]])
    assert manifest["model_double_fits"] == 60
    assert manifest["model_double_outer_predictions"] == 960
    assert manifest["real_lightgbm_fits"] == 4
    assert manifest["real_lightgbm_predictions"] == 3152
    assert manifest["relative_files"] == {
        name: g3.sha256_bytes(files[name]) for name in g3.TERMINAL_NAMES[:6]
    }
    assert all(value == 0 for value in manifest["accounting"].values())


def _private_observation(path: Path, *, fit_wall: float, fit_cpu: float) -> None:
    path.mkdir()
    (path / "resource_observations.json").write_bytes(
        g3.json_bytes(
            {
                "maximum_individual_fit_wall_seconds": fit_wall,
                "maximum_individual_fit_cpu_seconds": fit_cpu,
                "nonfit_wall_seconds_for_projection": 100.0,
                "nonfit_cpu_seconds_for_projection": 200.0,
                "simultaneous_restricted_storage_bytes": 3_000_000_000,
                "maximum_peak_rss_kib": 2 * 1024 * 1024,
                "python_warnings": 0,
                "fallbacks": 0,
                "nonzero_exits": 0,
                "gpu_hours": 0,
            }
        )
    )


def test_resource_projection_uses_worst_fit_and_full_root_overhead(
    tmp_path: Path,
) -> None:
    private_a = tmp_path / "a"
    private_b = tmp_path / "b"
    _private_observation(private_a, fit_wall=10.0, fit_cpu=20.0)
    _private_observation(private_b, fit_wall=12.0, fit_cpu=18.0)
    projection = synthetic.project_resources(private_a, private_b)
    assert projection["projected_wall_hours"] == (60 * 12 + 100) / 3600
    assert projection["projected_cpu_core_hours"] == (60 * 20 + 200) / 3600
    assert projection["restricted_storage_gb"] == 3.0
    assert projection["peak_rss_gib"] == 2.0
    assert projection["accepted"] is True
    assert all(projection["gates"].values())


def test_formal_binding_paths_network_and_attempt_are_fail_closed() -> None:
    bindings = synthetic.source_bindings()
    assert bindings["g3_synthetic_contract_sha256"] == g3.CONTRACT_SHA256
    assert bindings["g3_single_expert_contract_sha256"] == g3.PARENT_SHA256
    assert bindings["focused_test_sha256"] == g3.sha256_path(Path(__file__))
    assert synthetic.DEFAULT_ROOT_A.name == "g3-synthetic-attempt-1-root-a"
    assert synthetic.DEFAULT_ROOT_B.name == "g3-synthetic-attempt-1-root-b"
    assert synthetic.DEFAULT_RECEIPT.name == "g3-synthetic-attempt-1-receipt"
    assert synthetic.DEFAULT_CACHE.name == "g3-synthetic-attempt-1-cache"
    source = synthetic.SCRIPT.read_text(encoding="utf-8")
    assert '"--map-root-user"' in source
    assert '"--net"' in source
    assert '"UV_OFFLINE": "1"' in source
    assert "DEFAULT_RECEIPT.mkdir(parents=True)" in source
    assert "not path.exists() and not path.is_symlink()" in source
    assert "shutil.rmtree(cache_root)" in source


def test_current_implementation_opens_no_official_or_submission_capability() -> None:
    contract = json.loads(g3.CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["current_authority"]["implementation"] is False
    for field in (
        "official_inputs",
        "official_model_fits",
        "development_metrics",
        "confirmatory",
        "submission",
        "leaderboard_selection",
        "upload",
        "claim_creation_or_consumption",
    ):
        assert contract["current_authority"][field] is False
    for module in (g3.SCRIPT, synthetic.SCRIPT):
        source = module.read_text(encoding="utf-8")
        assert "requests" not in source
        assert "http://" not in source
        assert "https://" not in source
