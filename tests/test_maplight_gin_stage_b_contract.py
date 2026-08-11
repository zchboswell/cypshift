from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "benchmarks/maplight_gin_stage_b_contract.json"
RUNNER_PATH = ROOT / "research/maplight-fixed/run_stage_b_gin_catboost.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _runner() -> ModuleType:
    name = "cypshift_test_maplight_gin_stage_b"
    spec = importlib.util.spec_from_file_location(name, RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_stage_b_contract_binds_the_frozen_scientific_inputs() -> None:
    contract = _contract()
    assert contract["schema_version"] == "cypshift.maplight_gin_stage_b_contract.v1"
    inputs = contract["inputs"]
    assert isinstance(inputs, dict)
    for name in ("gin_contract", "stage_a_contract", "nan_contract"):
        record = inputs[name]
        assert isinstance(record, dict)
        path = ROOT / str(record["path"])
        assert path.is_file()
        assert _sha256(path) == record["sha256"]
    assert contract["pre_execution_accounting"] == {
        "model_fits": 0,
        "predictions": 0,
        "metric_evaluations": 0,
        "validation_target_values_parsed": 0,
        "public_test_rows_used": 0,
        "public_test_labels_parsed": 0,
        "public_test_family_task_slots_consumed": 0,
        "challenge_assumptions_added": 0,
    }


def test_stage_b_contract_freezes_only_the_declared_control_budget() -> None:
    contract = _contract()
    model = contract["model_contract"]
    assert isinstance(model, dict)
    configurations = model["configurations"]
    assert isinstance(configurations, list) and len(configurations) == 4
    assert model["cells"] == 18
    assert model["fits_per_cell"] == 8
    assert model["total_model_fits"] == 144
    assert model["model_prediction_rows"] == 8 * 36045
    assert model["derived_prediction_rows"] == 36045
    assert model["retained_probability_values"] == 9 * 36045
    evaluation = contract["evaluation_contract"]
    assert isinstance(evaluation, dict)
    assert evaluation["point_metric_evaluations"] == 11 * 18
    assert evaluation["sensitivity_point_metric_evaluations"] == 3 * 2 * 18
    bootstrap = evaluation["bootstrap"]
    assert isinstance(bootstrap, dict)
    assert bootstrap["metric_evaluations"] == 4 * 18 * 2000
    assert evaluation["total_metric_evaluations"] == 198 + 108 + 144000
    assert contract["controls"] == {
        "shuffle_seed": 20260816,
        "noise_seed": 20260817,
        "unique_raw_order": "raw_structure_sha256 ascending",
        "shuffle": "Use one NumPy default_rng permutation of the 15399 unique exact-raw GIN vectors, then expand the permuted mapping to every official row. Exact-raw duplicates receive the same shuffled vector.",
        "noise": "Use one NumPy default_rng standard-normal float64 matrix with shape 15399 by 300 in the same sorted exact-raw order, then expand it to every official row. Exact-raw duplicates receive the same noise vector.",
        "invariants": [
            "the unshuffled GIN matrix is never modified",
            "the shuffle is a whole-vector permutation without replacement",
            "noise is generated independently of structures and targets",
            "controls are generated before any validation target is available",
        ],
    }


def test_exact_raw_controls_are_deterministic_and_duplicate_safe() -> None:
    runner = _runner()
    gin = np.asarray(
        [[10.0, 11.0], [20.0, 21.0], [10.0, 11.0], [30.0, 31.0]],
        dtype=np.float64,
    )
    hashes = ["b", "a", "b", "c"]
    shuffled, noise = runner._make_controls(gin, hashes)
    shuffled_repeat, noise_repeat = runner._make_controls(gin, hashes)
    assert np.array_equal(shuffled, shuffled_repeat)
    assert np.array_equal(noise, noise_repeat)
    assert np.array_equal(shuffled[0], shuffled[2])
    assert np.array_equal(noise[0], noise[2])
    assert {tuple(row) for row in shuffled[[1, 0, 3]]} == {
        (10.0, 11.0),
        (20.0, 21.0),
        (30.0, 31.0),
    }
    changed = gin.copy()
    changed[2, 0] = 99.0
    with pytest.raises(runner.StageBModelError, match="exact-raw GIN repeat differs"):
        runner._make_controls(changed, hashes)


def test_stage_b_runner_surface_and_configuration_ids_are_fixed() -> None:
    runner = _runner()
    assert runner.CONTRACT_SHA256 == _sha256(CONTRACT_PATH)
    assert runner.SHUFFLE_SEED == 20260816
    assert runner.NOISE_SEED == 20260817
    assert [item[0] for item in runner.CONFIGURATIONS] == [
        "b1_gin_alone_catboost_seed_1",
        "b2_maplight_fixed_plus_gin_catboost_seed_1",
        "b2_maplight_fixed_plus_gin_catboost_seed_2",
        "b2_maplight_fixed_plus_gin_catboost_seed_3",
        "b2_maplight_fixed_plus_gin_catboost_seed_4",
        "b2_maplight_fixed_plus_gin_catboost_seed_5",
        "b3_maplight_fixed_plus_shuffled_gin_catboost_seed_1",
        "b4_maplight_fixed_plus_noise_catboost_seed_1",
    ]
    assert runner._arguments(["--run"]).run is True
    with pytest.raises(SystemExit):
        runner._arguments([])
