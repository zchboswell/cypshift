from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
FEATURE_PATH = ROOT / "research/maplight-fixed/maplight_fixed_features.py"
VERIFIER_PATH = ROOT / "research/maplight-fixed/verify_parity.py"
BUILDER_PATH = ROOT / "research/maplight-fixed/build_features.py"
COMPAT_PATH = ROOT / "research/maplight-fixed/run_int8_compat.py"
COMPAT_CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_int8_compat_contract.json"
BLOCKER_RECEIPT_PATH = (
    ROOT / "benchmarks/receipts/maplight_fixed_stage_a_feature_blocker.json"
)


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _assignment_literal(tree: ast.Module, name: str) -> Any:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            ):
                return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                assert node.value is not None
                return ast.literal_eval(node.value)
    raise AssertionError(f"assignment {name!r} was not found")


def test_fixed_feature_source_matches_pinned_descriptor_order_and_dimensions() -> None:
    feature_tree = ast.parse(FEATURE_PATH.read_text(encoding="utf-8"))
    local_names = tuple(_assignment_literal(feature_tree, "DESCRIPTOR_NAMES"))

    assert len(local_names) == len(set(local_names)) == 200
    assert (
        hashlib.sha256(
            json.dumps(local_names, separators=(",", ":")).encode()
        ).hexdigest()
        == "76ed228002c5cd229e4cbd8d62c3b3a49d698425a5216884c5c7b1b337f4293a"
    )
    assert _assignment_literal(feature_tree, "BINARY_MORGAN_DIMENSIONS") == 2048
    assert _assignment_literal(feature_tree, "MORGAN_COUNT_DIMENSIONS") == 1024
    assert _assignment_literal(feature_tree, "AVALON_COUNT_DIMENSIONS") == 1024
    assert _assignment_literal(feature_tree, "ERG_DIMENSIONS") == 315
    assert _assignment_literal(feature_tree, "RDKIT_DESCRIPTOR_DIMENSIONS") == 200
    assert _assignment_literal(feature_tree, "MAPLIGHT_FIXED_DIMENSIONS") == 2563


def test_fixed_feature_container_is_fail_closed_and_writes_npy_v1(
    tmp_path: Path,
) -> None:
    features = _load_module("maplight_fixed_features_test", FEATURE_PATH)
    arrays = features.FixedFeatureArrays(
        raw_structure_sha256=(hashlib.sha256(b"CCO").hexdigest(),),
        binary_morgan=np.zeros((1, 2048), dtype=np.uint8),
        morgan_count=np.zeros((1, 1024), dtype=np.int8),
        avalon_count=np.zeros((1, 1024), dtype=np.int8),
        erg=np.zeros((1, 315), dtype="<f8"),
        rdkit_descriptors=np.zeros((1, 200), dtype="<f8"),
    )
    complete = arrays.maplight_fixed()
    assert complete.shape == (1, 2563)
    assert complete.dtype == np.dtype("<f8")
    assert not complete.flags.writeable
    assert all(
        not getattr(arrays, name).flags.writeable
        for name in (
            "binary_morgan",
            "morgan_count",
            "avalon_count",
            "erg",
            "rdkit_descriptors",
        )
    )

    output = tmp_path / "complete.npy"
    features.write_npy_v1(output, complete)
    assert output.read_bytes()[6:8] == bytes((1, 0))
    assert np.array_equal(np.load(output, allow_pickle=False), complete)


def test_signed_int8_container_policy_is_explicit_and_safe_default_is_unchanged() -> (
    None
):
    features = _load_module("maplight_int8_container_test", FEATURE_PATH)
    common = {
        "raw_structure_sha256": (hashlib.sha256(b"CCO").hexdigest(),),
        "binary_morgan": np.zeros((1, 2048), dtype=np.uint8),
        "morgan_count": np.zeros((1, 1024), dtype=np.int8),
        "avalon_count": np.zeros((1, 1024), dtype=np.int8),
        "erg": np.zeros((1, 315), dtype="<f8"),
        "rdkit_descriptors": np.zeros((1, 200), dtype="<f8"),
    }
    common["avalon_count"][0, 0] = -112

    with np.testing.assert_raises(features.MapLightFeatureError):
        features.FixedFeatureArrays(**common)
    compatible = features.FixedFeatureArrays(
        **common, count_policy="upstream_signed_int8"
    )
    assert int(compatible.avalon_count[0, 0]) == -112
    assert not compatible.avalon_count.flags.writeable


def test_int8_compat_runner_is_direct_label_free_and_contract_bound() -> None:
    tree = ast.parse(COMPAT_PATH.read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert set(functions) >= {
        "run_compatibility_parity",
        "build_compatibility_features",
        "_worker_main",
        "_validate_build_root",
    }
    assert [
        argument.arg for argument in functions["build_compatibility_features"].args.args
    ] == ["build_id"]
    assert (
        _assignment_literal(tree, "CONTRACT_SHA256")
        == hashlib.sha256(COMPAT_CONTRACT_PATH.read_bytes()).hexdigest()
    )
    assert _assignment_literal(tree, "PERSISTED_BLOCKS") == (
        "binary_morgan",
        "morgan_count",
        "avalon_count",
        "erg",
        "rdkit_descriptors",
    )
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any("measurements.csv" in value for value in literals)
    assert not any("CatBoost" in value for value in literals)
    assert not any("http://" in value or "https://" in value for value in literals)


def test_int8_compat_runner_imports_without_rdkit_and_freezes_accounting_shape() -> (
    None
):
    before = set(sys.modules)
    research_root = str(COMPAT_PATH.parent)
    sys.path.insert(0, research_root)
    try:
        runner = _load_module("maplight_int8_compat_import_test", COMPAT_PATH)
    finally:
        sys.path.remove(research_root)
    imported = set(sys.modules) - before

    assert not imported & {"rdkit", "pandas", "catboost", "torch", "dgl", "molfeat"}
    values = [1, 1, 30038, 15399, 5, 5, 0]
    assert list(runner._operation_accounting(values).values()) == values
    assert runner._arguments(["--build-id", "1"]).build_id == 1
    assert runner._arguments(["--parity"]).parity is True


def test_signed_int8_feature_progress_is_exact_and_stops_at_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_module = _load_module("maplight_int8_progress_test", FEATURE_PATH)
    raw_hash = hashlib.sha256(b"CCO").hexdigest()
    stats = feature_module.CountOverflowStats(0, 0, 0, 0, 0)
    monkeypatch.setattr(
        feature_module,
        "_validated_molecules",
        lambda _raw, _hashes: ((raw_hash,), [object()]),
    )
    monkeypatch.setattr(
        feature_module,
        "_binary_morgan",
        lambda _molecules: np.zeros((1, 2048), dtype=np.uint8),
    )
    monkeypatch.setattr(
        feature_module,
        "_erg",
        lambda _molecules: np.zeros((1, 315), dtype="<f8"),
    )
    monkeypatch.setattr(
        feature_module,
        "_rdkit_descriptors",
        lambda _molecules: np.zeros((1, 200), dtype="<f8"),
    )

    def count_block(_molecules: object, *, block: str) -> tuple[object, object]:
        return np.zeros((1, 1024), dtype=np.int8), stats

    monkeypatch.setattr(feature_module, "_upstream_count_block", count_block)
    completed: list[str] = []
    feature_module.featurize_raw_structures_upstream_int8(
        ("CCO",), (raw_hash,), block_completed=completed.append
    )
    assert completed == [
        "binary_morgan",
        "morgan_count",
        "avalon_count",
        "erg",
        "rdkit_descriptors",
    ]

    def fail_at_avalon(_molecules: object, *, block: str) -> tuple[object, object]:
        if block == "avalon_count":
            raise feature_module.MapLightFeatureError("stop", block=block, row_index=0)
        return np.zeros((1, 1024), dtype=np.int8), stats

    monkeypatch.setattr(feature_module, "_upstream_count_block", fail_at_avalon)
    completed.clear()
    with pytest.raises(feature_module.MapLightFeatureError):
        feature_module.featurize_raw_structures_upstream_int8(
            ("CCO",), (raw_hash,), block_completed=completed.append
        )
    assert completed == ["binary_morgan", "morgan_count"]


def test_worker_accounting_is_merged_before_array_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    research_root = str(COMPAT_PATH.parent)
    sys.path.insert(0, research_root)
    try:
        runner = _load_module("maplight_int8_worker_accounting_test", COMPAT_PATH)
    finally:
        sys.path.remove(research_root)
    revision = "a" * 40
    receipt = {
        "schema_version": "cypshift.maplight_int8_compat_worker.v1",
        "worker": "upstream",
        "source_revision": revision,
        "fixture_rows": 8,
        "descriptor_names": list(runner.features.descriptor_names()),
        "arrays": list(runner.UPSTREAM_ARRAYS),
        "boundaries": {str(key): value for key, value in runner.BOUNDARIES.items()},
        "accounting": {
            "fixture_arrays_generated": 5,
            "fixture_row_loads": 8,
            "boundary_conversions_attempted": 3,
            "boundary_conversions_completed": 3,
        },
    }
    (tmp_path / "worker_receipt.json").write_text(json.dumps(receipt))
    for name in runner.UPSTREAM_ARRAYS:
        (tmp_path / f"{name}.npy").write_bytes(b"not-an-array")
    total = {key: 0 for key in runner.PARITY_ACCOUNTING_KEYS}

    def fail_array(*_args: object) -> None:
        raise runner.CompatError("array rejected")

    monkeypatch.setattr(runner, "_array_record", fail_array)
    with pytest.raises(runner.CompatError):
        runner._load_worker(tmp_path, "upstream", revision, total)
    assert total["fixture_arrays_generated"] == 5
    assert total["fixture_row_loads"] == 8
    assert total["boundary_conversions_attempted"] == 3
    assert total["boundary_conversions_completed"] == 3


def test_compat_runner_enforces_platform_and_npy_v1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    research_root = str(COMPAT_PATH.parent)
    sys.path.insert(0, research_root)
    try:
        runner = _load_module("maplight_int8_platform_test", COMPAT_PATH)
    finally:
        sys.path.remove(research_root)

    executable_sha256 = runner._sha256(Path(sys.executable).resolve())
    parent = {
        "compatible_environment": {
            "resolved_package_licenses": {"fixture-package@1.0": "test"},
            "interpreter": {"installed_executable_sha256": executable_sha256},
            "execution_platform": {
                "operating_system": "macOS 26.6",
                "darwin_release": "25.6.0",
                "architecture": "arm64",
                "cpu": "Apple M1",
            },
        }
    }
    distribution = SimpleNamespace(metadata={"Name": "fixture-package"}, version="1.0")
    monkeypatch.setattr(
        runner.importlib.metadata, "distributions", lambda: [distribution]
    )
    monkeypatch.setattr(runner.platform, "python_version", lambda: "3.10.13")
    monkeypatch.setattr(runner.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(runner.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(runner.platform, "mac_ver", lambda: ("26.6", (), ""))
    monkeypatch.setattr(runner.platform, "release", lambda: "25.6.0")
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="Apple M1\n"),
    )
    runner._verify_environment(parent)
    monkeypatch.setattr(runner.platform, "release", lambda: "25.5.0")
    with pytest.raises(runner.CompatError):
        runner._verify_environment(parent)

    array = np.zeros((8, 2048), dtype=np.uint8)
    version_two = tmp_path / "binary_morgan.npy"
    with version_two.open("wb") as handle:
        np.lib.format.write_array(handle, array, version=(2, 0), allow_pickle=False)
    with pytest.raises(runner.CompatError):
        runner._array_record(version_two, array.shape, array.dtype)


def test_parity_verifier_has_one_bounded_supervisor_and_no_model_surface() -> None:
    tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert set(functions) >= {
        "verify_synthetic_parity",
        "_worker_main",
        "_run_worker",
        "_promote_success",
        "_write_failure",
    }
    assert [
        argument.arg for argument in functions["verify_synthetic_parity"].args.args
    ] == ["attempt"]
    assert len(VERIFIER_PATH.read_text(encoding="utf-8").splitlines()) <= 1125

    imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not imports & {"catboost", "torch", "dgl", "molfeat"}
    source = VERIFIER_PATH.read_text(encoding="utf-8")
    assert "measurements.csv" not in source
    assert "public_test" in source
    assert "CatBoost" not in source
    assert "subprocess.run" in source
    assert "timeout=600" in source


def test_real_feature_builder_is_one_bounded_label_free_operation() -> None:
    tree = ast.parse(BUILDER_PATH.read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert set(functions) >= {
        "build_label_free_features",
        "_read_shadow_rows",
        "_unique_raw_inputs",
        "_write_arrays",
        "_write_failure",
    }
    assert [
        argument.arg for argument in functions["build_label_free_features"].args.args
    ] == ["build_id"]
    assert len(BUILDER_PATH.read_text(encoding="utf-8").splitlines()) <= 650

    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any("measurements.csv" in value for value in string_literals)
    assert not any("CatBoost" in value for value in string_literals)
    assert _assignment_literal(tree, "BLOCKS") == (
        "binary_morgan",
        "morgan_count",
        "avalon_count",
        "erg",
        "rdkit_descriptors",
    )
    assert _assignment_literal(tree, "SCIENTIFIC_ZEROS") == {
        "target_values_parsed": 0,
        "model_fits": 0,
        "predictions": 0,
        "metric_evaluations": 0,
        "public_test_rows_used": 0,
        "public_test_labels_parsed": 0,
        "public_test_family_task_slots_consumed": 0,
        "gin_weight_bytes_downloaded": 0,
        "challenge_assumptions_added": 0,
    }
    build_argument = next(
        node
        for node in ast.walk(functions["_arguments"])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        and ast.literal_eval(node.args[0]) == "--build-id"
    )
    keywords = {keyword.arg: keyword.value for keyword in build_argument.keywords}
    assert ast.literal_eval(keywords["required"]) is True
    assert ast.literal_eval(keywords["choices"]) == (1, 2)
    assert "BUILD_ONE_BLOCKER_NAME" in {
        node.id
        for node in ast.walk(functions["build_label_free_features"])
        if isinstance(node, ast.Name)
    }
    assert "maplight-fixed-stage-a-features-v1-build-1-blocker" in string_literals


def test_research_modules_import_without_rdkit_or_heavy_model_dependencies() -> None:
    before = set(sys.modules)
    feature_module = _load_module("maplight_fixed_features_import_test", FEATURE_PATH)
    verifier_module = _load_module("maplight_fixed_verifier_import_test", VERIFIER_PATH)
    imported = set(sys.modules) - before

    assert callable(feature_module.featurize_raw_structures)
    assert inspect.signature(
        feature_module.featurize_raw_structures
    ).parameters.keys() == {
        "raw_structures",
        "expected_raw_sha256",
    }
    assert callable(verifier_module.verify_synthetic_parity)
    loaded_by_verifier = verifier_module._import_path(
        "maplight_fixed_features_verifier_loader_test", FEATURE_PATH
    )
    assert loaded_by_verifier.FixedFeatureArrays.__module__ in sys.modules
    assert not imported & {"rdkit", "pandas", "catboost", "torch", "dgl", "molfeat"}


def test_real_feature_blocker_is_precise_and_scientifically_zero() -> None:
    receipt = json.loads(BLOCKER_RECEIPT_PATH.read_text(encoding="utf-8"))

    assert receipt["schema_version"] == (
        "cypshift.maplight_fixed_stage_a_feature_blocker.v1"
    )
    assert receipt["failure"] == {
        "build_id": 1,
        "block": "avalon_count",
        "unique_raw_index": 66,
        "raw_structure_sha256": (
            "ad830254cb6e5ab45fbcd786a76eb71def998120dbbd794e719e53c6ddaacd1f"
        ),
        "persisted_block_arrays": 0,
    }
    diagnosis = receipt["diagnosis"]
    assert diagnosis["maximum_sparse_count"] == 144
    assert diagnosis["bins_above_127"] == 1
    assert diagnosis["frozen_maximum_sparse_count"] == 127
    assert receipt["decision"]["result"] == "fail"
    assert receipt["accounting"] == {
        "feature_build_attempts": 1,
        "diagnostic_raw_rows_parsed": 1,
        "persisted_block_arrays": 0,
        "target_values_parsed": 0,
        "model_fits": 0,
        "predictions": 0,
        "metric_evaluations": 0,
        "public_test_rows_used": 0,
        "public_test_labels_parsed": 0,
        "public_test_family_task_slots_consumed": 0,
    }
