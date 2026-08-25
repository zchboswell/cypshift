from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT = (
    BENCHMARK
    / "global_v2_maplight_robustness_scoring_capability_reacceptance_contract.json"
)
D128 = BENCHMARK / "global_v2_maplight_robustness_scoring_capability_contract.json"
D129 = BENCHMARK / "global_v2_maplight_robustness_scoring_capability_rejection.json"
D126 = BENCHMARK / "global_v2_maplight_robustness_no_fit_acceptance.json"
D127_CLAIM = BENCHMARK / "global_v2_maplight_robustness_execution_claim.json"
SCORING_COMPILER = (
    ROOT
    / "research"
    / "maplight-fixed"
    / "global_v2_maplight_robustness_scoring_compiler.py"
)
OLD_DRIVER = (
    ROOT
    / "research"
    / "maplight-fixed"
    / "run_global_v2_maplight_robustness_scoring_capability_acceptance.py"
)


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_contract_binds_green_integrated_d129_and_all_parents() -> None:
    contract = _load(CONTRACT)
    assert contract["gate"] == (
        "G2_7F_MAPLIGHT_ROBUSTNESS_SCORING_CAPABILITY_REACCEPTANCE_CONTRACT_FROZEN"
    )
    assert contract["status"] == (
        "contract_only_distinct_attempt_no_new_implementation_or_official_operation"
    )
    parents = contract["parents"]
    assert parents["d128_scoring_capability_contract"]["sha256"] == _sha(D128)
    assert parents["d129_terminal_rejection"]["sha256"] == _sha(D129)
    assert parents["d126_no_fit_acceptance"]["sha256"] == _sha(D126)
    assert parents["permanently_unusable_d127_claim"]["sha256"] == _sha(
        D127_CLAIM
    )
    integrated = contract["integrated_parent_evidence"]
    assert integrated["commit"] == contract["base_commit"]
    assert integrated["post_main_ci_run"] == 32904446518
    assert integrated["post_main_ci_status"] == "success"


def test_d128_attempt_remains_consumed_and_old_driver_is_barred() -> None:
    contract = _load(CONTRACT)
    rejection = _load(D129)
    disposition = contract["d129_disposition"]
    assert rejection["attempt_accounting"]["attempts_consumed"] == 1
    assert rejection["attempt_accounting"]["attempts_remaining"] == 0
    assert disposition["old_attempts_remaining"] == 0
    assert disposition["old_acceptance_published"] is False
    assert disposition["old_acceptance_driver_current_sha256"] == _sha(OLD_DRIVER)
    assert disposition["reuse_old_attempt"] is False
    assert disposition["reuse_old_root"] is False
    assert disposition["reuse_old_driver"] is False
    assert disposition["reinterpret_old_determinism_as_acceptance"] is False


def test_occam_boundary_reuses_only_the_unchanged_scoring_compiler() -> None:
    contract = _load(CONTRACT)
    primitive = contract["reused_scientific_primitive"]
    assert primitive["sha256"] == _sha(SCORING_COMPILER)
    assert primitive["reuse_authorized_only_if_byte_identical"] is True
    assert primitive["output_columns"] == [
        "molecule_id",
        "endpoint",
        "standardized_structure_hash",
        "primary_component_hash",
        "source_file",
        "point",
        "low",
        "high",
    ]
    boundary = contract["occam_boundary"].lower()
    for forbidden_addition in ("model", "candidate", "seed", "claim"):
        assert forbidden_addition in boundary


def test_new_attempt_has_fixed_deep_root_and_no_cli_override() -> None:
    attempt = _load(CONTRACT)["new_single_attempt"]
    assert attempt["attempts"] == 1
    assert attempt["attempt_id"] == (
        "G2-7F-SCORING-CAPABILITY-REACCEPTANCE-ATTEMPT-1"
    )
    parent = Path(attempt["fixed_parent_root"])
    root = Path(attempt["fixed_work_root"])
    assert parent == Path("/tmp/cypshift-g2-7f")
    assert root == parent / "scoring-capability-attempt-1"
    assert root.is_absolute()
    assert ".." not in root.parts
    assert len(root.parts) >= 4
    assert attempt["cli_root_or_output_override"] is False
    assert attempt["future_driver_path"].endswith("_acceptance_v2.py")
    assert attempt["success_terminal_path"].endswith("_acceptance_v2.json")


def test_preflight_proves_cleanup_safety_before_any_work() -> None:
    preflight = _load(CONTRACT)["fail_before_work_preflight"]
    chronology = preflight["chronology"]
    assert "still-absent fixed work root" in chronology[4]
    assert "only after every preflight passes" in chronology[5]
    assert set(preflight["operations_before_preflight_pass"].values()) == {0}
    adversaries = " ".join(preflight["adversarial_requirements"]).lower()
    for required in (
        "shallow three-component root",
        "root or parent symlink",
        "existing root",
        "changed contract",
        "d-128 driver",
    ):
        assert required in adversaries


def test_terminal_requires_cleanup_before_one_no_replace_publication() -> None:
    rules = _load(CONTRACT)["execution_and_terminal_rules"]
    requirements = " ".join(rules["requirements"]).lower()
    assert "byte-identical two-file" in requirements
    assert "zero confirmatory value suffix decodes" in requirements
    assert "verify fixed work root and parent absent before publishing" in requirements
    assert "exactly one no-replace" in requirements
    failure = rules["failure_rule"].lower()
    for forbidden in (
        "no retry",
        "resume",
        "alternate root",
        "overwrite",
        "replacement",
        "reinterpretation",
    ):
        assert forbidden in failure


def test_contract_changes_no_science_and_grants_no_current_authority() -> None:
    contract = _load(CONTRACT)
    science = contract["unchanged_future_science"]
    assert science["minimum_total_fits"] == 720
    assert science["maximum_total_fits"] == 1020
    assert science["minimum_prediction_identities"] == 562752
    assert science["maximum_prediction_identities"] == 797232
    assert science["selection_tokens"] == 1
    assert science["runner_ups"] == 0
    assert science["hard_gpu_hours"] == 0
    assert set(contract["current_milestone_accounting"].values()) == {0}
    assert set(contract["current_authority"].values()) == {False}


def test_next_gate_remains_synthetic_and_cannot_skip_to_official_work() -> None:
    next_gate = _load(CONTRACT)["next_gate"].lower()
    for required in (
        "reviewed signed integration",
        "green post-main ci",
        "cleanup-root safety before work",
        "exactly one two-root",
        "zero real fit",
        "zero development metric",
        "do not implement the scientific runner",
        "create or consume a claim",
        "open an official byte",
        "access confirmatory truth",
        "use leaderboard evidence for selection",
    ):
        assert required in next_gate


def test_contract_contains_no_private_portal_result_fields() -> None:
    text = CONTRACT.read_text(encoding="utf-8").lower()
    for forbidden in (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
        "remote_submission_id",
    ):
        assert forbidden not in text
