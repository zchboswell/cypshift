from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_maplight_execution_contract.json"
CLAIM_PATH = BENCHMARK / "global_v2_maplight_execution_claim.json"
CONTRACT_SHA256 = "962484b7e8f20ca9b9e37735e82c4db62766116a47c49c44dbc90d14db7985c2"
CLAIM_SHA256 = "59d7d6915fc3f9e8ae0cb1fef2af805eb3d4d68c641091d518e4e02683730659"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_execution_contract_and_unconsumed_claim_have_exact_identity() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert _sha256(CLAIM_PATH) == CLAIM_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_contract.v1"
    )
    assert contract["gate"] == (
        "G2_2C_MAPLIGHT_DEVELOPMENT_EXECUTION_CONTRACT_FROZEN"
    )
    assert contract["status"] == (
        "contract_and_unconsumed_claim_only_no_official_execution_yet"
    )
    assert contract["base_commit"] == "cfc23b357298a4708b7808fc963483c99a12d1c7"
    assert claim["status"] == "G2_2C_CLAIM_UNCONSUMED"
    assert claim["contract_sha256"] == CONTRACT_SHA256
    assert claim["base_commit"] == contract["base_commit"]
    assert claim["claim_id"] == contract["execution"]["claim_id"]
    assert contract["execution"]["claim_path"] == CLAIM_PATH.name


def test_execution_contract_binds_accepted_parents_and_implementation() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    for parent in contract["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]

    implementation = contract["accepted_implementation"]
    assert _sha256(ROOT / implementation["runner_path"]) == implementation[
        "runner_sha256"
    ]
    assert _sha256(ROOT / implementation["synthetic_compiler_path"]) == (
        implementation["synthetic_compiler_sha256"]
    )
    assert claim["runner_source_sha256"] == implementation["runner_sha256"]
    assert claim["synthetic_compiler_source_sha256"] == implementation[
        "synthetic_compiler_sha256"
    ]
    assert claim["g2_2a_contract_sha256"] == contract["parents"][
        "g2_2a_contract"
    ]["sha256"]
    assert claim["g2_2b_acceptance_sha256"] == contract["parents"][
        "g2_2b_acceptance"
    ]["sha256"]


def test_claim_is_single_use_and_cannot_yet_be_consumed() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    assert set(claim) == set(contract["claim_contract"]["required_fields"])
    assert claim["maximum_consumptions"] == 1
    assert contract["execution"]["maximum_claim_consumptions"] == 1
    assert claim["future_official_compiler_source_sha256"] is None
    assert claim["future_attempt_wrapper_source_sha256"] is None
    assert claim["future_official_shaped_synthetic_acceptance_sha256"] is None
    assert "atomically creating" in contract["execution"]["attempt_start"]
    assert "remains consumed" in contract["execution"]["attempt_start"]
    assert "tracked claim is a frozen unconsumed authorization template" in (
        contract["claim_contract"]["publication"]
    )


def test_official_population_preflight_and_replay_ceiling_are_exact() -> None:
    contract = _load(CONTRACT_PATH)
    population = contract["population_and_preflight"]
    assert population["label_free_assignment"] == {
        "all_molecules": 4905,
        "all_components": 4553,
        "development_molecules": 3908,
        "development_components": 3640,
        "confirmatory_molecules": 997,
        "confirmatory_components": 913,
    }
    assert population["minimum_support"] == {
        "development_finite_targets_per_endpoint": 750,
        "outer_validation_targets_per_endpoint_repeat_fold": 75,
        "inner_training_targets_per_endpoint_repeat_outer_inner": 400,
    }
    execution = contract["execution"]
    assert execution["replays"] == 2
    assert execution["maplight_fits_per_replay"] == 300
    assert execution["maplight_fits_total_ceiling"] == 600
    assert execution["outer_prediction_rows_per_replay"] == 3908 * 4 * 3
    assert execution["inner_prediction_rows_per_replay"] == 3908 * 4 * 3 * 4
    assert not execution["retry"]
    assert not execution["resume"]
    assert not execution["overwrite"]
    assert execution["resource_ceiling"] == {
        "cpu_core_hours": 200,
        "gpu_hours": 0,
        "restricted_storage_gb": 80,
        "maximum_wall_hours": 12,
    }


def test_claim_binds_exact_official_receipts_without_opening_sources() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    contract_receipts = {
        "dataset_revision": contract["official_inputs"]["dataset_revision"],
        **{
            name: value
            for name, value in contract["official_inputs"].items()
            if name.endswith("_sha256")
        },
    }
    assert claim["official_input_receipts"] == contract_receipts
    receipts = claim["official_input_receipts"]
    assert len(receipts["dataset_revision"]) == 40
    assert set(receipts["dataset_revision"]) <= set("0123456789abcdef")
    assert all(
        len(value) == 64 and set(value) <= set("0123456789abcdef")
        for name, value in receipts.items()
        if name != "dataset_revision"
    )
    assert "Reading any corresponding official file" in contract["official_inputs"][
        "read_boundary"
    ]


def test_contract_freeze_has_zero_official_and_forbidden_operations() -> None:
    contract = _load(CONTRACT_PATH)
    assert all(value == 0 for value in contract["current_milestone_accounting"].values())
    assert all(value == 0 for value in contract["forbidden_accounting"].values())
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"]
    assert authority["tracked_unconsumed_claim"]
    assert not any(
        value
        for name, value in authority.items()
        if name not in {"contract_and_static_tests", "tracked_unconsumed_claim"}
    )


def test_terminals_cleanup_and_next_gate_fail_closed() -> None:
    contract = _load(CONTRACT_PATH)
    terminal = contract["terminal_contract"]
    assert terminal["statuses"] == [
        "G2_2_FAILED",
        "G2_2_UNDERPOWERED",
        "G2_2_MAPLIGHT_REPRODUCED",
    ]
    assert terminal["status_specific_file_sets"]["G2_2_FAILED"] == [
        "failure.json",
        "manifest.json",
    ]
    assert terminal["status_specific_file_sets"]["G2_2_UNDERPOWERED"] == [
        "preflight.json",
        "manifest.json",
    ]
    assert len(
        terminal["status_specific_file_sets"]["G2_2_MAPLIGHT_REPRODUCED"]
    ) == 6
    assert "every forbidden counter must be zero" in terminal[
        "reproduction_acceptance"
    ]
    assert "no retry, resume, overwrite" in terminal["failure"]
    assert "Cleanup failure changes the status" in contract["execution"]["cleanup"]
    assert contract["next_gate"].startswith(
        "Implement only the additive official capability compiler"
    )
    assert "Do not consume the claim or open official inputs" in contract["next_gate"]
