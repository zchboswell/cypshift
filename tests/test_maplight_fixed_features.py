from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FEATURE_PATH = ROOT / "research/maplight-fixed/maplight_fixed_features.py"
VERIFIER_PATH = ROOT / "research/maplight-fixed/verify_parity.py"
UPSTREAM_PATH = (
    ROOT
    / "data/external/maplight_tdc/c249378c63232354d17083c83fe94fe728960a27/maplight.py"
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


def _upstream_descriptor_names(tree: ast.Module) -> tuple[str, ...]:
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "get_chosen_descriptors"
    )
    assignment = next(
        node
        for node in function.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "chosen_descriptors"
            for target in node.targets
        )
    )
    return tuple(ast.literal_eval(assignment.value))


def test_fixed_feature_source_matches_pinned_descriptor_order_and_dimensions() -> None:
    feature_tree = ast.parse(FEATURE_PATH.read_text(encoding="utf-8"))
    upstream_tree = ast.parse(UPSTREAM_PATH.read_text(encoding="utf-8"))
    local_names = tuple(_assignment_literal(feature_tree, "DESCRIPTOR_NAMES"))
    upstream_names = _upstream_descriptor_names(upstream_tree)

    assert local_names == upstream_names
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
    assert len(VERIFIER_PATH.read_text(encoding="utf-8").splitlines()) <= 1100

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
    assert not imported & {"rdkit", "pandas", "catboost", "torch", "dgl", "molfeat"}
