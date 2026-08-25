from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_x1_synthetic_compiler_contract.json"
ACCEPTANCE_PATH = BENCHMARK / "global_v2_x1_synthetic_compiler_acceptance.json"
PARENT_PATH = BENCHMARK / "global_v2_x1_provenance_contract.json"
CONTRACT_SHA256 = "db36935e2fb7478f8e038f094a11bcdd47ed8574541b50b2a27170170eba3442"
ACCEPTANCE_SHA256 = "5ea379d18c7c3422c112726c25ba869e77fea91fb06ddac1f13d2529025001a8"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_x1_synthetic_compiler_contract_has_exact_identity_and_parent() -> None:
    contract = _load(CONTRACT_PATH)
    parent = contract["parent"]
    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026."
        "global_v2_x1_synthetic_compiler_contract.v1"
    )
    assert contract["gate"] == (
        "G2_5B_EXP_X1_SYNTHETIC_COMPILER_CONTRACT_FROZEN"
    )
    assert contract["status"] == (
        "synthetic_implementation_contract_only_no_acquisition_authority"
    )
    assert contract["base_commit"] == "877e8161b30d981ef764753caeb2b2892282168e"
    assert parent["path"] == PARENT_PATH.name
    assert parent["sha256"] == _sha256(PARENT_PATH)
    assert parent["sha256"] == (
        "a51f81a411e35e6514cbf2739a382b63b6c4db2e379e18004907a8e590a21c1d"
    )


def test_x1_compiler_scope_is_minimal_and_uses_existing_runtime() -> None:
    scope = _load(CONTRACT_PATH)["implementation_scope"]
    assert scope["compiler"] == (
        "research/external-transfer/global_v2_x1_compiler.py"
    )
    assert scope["synthetic_driver"] == (
        "research/external-transfer/run_global_v2_x1_synthetic.py"
    )
    assert set(scope["allowed_reuse"]) == {
        "src/cypshift/chemistry.py",
        "src/cypshift/openadmet_topology.py",
    }
    assert "Python 3.12.3/RDKit 2026.3.5" in scope["dependency_rule"]
    assert "no dependency" in _load(CONTRACT_PATH)["occam_boundary"]
    assert "model" in _load(CONTRACT_PATH)["occam_boundary"]


def test_x1_compiler_freezes_exact_tables_joins_and_read_only_sqlite() -> None:
    contract = _load(CONTRACT_PATH)
    schema = contract["future_source_schema"]
    sqlite = contract["sqlite_capability"]
    assert set(schema["required_tables"]) == {
        "activities",
        "assays",
        "target_dictionary",
        "molecule_dictionary",
        "compound_structures",
        "docs",
        "source",
    }
    assert {"standard_relation", "activity_comment", "potential_duplicate"} <= set(
        schema["required_tables"]["activities"]
    )
    assert "activities.assay_id = assays.assay_id" in schema["join_graph"]
    assert "docs.src_id = source.src_id" in schema["join_graph"]
    assert "explicit complete ORDER BY" in schema["query_policy"]
    assert "Never use SELECT *" in schema["query_policy"]
    assert "mode=ro and immutable=1" in sqlite["open_mode"]
    assert "PRAGMA query_only=ON" in sqlite["open_mode"]
    assert "exactly one terminal eligibility state" in sqlite["row_completeness"]
    assert "CREATE" in sqlite["no_mutation"]
    assert "ATTACH" in sqlite["no_mutation"]


def test_x1_filter_is_exact_ordered_and_nonaggregating() -> None:
    contract = _load(CONTRACT_PATH)
    filtering = contract["preservation_and_filtering"]
    reasons = filtering["one_primary_reason_order"]
    assert len(reasons) == 13
    assert reasons[0] == "TARGET_NOT_SELECTED"
    assert reasons[-1] == "STRUCTURE_MISSING_OR_QUARANTINED"
    assert len(set(reasons)) == len(reasons)
    eligibility = filtering["eligibility"]
    assert eligibility["standard_type"] == "IC50"
    assert eligibility["standard_relation"] == "="
    assert eligibility["standard_units"] == "nM"
    assert eligibility["standard_flag"] == 1
    assert eligibility["potential_duplicate"] == 0
    assert eligibility["data_validity_comment"] is None
    assert eligibility["minimum_confidence_score"] == 9
    assert "<= 0.011" in eligibility["recompute"]
    assert "not averaged" in filtering["replicates"]
    assert "format(value, '.17g')" in filtering["numeric_serialization"]


def test_x1_identity_recomputes_standardized_and_equivalence_keys() -> None:
    identity = _load(CONTRACT_PATH)["chemistry_identity"]
    standardization = identity["standardization"]
    equivalence = identity["equivalence"]
    assert standardization["policy_id"] == "rdkit-cleanup-fragment-parent-v1"
    assert standardization["implementation"] == (
        "cypshift.chemistry.standardize_molecule"
    )
    assert "never trusted identity" in standardization["rule"]
    assert equivalence["policy_id"] == (
        "rdkit-standard-inchi-connectivity-block-v1"
    )
    assert "first fourteen-character connectivity block" in equivalence["formula"]
    assert "conservative exclusion key only" in equivalence["interpretation"]
    assert "never fall back to the source-provided InChIKey" in equivalence["failure"]
    assert "unique recomputed standardized_structure_hash" in identity[
        "unique_external_molecule"
    ]


def test_x1_union_graph_preserves_forbidden_ghost_connectors() -> None:
    contract = _load(CONTRACT_PATH)
    graph = contract["union_family_graph"]
    exclusion = contract["exclusion_and_support"]
    assert "forbidden as exact/equivalent label-free connector nodes" in graph[
        "population"
    ]
    assert "no blinded-test structure" in graph["population"]
    assert len(graph["edges"]) == 2
    assert "connectivity-block" in graph["edges"][0]
    assert "inclusive RDKit Morgan/Tanimoto similarity >= 0.60" in graph["edges"][1]
    assert "compute every unordered pair exactly once" in graph["algorithm"]
    assert "Approximate neighbor search" in graph["algorithm"]
    assert "retain its node and edges as label-free topology" in exclusion[
        "global_exact_equivalent"
    ]
    assert "outer-validation challenge node" in exclusion["outer_cell"]
    assert "outer-validation or inner-validation" in exclusion["inner_cell"]
    assert "confirmatory challenge node" in exclusion["confirmatory"]
    assert "confirmatory truth remain absent" in exclusion["confirmatory"]


def test_x1_support_uses_unique_molecules_and_components() -> None:
    contract = _load(CONTRACT_PATH)
    support = contract["exclusion_and_support"]
    thresholds = support["official_thresholds"]
    parent_thresholds = _load(PARENT_PATH)["prospective_support_falsifier"]
    assert "unique safe external standardized hashes" in support["support_counts"]
    assert "distinct union component hashes" in support["support_counts"]
    assert thresholds[
        "minimum_novel_molecules_per_endpoint_after_global_exact_equivalent_removal"
    ] == 1000
    assert thresholds[
        "minimum_family_safe_external_components_per_endpoint_in_every_outer_cell"
    ] == 750
    assert thresholds["all_four_endpoints_required"]
    assert thresholds[
        "minimum_novel_molecules_per_endpoint_after_global_exact_equivalent_removal"
    ] == parent_thresholds[
        "minimum_novel_molecules_per_endpoint_after_global_exact_equivalent_removal"
    ]
    assert thresholds[
        "minimum_family_safe_external_components_per_endpoint_in_every_outer_cell"
    ] == parent_thresholds[
        "minimum_family_safe_external_components_per_endpoint_in_every_outer_cell"
    ]
    assert "Fail EXP-X1 without model fitting" in thresholds["decision"]


def test_x1_synthetic_fixture_falsifies_all_boundaries() -> None:
    fixture = _load(CONTRACT_PATH)["synthetic_fixture"]
    assert fixture["roots"] == 2
    assert fixture["sqlite_tables"] == 7
    assert fixture["external_compounds_total"] == 84
    assert fixture["eligible_external_compounds_before_overlap"] == 80
    assert fixture["activity_rows_total"] == 336
    assert fixture["eligible_activity_rows"] == 320
    assert fixture["ineligible_activity_rows"] == 16
    assert fixture["challenge_components"] == 20
    assert fixture["challenge_molecules"] == 40
    assert fixture["global_exact_forbidden_structures"] == 10
    assert fixture["global_equivalent_forbidden_structures"] == 10
    assert fixture["global_novel_structures_per_endpoint"] == 60
    assert fixture["union_unique_structure_nodes"] == 110
    assert fixture["union_components"] == 40
    assert fixture["expected_outer_safe_per_endpoint_cell"] == {
        "molecules": 52,
        "union_components": 36,
    }
    assert fixture["expected_inner_safe_per_endpoint_cell"] == {
        "molecules": 44,
        "union_components": 32,
    }
    assert "50 novel molecules and 35 outer-safe components" in fixture[
        "support_threshold_probe"
    ]
    assert "fails the immutable official 1000/750" in fixture[
        "support_threshold_probe"
    ]


def test_x1_stage_graph_separates_values_topology_and_decision() -> None:
    stages = _load(CONTRACT_PATH)["least_privilege_stage_graph"]
    assert "before an activity row is parsed" in stages["source_preflight"]
    assert "separate restricted raw/eligible capabilities" in stages["raw_compiler"]
    assert "eligible external identities without values" in stages[
        "topology_compiler"
    ]
    assert "without truth" in stages["topology_compiler"]
    assert "cannot open validation truth" in stages["capability_joiner"]
    assert "caller-bound thresholds" in stages["support_decider"]
    assert "no-resume" in stages["terminal_publisher"]


def test_x1_acceptance_is_exact_order_adversarial_and_non_scientific() -> None:
    contract = _load(CONTRACT_PATH)
    acceptance = contract["acceptance"]
    resources = contract["resource_ceiling"]
    assert acceptance["fresh_roots_required"] == 2
    assert acceptance["sqlite_file_hashes_must_differ"]
    assert acceptance["logical_source_hashes_must_match"]
    assert acceptance["relative_terminal_maps_byte_identical"]
    assert acceptance["outer_contexts"] == 15
    assert acceptance["outer_endpoint_cells"] == 60
    assert acceptance["inner_contexts"] == 60
    assert acceptance["inner_endpoint_cells"] == 240
    assert acceptance["miniature_support_pass"]
    assert not acceptance["official_support_pass"]
    assert "mechanics only" in acceptance["scientific_interpretation"]
    assert resources["synthetic_sqlite_activity_rows"] == 672
    assert resources["maximum_pairwise_union_comparisons"] == 11990
    assert resources["model_fits"] == 0
    assert resources["gpu_hours"] == 0


def test_x1_contract_opens_no_synthetic_external_or_official_capability() -> None:
    contract = _load(CONTRACT_PATH)
    accounting = contract["current_milestone_accounting"]
    assert accounting["inherited_prefreeze_external_preview_minimum_records"] == 45
    assert all(
        value == 0
        for name, value in accounting.items()
        if name != "inherited_prefreeze_external_preview_minimum_records"
    )
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"]
    assert not any(
        value for name, value in authority.items() if name != "contract_and_static_tests"
    )
    assert "implement only the two-root synthetic compiler" in contract["next_gate"]
    assert "single-use acquisition claim" in contract["next_gate"]
    assert "Do not download or open ChEMBL activity data" in contract["next_gate"]


def test_x1_synthetic_acceptance_binds_exact_code_and_zero_real_authority() -> None:
    acceptance = _load(ACCEPTANCE_PATH)
    bindings = acceptance["source_bindings"]
    assert _sha256(ACCEPTANCE_PATH) == ACCEPTANCE_SHA256
    assert acceptance["status"] == "G2_5B_EXP_X1_SYNTHETIC_COMPILER_ACCEPTED"
    assert acceptance["contract_sha256"] == CONTRACT_SHA256
    assert bindings["compiler_sha256"] == _sha256(
        ROOT / "research/external-transfer/global_v2_x1_compiler.py"
    )
    assert bindings["synthetic_driver_sha256"] == _sha256(
        ROOT / "research/external-transfer/run_global_v2_x1_synthetic.py"
    )
    assert bindings["focused_tests_sha256"] == _sha256(
        ROOT / "tests/test_openadmet_global_v2_x1_synthetic_compiler.py"
    )
    assert acceptance["roots"]["physical_sqlite_hashes_differ"]
    assert acceptance["roots"]["relative_terminal_maps_byte_identical"]
    assert acceptance["focused_tests_passed"] == 21
    assert acceptance["accounting"]["synthetic_activity_rows_opened"] == 672
    assert acceptance["accounting"]["synthetic_union_comparisons"] == 11990
    assert not acceptance["support_decisions"]["official_thresholds"]["pass"]
    assert not acceptance["authority"]["external_record_acquisition"]
    assert not acceptance["authority"]["model_fitting"]
    assert not acceptance["authority"]["submission"]
