from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CLAIM_PATH = BENCHMARK / "global_v2_x1_acquisition_claim.json"
FAILURE_PATH = BENCHMARK / "global_v2_x1_acquisition_failure.json"
CLAIM_SHA256 = "f1bea8327896c0eb01a2a13032af265f1ed0b42d280109acdf10262ae1ba5c60"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_claim_has_exact_unconsumed_identity() -> None:
    claim = _load(CLAIM_PATH)
    assert _sha256(CLAIM_PATH) == CLAIM_SHA256
    assert claim["gate"] == "G2_5C_EXP_X1_ACQUISITION_CLAIM_FROZEN"
    assert claim["base_commit"] == "95d29a83962b7edfde460ba53db85c8fed021190"
    assert claim["claim_id"] == "g2-5c-x1-acquisition-attempt-1"
    assert claim["maximum_consumptions"] == 1
    assert claim["consumed"] is False


def test_claim_binds_all_parents_and_accepted_sources() -> None:
    claim = _load(CLAIM_PATH)
    for parent in claim["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]
    sources = {
        "compiler_sha256": ROOT
        / "research"
        / "external-transfer"
        / "global_v2_x1_compiler.py",
        "synthetic_driver_sha256": ROOT
        / "research"
        / "external-transfer"
        / "run_global_v2_x1_synthetic.py",
        "focused_tests_sha256": ROOT
        / "tests"
        / "test_openadmet_global_v2_x1_synthetic_compiler.py",
        "chemistry_source_sha256": ROOT / "src" / "cypshift" / "chemistry.py",
        "topology_source_sha256": ROOT
        / "src"
        / "cypshift"
        / "openadmet_topology.py",
        "root_lock_sha256": ROOT / "uv.lock",
    }
    assert claim["accepted_source_bindings"] == {
        name: _sha256(path) for name, path in sources.items()
    }


def test_exact_source_and_no_fallback_are_frozen() -> None:
    claim = _load(CLAIM_PATH)
    source = claim["source"]
    assert source["database"] == "ChEMBL"
    assert source["release"] == "chembl_37"
    assert source["release_date"] == "2026-05-01"
    assert source["doi"] == "10.6019/chembl.database.37"
    assert source["archive_url"].endswith("/chembl_37_sqlite.tar.gz")
    assert source["archive_sha256"] == (
        "33c203740555f96067710cdfc1c3c55d890660e5908ec5cbf5817492c290d281"
    )
    assert source["maximum_downloads"] == 1
    assert source["alternate_source_or_mirror"] is False
    challenge = claim["challenge_source"]
    parent = _load(BENCHMARK / "global_v2_experiment_contract.json")
    receipts = parent["inputs"]["accepted_artifacts"]
    assert challenge["root"] == (
        "/home/zbos/cypshift-private/openadmet-2026/r2b-official-v1"
    )
    assert challenge["dataset_revision"] == (
        parent["public_source_refresh"]["dataset"]["head_revision"]
    )
    for name in (
        "r2b_manifest_sha256",
        "direct_observations_sha256",
        "group_folds_sha256",
        "training_topology_sha256",
    ):
        assert challenge[name] == receipts[name]
    assert challenge["exact_training_structures"] == 4905
    assert "Do not parse target columns" in challenge["forbidden_capability"]


def test_future_adapter_bindings_block_consumption() -> None:
    claim = _load(CLAIM_PATH)
    assert all(value is None for value in claim["future_consumption_bindings"].values())
    preconditions = " ".join(claim["consumption"]["preconditions"])
    assert "real-source adapter" in preconditions
    assert "official-shaped synthetic" in preconditions
    assert "atomic no-replace creation" in claim["consumption"]["atomicity"]
    assert "remains consumed" in claim["consumption"]["atomicity"]
    assert "No retry" in claim["consumption"]["no_replace"]


def test_paths_are_fixed_attempt_absent_and_receipt_narrow() -> None:
    paths = {name: Path(value) for name, value in _load(CLAIM_PATH)["paths"].items()}
    attempt = paths["attempt_root"]
    receipt = paths["receipt_root"]
    assert all(path.is_absolute() for path in paths.values())
    assert attempt.name == "g2-5c-x1-acquisition-attempt-1"
    assert receipt.name == "g2-5c-x1-acquisition-attempt-1-receipt"
    assert all(
        path == attempt or attempt in path.parents or path == receipt
        for path in paths.values()
    )
    assert all(path not in {Path("/"), Path.home()} for path in paths.values())
    assert not attempt.exists()
    if receipt.exists():
        receipt_path = receipt / "receipt.json"
        assert not receipt.is_symlink()
        assert {path.name for path in receipt.iterdir()} == {"receipt.json"}
        assert receipt_path.is_file() and not receipt_path.is_symlink()
        assert stat.S_IMODE(receipt.stat().st_mode) == 0o555
        assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o444
        failure = _load(FAILURE_PATH)
        assert _sha256(receipt_path) == failure["private_aggregate_receipt"]["sha256"]


def test_network_read_and_target_boundaries_fail_closed() -> None:
    claim = _load(CLAIM_PATH)
    consumption = claim["consumption"]
    assert "exactly one HTTPS download request" in consumption["network_boundary"]
    assert "before listing or extraction" in consumption["network_boundary"]
    assert "/usr/bin/unshare --user --map-root-user --net" in consumption[
        "network_boundary"
    ]
    assert "read-only and immutable" in consumption["read_boundary"]
    assert "fixed challenge_source root" in consumption["read_boundary"]
    targets = claim["target_verification_before_activity_query"]
    assert targets["organism"] == "Homo sapiens"
    assert targets["target_type"] == "SINGLE PROTEIN"
    assert targets["targets"] == {
        "CYP1A2": "CHEMBL3356",
        "CYP2C9": "CHEMBL3397",
        "CYP2D6": "CHEMBL289",
        "CYP3A4": "CHEMBL340",
    }
    assert "before an activity query" in targets["failure"]


def test_support_and_resource_falsifiers_are_conjunctive() -> None:
    claim = _load(CLAIM_PATH)
    support = claim["support_falsifier"]
    assert support["minimum_novel_eligible_molecules_per_endpoint"] == 1000
    assert support["minimum_family_safe_external_components_per_endpoint_per_outer_cell"] == 750
    assert support["all_four_endpoints_required"]
    assert support["all_outer_cells_required"]
    assert "no source fallback" in support["failure"]
    lineage = support["decision_lineage"]
    assert "accepted compiler hash" in lineage
    assert "all challenge_source receipts" in lineage
    assert "complete union-node/edge/component receipt" in lineage
    resources = claim["resource_falsifier"]
    assert resources["cpu_core_hours"] <= 800
    assert resources["gpu_hours"] == 0
    assert resources["maximum_restricted_storage_gb"] <= 200
    assert resources["process_concurrency"] == 1
    assert resources["model_fits"] == 0
    assert "no retry" in resources["rule"].lower()


def test_cleanup_keeps_only_aggregate_receipt() -> None:
    claim = _load(CLAIM_PATH)
    terminal = claim["terminal_receipt"]
    assert len(terminal["allowed_statuses"]) == 5
    assert "no row-level external values" in terminal["publication"]
    cleanup = claim["cleanup"]
    assert cleanup["required"]
    assert cleanup["delete_after_aggregate_receipt_acceptance"] == [
        "attempt_root including archive_path, extract_root, private_root and terminal_root"
    ]
    assert cleanup["retain"] == [
        "receipt_root aggregate hashes, counts, resources, accounting, decision and cleanup receipt"
    ]
    assert "receipt_root absent" in cleanup["receipt_publication"]
    assert "atomically with no replace" in cleanup["receipt_publication"]
    assert "remove all write bits" in cleanup["receipt_publication"]


def test_claim_freeze_has_zero_execution_authority_and_operations() -> None:
    claim = _load(CLAIM_PATH)
    current = claim["current_authority"]
    assert current["claim_and_static_tests"]
    assert not any(
        value for name, value in current.items() if name != "claim_and_static_tests"
    )
    future = claim["post_adapter_integration_authority"]
    assert future["maximum_consumptions"] == 1
    assert future["maximum_downloads"] == 1
    assert future["archive_and_external_support_compilation"]
    assert future["official_identity_inputs"]
    assert future["official_training_structures"]
    assert future["maximum_official_training_structures"] == 4905
    assert future["official_fold_identity_capability"]
    assert not future["official_target_values"]
    assert not future["official_target_or_feature_inputs"]
    assert not any(
        future[name]
        for name in (
            "official_target_or_feature_inputs",
            "model_fitting",
            "prediction_generation",
            "metric_evaluation",
            "submission",
            "upload",
        )
    )
    accounting = claim["current_milestone_accounting"]
    assert accounting["acquisition_claims_created"] == 1
    assert all(
        value == 0
        for name, value in accounting.items()
        if name != "acquisition_claims_created"
    )
    assert "Do not consume this claim" in claim["next_gate"]
