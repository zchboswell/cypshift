from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, cast

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "research/maplight-fixed/run_public_comparator_predictions.py"
BUDGET = ROOT / "benchmarks/phase_0_75_evaluation_budget.json"


def _module() -> Any:
    spec = importlib.util.spec_from_file_location("public_predictions_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _function_names(name: str) -> set[str]:
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )
    return {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}


def test_public_prediction_budget_and_families_are_exact() -> None:
    module = _module()
    assert (
        hashlib.sha256(BUDGET.read_bytes()).hexdigest()
        == module.EVALUATION_BUDGET_SHA256
    )
    budget = json.loads(BUDGET.read_text(encoding="utf-8"))
    assert [family["family_id"] for family in budget["families"][:2]] == [
        "maplight_fixed",
        "maplight_gin",
    ]
    assert budget["families"][2]["status_by_task"] == {
        task: "reserved_unconsumed" for task in module.TASKS
    }
    assert module.SEEDS == (1, 2, 3, 4, 5)
    assert module.TASK_ROWS == {
        "cyp2c9_veith": 2419,
        "cyp2d6_veith": 2626,
        "cyp3a4_veith": 2467,
    }
    assert sum(module.TASK_ROWS.values()) == module.TOTAL_ROWS == 7512
    assert module.FIXED_WIDTHS == (1024, 1024, 315, 200)


def test_prediction_path_has_no_public_label_or_source_projection_access() -> None:
    prediction_names = _function_names("run_predictions")
    assert not prediction_names & {
        "SOURCE_ROOT",
        "SOURCE_MANIFEST",
        "SOURCE_MOLECULES",
        "SOURCE_SPLIT",
        "_source_rows",
    }
    source_names = _function_names("_source_rows")
    assert {"SOURCE_MOLECULES", "SOURCE_SPLIT", "SOURCE_HASHES"} <= source_names
    source = RUNNER.read_text(encoding="utf-8")
    assert "public_test_labels_parsed" in source
    assert "PUBLIC_TEST_MEASUREMENTS" not in source


def test_prediction_csv_has_exact_order_and_probability_mean(tmp_path: Path) -> None:
    module = _module()
    rows = [
        {
            "task": "cyp2c9_veith",
            "molecule_id": "test-1",
            "source_row": "2",
            "raw_structure_sha256": "a" * 64,
            "standardized_structure_sha256": "b" * 64,
        },
        {
            "task": "cyp2c9_veith",
            "molecule_id": "test-2",
            "source_row": "10",
            "raw_structure_sha256": "c" * 64,
            "standardized_structure_sha256": "d" * 64,
        },
    ]
    values = {
        seed: np.asarray([seed / 10, seed / 20], dtype=np.float64)
        for seed in module.SEEDS
    }
    path = tmp_path / "predictions.csv"
    module._write_predictions(path, rows, values)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output = list(reader)
        assert tuple(cast(list[str], reader.fieldnames)) == module.PREDICTION_COLUMNS
    assert [row["source_row"] for row in output] == ["2", "10"]
    assert [float(row["prediction_probability_mean"]) for row in output] == [
        0.3,
        0.15,
    ]


def test_public_runner_does_not_change_core_cli_or_dependencies() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "catboost" not in pyproject.lower()
    assert "molfeat" not in pyproject.lower()
    assert "torch" not in pyproject.lower()
    scripts = ast.parse((ROOT / "src/cypshift/cli.py").read_text(encoding="utf-8"))
    text = ast.unparse(scripts)
    for command in ("audit", "train", "predict", "report"):
        assert command in text


def test_repeat_manifest_ignores_only_declared_attempt_observations() -> None:
    module = _module()
    first = {
        "attempt": 1,
        "runtime_seconds": 10.0,
        "peak_rss_gib": 1.0,
        "fits": [{"runtime_seconds": 2.0, "prediction_element_sha256": "a" * 64}],
        "accounting": {
            "additional_family_task_slots_consumed_this_attempt": 6,
            "public_test_family_task_slots_consumed": 6,
        },
        "predictions": {"maplight_fixed__cyp2c9_veith": {"sha256": "b" * 64}},
    }
    second = json.loads(json.dumps(first))
    second["attempt"] = 2
    second["runtime_seconds"] = 11.0
    second["peak_rss_gib"] = 2.0
    second["fits"][0]["runtime_seconds"] = 3.0
    second["accounting"]["additional_family_task_slots_consumed_this_attempt"] = 0
    assert module._repeat_comparable_manifest(
        first
    ) == module._repeat_comparable_manifest(second)
    second["predictions"]["maplight_fixed__cyp2c9_veith"]["sha256"] = "c" * 64
    assert module._repeat_comparable_manifest(
        first
    ) != module._repeat_comparable_manifest(second)
