from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "benchmarks/maplight_gin_stage_b_contract.json"
SCORER = ROOT / "research/maplight-fixed/run_stage_b_inference.py"


def _assignment(module: ast.Module, name: str) -> ast.AST:
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return node.value
    raise AssertionError(f"missing assignment: {name}")


def test_stage_b_inference_matches_the_frozen_metric_budget() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    evaluation = contract["evaluation_contract"]
    assert evaluation["point_metric_evaluations"] == 198
    assert evaluation["sensitivity_point_metric_evaluations"] == 108
    assert evaluation["bootstrap"]["metric_evaluations"] == 144000
    assert evaluation["total_metric_evaluations"] == 144306
    source = SCORER.read_text(encoding="utf-8")
    assert "metrics == 198" in source
    assert "metrics == 306" in source
    assert "metrics == 144306" in source


def test_stage_b_inference_exposes_one_direct_operation() -> None:
    module = ast.parse(SCORER.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "run_inference" in functions
    assert "main" in functions
    assert [argument.arg for argument in functions["run_inference"].args.args] == []
    source = SCORER.read_text(encoding="utf-8")
    assert 'parser.add_argument("--run", action="store_true", required=True)' in source
    assert 'public_test_rows_used": 0' in source
    assert 'public_test_labels_parsed": 0' in source
    assert 'challenge_assumptions_added": 0' in source


def test_stage_b_inference_freezes_only_declared_configurations_and_stops_at_point_95() -> (
    None
):
    module = ast.parse(SCORER.read_text(encoding="utf-8"))
    new = _assignment(module, "NEW_CONFIGS")
    point = _assignment(module, "POINT_CONFIGS")
    boot = _assignment(module, "BOOT_CONFIGS")
    contrasts = _assignment(module, "CONTRASTS")
    assert isinstance(new, ast.Tuple) and len(new.elts) == 9
    assert isinstance(point, ast.Tuple) and len(point.elts) == 3
    assert isinstance(point.elts[2], ast.Starred)
    assert isinstance(boot, ast.Tuple) and len(boot.elts) == 4
    assert isinstance(contrasts, ast.Dict)
    assert {ast.literal_eval(key) for key in contrasts.keys} == {
        "primary",
        "shuffle_control",
        "noise_control",
    }
    source = SCORER.read_text(encoding="utf-8")
    assert '_require(maximum < 0.95, "AUPRC forensic threshold reached")' in source
    assert "Chemprop" not in source
    assert "tdc-public" not in source.lower()
