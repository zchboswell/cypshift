from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "benchmarks"
SOURCE_CONTRACT = BENCHMARKS / "maplight_source_contract.json"
EVALUATION_BUDGET = BENCHMARKS / "phase_0_75_evaluation_budget.json"
SHADOW_CONTRACT = BENCHMARKS / "tdc_cyp_shadow_v1_contract.json"
SHADOW_IMPLEMENTATION_CONTRACT = (
    BENCHMARKS / "tdc_cyp_shadow_v1_implementation_contract.json"
)


def _load(path: Path) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            assert key not in value, f"duplicate JSON key {key!r} in {path}"
            value[key] = item
        return value

    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
    )
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_maplight_source_contract_separates_exact_and_local_scoring() -> None:
    contract = _load(SOURCE_CONTRACT)

    assert contract["schema_version"] == "cypshift.maplight_source_contract.v1"
    blocks = contract["exact_feature_method"]["blocks_in_order"]
    assert [block["name"] for block in blocks] == [
        "morgan_count",
        "avalon_count",
        "erg",
        "rdkit_descriptors",
    ]
    assert sum(block["dimensions"] for block in blocks) == 2563
    assert contract["exact_feature_method"]["gin"]["combined_dimensions"] == (
        2563 + 300
    )
    assert contract["exact_estimator_method"]["seeds"] == [1, 2, 3, 4, 5]

    scoring = contract["published_scoring_semantics"]
    assert scoring["prediction_averaging_upstream"] is False
    assert "seed-specific" in scoring["notebook_operation"]
    assert "PyTDC 1.1.15" in scoring["frozen_local_rounding"]
    assert "cannot be independently recovered" in scoring[
        "historical_published_rounding"
    ]
    assert "separately labeled" in scoring["claim_boundary"]

    notebook = contract["notebook_execution_audit"]
    assert notebook["active_benchmark"] == "ppbr_az"
    assert notebook["unchanged_notebook_cyp_runs"] == 0
    assert contract["gin_provenance"]["tdc_veith_overlap_status"] == "unknown"
    assert contract["gin_provenance"]["discarded_transport_bytes"] == 7467310
    assert contract["gin_provenance"]["persisted_weight_bytes"] == 0
    assert contract["gin_provenance"]["artifact_license_status"] == (
        "not_disclosed_or_established"
    )
    assert all(value == 0 for value in contract["frozen_boundaries"].values())


def test_public_test_budget_has_exactly_three_unconsumed_families() -> None:
    budget = _load(EVALUATION_BUDGET)

    assert budget["schema_version"] == "cypshift.phase_0_75_evaluation_budget.v1"
    assert budget["source_contract"]["sha256"] == _sha256(SOURCE_CONTRACT)
    assert budget["family_count_per_task"] == 3
    assert [family["family_id"] for family in budget["families"]] == [
        "maplight_fixed",
        "maplight_gin",
        "final_locked_cypshift",
    ]
    for family in budget["families"]:
        assert set(family["status_by_task"]) == set(budget["tasks"])
        assert set(family["status_by_task"].values()) == {"reserved_unconsumed"}

    for family in budget["families"][:2]:
        assert family["declared_seeds"] == [1, 2, 3, 4, 5]
        assert family["authorized_primary_metric_evaluations_total"] == 18
        assert family["prediction_columns"][-1] == "prediction_probability_mean"

    assert budget["scoring_boundary"]["auroc_evaluations_authorized"] == 0
    assert budget["scoring_boundary"]["bootstrap_evaluations_authorized"] == 0
    assert budget["initial_accounting"]["consumed_task_slots"] == 0
    assert budget["initial_accounting"]["phase_0_75_public_test_labels_parsed"] == 0


def test_shadow_contract_is_global_label_independent_and_row_preserving() -> None:
    contract = _load(SHADOW_CONTRACT)

    assert contract["schema_version"] == "cypshift.tdc_cyp_shadow_contract.v1"
    population = contract["population"]
    assert sum(population["task_rows"].values()) == population["source_rows"]
    assert sum(population["task_membership_by_unique_structure"].values()) == (
        population["unique_standardized_structures"]
    )
    assert population["source_rows"] == 30038
    assert population["unique_standardized_structures"] == 15354
    assert population["row_policy"].startswith("Preserve every official source row")

    assert set(contract["protocols"]) == {"scaffold", "community"}
    community = contract["protocols"]["community"]
    assert community["similarity_threshold_inclusive"] == 0.6
    assert community["pair_distances"] == 15354 * 15353 // 2
    assert community["distance_storage"] == (
        "contiguous numpy.float64 one-dimensional array"
    )
    assert community["reordering"] is True

    assert [repeat["seed"] for repeat in contract["repeats"]] == [
        20260810,
        20260811,
        20260812,
    ]
    assert contract["fold_assignment"]["task_rule"].startswith(
        "Join the same global assignment"
    )
    assert contract["fold_assignment"]["outer_validation_inner_fold_sentinel"] == (
        ""
    )
    assert contract["input_projection_contract"]["rows"]["target_columns"] == 0
    assert contract["input_projection_contract"]["rows"]["public_test_rows"] == 0
    assert contract["assignment_firewall"]["assignment_allowed_inputs"] == [
        "the receipt-bound shadow_input_rows.csv projection",
        "this tracked contract",
        "the pinned core environment",
    ]
    assert "canonical molecule or provenance roots" in contract[
        "assignment_firewall"
    ]["forbidden_inputs"]
    assert contract["output_contract"]["shadow_rows"]["target_columns"] == 0
    assert contract["initial_accounting"] == {
        "target_values_used_for_assignment": 0,
        "public_test_rows_emitted": 0,
        "public_test_labels_parsed": 0,
        "feature_matrices_generated": 0,
        "model_fits": 0,
        "predictions": 0,
        "metric_evaluations": 0,
    }


def test_phase_0_75_contracts_bind_unchanged_public_source_manifest() -> None:
    public_sources = BENCHMARKS / "public_sources.json"
    expected = _sha256(public_sources)

    assert _load(SOURCE_CONTRACT)["public_source_manifest"]["sha256"] == expected
    assert (
        _load(SHADOW_CONTRACT)["source_contracts"]["public_sources"]["sha256"]
        == expected
    )


def test_shadow_implementation_contract_extends_the_reviewed_parent() -> None:
    contract = _load(SHADOW_IMPLEMENTATION_CONTRACT)

    assert contract["schema_version"] == (
        "cypshift.tdc_cyp_shadow_implementation_contract.v1"
    )
    assert contract["parent_contract"] == {
        "path": "benchmarks/tdc_cyp_shadow_v1_contract.json",
        "sha256": _sha256(SHADOW_CONTRACT),
    }
    assert contract["trusted_projection"]["raw_count_definitions"] == {
        "unique_raw_structures": (
            "Number of distinct exact decoded raw_structure strings across retained "
            "rows."
        ),
        "unique_standardized_hash_raw_pairs": (
            "Number of distinct (standardized_structure_hash, exact raw_structure) "
            "pairs across retained rows."
        ),
        "expected_unique_raw_structures": 15399,
        "expected_unique_standardized_hash_raw_pairs": 15399,
    }
    assert contract["assignment_environment"] == {
        "python": "3.11",
        "rdkit": "2026.03.5",
        "numpy": "2.4.6",
        "lock_sha256": _sha256(ROOT / "uv.lock"),
        "full_run_rule": (
            "Run the Taylor-Butina assignment alone in one child process. A parent "
            "watchdog polls child RSS once per second, kills the worker if wall time "
            "exceeds 240 minutes or observed RSS exceeds 12 GiB, and writes the "
            "frozen blocker receipt. Fail closed if RSS cannot be observed. Do not "
            "change dtype, threshold, fingerprint, ordering, or algorithm."
        ),
        "watchdog_poll_seconds": 1.0,
        "rss_source": (
            "ps -o rss= -p <worker_pid>, interpreted as KiB on the pinned macOS "
            "host, with a one-second command timeout"
        ),
    }
    for path in contract["implementation_paths"].values():
        assert (ROOT / path).is_file()
