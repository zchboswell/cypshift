from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
CONTRACT_PATH = ROOT / "benchmarks" / "openadmet_cyp_2026" / "validation_contract.json"


def load_contract() -> dict[str, object]:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_r2_input_chain_and_direct_compiler_are_receipt_bound() -> None:
    contract = load_contract()
    assert contract["schema_version"].endswith(".v2")
    assert contract["gate"] == "R2_VALIDATION_CONTRACT_V2_FROZEN"
    assert contract["supersedes"]["commit"] == (
        "2abcc107f36cc25f6bc1bb3277efe7e0158fe22e"
    )
    inputs = contract["input_chain"]
    assert inputs["dataset_revision"] == "85f8b358d0a2056a98b990dd75d3b3ec9247862b"
    assert inputs["direct_source"] == {
        "path": "cyp-challenge-TRAIN_inhibition.csv",
        "sha256": "b8f79addd266fb6f9f4c222c5e4e73d926362328b6a8d2841871a54e46bd2278",
        "rows": 4905,
    }
    assert inputs["r1_source_row_adapter"] == {
        "manifest_sha256": "331b4d439fb655a5e73a92238095e0519e8c3c9d62230fffda9ba22824cd6d08",
        "source_rows_sha256": "f9b058b32d24dd6af7d2f46dd77869cc3868e30d523fe5b52529acb465c03608",
        "molecules_sha256": "0291f961970c3c2ca032ab96651dd1395bd408834a6284f3bb01805e4321e5eb",
    }
    topology = inputs["r1_topology"]
    assert topology["schema_version"] == "cypshift.openadmet_cyp_2026.topology_audit.v1"
    assert (
        topology["manifest_sha256"]
        == "4df499a0c483835ea0eb23dfcaec6a7cf1b9b52d410b67c32a03636c6250e0dc"
    )
    assert (
        topology["molecule_audit_sha256"]
        == "5053fde0e34de221a7ea4c48a09674bf1227bc79f02235b4527d00567768174a"
    )
    assert (
        topology["training_topology_sha256"]
        == "710978431402dbb737244bf01a9f4d9e4e398181400627db680a4f12d06d3b8a"
    )
    compiler = contract["direct_compiler"]
    assert compiler["row_contract"]["expected_rows"] == 4905 * 4
    assert compiler["source_policy"]["allowed_files"] == [
        "cyp-challenge-TRAIN_inhibition.csv"
    ]
    assert "cyp-challenge-TRAIN_TDI.csv" in compiler["source_policy"]["forbidden_files"]
    assert set(compiler["state_rules"]) == {
        "missing",
        "complete",
        "orphan_auxiliary",
        "partial",
    }
    assert compiler["invalid_input_policy"].startswith("Fail before writing")
    assert "only complete" in compiler["eligibility"]
    assert compiler["semantic_firewall"][0] == "Call low/high/std reported fields only."
    assert (
        "Do not call them censoring, confidence, credible, or scoring intervals."
        in compiler["semantic_firewall"]
    )


def test_local_statuses_episodes_and_cliffs_are_frozen_without_rescue() -> None:
    contract = load_contract()
    local = contract["local_pairs"]
    assert local["relation"].startswith("unordered pair")
    assert local["eligibility"] == [
        "both observations complete",
        "inclusive Morgan/Tanimoto similarity >= 0.60",
        "same endpoint",
        "same frozen component",
    ]
    assert local["remote_pair_policy"].startswith("Do not use")
    assert (
        "low sample support is never LOCAL_FAILED"
        in local["status_rules"]["LOCAL_UNDERPOWERED"]
    )
    assert (
        "scientific or contract-integrity defect"
        in local["status_rules"]["LOCAL_FAILED"]
    )
    diagnostics = local["official_diagnostics"]
    assert diagnostics["CYP1A2"] == {
        "eligible_components": 18,
        "eligible_pairs": 28,
        "status": "LOCAL_UNDERPOWERED",
    }
    assert diagnostics["CYP2C9"] == {
        "eligible_components": 13,
        "eligible_pairs": 13,
        "status": "LOCAL_UNDERPOWERED",
    }
    assert diagnostics["CYP2D6"] == {
        "eligible_components": 14,
        "eligible_pairs": 28,
        "status": "LOCAL_UNDERPOWERED",
    }
    assert (
        diagnostics["CYP3A4"]["status"]
        == "LOCAL_SUPPORTED_PROVISIONAL_PENDING_FOLD_AUDIT"
    )
    episodes = contract["campaign_episodes"]
    assert episodes["selector_endpoints"] == ["CYP1A2", "CYP2C9", "CYP3A4"]
    assert episodes["excluded_selector_endpoints"] == ["CYP2D6"]
    assert episodes["absolute_potency_cutoff"] is None
    assert episodes["query_rule"]["cap"] == 10
    assert episodes["query_rule"]["ranking"] == [
        "similarity descending",
        "molecule_id ascending",
    ]
    assert "After anchor selection" in episodes["query_rule"]["availability"]
    assert "non-anchor measurement magnitudes" in episodes["query_rule"]["availability"]
    assert episodes["random_anchor_stress"]["seed"] == 20260818
    assert "SHA256" in episodes["random_anchor_stress"]["choice"]
    assert episodes["random_anchor_stress"]["purpose"].startswith("stress control")
    assert all(
        "selector_labeled_query_cells" in value
        for value in episodes["preliminary_diagnostics"].values()
        if isinstance(value, dict)
    )
    cliffs = contract["activity_cliff"]
    assert cliffs["eligibility"] == [
        "direct pair similarity >= 0.60",
        "absolute point delta >= 1.0",
        "reported bounds are directionally non-overlapping",
    ]
    assert cliffs["official_diagnostics"]["CYP3A4"] == {"pairs": 96, "components": 38}


def test_firewall_folds_scorecard_and_artifacts_have_no_model_authority() -> None:
    contract = load_contract()
    firewall = contract["public_truth_firewall"]
    assert firewall["public_episode_fields"] == [
        "episode_id",
        "protocol",
        "repeat",
        "outer_fold",
        "outer_group_id",
        "query_molecule_ids",
        "candidate_pool_id",
        "episode_policy_id",
    ]
    assert firewall["truth_fields"] == [
        "episode_id",
        "selector_cyp_truth",
        "anchor_molecule_id_truth",
        "query_truth_references",
        "query_truth_availability_masks",
    ]
    assert firewall["oracle_runner_fields"] == [
        "episode_id",
        "anchor_molecule_id_truth",
        "anchor_observation_references",
        "anchor_value_availability_mask",
    ]
    assert firewall["scorer_only_fields"] == [
        "episode_id",
        "selector_cyp_truth",
        "query_truth_references",
        "query_truth_availability_masks",
    ]
    assert "selector_cyp_truth" in firewall["public_exclusions"]
    assert "selector values" in firewall["public_exclusions"]
    assert "anchor identity" in firewall["public_exclusions"]
    assert "complete truth row" in firewall["oracle_rule"]
    assert (
        "episode-specific global training set" in firewall["anchor_global_fit_policy"]
    )
    assert firewall["inferred_candidate_pool"].startswith("Deferred")
    folds = contract["folds"]
    assert folds["seeds"] == [20260810, 20260811, 20260812]
    assert folds["outer_folds"] == 5 and folds["inner_folds"] == 4
    algorithm = folds["assignment_algorithm"]
    assert algorithm["policy_id"] == "openadmet-balanced-component-folds-sha256-v1"
    assert algorithm["outer_scope"] == "openadmet-direct-outer-v1"
    assert algorithm["inner_scope"] == ("openadmet-direct-inner-v1|outer=<outer_fold>")
    assert "reconstructed-family proxy" in folds["group_authority"]
    assert folds["fold_support_minimum"] == {
        "eligible_components_per_outer_validation_fold": 5,
        "eligible_pairs_per_outer_validation_fold": 20,
        "purpose": "A simple predeclared minimum for endpoint downgrade; do not regenerate topology or tune the minimum after observing outcomes.",
    }
    scorecard = contract["scorecard"]
    assert scorecard["primary_resampling"] == "component_bootstrap"
    assert scorecard["blocked_naming"] == ["official ST-RAE", "interval-hit"]
    assert set(contract["future_artifacts"]["required"]) == {
        "direct_observations.csv",
        "group_folds.csv",
        "campaign_episodes_public.csv",
        "campaign_episodes_truth.csv",
        "episode_label_masks.csv",
        "topology_viability.json",
        "manifest.json",
    }
    authority = contract["authority"]
    assert all(
        value is False for value in authority.values() if isinstance(value, bool)
    )
    assert "R2 v2 freezes the corrected contract only" in authority["status_note"]
    leakage = contract["acceptance"]["leakage_invariants"]
    assert leakage[0].startswith("GLOBAL_FAMILY_HOLDOUT exposes zero labels")
    assert leakage[1].startswith(
        "ANCHOR_EXPANSION_HOLDOUT exposes exactly the designated anchor"
    )
    assert (
        contract["acceptance"]["next_gate"]
        == "R2_VALIDATION_ARTIFACTS_IMPLEMENTED_AND_SYNTHETICALLY_ACCEPTED"
    )
