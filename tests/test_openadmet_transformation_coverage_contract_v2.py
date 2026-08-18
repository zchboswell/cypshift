from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from rdkit import Chem

ROOT = Path(__file__).parents[1]
PATH = ROOT / "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v2.json"
PARENT_PATH = (
    ROOT / "benchmarks/openadmet_cyp_2026/transformation_coverage_contract.json"
)

STATUS = [
    "R4_TRANSFORMATION_COVERAGE_FAILED",
    "R4_TRANSFORMATION_COVERAGE_UNDERPOWERED",
    "R4_TRANSFORMATION_COVERAGE_SUPPORTED",
]
ROWS = [
    "VALID_STEREO",
    "VALID_SINGLE",
    "VALID_DOUBLE",
    "AMBIGUOUS",
    "UNSUPPORTED",
    "STANDARDIZATION_HAZARD",
]
VALID = ROWS[:3]


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise AssertionError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load(path: Path = PATH) -> dict[str, Any]:
    value = json.loads(path.read_bytes(), object_pairs_hook=_unique)
    assert isinstance(value, dict)
    return value


def test_v2_is_strict_additive_child_of_immutable_v1() -> None:
    contract = load()
    parent = load(PARENT_PATH)
    with pytest.raises(AssertionError, match="duplicate JSON key"):
        json.loads('{"duplicate": 1, "duplicate": 2}', object_pairs_hook=_unique)
    assert set(contract) == {
        "schema_version",
        "freeze_date",
        "gate",
        "status",
        "base_commit",
        "purpose",
        "parent",
        "inheritance",
        "inputs",
        "scope",
        "trusted_projections",
        "extraction",
        "populations",
        "outputs",
        "support",
        "accounting_zeros",
        "authority",
        "failure_policy",
        "required_outputs_after_implementation",
        "forbidden",
    }
    assert (
        contract["schema_version"]
        == "cypshift.openadmet_cyp_2026.transformation_coverage_contract.v2"
    )
    assert contract["freeze_date"] == "2026-08-18"
    assert (
        contract["gate"]
        == parent["gate"]
        == "R4_TRANSFORMATION_COVERAGE_CONTRACT_FROZEN"
    )
    assert contract["status"] == "contract_only_not_implemented"
    assert contract["parent"] == {
        "path": "benchmarks/openadmet_cyp_2026/transformation_coverage_contract.json",
        "schema_version": "cypshift.openadmet_cyp_2026.transformation_coverage_contract.v1",
        "sha256": "d4c999e66309d27caab558f69cdba3fe1762aa9804053b0f1b86a2401297aec5",
        "immutable": True,
    }
    assert (
        hashlib.sha256(PARENT_PATH.read_bytes()).hexdigest()
        == contract["parent"]["sha256"]
    )
    assert contract["inheritance"]["mode"] == "immutable_parent_plus_explicit_overrides"
    assert contract["inheritance"]["inherited_sections"] == [
        "inputs",
        "scope",
        "trusted_projections",
        "populations",
        "accounting_zeros",
        "authority",
        "required_outputs_after_implementation",
        "forbidden",
    ]
    assert contract["inheritance"]["override_sections"] == [
        "extraction",
        "outputs",
        "support",
        "failure_policy",
    ]
    assert (
        contract["inheritance"]["parent_values_remain_authoritative_unless_overridden"]
        is False
    )
    assert contract["inheritance"]["no_new_data_or_authority"] is True
    assert contract["inheritance"]["override_rule"].startswith(
        "Each v2 override section replaces the parent section wholesale"
    )
    resolution = contract["inheritance"]["override_resolution"]
    assert resolution == {
        "mode": "whole_section_replacement",
        "recursive_merge": False,
        "sections": {
            "extraction": "Use this complete self-contained v2 extraction section.",
            "outputs": "Use this complete self-contained v2 output and publication section.",
            "support": "Use this complete self-contained v2 support arithmetic section.",
            "failure_policy": "Use this complete self-contained v2 failure-code and terminal-policy section.",
        },
        "inherited_sections": "Use exact byte-decoded parent values for every section listed in inherited_sections.",
    }
    for section in contract["inheritance"]["inherited_sections"]:
        assert contract[section] == parent[section]


def test_v2_receipt_is_recomputed_and_binds_every_repair_subtree() -> None:
    extraction = load()["extraction"]
    receipt = extraction["extraction_spec_receipt"]
    material = {"extraction_spec_id": extraction["extraction_spec_id"]}
    material.update({name: extraction[name] for name in receipt["receipt_subtrees"]})
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert (
        receipt["sha256"]
        == "c7fb3a6a905d4265a174cdcde4e5f391c3d7f154a8cc2ed126a3830796c41e74"
    )
    assert receipt["sha256"] == hashlib.sha256(encoded).hexdigest()
    assert extraction["extraction_spec_id"] == "cypshift.trace.mmp.v2"
    assert "serialization" in receipt["receipt_subtrees"]
    assert "hazards" in receipt["receipt_subtrees"]
    assert "class_rules" in receipt["receipt_subtrees"]
    assert "execution_boundary" in receipt["receipt_subtrees"]


def test_joint_enumeration_and_reusable_exact_id_are_unambiguous() -> None:
    extraction = load()["extraction"]
    candidates = extraction["candidate_generation"]
    assert extraction["execution_boundary"] == {
        "device": "CPU",
        "gpu_access": False,
        "model_fit": False,
        "prediction": False,
        "numeric_target_access": False,
    }
    assert candidates["double_cut_reachable_when_single_valid"] is True
    assert "jointly" in candidates["enumeration"]
    assert "do not suppress double cuts" in candidates["enumeration"]
    assert candidates["ranking"] == [
        "maximum_conserved_heavy_atoms",
        "minimum_cut_count",
        "minimum_exact_changed_heavy_atom_fraction",
        "maximum_attachment_environment_agreement_radius_1",
        "maximum_attachment_environment_agreement_radius_2",
    ]
    assert (
        extraction["fragmentation"]["order"]
        == "Enumerate single and double cuts jointly, then deduplicate and rank the complete candidate set."
    )
    assert extraction["fragmentation"]["virtual_h_generation"]["eligible_predicate"]
    ids = extraction["ids"]
    assert ids["exact_transformation_id_material"] == [
        "v2_spec_hash",
        "removed_labeled_fragment",
        "added_labeled_fragment",
        "attachment_labels_array",
    ]
    assert ids["exact_transformation_id_excludes"] == [
        "transformation_pair_id",
        "direction_id",
        "molecule_id",
        "anchor_molecule_id",
        "analog_molecule_id",
        "rooted_environment",
        "stereo_element_values unless the stereo-specific material is used",
    ]
    assert ids["molecule_ids_in_exact_id_material"] is False
    assert ids["pair_or_direction_in_exact_id_material"] is False
    assert "reusable across pairs and directions" in ids["exact_transformation_id"]
    assert "pair/anchor/analog provenance only" in ids["direction_id"]
    assert "never part of exact-transformation ID" in ids["direction_id"]
    assert ids["environment_level_1_id_material"] == [
        "v2_spec_hash",
        "exact_transformation_id",
        "anchor_env_radius_1_array",
        "analog_env_radius_1_array",
    ]
    assert ids["environment_level_2_id_material"] == [
        "v2_spec_hash",
        "exact_transformation_id",
        "anchor_env_radius_2_array",
        "analog_env_radius_2_array",
    ]
    assert ids["pair_id_material"] == [
        "v2_spec_hash",
        "lower_standardized_structure_hash",
        "upper_standardized_structure_hash",
    ]
    assert (
        "SHA256" in ids["pair_id"]
        and "lower_standardized_structure_hash" in ids["pair_id"]
    )
    assert ids["direction_id_material"] == [
        "v2_spec_hash",
        "transformation_pair_id",
        "anchor_standardized_structure_hash",
        "analog_standardized_structure_hash",
    ]
    assert "transformation_pair_id" in ids["direction_id"]
    assert ids["undirected_exchange_id_material"] == [
        "v2_spec_hash",
        "sorted_fragment_pair",
        "attachment_arity",
    ]
    assert ids["transformation_class_id_material"] == ["v2_spec_hash", "class_token"]
    assert "pair_direction_class_id_rule" in ids
    assert (
        "direction_id separately carries pair/anchor/analog provenance"
        in ids["pair_direction_class_id_rule"]
    )
    assert ids["stereo_exact_transformation_id_material"] == [
        "v2_spec_hash",
        "canonical_nonstereo_full_graph",
        "directional_canonical_stereo_record",
    ]
    assert "canonical_nonstereo_full_graph" in ids["stereo_exact_transformation_id"]
    assert ids["reversal"]["class"].startswith("single_cut_growth reverses")
    assert ids["reversal"]["same"] == [
        "transformation_pair_id",
        "undirected_exchange_id",
    ]
    assert (
        "same if and only if"
        in ids["reversal"]["conditional_same"]["transformation_class_id"]
    )
    assert "single_cut_contraction" in ids["reversal"]["class"]


def test_exact_valid_row_serialization_is_frozen() -> None:
    extraction = load()["extraction"]
    serial = extraction["serialization"]
    assert (
        serial["similarity"]
        == "Finite RDKit Tanimoto serialized as a decimal string with format(value, '.17g'); threshold comparison is inclusive at 0.6."
    )
    assert (
        serial["booleans"]
        == "Lowercase JSON booleans true/false inside JSON fields; scalar CSV booleans are exactly true or false."
    )
    assert (
        serial["lists"]
        == "Compact JSON arrays; atom-index arrays are ascending integers; warning arrays are sorted unique strings."
    )
    assert (
        serial["rational"]
        == "Reduced non-negative integer numerator/denominator string num/den; zero is 0/1."
    )
    assert serial["field_rules"]["similarity"].endswith("format(value, '.17g')")
    assert serial["field_rules"]["changed_heavy_atom_fraction"] == (
        "reduced num/den rational string"
    )
    assert serial["field_rules"]["warnings"].startswith("compact JSON array")
    assert "candidate-material" in serial["invalid_transform_fields"]
    assert (
        "candidate_material"
        in load()["outputs"]["schemas"]["transformation_pairs.csv"][
            "invalid_transform_fields"
        ]
    )
    assert (
        "tie_material"
        in load()["outputs"]["schemas"]["transformation_pairs.csv"]["columns"]
    )
    assert extraction["canonicalization"]["tie_digest"].startswith("Lowercase SHA256")
    assert extraction["canonicalization"]["tie_material"].startswith(
        "Compact canonical JSON array"
    )
    assert extraction["canonicalization"]["tie_serialization"]["valid"] == {
        "tie_count": "1",
        "tie_material": "[candidate_material]",
        "candidate_material_only_valid": True,
    }
    no_candidates = extraction["canonicalization"]["tie_serialization"]["no_candidates"]
    assert no_candidates["tie_material"] == "[]"
    assert no_candidates["tie_digest"] == hashlib.sha256(b"[]").hexdigest()


def test_stereo_virtual_h_rooted_environment_and_candidate_material_are_executable() -> (
    None
):
    extraction = load()["extraction"]
    stereo = extraction["fragmentation"]["stereo_policy"]
    assert stereo["precedence"].startswith("For an identical non-stereo graph")
    stereo_row = stereo["valid_row"]
    assert stereo_row["status"] == "VALID_STEREO"
    assert stereo_row["cut_count"] == 0
    assert stereo_row["removed_labeled_fragment"] == ""
    assert stereo_row["added_labeled_fragment"] == ""
    assert stereo_row["attachment_labels_array"] == []
    assert stereo_row["left_attachment_environment_radius_1"] == []
    assert stereo_row["right_attachment_environment_radius_1"] == []
    assert stereo_row["left_attachment_environment_radius_2"] == []
    assert stereo_row["right_attachment_environment_radius_2"] == []
    assert stereo_row["changed_heavy_atom_fraction"] == (
        "0/1 because no heavy atom is added or removed"
    )
    assert stereo_row["class"] == "stereochemical_change"
    assert "stereo_exact_transformation_id_material" in stereo_row["exact_id"]
    assert stereo_row["class_id"].startswith("Use transformation_class_id_material")
    assert (
        stereo_row["environment_ids"]
        == "empty because a cut=0 stereo row has no attachment roots"
    )
    virtual_h = extraction["fragmentation"]["virtual_h_generation"]
    fragmentation = extraction["fragmentation"]
    assert fragmentation["human_input_hydrogen_side_notation"] == "[*:1][H]"
    assert fragmentation["hydrogen_side_token"] == "[H][*:1]"
    for notation in ("[*:1][H]", "[H][*:1]"):
        molecule = Chem.MolFromSmiles(notation)
        assert molecule is not None
        assert (
            Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
            == "[H][*:1]"
        )

    def virtual_h_id(notation: str) -> str:
        molecule = Chem.MolFromSmiles(notation)
        assert molecule is not None
        canonical = Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
        material = ["test-v2-spec", canonical, "C[*:1]", [1]]
        return hashlib.sha256(
            json.dumps(material, separators=(",", ":")).encode()
        ).hexdigest()

    assert virtual_h_id("[*:1][H]") == virtual_h_id("[H][*:1]")
    assert (
        "fragment equality" in fragmentation["virtual_h_generation"]["representation"]
    )
    assert (
        "exact RDKit-canonical [H][*:1]"
        in fragmentation["virtual_h_generation"]["eligible_predicate"]
    )
    assert virtual_h["minimum_implicit_hydrogens"] == 1
    assert (
        virtual_h["atom_order"] == "canonical standardized RDKit atom index ascending"
    )
    assert len(virtual_h["per_atom_procedure"]) == 5
    assert "GetNumImplicitHs()" in virtual_h["eligible_predicate"]
    assert "at least 1" in virtual_h["eligible_predicate"]
    env = extraction["canonicalization"]["attachment_environment_rule"]
    assert env["radii"] == [1, 2]
    assert env["rdkit_options"] == {
        "canonical": True,
        "isomericSmiles": True,
        "kekuleSmiles": False,
        "allBondsExplicit": False,
        "allHsExplicit": False,
        "rootedAtAtom": "atom_idx",
    }
    assert "FindAtomEnvironmentOfRadiusN" in env["construction"]
    assert "useHs=False" in env["construction"]
    assert "enforceSize=False" in env["construction"]
    assert "sorted_atom_ids" in env["construction"]
    assert "sorted_bond_ids" in env["construction"]
    assert "MolFragmentToSmiles" in env["construction"]
    material = extraction["canonicalization"]["candidate_material_schema"]
    assert material["encoding"].startswith("UTF-8 JSON object")
    assert set(material["keys_and_types"]) == {
        "cut_count",
        "conserved_core_smiles",
        "removed_labeled_fragment",
        "added_labeled_fragment",
        "attachment_labels_array",
        "left_attachment_environment_radius_1",
        "right_attachment_environment_radius_1",
        "left_attachment_environment_radius_2",
        "right_attachment_environment_radius_2",
        "left_virtual_h_eligible",
        "right_virtual_h_eligible",
        "changed_left_atom_indices",
        "changed_right_atom_indices",
        "changed_heavy_atom_fraction",
        "stereo",
        "class",
    }
    assert material["stereo_keys_and_types"] == {
        "changed": "boolean",
        "elements": "array of objects with kind string, atom_indices array of integers, bond_indices array of integers, left_value string, right_value string",
    }
    assert extraction["canonicalization"]["dummy_permutation"][
        "allowed_attachment_labels"
    ] == {
        "single": [1],
        "double": [1, 2],
    }
    assert extraction["class_rules"]["single_cut_growth"]["reversal"] == (
        "single_cut_contraction"
    )
    assert extraction["class_rules"]["single_cut_contraction"]["reversal"] == (
        "single_cut_growth"
    )
    assert extraction["class_rules"]["double_cut_exchange"]["cut_count"] == 2
    assert "H->heavy" in extraction["class_rules"]["single_cut_growth"]["assignment"]
    assert (
        "heavy->H" in extraction["class_rules"]["single_cut_contraction"]["assignment"]
    )
    assert (
        "non-H single exchange"
        in extraction["class_rules"]["single_cut_exchange"]["assignment"]
    )
    assert (
        "double exchange"
        in extraction["class_rules"]["double_cut_exchange"]["assignment"]
    )
    assert extraction["class_rules"]["reusable_class_id_scope"] == (
        "The reusable transformation_class_id is exactly [v2_spec_hash, class_token]."
    )


def test_outputs_are_complete_and_firewalled() -> None:
    contract = load()
    outputs = contract["outputs"]
    assert outputs["success_files_exact"] == [
        "transformation_pairs.csv",
        "episode_transformations.csv",
        "transformation_coverage.json",
        "manifest.json",
    ]
    assert outputs["failure_files_exact"] == ["failure_receipt.json"]
    assert outputs["publication"] == {
        "success_files_exact": outputs["success_files_exact"],
        "failure_files_exact": outputs["failure_files_exact"],
        "atomic": True,
        "read_only": True,
        "no_overwrite": True,
        "private_artifacts_removed_before_publish": True,
    }
    assert "renameat2(RENAME_NOREPLACE)" in outputs["serialization"]["publication"]
    assert "failure_receipt.json" in outputs["serialization"]["failure_publication"]
    pair = outputs["schemas"]["transformation_pairs.csv"]
    episode = outputs["schemas"]["episode_transformations.csv"]
    coverage = outputs["schemas"]["transformation_coverage.json"]
    assert pair["schema_version"].endswith(".transformation_pairs.v2")
    assert episode["schema_version"].endswith(".episode_transformations.v2")
    assert pair["status_values"] == episode["status_values"] == ROWS
    assert pair["valid_statuses"] == episode["valid_statuses"] == VALID
    assert pair["invalid_statuses"] == episode["invalid_statuses"] == ROWS[3:]
    assert pair["invalid_status_transform_fields_empty"] is True
    assert set(pair["invalid_transform_fields"]).issubset(pair["columns"])
    assert set(pair["column_types"]) == set(pair["columns"])
    assert set(pair["invalid_field_sentinels"]) == set(
        pair["invalid_transform_fields"]
    ) | {
        "a_to_b_direction_id",
        "b_to_a_direction_id",
        "tie_count",
        "tie_material",
        "tie_digest",
    }
    assert "a_to_b_transformation_class_id" in pair["columns"]
    assert "b_to_a_transformation_class_id" in pair["columns"]
    assert pair["column_types"]["a_to_b_transformation_class_id"] == (
        "lowercase_sha256_or_empty"
    )
    assert "a_to_b_direction_id" not in pair["invalid_transform_fields"]
    assert "b_to_a_direction_id" not in pair["invalid_transform_fields"]
    assert "tie_count" not in pair["invalid_transform_fields"]
    assert pair["invalid_field_sentinels"]["a_to_b_direction_id"].startswith(
        "retain non-empty"
    )
    assert pair["invalid_field_sentinels"]["tie_digest"] == (
        "status-specific; see tie_field_policy"
    )
    assert pair["tie_field_policy"]["VALID_STEREO/VALID_SINGLE/VALID_DOUBLE"] == (
        "tie_count=1, tie_material=[candidate_material], tie_digest=SHA256(tie_material)"
    )
    assert "tie_count>=2" in pair["tie_field_policy"]["AMBIGUOUS with S2"]
    assert (
        "candidate_material is empty" in pair["tie_field_policy"]["AMBIGUOUS with S2"]
    )
    assert pair["tie_field_policy"][
        "AMBIGUOUS without S2/UNSUPPORTED/STANDARDIZATION_HAZARD"
    ].startswith("tie_count=0, tie_material=[]")
    assert {
        "selector",
        "selector_cyp_truth",
        "query_complete",
        "anchor_complete",
        "oracle_scorable",
        "target",
        "prediction",
    }.isdisjoint(episode["columns"])
    assert episode["selector_column_present"] is False
    assert "directional_transformation_class_id" not in episode["columns"]
    assert episode["endpoint_availability_columns"] == []
    assert episode["oracle_scorability_columns"] == []
    assert set(episode["column_types"]) == set(episode["columns"])
    assert set(episode["invalid_sentinels"]) == {
        "direction_id",
        "cyp3a4_training_family_exact_support_count",
        "cyp3a4_training_family_class_support_count",
        "tie_count",
        "tie_material",
        "tie_digest",
        "ambiguous",
        "warnings",
    }
    assert "direction_id" not in episode["invalid_transform_fields_empty"]
    assert (
        "cyp3a4_training_family_exact_support_count"
        not in episode["invalid_transform_fields_empty"]
    )
    assert episode["invalid_sentinels"]["tie_material"] == (
        "status-specific; see tie_field_policy"
    )
    assert episode["invalid_sentinels"]["tie_count"] == (
        "status-specific; see tie_field_policy"
    )
    assert episode["invalid_sentinels"]["tie_digest"] == (
        "status-specific; see tie_field_policy"
    )
    assert "tie_count=1" in episode["tie_field_policy"]
    assert "tie_count>=2" in episode["tie_field_policy"]
    assert "tie_count=0" in episode["tie_field_policy"]
    assert coverage["required_sections"] == list(
        dict.fromkeys(coverage["required_sections"])
    )
    assert coverage["row_level_endpoint_availability"] is False
    assert coverage["row_level_oracle_scorability"] is False
    assert coverage["selector_facts"] is False
    assert coverage["scorable_facts"] is False
    assert coverage["local_cyp3a4_state_only"] is True
    assert coverage["valid_statuses_for_gates_frequencies_support"] == VALID
    assert set(coverage["section_schemas"]) >= {
        "counts",
        "status_partition",
        "fractions",
        "exact_transformation_frequency",
        "transformation_class_frequency",
        "independent_group_support",
        "valid_changed_heavy_atom_fraction_distribution",
        "cross_cyp_valid_transformation_sharing",
        "test_query_coverage",
        "selected_anchor_structural_coverage",
        "local_cyp3a4_state",
        "accounting",
        "authority",
    }
    assert coverage["section_schemas"]["counts"]["status_counts_absent"] is True
    assert "status_counts" not in coverage["section_schemas"]["counts"]
    assert "sum exactly" in coverage["section_schemas"]["status_partition"]["sum_rule"]
    assert coverage["section_schemas"]["test_query_coverage"]["values"] is None
    assert (
        coverage["section_schemas"]["selected_anchor_structural_coverage"]["fields"][
            "cell_support"
        ]
        == "exactly 15 support records in [repeat, outer_fold] order"
    )
    assert coverage["frequency_units"]["scope"] == "union of directional valid views"
    assert (
        "2 * valid structural pair rows"
        in coverage["frequency_units"]["two_direction_denominator"]
    )
    assert coverage["section_schemas"]["fractions"]["representation"].startswith(
        "one exact reduced rational"
    )
    support_schema = coverage["section_schemas"]["independent_group_support"]
    assert support_schema["keys"] == ["exact", "class"]
    assert support_schema["record_fields"] == ["families_overall"]
    assert "repeat_cell_records" not in support_schema
    assert coverage["frequency_units"]["independent_group_support"].startswith(
        "exact and class maps"
    )
    assert (
        coverage["cross_cyp_valid_transformation_sharing"]["id_unit"]
        == "exact_transformation_id"
    )


def test_support_arithmetic_thresholds_and_selected_gate_are_frozen() -> None:
    contract = load()
    support = contract["support"]
    fold_columns = contract["trusted_projections"]["fold_projection"]["columns"]
    assert {
        "repeat",
        "outer_fold",
        "outer_validation_fold",
        "similarity_component_hash",
    } <= set(fold_columns)
    fold = support["local_validation_fold_arithmetic"]
    assert fold["cell_key"] == ["endpoint", "repeat", "outer_validation_fold"]
    assert (
        fold["validation_molecule_predicate"]
        == "molecule belongs to the same repeat's held-out side, outer_fold == outer_validation_fold, and has complete direct availability for the endpoint"
    )
    assert (
        fold["validation_pair_predicate"]
        == "both molecules satisfy validation_molecule_predicate, share one component, have inclusive Tanimoto >=0.60, and the union row has a valid status"
    )
    assert (
        fold["pair_unit"]
        == "distinct canonical unordered standardized-structure-hash pair per cell"
    )
    assert (
        fold["family_unit"]
        == "distinct similarity_component_hash among those pairs per cell"
    )
    assert (
        "count each valid canonical unordered pair exactly once"
        in fold["overall_arithmetic"]
    )
    assert "held-out-side pairs/families" in fold["fold_arithmetic"]
    assert (
        "directions never increase pair or family counts"
        in fold["directional_contribution"]
    )
    assert "exactly 15 cells" in fold["cell_counts"]
    assert (
        "outer_fold equals the cell's outer_validation_fold"
        in fold["held_out_inclusion"]
    )
    assert (
        "outer_fold == outer_validation_fold" in fold["validation_molecule_predicate"]
    )
    assert "outer_validation_fold" in fold["cell_key"]
    local = support["local_cyp3a4"]
    assert local["minimum_proxy_families_overall"] == 50
    assert local["minimum_pairs_overall"] == 200
    assert local["minimum_proxy_families_each_fold_cell"] == 5
    assert local["minimum_pairs_each_fold_cell"] == 20
    assert local["overall_units"] == {
        "families": "distinct component hashes over all valid complete CYP3A4 local pairs",
        "pairs": "distinct unordered standardized-structure-hash pairs over all valid complete CYP3A4 local pairs",
    }
    assert (
        local["fold_units"]["families"]
        == "distinct component hashes per repeat/outer_validation_fold held-out cell"
    )
    assert (
        local["fold_units"]["pairs"]
        == "distinct unordered standardized-structure-hash pairs per repeat/outer_validation_fold held-out cell"
    )
    episode = support["episode_training_support_arithmetic"]
    assert episode["cell_key"] == [
        "episode_id",
        "repeat",
        "outer_fold",
        "outer_group_id",
    ]
    assert "distinct training component hashes" in episode["exact_support"]
    assert "distinct training component hashes" in episode["class_support"]
    assert "candidate TRAINING local pairs" in episode["training_pair_predicate"]
    assert (
        "both molecules must be CYP3A4 complete" in episode["training_pair_predicate"]
    )
    assert (
        "component outer_fold != episode.outer_fold"
        in episode["training_pair_predicate"]
    )
    assert "component != episode.outer_group_id" in episode["training_pair_predicate"]
    assert "exact_transformation_id" in episode["episode_direction_match"]
    assert "transformation_class_id" in episode["episode_direction_match"]
    assert "distinct component" in episode["distinct_component_rule"]
    assert episode["valid_statuses_only"] is True
    assert episode["selected_family_policy"]["valid_statuses"] == VALID
    assert episode["selected_family_policy"]["cell_key"] == ["repeat", "outer_fold"]
    assert (
        episode["selected_family_policy"]["cell_unit"]
        == "distinct component hashes per repeat/outer_fold selected cell"
    )
    assert "outer_group_id" in episode["selected_family_policy"]["deduplication"]
    assert episode["selected_family_policy"]["outer_group_unit"] == (
        "distinct outer_group_id values per repeat/outer_fold selected cell for the endpoint record"
    )
    assert "no selector or scorable fact" in episode["selected_gate"]
    assert support["status_precedence"] == STATUS
    assert support["test_query_coverage"] == "NOT_COMPUTED_TEST_ACCESS_FORBIDDEN"


def test_failure_codes_and_authority_do_not_expand_scope() -> None:
    contract = load()
    failure = contract["failure_policy"]
    mapping = failure["code_mapping"]
    assert failure["integrity_failure"].startswith("Receipt, schema, firewall")
    assert failure["clean_underpowered"].startswith("Emit the four success artifacts")
    assert failure["supported"].startswith("Emit the four success artifacts")
    assert set(failure["terminal_integrity_failure_codes"]) == {
        "C1",
        "C5",
        "V1",
        "V2",
        "V4",
        "P1",
        "P2",
        "P5",
        "P6",
    }
    assert set(failure["terminal_integrity_failure_codes"]) <= set(mapping)
    assert failure["terminal_integrity_failure_codes"] == sorted(
        set(failure["terminal_integrity_failure_codes"])
    )
    assert mapping["C5"] == {
        "terminal": True,
        "status": "R4_TRANSFORMATION_COVERAGE_FAILED",
        "meaning": "distinct molecule identities share one standardized_structure_hash; molecule ID cannot rescue the collision",
    }
    assert mapping["C1"]["meaning"] == "invalid or unparsable structure"
    assert mapping["S3"]["status"] == "AMBIGUOUS"
    assert mapping["S6"]["status"] == "UNSUPPORTED"
    terminal_map = failure["terminal_condition_code_map"]
    row_map = failure["row_condition_code_map"]
    assert failure["terminal_condition_code_one_to_one"] is True
    assert len({item["code"] for item in terminal_map}) == len(terminal_map)
    assert len({item["condition"] for item in terminal_map}) == len(terminal_map)
    assert len({item["code"] for item in row_map}) == len(row_map)
    assert len({item["condition"] for item in row_map}) == len(row_map)
    assert {item["code"] for item in terminal_map} == set(
        failure["terminal_integrity_failure_codes"]
    )
    assert {item["code"] for item in row_map} == set(failure["row_exclusion_codes"])
    assert set(failure["terminal_condition_aliases"]) == set(
        failure["terminal_integrity_conditions"]
    )
    assert all(
        failure["terminal_condition_aliases"][condition]
        in failure["terminal_integrity_failure_codes"]
        for condition in failure["terminal_integrity_conditions"]
    )
    assert (
        "distinct_identity_same_standardized_hash"
        not in contract["extraction"]["hazards"]
    )
    assert "C5" in failure["terminal_integrity_failure_codes"]
    assert "C5" not in failure["row_exclusion_codes"]
    assert set(failure["row_exclusion_codes"]) == {"C2", "C3", "C6", "S2", "S3", "S6"}
    assert "one code and status" in failure["row_code_mapping"]
    assert failure["row_code_precedence"] == ["C2", "C6", "C3", "S3", "S2", "S6"]
    assert "emit the first code" in failure["row_code_precedence_rule"]
    assert set(failure["row_code_precedence"]) == set(failure["row_exclusion_codes"])
    assert failure["row_status_values"] == ROWS
    assert failure["valid_statuses_for_gates_frequencies_support"] == VALID
    authority = contract["authority"]
    for key in (
        "model_fits",
        "predictions",
        "metrics",
        "official_st_rae",
        "test_access",
        "tdi",
        "submissions",
        "transduction",
        "label_derivation",
    ):
        assert authority[key] is False
    assert (
        "exact_field_order"
        not in contract["outputs"]["schemas"]["transformation_coverage.json"][
            "section_schemas"
        ]["authority"]
    )
    for state in authority["conditional_authority"].values():
        assert state["coverage_artifacts"] in {False, True}
        assert state["geometry_coverage"] in {False, True}
        assert all(
            state[key] is False
            for key in (
                "model_fits",
                "predictions",
                "metrics",
                "official_st_rae",
                "test_access",
                "tdi",
                "submissions",
                "transduction",
            )
        )
    assert contract["accounting_zeros"]["numeric_target_magnitudes_parsed"] == 0
    assert contract["accounting_zeros"]["model_fits"] == 0
    forbidden = contract["forbidden"]
    assert "predictive MCS fallback" in forbidden
    assert "delta-model fitting" in forbidden
    assert "test access" in forbidden
    manifest = contract["outputs"]["schemas"]["manifest.json"]
    receipt = contract["outputs"]["schemas"]["failure_receipt.json"]
    assert manifest["required_fields"][-3:] == ["runtime", "accounting", "authority"]
    assert manifest["runtime"]["no_target_or_prediction_fields"] is True
    assert receipt["required_fields"][-3:] == ["accounting", "runtime", "authority"]
    assert "terminal_condition_code" not in receipt["required_fields"]
    assert "primary code" in receipt["field_types"]["terminal_integrity_failure_codes"]
    assert receipt["accounting"]["all_zero"] is True


def test_cross_field_bindings_are_mechanical_not_prose_only() -> None:
    contract = load()
    extraction = contract["extraction"]
    receipt = extraction["extraction_spec_receipt"]
    ids = extraction["ids"]
    assert ids["spec_hash_source"] == "extraction.extraction_spec_receipt.sha256"
    assert ids["exact_transformation_id_material"][0] == "v2_spec_hash"
    assert ids["pair_id_material"][0] == "v2_spec_hash"
    assert ids["direction_id_material"][0] == "v2_spec_hash"
    assert ids["transformation_class_id_material"][0] == "v2_spec_hash"
    assert ids["stereo_exact_transformation_id_material"][0] == "v2_spec_hash"
    assert "class_rules" in receipt["receipt_subtrees"]
    assert "execution_boundary" in receipt["receipt_subtrees"]
    pair = contract["outputs"]["schemas"]["transformation_pairs.csv"]
    episode = contract["outputs"]["schemas"]["episode_transformations.csv"]
    assert set(pair["invalid_transform_fields"]) | {
        "a_to_b_direction_id",
        "b_to_a_direction_id",
        "tie_count",
        "tie_material",
        "tie_digest",
    } == set(pair["invalid_field_sentinels"])
    assert set(pair["column_types"]) == set(pair["columns"])
    assert set(episode["column_types"]) == set(episode["columns"])
    coverage = contract["outputs"]["schemas"]["transformation_coverage.json"]
    required = set(coverage["required_sections"])
    assert required - {"contract_sha256", "status"} <= set(
        coverage["section_schemas"]
    ) | {"frequency_units"}
    assert (
        coverage["valid_statuses_for_gates_frequencies_support"]
        == extraction["valid_statuses"]
    )
    assert contract["support"]["valid_statuses"] == extraction["valid_statuses"]
    endpoint_schema = coverage["section_schemas"]["local_by_endpoint"]
    assert endpoint_schema["endpoint_map_exact"] is True
    assert endpoint_schema["keys"] == ["CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4"]
    assert endpoint_schema["count_record_fields"] == [
        "denominator_rows",
        "valid_rows",
        "single_cut_rows",
        "double_cut_rows",
    ]
    assert endpoint_schema["status_record_fields"] == ROWS
    assert endpoint_schema["fraction_record_fields"] == [
        "valid_stereo_fraction",
        "single_cut_fraction",
        "double_cut_fraction",
        "ambiguous_fraction",
        "unsupported_fraction",
        "standardization_hazard_fraction",
    ]
    for section in ("counts", "status_partition", "fractions"):
        schema = coverage["section_schemas"][section]
        assert schema["record_applies_to"] == [
            "union",
            "selected_primary",
            "stress",
        ]
        assert schema["local_by_endpoint_value"].startswith("Exact four-endpoint map")
    assert (
        "status_partition.local_by_endpoint[e]"
        in coverage["section_schemas"]["status_partition"]["sum_rule"]
    )
    assert (
        "counts.local_by_endpoint[e].denominator_rows"
        in coverage["section_schemas"]["fractions"]["denominator"]
    )
    support_schema = coverage["section_schemas"]["independent_group_support"]
    assert "no held-out exclusion" in support_schema["population"]
    assert support_schema["unit"] == "distinct full-population component hashes"
    selected_schema = coverage["section_schemas"]["selected_anchor_structural_coverage"]
    assert selected_schema["record_fields"] == [
        "repeat",
        "outer_fold",
        "rows",
        "valid_rows",
        "distinct_families",
        "meets_gate",
    ]
    assert selected_schema["overall_deduplication"].startswith(
        "deduplicate distinct component hashes"
    )
    assert (
        coverage["section_schemas"]["local_cyp3a4_state"]["overall_not_sum_of_cells"]
        is True
    )
    assert coverage["section_schemas"]["fractions"]["zero"] == "0/1"
    selected_policy = contract["support"]["episode_training_support_arithmetic"][
        "selected_family_policy"
    ]
    assert selected_policy["cell_key"] == ["repeat", "outer_fold"]
    assert "across selected rows and repeats" in selected_policy["overall_unit"]
    assert "distinct outer_group_id" in selected_policy["outer_group_unit"]
    failure = contract["failure_policy"]
    assert set(failure["row_condition_code_map"][i]["code"] for i in range(6)) == set(
        failure["row_exclusion_codes"]
    )
    assert set(
        failure["terminal_condition_code_map"][i]["code"] for i in range(9)
    ) == set(failure["terminal_integrity_failure_codes"])
    assert "distinct_identity_same_standardized_hash" not in extraction["hazards"]
    assert "C5" not in failure["row_exclusion_codes"]
