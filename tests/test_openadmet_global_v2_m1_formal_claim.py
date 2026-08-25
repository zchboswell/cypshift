from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
RESEARCH = ROOT / "research" / "multitask-mlp"
CLAIM_PATH = BENCHMARK / "global_v2_m1_formal_attempt_claim.json"
CONTRACT_PATH = BENCHMARK / "global_v2_m1_synthetic_contract.json"
ACCEPTANCE_PATH = BENCHMARK / "global_v2_m1_implementation_acceptance.json"
CLAIM_SHA256 = "d6693d11dba104b50a3b0d7785be0285f5a6db00ae9c9cf4346d1bbe13816497"
sys.path.insert(0, str(RESEARCH))
m1 = importlib.import_module("m1_runner")
synthetic = importlib.import_module("run_m1_synthetic")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_claim_is_exact_unconsumed_and_driver_authentic() -> None:
    claim = synthetic.load_formal_claim(CLAIM_PATH)
    assert _sha256(CLAIM_PATH) == CLAIM_SHA256
    assert claim["gate"] == "G2_4C_EXP_M1_FORMAL_ATTEMPT_CLAIM_FROZEN"
    assert claim["base_commit"] == "229d31c1afd5451b6158fcb3c008ad98fc6aa46a"
    assert claim["attempt_id"] == "g2-4c-m1-synthetic-attempt-1"
    assert claim["maximum_attempts"] == 1
    assert claim["consumed"] is False


def test_claim_binds_exact_parents_and_all_six_sources() -> None:
    claim = _load(CLAIM_PATH)
    assert claim["parents"] == {
        "synthetic_contract": {
            "path": CONTRACT_PATH.name,
            "sha256": _sha256(CONTRACT_PATH),
        },
        "implementation_acceptance": {
            "path": ACCEPTANCE_PATH.name,
            "sha256": _sha256(ACCEPTANCE_PATH),
        },
    }
    paths = {
        "research_pyproject_sha256": RESEARCH / "pyproject.toml",
        "research_python_pin_sha256": RESEARCH / ".python-version",
        "research_uv_lock_sha256": RESEARCH / "uv.lock",
        "m1_runner_sha256": RESEARCH / "m1_runner.py",
        "m1_synthetic_driver_sha256": RESEARCH / "run_m1_synthetic.py",
        "focused_test_sha256": ROOT
        / "tests"
        / "test_openadmet_global_v2_m1_synthetic_implementation.py",
    }
    assert claim["source_bindings"] == {
        name: _sha256(path) for name, path in paths.items()
    }


def test_claim_paths_are_absolute_fixed_and_destructively_narrow() -> None:
    paths = {name: Path(value) for name, value in _load(CLAIM_PATH)["paths"].items()}
    assert all(path.is_absolute() for path in paths.values())
    assert paths["environment_root"] == Path(
        "/home/zbos/code/cypshift/research/multitask-mlp/.venv"
    )
    assert paths["root_a"].name == "g2-4c-m1-synthetic-attempt-1-root-a"
    assert paths["root_b"].name == "g2-4c-m1-synthetic-attempt-1-root-b"
    assert paths["receipt_root"].name == "g2-4c-m1-synthetic-attempt-1-receipt"
    assert paths["cache_root"].name == "g2-4c-m1-synthetic-attempt-1-cache"
    assert (
        len({path.parent for name, path in paths.items() if name != "environment_root"})
        == 1
    )
    assert all(path not in {Path("/"), Path.home()} for path in paths.values())


def test_environment_and_formal_topology_are_frozen_without_timing() -> None:
    claim = _load(CLAIM_PATH)
    environment = claim["environment_receipt"]
    assert environment["python"] == "3.12.3"
    assert environment["numpy"] == "2.5.2"
    assert environment["rdkit"] == "2026.03.5"
    assert environment["torch"] == "2.13.0+cpu"
    assert environment["cuda_available"] is False
    assert environment["packages"] == 13
    assert environment["dedicated_cache"]
    assert environment["network_during_formal_roots"] is False
    formal = claim["formal_execution"]
    assert formal["roots"] == 2
    assert formal["fits_per_root"] == 16
    assert formal["fits_total"] == 32
    assert formal["epochs_per_fit"] == 300
    assert formal["training_rows"] == 3908
    assert formal["prediction_rows"] == 997
    assert formal["input_columns"] == 2248
    assert formal["maximum_concurrent_fits"] == 4
    assert formal["threads_per_fit"] == 4
    assert formal["gpu_hours"] == 0
    assert formal["network_launcher"] == "unshare --user --map-root-user --net"
    assert "no retry" in formal["no_replace"].lower()


def test_claim_freeze_runs_nothing_and_only_integration_opens_probe() -> None:
    claim = _load(CLAIM_PATH)
    current = claim["current_authority"]
    assert current["claim_contract_only"]
    assert not any(
        value for name, value in current.items() if name != "claim_contract_only"
    )
    future = claim["post_integration_authority"]
    assert future["claim_consumption"]
    assert future["formal_probe"]
    assert future["maximum_consumptions"] == 1
    assert not future["official_inputs"]
    assert not future["official_model_fits"]
    accounting = claim["current_milestone_accounting"]
    assert accounting["formal_claims_created"] == 1
    assert accounting["formal_claims_consumed"] == 0
    assert accounting["formal_probe_fits"] == 0
    assert all(
        value == 0
        for name, value in accounting.items()
        if name != "formal_claims_created"
    )
    assert "do not execute a fit before integration" in claim["next_gate"]
