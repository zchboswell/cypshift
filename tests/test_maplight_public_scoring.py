from __future__ import annotations

import ast
import csv
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/maplight-fixed/score_public_comparators.py"


def _module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("maplight_public_scoring", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_scoring_budget_is_exact() -> None:
    module = _module()
    assert module.TASKS == ("cyp2c9_veith", "cyp2d6_veith", "cyp3a4_veith")
    assert module.FAMILIES == ("maplight_fixed", "maplight_gin")
    assert len(module.PREDICTION_COLUMNS) == 6
    assert sum(module.TASK_ROWS.values()) == 7512
    assert sum(len(tasks) for tasks in module.ANCHORS.values()) == 6
    assert set(module.PREDICTION_ROOTS) == {3, 4}
    assert len(module.EXPECTED_PREDICTION_FILES) == 14


def test_public_scoring_tolerance_boundaries_are_frozen() -> None:
    module = _module()
    assert module._reproduction_status(0.005) == "reproduced_within_0.005"
    assert module._reproduction_status(-0.005) == "reproduced_within_0.005"
    assert (
        module._reproduction_status(0.0050000001)
        == "outside_preferred_tolerance_0.005_to_0.010"
    )
    assert (
        module._reproduction_status(-0.010)
        == "outside_preferred_tolerance_0.005_to_0.010"
    )
    assert (
        module._reproduction_status(0.0100000001) == "reproduction_blocker_over_0.010"
    )


def test_public_target_loader_interprets_only_selected_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    path = tmp_path / "measurements.csv"
    rows = [
        {
            "measurement_id": "train:label",
            "molecule_id": "train",
            "endpoint": "binary_inhibition_veith",
            "isoform": "CYP2C9",
            "nadph_condition": "not_reported",
            "probe": "not_reported",
            "readout": "binary_label",
            "value": "DO_NOT_PARSE",
            "lower_bound": "",
            "upper_bound": "",
            "censoring": "none",
            "unit": "binary",
            "quality": "accepted",
            "source": "fixture",
            "provenance": "{}",
        },
        {
            "measurement_id": "test:label",
            "molecule_id": "test",
            "endpoint": "binary_inhibition_veith",
            "isoform": "CYP2C9",
            "nadph_condition": "not_reported",
            "probe": "not_reported",
            "readout": "binary_label",
            "value": "1.0",
            "lower_bound": "",
            "upper_bound": "",
            "censoring": "none",
            "unit": "binary",
            "quality": "accepted",
            "source": "fixture",
            "provenance": "{}",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=module.MEASUREMENT_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    path.chmod(0o444)
    tmp_path.chmod(0o555)
    monkeypatch.setattr(module, "MEASUREMENTS_PATH", path)
    monkeypatch.setattr(module, "MEASUREMENTS_SHA256", module._sha256(path))
    monkeypatch.setattr(module, "MEASUREMENT_ROWS", 2)
    accounting = {
        "measurement_rows_traversed": 0,
        "public_test_labels_parsed": 0,
        "public_test_primary_metric_evaluations": 0,
    }
    targets, traversed = module._load_public_targets(
        [{"molecule_id": "test", "task": "cyp2c9_veith"}], accounting
    )
    assert targets == {"test": 1}
    assert traversed == 2
    assert accounting["measurement_rows_traversed"] == 2
    assert accounting["public_test_labels_parsed"] == 1


def _prediction_fixture(module, tmp_path: Path) -> dict[str, int]:  # type: ignore[no-untyped-def]
    root = tmp_path / "predictions"
    root.mkdir()
    targets: dict[str, int] = {}
    for family in module.FAMILIES:
        for task in module.TASKS:
            rows = []
            for index, target in enumerate((0, 1)):
                molecule_id = f"{task}:{index}"
                targets[molecule_id] = target
                row = {
                    "task": task,
                    "molecule_id": molecule_id,
                    "source_row": str(index + 1),
                    "raw_structure_sha256": "0" * 64,
                    "standardized_structure_sha256": "1" * 64,
                }
                row.update({column: "0.5" for column in module.PREDICTION_COLUMNS})
                rows.append(row)
            module._write_csv(
                root / f"{family}__{task}.csv", module.PREDICTION_FILE_COLUMNS, rows
            )
    module.PREDICTION_ROOTS = {3: root}
    return targets


def _accounting() -> dict[str, int]:
    return {
        "measurement_rows_traversed": 0,
        "public_test_labels_parsed": 0,
        "public_test_primary_metric_evaluations": 0,
    }


def test_public_scorer_executes_exactly_36_calls_and_pytcd_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    targets = _prediction_fixture(module, tmp_path)
    calls = 0

    def metric(_labels, _probability):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return 0.5

    monkeypatch.setattr(module, "_average_precision", lambda: metric)
    accounting = _accounting()
    metric_rows, scorecard, maximum = module._score(targets, accounting)
    assert calls == accounting["public_test_primary_metric_evaluations"] == 36
    assert len(metric_rows) == 36
    assert len(scorecard) == 6
    assert maximum == 0.5
    assert module._seed_summary((0.7004, 0.7014, 0.7024, 0.7034, 0.7044)) == (
        0.702,
        0.001,
    )


def test_public_scorer_stops_immediately_at_forensic_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    targets = _prediction_fixture(module, tmp_path)
    monkeypatch.setattr(module, "_average_precision", lambda: lambda _y, _p: 0.95)
    accounting = _accounting()
    with pytest.raises(module.ForensicGateTriggered) as error:
        module._score(targets, accounting)
    assert accounting["public_test_primary_metric_evaluations"] == 1
    assert error.value.family == "maplight_fixed"
    assert error.value.task == "cyp2c9_veith"
    assert error.value.column == "prediction_seed_1"
    assert error.value.score == 0.95


def test_public_scorer_counts_only_completed_metrics_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    targets = _prediction_fixture(module, tmp_path)
    calls = 0

    def metric(_labels, _probability):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic metric failure")
        return 0.5

    monkeypatch.setattr(module, "_average_precision", lambda: metric)
    accounting = _accounting()
    with pytest.raises(RuntimeError, match="synthetic metric failure"):
        module._score(targets, accounting)
    assert calls == 2
    assert accounting["public_test_primary_metric_evaluations"] == 1


def test_public_scorer_has_one_metric_and_no_model_surface() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    source = ast.unparse(tree)
    assert source.count("average_precision_score(y, probability)") == 1
    assert "CatBoost" not in source
    assert "fit(" not in source
    assert "predict_proba" not in source
    assert "GIN" not in source
    assert "third_family_task_slots_consumed': 0" in source
    parser_options = {
        constant.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        for constant in node.args
        if isinstance(constant, ast.Constant) and isinstance(constant.value, str)
    }
    assert parser_options == {"--score"}
