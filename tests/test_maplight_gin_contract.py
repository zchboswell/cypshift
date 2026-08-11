from __future__ import annotations

import ast
import hashlib
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "benchmarks/maplight_gin_contract.json"
RESEARCH_ROOT = ROOT / "research/maplight-gin"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_gin_contract_binds_tracked_sources_and_one_representation() -> None:
    contract = _contract()
    assert contract["schema_version"] == "cypshift.maplight_gin_contract.v2"
    parents = contract["parents"]
    for name in ("maplight_source_contract", "fixture"):
        record = parents[name]
        assert _sha256(ROOT / record["path"]) == record["sha256"]

    representation = contract["representation"]
    assert representation["upstream_call"] == (
        "PretrainedDGLTransformer(kind='gin_supervised_masking', dtype=float)"
    )
    assert representation["dimensions"] == 300
    assert representation["dtype"] == "numpy.float64"
    assert representation["pooling"] == "mean"
    assert representation["batch_size"] == 32
    assert contract["operations"]["real_builds"] == 2
    assert contract["stage_b_authority_after_repeat_gate"]["public_test"] is False


def test_gin_environment_is_isolated_and_fully_locked() -> None:
    contract = _contract()
    environment = contract["environment"]
    for field, hash_field in (
        ("python_version_path", "python_version_sha256"),
        ("project_path", "project_sha256"),
        ("lock_path", "lock_sha256"),
    ):
        assert _sha256(ROOT / environment[field]) == environment[hash_field]

    research_project = tomllib.loads((RESEARCH_ROOT / "pyproject.toml").read_text())
    root_project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    heavy = {"catboost", "dgl", "dgllife", "molfeat", "torch"}
    research_names = {
        dependency.split("==", maxsplit=1)[0]
        for dependency in research_project["project"]["dependencies"]
    }
    root_names = {
        dependency.split("[", maxsplit=1)[0]
        .split(">", maxsplit=1)[0]
        .split("=", maxsplit=1)[0]
        for dependency in root_project["project"]["dependencies"]
    }
    assert heavy <= research_names
    assert "python-dotenv" in research_names
    assert heavy.isdisjoint(root_names)
    assert research_project["project"]["requires-python"] == "==3.10.*"
    assert research_project["tool"]["uv"]["package"] is False


def test_gin_rights_and_firewalls_are_bounded() -> None:
    contract = _contract()
    rights = contract["rights_and_provenance"]
    assert rights["artifact_specific_license"] == "not_disclosed_in_metadata"
    assert rights["tdc_structure_overlap"] == "unknown"
    assert rights["tdc_target_overlap"] == "unknown"
    assert rights["allowed_claim"] == "pretrained representation transfer"
    assert contract["weight"]["redistribution"] == "forbidden_by_this_contract"
    assert set(contract["scientific_zeros_before_stage_b_models"].values()) == {0}
    assert contract["stage_b_authority_after_repeat_gate"]["controls"] == [
        "fixed_maplight",
        "gin_alone",
        "fixed_plus_gin",
        "fixed_plus_deterministically_row_shuffled_gin",
        "fixed_plus_same_dimensional_seeded_random_noise",
    ]


def test_gin_runner_has_one_direct_public_boundary() -> None:
    path = RESEARCH_ROOT / "build_gin_embeddings.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "main" in functions
    assert "_freeze_weight" in functions
    assert "_parity" in functions
    assert "_build" in functions
    assert path.resolve().is_relative_to(RESEARCH_ROOT.resolve())
    assert not path.resolve().is_relative_to((ROOT / "src").resolve())

    source = path.read_text(encoding="utf-8")
    assert "gin_supervised_masking" in source
    assert "PretrainedDGLTransformer" in source
    assert "public_test_labels" in source
    assert "MOLFEAT_MODEL_STORE_BUCKET" in source
