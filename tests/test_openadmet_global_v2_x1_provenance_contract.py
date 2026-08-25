from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_x1_provenance_contract.json"
CONTRACT_SHA256 = "a51f81a411e35e6514cbf2739a382b63b6c4db2e379e18004907a8e590a21c1d"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_x1_provenance_contract_has_exact_identity_and_parents() -> None:
    contract = _load(CONTRACT_PATH)
    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_x1_provenance_contract.v1"
    )
    assert contract["gate"] == "G2_5A_EXP_X1_PROVENANCE_CONTRACT_FROZEN"
    assert contract["status"] == "contract_only_metadata_review"
    assert contract["base_commit"] == "b89fdfdd0b61d2c973ffe6c4fb06ff1b02f9bbf3"
    for parent in contract["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]


def test_x1_contract_selects_one_exact_four_endpoint_source() -> None:
    contract = _load(CONTRACT_PATH)
    selection = contract["source_selection"]
    source = contract["source_identity"]
    assert selection["selected_source"] == "ChEMBL 37"
    assert "exactly one source" in selection["policy"]
    assert "reject EXP-X1" in selection["no_fallback"]
    assert set(selection["rejected_candidates"]) == {
        "OpenADMET Octant CYP inhibition release",
        "PubChem CYP assays",
        "Pretrained CheMeleon or other third-party weights",
    }
    assert source["release"] == "chembl_37"
    assert source["release_date"] == "2026-05-01"
    assert source["doi"] == "10.6019/chembl.database.37"
    assert source["archive_url"].endswith("/chembl_37_sqlite.tar.gz")
    assert source["archive_sha256"] == (
        "33c203740555f96067710cdfc1c3c55d890660e5908ec5cbf5817492c290d281"
    )
    assert not source["archive_acquired_at_freeze"]
    assert source["license"]["name"] == (
        "Creative Commons Attribution-ShareAlike 3.0 Unported"
    )


def test_x1_contract_freezes_exact_human_single_protein_targets() -> None:
    contract = _load(CONTRACT_PATH)
    targets = contract["endpoint_targets"]
    assert {name: value["target_chembl_id"] for name, value in targets.items()} == {
        "CYP1A2": "CHEMBL3356",
        "CYP2C9": "CHEMBL3397",
        "CYP2D6": "CHEMBL289",
        "CYP3A4": "CHEMBL340",
    }
    assert all(value["organism"] == "Homo sapiens" for value in targets.values())
    assert all(value["tax_id"] == 9606 for value in targets.values())
    assert all(value["target_type"] == "SINGLE PROTEIN" for value in targets.values())


def test_x1_contract_preserves_provenance_and_uses_exact_ic50_only() -> None:
    contract = _load(CONTRACT_PATH)
    preservation = contract["provenance_and_preservation"]
    eligibility = contract["eligibility"]
    assert {
        "activities",
        "assays",
        "target_dictionary",
        "molecule_dictionary",
        "compound_structures",
        "docs",
        "source",
    } == set(preservation["required_tables"])
    assert {"standard_relation", "activity_comment", "data_validity_comment"} <= set(
        preservation["required_activity_fields"]
    )
    filters = eligibility["activity_filter"]
    assert filters["standard_type"] == "IC50"
    assert filters["standard_relation"] == "="
    assert filters["standard_units"] == "nM"
    assert filters["standard_flag"] == 1
    assert filters["potential_duplicate"] == 0
    assert filters["data_validity_comment"] is None
    assert filters["minimum_assay_confidence_score"] == 9
    assert "0.011" in eligibility["normalization"]
    assert "authorizes no averaging rule" in eligibility["replicates"]


def test_x1_contract_blocks_exact_equivalent_and_family_leakage() -> None:
    overlap = _load(CONTRACT_PATH)["challenge_overlap_and_folds"]
    assert "4,905" in overlap["global_exact_equivalent_rule"]
    assert "remove every external molecule" in overlap["global_exact_equivalent_rule"]
    assert "held-out challenge component" in overlap["outer_fold_rule"]
    assert "every inner validation component" in overlap["inner_fold_rule"]
    assert "Confirmatory truth remains sealed" in overlap["confirmatory_rule"]
    assert "Do not open or use blinded-test structures" in overlap["blinded_test_rule"]
    assert overlap["evaluation_population"].startswith("Score only challenge rows")


def test_x1_contract_support_falsifier_is_all_endpoint_and_no_fallback() -> None:
    contract = _load(CONTRACT_PATH)
    support = contract["prospective_support_falsifier"]
    assert support[
        "minimum_novel_molecules_per_endpoint_after_global_exact_equivalent_removal"
    ] == 1000
    assert support[
        "minimum_family_safe_external_components_per_endpoint_in_every_outer_cell"
    ] == 750
    assert support["all_four_endpoints_required"]
    assert "Reject EXP-X1 immediately" in support["decision"]
    assert "add a source" in support["decision"]
    arithmetic = contract["later_experiment_boundary"]["source_specific_arithmetic"]
    assert "0.100 absolute CYP3A4 MAE" in arithmetic
    assert "0.025 four-endpoint macro" in arithmetic


def test_x1_contract_inherits_exact_acceptance_and_resource_margin() -> None:
    contract = _load(CONTRACT_PATH)
    experiment = contract["later_experiment_boundary"]
    acceptance = experiment["acceptance"]
    assert experiment["baseline"]["component_macro_mae"] == 0.5838
    assert acceptance["minimum_relative_primary_improvement"] == 0.05
    assert acceptance["minimum_absolute_component_macro_mae_improvement"] == 0.025
    assert acceptance["maximum_endpoint_mae_degradation"] == 0.02
    assert acceptance["external_no_external_ablation_must_pass"]
    assert acceptance["all_conditions_conjunctive"]
    resources = contract["resource_boundary"]
    assert resources["parent_ceiling"] == {
        "cpu_core_hours": 1000,
        "gpu_hours": 220,
        "restricted_storage_gb": 250,
    }
    assert resources["future_maximum_with_twenty_percent_margin"] == {
        "cpu_core_hours": 800,
        "gpu_hours": 176,
        "restricted_storage_gb": 200,
    }


def test_x1_contract_opens_no_records_or_scientific_authority() -> None:
    contract = _load(CONTRACT_PATH)
    metadata = contract["metadata_review"]
    assert metadata["external_activity_records_opened"] == 0
    assert metadata["external_dataset_files_downloaded"] == 0
    assert metadata["official_challenge_inputs_opened"] == 0
    accounting = contract["current_milestone_accounting"]
    assert accounting["inherited_prefreeze_external_preview_minimum_records"] == 45
    assert all(
        value == 0
        for name, value in accounting.items()
        if name != "inherited_prefreeze_external_preview_minimum_records"
    )
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"]
    assert authority["metadata_review"]
    assert not any(
        value
        for name, value in authority.items()
        if name not in {"contract_and_static_tests", "metadata_review"}
    )
    assert "synthetic-only ChEMBL compiler" in contract["next_gate"]
    assert "single-use acquisition claim" in contract["next_gate"]
    assert "Do not download the archive" in contract["next_gate"]
