from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "benchmarks" / "maplight_fixed_stage_a_contract.json"
SOURCE_CONTRACT_PATH = ROOT / "benchmarks" / "maplight_source_contract.json"
TARGET_PROJECTION_PATH = ROOT / "research/maplight-fixed/prepare_stage_a_targets.py"
CATBOOST_RUNNER_PATH = ROOT / "research/maplight-fixed/run_stage_a_catboost.py"


def _load_json(path: Path) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            assert key not in result, f"duplicate JSON key {key!r} in {path}"
            result[key] = value
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
    )
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_stage_a_contract_binds_source_shadow_and_compatible_environment() -> None:
    contract = _load_json(CONTRACT_PATH)
    source = _load_json(SOURCE_CONTRACT_PATH)

    assert contract["schema_version"] == ("cypshift.maplight_fixed_stage_a_contract.v1")
    frozen = contract["frozen_sources"]
    assert frozen["maplight_source_contract"]["sha256"] == _sha256(SOURCE_CONTRACT_PATH)
    assert frozen["maplight_repository"]["revision"] == source["repository"]["revision"]
    assert frozen["maplight_repository"]["tree"] == source["repository"]["tree"]
    assert frozen["maplight_repository"]["files"] == {
        name: item["sha256"] for name, item in source["repository"]["files"].items()
    }
    assert frozen["paper"]["pdf_sha256"] == source["paper"]["pdf"]["sha256"]
    assert frozen["shadow_benchmark"]["rows"] == 30038
    assert frozen["shadow_benchmark"]["rows_sha256"] == (
        "b633af0cbd5aa98a03ae77eb3e021eb32b441ae8133e24a2c9eb85394e41bc5f"
    )
    assert frozen["train_only_measurements"]["public_test_rows"] == 0

    environment = contract["compatible_environment"]
    for path_key, hash_key in (
        ("project_path", "project_sha256"),
        ("lock_path", "lock_sha256"),
        ("python_version_path", "python_version_sha256"),
    ):
        assert environment[hash_key] == _sha256(ROOT / environment[path_key])

    project = tomllib.loads((ROOT / environment["project_path"]).read_text())
    assert project["project"]["requires-python"] == "==3.10.*"
    assert project["project"]["dependencies"] == [
        "catboost==1.2.1",
        "numpy==1.25.2",
        "pandas==2.0.3",
        "rdkit==2023.3.3",
        "scikit-learn==1.3.0",
        "scipy==1.11.2",
    ]
    assert project["tool"]["uv"] == {
        "exclude-newer": "2023-08-29T00:00:00Z",
        "package": False,
    }

    lock = tomllib.loads((ROOT / environment["lock_path"]).read_text())
    assert lock["options"]["exclude-newer"] == environment["result_blind_cutoff_utc"]
    package_versions = {
        item["name"]: item["version"]
        for item in lock["package"]
        if "version" in item and item["name"] != "cypshift-maplight-fixed-reproduction"
    }
    for name, version in environment["direct_packages"].items():
        assert package_versions[name] == version
    license_packages = {
        item.rsplit("@", 1)[0] for item in environment["resolved_package_licenses"]
    }
    assert license_packages == set(package_versions)

    cutoff = datetime.fromisoformat(environment["result_blind_cutoff_utc"])
    for package in lock["package"]:
        artifacts = ([package["sdist"]] if "sdist" in package else []) + package.get(
            "wheels", []
        )
        for artifact in artifacts:
            uploaded = artifact.get("upload-time")
            if uploaded is not None:
                assert datetime.fromisoformat(uploaded.replace("Z", "+00:00")) <= cutoff


def test_stage_a_fixture_and_feature_contract_are_exact_and_fail_closed() -> None:
    contract = _load_json(CONTRACT_PATH)
    fixture = contract["parity_fixture"]
    fixture_path = ROOT / fixture["path"]

    assert _sha256(fixture_path) == fixture["sha256"]
    assert len(fixture_path.read_bytes()) == fixture["size_bytes"]
    with fixture_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == fixture["rows"] == 8
    assert list(rows[0]) == ["fixture_id", "pandas_index", "raw_smiles"]
    assert [int(row["pandas_index"]) for row in rows] == fixture[
        "pandas_index_in_file_order"
    ]
    assert rows[-2]["raw_smiles"] != rows[-1]["raw_smiles"]

    features = contract["feature_contract"]
    blocks = features["blocks"]
    assert features["complete_dimensions"] == sum(
        blocks[name]["dimensions"]
        for name in ("morgan_count", "avalon_count", "erg", "rdkit_descriptors")
    )
    assert features["maplight_fixed_slices"] == {
        "morgan_count": "0:1024",
        "avalon_count": "1024:2048",
        "erg": "2048:2363",
        "rdkit_descriptors": "2363:2563",
    }
    assert blocks["morgan_count"]["artifact_dtype"] == "numpy.int8"
    assert blocks["avalon_count"]["artifact_dtype"] == "numpy.int8"
    assert blocks["binary_morgan"]["parameters"]["includeChirality"] is True
    assert "0 through 127" in features["count_safety"]
    assert "Never wrap" in features["count_safety"]
    assert "Reject the complete" in features["nonfinite_policy"]
    assert fixture["expected_array_hash_status"].startswith(
        "Not generated at contract freeze"
    )
    assert "greater than 1" in " ".join(fixture["required_comparisons"])


def test_stage_a_ladder_has_six_unique_candidates_and_exact_accounting() -> None:
    contract = _load_json(CONTRACT_PATH)
    ladder = contract["candidate_ladder"]
    evaluation = contract["shadow_evaluation"]
    bootstrap = contract["paired_uncertainty"]

    outer_cells = (
        len(evaluation["tasks"])
        * len(evaluation["protocols"])
        * len(evaluation["repeats"])
    )
    assert outer_cells == evaluation["outer_cells"] == 18
    candidates = ladder["candidates"]
    assert len(candidates) == ladder["total_unique_candidates"] == 6
    assert len({item["configuration_id"] for item in candidates}) == 6
    assert all(item["fits"] == outer_cells * len(item["seeds"]) for item in candidates)
    assert sum(item["fits"] for item in candidates) == ladder["total_model_fits"]
    assert ladder["total_model_fits"] == 180
    assert ladder["total_catboost_fits"] == 162
    assert ladder["total_extra_trees_fits"] == 18
    assert ladder["inner_fits"] == evaluation["inner_folds_used"] == 0

    full_blocks = ["morgan_count", "avalon_count", "erg", "rdkit_descriptors"]
    full_catboost = [
        item
        for item in candidates
        if item["feature_blocks"] == full_blocks and item["estimator"] == "catboost"
    ]
    assert len(full_catboost) == 1
    assert full_catboost[0]["seeds"] == [1, 2, 3, 4, 5]

    assert evaluation["model_prediction_rows"] == (
        evaluation["outer_validation_rows_across_cells"] * 10
    )
    assert (
        evaluation["derived_r5_mean_probability_rows"]
        == evaluation["outer_validation_rows_across_cells"]
    )
    assert evaluation["point_metric_evaluations"] == (
        evaluation["model_prediction_vectors"]
        + evaluation["derived_r5_mean_probability_vectors"]
    )
    assert bootstrap["bootstrap_metric_evaluations"] == (
        bootstrap["bootstrap_configurations_scored"]
        * bootstrap["bootstrap_cells"]
        * bootstrap["replicates_accepted_per_protocol"]
    )
    assert bootstrap["total_metric_evaluations_including_points"] == (
        bootstrap["bootstrap_metric_evaluations"]
        + evaluation["point_metric_evaluations"]
    )
    assert bootstrap["total_metric_evaluations_including_points"] == 108198
    assert "adds no metric evaluation" in bootstrap["group_concentration_check"]


def test_stage_a_firewalls_public_test_and_keeps_core_lightweight() -> None:
    contract = _load_json(CONTRACT_PATH)
    accounting = contract["initial_accounting"]

    scientific_zero_keys = {
        "synthetic_feature_arrays_generated",
        "real_feature_rows_parsed",
        "real_feature_matrices_generated",
        "raw_measurement_labels_parsed",
        "training_target_values_parsed",
        "scoring_target_values_parsed",
        "model_fits",
        "model_prediction_vectors",
        "derived_prediction_vectors",
        "metric_evaluations",
        "public_test_rows_used",
        "public_test_labels_parsed",
        "public_test_predictions",
        "public_test_metric_evaluations",
        "public_test_family_task_slots_consumed",
        "gin_weight_bytes_downloaded",
        "challenge_assumptions_added",
    }
    assert all(accounting[key] == 0 for key in scientific_zero_keys)
    assert (
        contract["process_firewall"]["trusted_target_projection"][
            "public_test_label_parses"
        ]
        == 0
    )
    assert contract["process_firewall"]["trusted_target_projection"][
        "scoring_target_columns"
    ] == ["task", "molecule_id", "source_row", "target"]
    assert contract["process_firewall"]["trusted_target_projection"][
        "outer_training_target_columns"
    ] == ["task", "protocol", "repeat", "molecule_id", "source_row", "target"]
    assert (
        "public-test"
        in contract["process_firewall"]["feature_process"]["must_not_resolve"]
    )
    assert (
        "validation target"
        in contract["process_firewall"]["model_cell_process"]["must_not_resolve"]
    )
    assert contract["review_gates"]["before_public_test"].endswith(
        "This contract consumes no public-test family-task slot."
    )

    core = tomllib.loads((ROOT / "pyproject.toml").read_text())
    core_dependencies = " ".join(core["project"]["dependencies"]).lower()
    assert "catboost" not in core_dependencies
    assert "pandas" not in core_dependencies
    assert "torch" not in core_dependencies
    assert "molfeat" not in core_dependencies
    assert "dgl" not in core_dependencies


def test_stage_a_target_projection_is_one_direct_train_only_process() -> None:
    tree = ast.parse(TARGET_PROJECTION_PATH.read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert set(functions) >= {
        "prepare_targets",
        "_targets",
        "_write_csv",
        "_write_failure",
    }
    assert functions["prepare_targets"].args.args == []

    assignments = {
        target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance((target := node.targets[0]), ast.Name)
        and target.id in {"SCORING_COLUMNS", "TRAINING_COLUMNS", "ACCOUNTING"}
    }
    contract = _load_json(CONTRACT_PATH)
    firewall = contract["process_firewall"]["trusted_target_projection"]
    assert list(assignments["SCORING_COLUMNS"]) == firewall["scoring_target_columns"]
    assert (
        list(assignments["TRAINING_COLUMNS"])
        == firewall["outer_training_target_columns"]
    )
    assert assignments["ACCOUNTING"] == {
        "train_val_labels_parsed": 30038,
        "training_target_values_emitted": 144183,
        "scoring_target_values_emitted": 30038,
        "cell_target_files_emitted": 18,
        "public_test_rows_used": 0,
        "public_test_labels_parsed": 0,
        "feature_arrays_opened": 0,
        "model_fits": 0,
        "predictions": 0,
        "metric_evaluations": 0,
        "gin_weight_bytes_downloaded": 0,
        "challenge_assumptions_added": 0,
    }
    imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not imports & {"catboost", "sklearn", "rdkit", "torch", "dgl", "molfeat"}


def test_target_projection_treats_tracked_contract_and_ignored_inputs_differently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module("stage_a_target_projection_mode_test", TARGET_PROJECTION_PATH)
    shadow_root = tmp_path / "shadow"
    measurement_root = tmp_path / "measurements"
    shadow_root.mkdir()
    measurement_root.mkdir()
    contract = tmp_path / "contract.json"
    shadow_rows = shadow_root / "rows.csv"
    shadow_manifest = shadow_root / "manifest.json"
    measurements = measurement_root / "measurements.csv"
    measurement_manifest = measurement_root / "manifest.json"
    contract.write_text(
        '{"schema_version":"cypshift.maplight_fixed_stage_a_contract.v1"}',
        encoding="utf-8",
    )
    for path in (shadow_rows, shadow_manifest, measurements, measurement_manifest):
        path.write_text("fixture\n", encoding="utf-8")
        path.chmod(0o444)
    shadow_root.chmod(0o555)
    measurement_root.chmod(0o555)
    for name, value in (
        ("CONTRACT_PATH", contract),
        ("SHADOW_ROOT", shadow_root),
        ("SHADOW_ROWS_PATH", shadow_rows),
        ("SHADOW_MANIFEST_PATH", shadow_manifest),
        ("MEASUREMENT_ROOT", measurement_root),
        ("MEASUREMENT_TDC_ROOT", measurement_root),
        ("MEASUREMENT_PATH", measurements),
        ("MEASUREMENT_MANIFEST_PATH", measurement_manifest),
    ):
        monkeypatch.setattr(module, name, value)
    for name, path in (
        ("CONTRACT_SHA256", contract),
        ("SHADOW_ROWS_SHA256", shadow_rows),
        ("SHADOW_MANIFEST_SHA256", shadow_manifest),
        ("MEASUREMENT_SHA256", measurements),
        ("MEASUREMENT_MANIFEST_SHA256", measurement_manifest),
    ):
        monkeypatch.setattr(module, name, _sha256(path))
    monkeypatch.setattr(module, "_clean_revision", lambda: "a" * 40)
    try:
        assert module._verify_inputs() == "a" * 40
    finally:
        shadow_root.chmod(0o755)
        measurement_root.chmod(0o755)


def test_stage_a_catboost_runner_has_only_the_frozen_prediction_surface() -> None:
    tree = ast.parse(CATBOOST_RUNNER_PATH.read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert set(functions) >= {"run_predictions", "_worker", "_feature_matrix"}
    research_root = str(CATBOOST_RUNNER_PATH.parent)
    sys.path.insert(0, research_root)
    try:
        runner = _load_module("stage_a_catboost_runner_test", CATBOOST_RUNNER_PATH)
    finally:
        sys.path.remove(research_root)
    candidates = runner.CANDIDATES
    assert len(candidates) == 9
    assert [item[2] for item in candidates] == [1, 1, 1, 1, 1, 2, 3, 4, 5]
    assert all("extra" not in item[0] for item in candidates)

    constructors = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "CatBoostClassifier"
    ]
    assert len(constructors) == 1
    assert {keyword.arg for keyword in constructors[0].keywords} == {
        "random_strength",
        "random_seed",
        "verbose",
        "loss_function",
    }
    source = CATBOOST_RUNNER_PATH.read_text(encoding="utf-8")
    assert "scoring_targets.csv" not in source
    assert "average_precision" not in source
    assert "ExtraTrees" not in source
    assert 'metric_evaluations": 0' in source
